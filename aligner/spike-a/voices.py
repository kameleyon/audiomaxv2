#!/usr/bin/env python3
"""
SPIKE A, voice arm — does the CHOICE OF VOICE move word-sync quality, and by how
much, with what uncertainty.

WHAT THIS FILE EXISTS TO SETTLE
-------------------------------
`fixtures.json:19` locks `fr` to one voice on this sentence:

    "Miriam 88.2%, Mario 94.4%, Robert 100% agreement within 250 ms.
     VOICE CHOICE IS A WORD-SYNC VARIABLE -- a 12-point swing."

Three separate reviewers have since found that sentence inadmissible, for three
INDEPENDENT reasons, and all three are correct:

  1. WRONG INSTRUMENT (Forge, Jury). The figures came from `hypereal.py` while it
     still degraded to SEGMENT timings and reported them as words. They are
     word-vs-segment comparisons. `out/spike-a-crossengine.json:54` says so in
     the artifact itself.
  2. WRONG METRIC (Atlas). `agree_within_250ms_pct` is CROSS-ENGINE AGREEMENT.
     The bar is `matched_within_drift_pct` at 250 ms (roadmap:295-305). They are
     different quantities; `voice_langs.sync_metric` is an enum with both members
     precisely so a substitution has to be defended.
  3. NO POWER (Halo). n was ~17 display tokens on ONE 8-second clip, no
     repetition. 15/17 vs 17/18 vs 18/18 is a two-token difference. Halo:
     "it is still an argument, now with two tokens attached."

This file answers the question on the bar's own metric, at a sample size where a
12-point difference is resolvable, and WITH A NOISE FLOOR — because the decisive
control was never run: Fish `s2-pro` is sampled at temperature 0.8, so the SAME
voice does not produce the same audio twice. Until you know how much the metric
moves when NOTHING changes but the random seed, you cannot say what it means
when the voice changes. Every clip below is therefore synthesized TWICE.

WHAT IS MEASURED
----------------
`matched_within_drift_pct` at `drift_bound_ms = 250`, computed by the SHIPPED
code path — `worker/src/match/matchTokens` for placement and the identical local
three-point neighbour interpolation for drift. Not a reimplementation with the
same name: `--self-test` asserts this file reproduces the committed
62.5 / 68.2 / 75.0 for `en` / `es` / `fr` EXACTLY, off the committed audio, and
fails if it does not.

THE MATCHER MOVED INTO THE PRODUCT IN THIS ROUND, and the reason is the previous
round's finding. `measure.match` was a monotonic greedy loop with a six-token
lookahead and NO RE-SYNC PATH; three of six long clips desynced mid-clip and
never recovered, against full transcripts. That could be diagnosed here and not
fixed here, because "here" is a measurement script. It is
`worker/src/match/match.ts` now, with the re-sync path and its own tests, and
this file calls it — so the number below and the behaviour a reader gets are one
code path. See ADR-0006.

WHAT IS ALSO MEASURED, AND WHY
------------------------------
`agree_within_250ms_pct` — the substituted metric — computed HONESTLY this time
(word-level both sides: faster-whisper `base` against `small`, paired by DISPLAY
INDEX, never by surface-form uniqueness, H26-M8). Not because it is the bar, but
because the claim under review is stated in it. If the two metrics rank the
voices differently on the same audio, then no amount of care about the first
number rescues a decision made on the second.

THE TRAP THIS SPIKE HAS FALLEN INTO FIVE TIMES
----------------------------------------------
Five instruments here produced failing numbers that were the instrument's fault.
So `--self-test` does not check that this file agrees with itself. It MUTATES the
measurement and asserts each control FAILS:

  CTL-EQUIV     reproduces the committed figures  · mutated: drift bound moved
  CTL-NULL      same audio scored twice -> zero   · mutated: one token displaced
  CTL-POWER     1 displaced token is NOT called significant at this n
  CTL-SHIFT     many displaced tokens ARE         · both directions asserted
  CTL-TAIL      a tail-only defect leaves the median alone and moves p95
                — the tell this spike has shown every single time
  CTL-STATS     Wilson / McNemar / bootstrap against hand-computable values
  CTL-BOOT      the sentence-block bootstrap widens when blocks are correlated
  CTL-DESYNC    the admissibility gate fires on a matcher that stops tracking
  CTL-RESYNC    and does NOT fire when the matcher re-acquires the page after a
                mid-stream gap wider than its lookahead — with the display
                tokens it jumped over left unmatched, because a recovery that
                credited them would be a recovery that invented coverage

Every control is asserted in BOTH directions: it holds on clean input and it
breaks on mutated input. A control that only ever passes is not a control.

COST DISCIPLINE (owner's standing rule)
---------------------------------------
`--probe` makes ONE TTS call and stops. `--synth` refuses to run until the probe
artifact exists, prints the exact call count and byte count it is about to spend,
and requires `--yes`. No key is ever printed.

USAGE
    python voices.py --self-test          # no network, no cost
    python voices.py --probe              # 1 TTS call, then STOP
    python voices.py --synth --yes        # the remaining calls
    python voices.py --measure            # ASR + statistics -> out/spike-a-voices.json
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import random
import statistics
import sys
import time

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "out"
sys.path.insert(0, str(ROOT))

import measure as M          # noqa: E402  bridge to the shipped matcher + the drift bound
import harness as H          # noqa: E402  wav_info, SENT_END, LF-safe write_json

ARTIFACT = OUT / "spike-a-voices.json"
PROBE_ARTIFACT = OUT / "spike-a-voices-probe.json"
DRIFT_MS = M.DRIFT_MS        # 250, fixed before the run. Imported, never restated.
BAR_MATCHED_PCT = M.BAR_MATCHED_PCT

# ── The voices ───────────────────────────────────────────────────────────────
#
# THE COMPARISON ARM OF THE ORIGINAL CLAIM IS NOT IDENTIFIABLE FROM THIS
# REPOSITORY. `fixtures.json:18` records Mario as `d12dae2d...` — truncated —
# and Miriam's reference_id appears nowhere at all. `grep -rn` over the whole
# repository returns three prose mentions and no ID, and neither prefix is in
# Fish's French catalogue by score rank. So the run that locked `fr` cannot be
# re-executed by anyone, including its author. That is a reproducibility defect
# in its own right and it is reported as one; it is ALSO the reason the two
# comparison voices below are named with their FULL reference_id and their
# catalogue title as the provider returns it, so that this run can be.
#
# `locked` is the voice `fixtures.json` actually ships (`a5d7dcbb...`). Note that
# Fish's catalogue titles it "Voix Curieuse et Claire", not "Robert" — the name
# in `fixtures.json` is a local alias with no recorded mapping, which is the same
# defect one degree smaller.
VOICES = {
    "locked": {
        "reference_id": "a5d7dcbb81b4472ea0e240af3edaae7d",
        "fixtures_alias": "Robert",
        "provider_title": "Voix Curieuse et Claire",
        "languages": ["fr"],
    },
    "narrateur": {
        "reference_id": "4f2a0684dd0247dda68f339738c780e6",
        "fixtures_alias": None,
        "provider_title": "Le narrateur",
        "languages": ["fr"],
    },
    "feminine": {
        "reference_id": "5567200c7d8341738f0892bbacd3be3c",
        "fixtures_alias": None,
        "provider_title": "Feminine",
        "languages": ["fr"],
    },
}
REPLICATES = 2               # the noise floor. Fish s2-pro samples at temperature 0.8.

# ── The long fixture ─────────────────────────────────────────────────────────
#
# The evidence floor (roadmap:332-347, enforced in `voice_langs`) requires
# `sync_matched_words >= 200` and `sync_longest_clip_ms >= 300000`. The whole
# committed corpus is 63 seconds and 14-24 display tokens per clip, where ONE
# token is 4-6 percentage points and a bar of 95 cannot be resolved at all. This
# text is written to clear the floor in a single call: ~900 display tokens, ~5
# minutes spoken, with the same hard-token classes `fixtures.json` selects for
# (numerals, grouped thousands with a SPACE separator, years, abbreviations,
# percentages) distributed across the whole clip rather than packed into one
# sentence.
#
# It is NOT added to `fixtures.json` — that file belongs to Probe. It lives here,
# beside the run that uses it, and its SHA-256 is recorded in the artifact.
FR_LONG = (
    "Le rapport annuel de la bibliotheque municipale decrit un programme de numerisation "
    "commence en 1984 et poursuivi sans interruption depuis. Le service compte aujourd'hui "
    "47 postes de travail repartis sur 3 etages, et il traite en moyenne 1 250 documents par "
    "semaine. Le Dr Chen, qui dirige l'equipe technique, rappelle que la premiere campagne ne "
    "concernait que les registres paroissiaux et les plans cadastraux.\n\n"

    "Les collections anciennes posent des difficultes particulieres. Le papier se fragilise, "
    "l'encre palit, et certaines reliures ne supportent plus d'etre ouvertes a plat. Pour ces "
    "pieces, l'atelier utilise un berceau reglable qui limite l'angle d'ouverture a 52 degres. "
    "Chaque volume est photographie page par page, puis controle par un operateur qui verifie "
    "la nettete, le cadrage et la fidelite des couleurs.\n\n"

    "La chaine de traitement comprend quatre etapes. La premiere est la preparation "
    "materielle, qui consiste a depoussierer, a retirer les agrafes et a noter l'etat de "
    "conservation. La deuxieme est la prise de vue proprement dite. La troisieme est le "
    "traitement informatique des images. La quatrieme est la description, c'est-a-dire la "
    "redaction des notices qui permettront de retrouver un document parmi des millions "
    "d'autres.\n\n"

    "Le cout moyen d'une page numerisee a beaucoup baisse. En 2019, il atteignait encore 12 "
    "centimes; il est aujourd'hui inferieur a 4 centimes pour les documents courants. Cette "
    "baisse s'explique par l'automatisation du tournage de pages, par la chute du prix des "
    "capteurs et par une meilleure organisation du travail. Elle ne concerne toutefois pas les "
    "pieces fragiles, qui restent traitees a la main.\n\n"

    "La question du stockage revient a chaque reunion du comite. Une page en haute definition "
    "occupe environ 40 megaoctets, et le programme produit pres de 3 400 pages par jour ouvre. "
    "Les fichiers sont conserves en trois exemplaires, sur deux sites distincts, avec une "
    "verification d'integrite mensuelle. Le Prof. Adams, invite l'an dernier, a insiste sur le "
    "fait qu'une copie que personne ne verifie n'est pas une sauvegarde.\n\n"

    "L'acces du public a ete repense en profondeur. Le portail propose une recherche par mot, "
    "par date et par lieu, ainsi qu'une lecture page a page directement dans le navigateur. "
    "Les usagers peuvent telecharger les images en basse definition sans formalite; la haute "
    "definition reste soumise a une demande motivee. Les statistiques montrent que 8 visiteurs "
    "sur 10 arrivent depuis un moteur de recherche.\n\n"

    "L'accessibilite constitue un chantier a part entiere. Les documents dactylographies se "
    "pretent bien a la reconnaissance automatique de caracteres, et le texte obtenu peut etre "
    "lu par une synthese vocale. Les manuscrits resistent davantage. L'equipe travaille avec "
    "une association de personnes deficientes visuelles, qui teste chaque nouvelle version du "
    "portail et signale les obstacles rencontres.\n\n"

    "Les erreurs de reconnaissance ne se repartissent pas au hasard. Elles se concentrent sur "
    "les noms propres, sur les chiffres et sur les abreviations. Un registre ou figurent des "
    "sommes en francs anciens produira davantage de confusions qu'une lettre manuscrite en "
    "prose continue. Pour cette raison, les notices comportent toujours une transcription "
    "verifiee des elements essentiels: la date, le lieu et les personnes citees.\n\n"

    "La formation des agents occupe une place importante. Un nouvel operateur suit 3 semaines "
    "d'apprentissage avant de travailler seul. Il apprend a manipuler les documents, a regler "
    "l'eclairage et a reconnaitre les defauts qui imposent une reprise. Le taux de reprise, "
    "qui depassait 9 pour cent au demarrage, est descendu sous la barre de 2 pour cent depuis "
    "l'installation du nouveau materiel.\n\n"

    "Le droit d'auteur limite la diffusion d'une partie des fonds. Les oeuvres tombees dans le "
    "domaine public sont librement consultables. Les autres ne sont accessibles que depuis les "
    "postes installes dans la salle de lecture, et uniquement pour un usage de recherche. "
    "Cette distinction, mal comprise du public, fait l'objet d'une notice explicative affichee "
    "a l'entree et reprise sur le portail.\n\n"

    "Les partenariats se sont multiplies. Le service travaille avec les archives "
    "departementales, avec deux universites et avec plusieurs societes savantes. Chacun "
    "apporte des documents, du personnel ou des moyens financiers. En contrepartie, les images "
    "produites rejoignent un catalogue commun, ce qui evite qu'un meme ouvrage soit numerise "
    "deux fois par deux etablissements voisins.\n\n"

    "Les perspectives pour les 5 prochaines annees sont claires. Il s'agit d'achever la "
    "campagne sur les periodiques regionaux, d'ameliorer la recherche en texte integral et de "
    "garantir la conservation a long terme des fichiers deja produits. Le rapport se termine "
    "par une recommandation simple: mesurer regulierement ce que l'on pretend ameliorer, et "
    "publier les resultats meme lorsqu'ils sont decevants.\n\n"

    "Un mot enfin sur la mesure elle-meme. Le comite a demande que chaque indicateur soit "
    "accompagne de son incertitude, et non presente comme un chiffre unique. Une difference de "
    "quelques points entre deux ateliers ne signifie rien si elle repose sur une trentaine de "
    "pages. Le rapport applique cette regle a ses propres tableaux, quitte a reconnaitre que "
    "certaines comparaisons ne sont pas encore concluantes.\n\n"

    "La bibliotheque publie enfin la liste complete de ses prestataires. Trois societes "
    "interviennent sur la chaine: l'une pour la prise de vue, l'autre pour l'hebergement des "
    "fichiers, la troisieme pour la reconnaissance de texte. Les usagers savent ainsi ou "
    "passent les documents qu'ils confient, et a quelles conditions. Cette transparence a ete "
    "demandee par le conseil d'administration en 2019, et elle est reconduite chaque annee.\n\n"

    # The five paragraphs below were added after the cost probe. The first probe
    # rendered 869 display words as 270.3 s, which CLEARS the 200-matched-word
    # floor and MISSES the 300 s clip floor by 10 percent — and a floor missed by
    # ten percent is missed. Voices differ in speaking rate by more than that, so
    # the target is ~1200 words rather than the ~1000 that would just scrape past
    # at the locked voice's rate. The 869-word render is discarded; its call is
    # counted in the spend.
    "Le budget de fonctionnement s'eleve a 640 000 euros par an, dont 62 pour cent de masse "
    "salariale. Les credits d'investissement, plus irreguliers, ont permis en 2019 l'achat de "
    "2 scanners a plat et d'un poste de traitement couleur. La collectivite demande chaque "
    "annee un etat detaille des depenses, ventile par collection et par type d'operation, afin "
    "de comparer le cout reel d'une page selon son support.\n\n"

    "La securite des donnees fait l'objet d'un protocole ecrit. Les postes de travail ne sont "
    "pas connectes au reseau general, les supports amovibles sont interdits, et les transferts "
    "passent par un serveur intermediaire ou chaque fichier est controle. Un incident survenu "
    "en 2019 sur un disque externe a conduit a durcir ces regles; depuis, aucune perte de "
    "donnee n'a ete constatee sur les 3 dernieres campagnes.\n\n"

    "Les usagers eloignes representent une part croissante du public. Un tiers des "
    "consultations vient desormais d'une autre region, et 7 pour cent de l'etranger. Cette "
    "evolution change la nature du service: il ne s'agit plus seulement d'accueillir des "
    "lecteurs dans une salle, mais de repondre a des demandes ecrites, souvent precises, "
    "parfois formulees dans une langue que l'equipe ne pratique pas couramment.\n\n"

    "Le vocabulaire employe dans les notices merite une remarque. Les termes anciens designent "
    "des realites disparues, et un lecteur d'aujourd'hui ne les reconnait pas toujours. Le "
    "service maintient donc un glossaire de 1 400 entrees, relie aux notices, qui explique en "
    "une phrase ce qu'etait un arpent, une gabelle ou un livre tournois. Ce glossaire est "
    "consulte bien plus souvent que prevu.\n\n"

    "Enfin, le rapport rappelle une evidence trop souvent oubliee. Numeriser un document ne le "
    "conserve pas: cela en produit une image, qui devra elle-meme etre conservee, migree et "
    "verifiee pendant des decennies. L'original reste l'original, et le magasin qui l'abrite "
    "demande autant d'attention que le serveur qui heberge sa copie. Les deux budgets sont "
    "distincts, et aucun ne remplace l'autre."
)

# The SHORT fixture is `fixtures.json`'s own `fr` text, read from the file rather
# than copied — a copy is how two artifacts in one commit come to contradict each
# other (J26/J27's finding of the round).
def short_fr_text() -> str:
    return json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))["languages"]["fr"]["text"]


def clip_path(voice: str, rep: int, kind: str = "long") -> pathlib.Path:
    return OUT / (f"fr-{kind}-{voice}-r{rep}.wav" if kind == "long"
                  else f"fr-{kind}-{voice}.wav")


def planned_clips():
    """(voice, replicate, kind, text, path). The long arm answers the question;
    the short arm reproduces the ORIGINAL claim's conditions on the bar's metric,
    so the two are comparable and the difference between them is attributable."""
    rows = []
    for v in VOICES:
        for rep in range(1, REPLICATES + 1):
            rows.append((v, rep, "long", FR_LONG, clip_path(v, rep, "long")))
    short = short_fr_text()
    for v in VOICES:
        # The locked voice's short clip is ALREADY COMMITTED as out/fr.wav and is
        # reused rather than re-synthesized: the committed figure 75.0 was taken
        # on those exact bytes, and re-rendering would silently change the thing
        # every prior number refers to.
        p = OUT / "fr.wav" if v == "locked" else clip_path(v, 1, "short")
        rows.append((v, 1, "short", short, p))
    return rows


# ── Statistics ───────────────────────────────────────────────────────────────
#
# Pure Python and hand-checkable on purpose. A number this repository is being
# asked to trust should not depend on a library nobody in the review opens.

def wilson_ci(k: int, n: int, z: float = 1.959963985) -> tuple:
    """Wilson score interval for a binomial proportion, as PERCENTAGES.

    Wilson and not Wald: at 18/18 the Wald interval is [100, 100] — width zero,
    which is exactly the reading that made "Robert 100%" sound like a
    measurement. Wilson at 18/18 is [82.4, 100]. The difference between those two
    intervals is the entire dispute.
    """
    if n <= 0:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round(100.0 * max(0.0, c - h), 1), round(100.0 * min(1.0, c + h), 1))


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value: binomial(b+c, 0.5) on the discordant pairs.

    PAIRED, because both voices read the SAME text and are scored on the SAME
    display tokens. An unpaired two-proportion test on this design throws away
    the pairing and is the wrong test — it is also the more permissive one, which
    is the direction this project's errors have always gone.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def paired_diff_ci(b: int, c: int, n: int, z: float = 1.959963985) -> tuple:
    """95% CI for the paired difference in proportions, as PERCENTAGE POINTS.

    The conditional (Wilson-on-discordants) construction: the difference is
    ((2*phi) - 1) * (b+c)/n where phi = b/(b+c), so a Wilson interval on phi maps
    straight onto an interval for the difference. Degenerate by design when there
    are no discordant pairs — with b = c = 0 the difference is exactly zero and
    the interval is [0, 0], which is the correct statement and not a missing one.
    """
    nd = b + c
    if n <= 0:
        return (None, None)
    if nd == 0:
        return (0.0, 0.0)
    lo, hi = wilson_ci(b, nd, z)
    scale = nd / n
    return (round((2 * lo / 100.0 - 1) * scale * 100.0, 1),
            round((2 * hi / 100.0 - 1) * scale * 100.0, 1))


def block_bootstrap_diff(a_out, b_out, blocks, iters: int = 10000, seed: int = 20260809):
    """95% CI for the difference in `matched_within_drift_pct`, resampling SENTENCES.

    WHY A BLOCK BOOTSTRAP AND NOT JUST McNEMAR. The per-token outcomes are NOT
    independent: drift at token i is computed from the timestamps of i-1 and i+1,
    so a single badly placed token spoils its neighbours, and a whole sentence
    the recogniser dropped fails together. Treating 900 tokens as 900 independent
    trials understates the interval — in the permissive direction, again. The
    resampling unit is therefore the SENTENCE, which is the unit that fails
    together, and the interval it produces is the one to quote.

    McNemar is still reported beside it. When the two disagree, the bootstrap is
    the honest one and the gap between them is the cost of the independence
    assumption, made visible instead of assumed away.
    """
    if not blocks:
        return (None, None)
    rng = random.Random(seed)
    n = sum(len(bl) for bl in blocks)
    diffs = []
    for _ in range(iters):
        sa = sb = 0
        tot = 0
        for _ in range(len(blocks)):
            bl = blocks[rng.randrange(len(blocks))]
            for i in bl:
                sa += a_out[i]
                sb += b_out[i]
                tot += 1
        if tot:
            diffs.append(100.0 * (sa - sb) / tot)
    diffs.sort()
    lo = diffs[int(0.025 * (len(diffs) - 1))]
    hi = diffs[int(0.975 * (len(diffs) - 1))]
    return (round(lo, 1), round(hi, 1)), n


def n_for_mcnemar(delta_pp: float, discordance: float, power: float = 0.80,
                  alpha: float = 0.05) -> int:
    """Display tokens needed to detect `delta_pp` percentage points, paired.

    Answers Halo's question directly: not "is 17 enough" but "what would be".
    `discordance` is the share of tokens on which the two voices disagree, which
    is the quantity that actually drives power in a paired design and which
    NOBODY had, because nobody had run the same text through two voices on the
    bar's metric.
    """
    if delta_pp <= 0 or discordance <= 0:
        return -1
    za, zb = 1.959963985, 0.8416212336
    d = delta_pp / 100.0
    if d >= discordance:                      # every discordant pair one way
        phi = 1.0
    else:
        phi = 0.5 * (1 + d / discordance)
    if phi <= 0.5:
        return -1
    nd = ((za * 0.5 + zb * math.sqrt(phi * (1 - phi))) / (phi - 0.5)) ** 2
    return int(math.ceil(nd / discordance))


def n_for_two_proportions(p1: float, p2: float, power: float = 0.80,
                          alpha: float = 0.05) -> int:
    """Per-group n for an UNPAIRED comparison of two rates, as a sanity anchor."""
    if p1 == p2:
        return -1
    za, zb = 1.959963985, 0.8416212336
    pbar = (p1 + p2) / 2
    num = (za * math.sqrt(2 * pbar * (1 - pbar)) + zb * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2
    return int(math.ceil(num / (p1 - p2) ** 2))


# ── Scoring ──────────────────────────────────────────────────────────────────

class Mutation:
    """The knob `--self-test` turns. Off in every real run; the artifact records
    that it was off, so a mutated number cannot be published by accident."""
    drift_bound_ms = DRIFT_MS
    displace = ()            # (token_index, milliseconds) pairs applied to the ASR stream
    truncate_obs = None      # keep only this fraction of the ASR stream (desync control)
    drop_obs = None          # (start, count): excise a RUN mid-stream (re-sync control)
    active = False

    @classmethod
    def reset(cls):
        cls.drift_bound_ms = DRIFT_MS
        cls.displace = ()
        cls.truncate_obs = None
        cls.drop_obs = None
        cls.active = False


def decode(wav: pathlib.Path, lang: str, model: str = "base"):
    """Shipped decoder, shipped configuration. Deterministic — `--self-test`'s
    CTL-EQUIV would not hold otherwise, and if it stops holding, that is the
    finding, not a flake to retry."""
    obs, _, timing = M.transcribe(wav, lang, model, "int8", False)
    return obs, timing


def apply_displacement(obs):
    """Move named observed tokens by a named number of milliseconds.

    This is how a control is given teeth. Displacing k tokens by more than the
    250 ms bound must cost EXACTLY k tokens' worth of the metric plus whatever it
    does to their neighbours; if the harness does not respond, the harness is not
    measuring drift.
    """
    if Mutation.truncate_obs is not None:
        obs = obs[:max(1, int(len(obs) * Mutation.truncate_obs))]
    if Mutation.drop_obs is not None:
        # A RUN excised from the middle — the divergence the lookahead window
        # cannot span, injected. Truncation removes the tail and there is nothing
        # to recover; this removes the middle and leaves a tail that a matcher
        # with a re-sync path must reach and one without it cannot.
        at, n = Mutation.drop_obs
        obs = obs[:at] + obs[at + n:]
    if not Mutation.displace:
        return obs
    out = [dict(o) for o in obs]
    for idx, ms in Mutation.displace:
        if 0 <= idx < len(out):
            out[idx]["s"] += ms / 1000.0
            out[idx]["e"] += ms / 1000.0
    return out


def asr_absence(obs, disp, lang: str = "fr") -> list:
    """Display tokens the recogniser NEVER EMITTED, under every relaxation the
    matcher itself can apply. Returns `[(display_index, token), ...]`.

    ── WHY THIS IS IN THE ARTIFACT AND NOT IN A REPORT ──────────────────────
    The sentence "the 95 bar is not reachable by fixing the matcher" reframes
    Phase 6, and it rested on arithmetic that appeared in NO file. That is
    `J30-m1` — a published figure whose route nobody wrote down — recreated on a
    bigger claim. It is computed here, by the run that publishes it.
    """
    t = M.normalizer(lang, [d[0] for d in disp], [o["w"] for o in obs])
    kept = [r for r in t["observed"] if r["fold"]]
    ofold = [r["fold"] for r in kept]
    oloose = [r["loose"] for r in kept]
    odigits = {r["digits"] for r in kept if r["digits"]}
    grouped = t["grouped"]

    # Every contiguous run of 1-3 observed tokens, on both folds. Three because
    # that is the longest sequence `spokenForms` emits (a year: "mille" "neuf"
    # "cent"), so a longer window could not place anything a shorter one cannot.
    def runs(stream):
        s = set()
        for i, _ in enumerate(stream):
            s.add((stream[i],))
            if i + 1 < len(stream):
                s.add((stream[i], stream[i + 1]))
            if i + 2 < len(stream):
                s.add((stream[i], stream[i + 1], stream[i + 2]))
        return s
    seen = runs(ofold) | runs(oloose)

    missing = []
    for j, row in enumerate(t["display"]):
        if not row["fold"]:
            continue                      # punctuation-only: not a placeable word
        ok = (any(tuple(seq) in seen for seq in row["forms"] if seq)
              or any(tuple(seq) in seen for seq in row["looseForms"] if seq))
        if not ok:                        # the many-to-one case: `1 250` heard as `1250`
            for span in (2, 3):
                for start in range(max(0, j - span + 1), j + 1):
                    g = grouped.get(str(start), {}).get(str(span))
                    if g and g in odigits:
                        ok = True
                        break
                if ok:
                    break
        if not ok:
            missing.append((j, disp[j][0]))
    return missing


def score(obs, text: str, lang: str = "fr") -> dict:
    """`matched_within_drift_pct` and the per-display-token outcome vector.

    The aggregate is the SHIPPED definition, byte for byte: local three-point
    neighbour interpolation on display CHARACTER offsets, endpoints excluded from
    the numerator (J22-M4), denominator `len(display)`. The vector is the same
    quantity per token, and it is the thing every statistic below consumes —
    which is why the aggregate is asserted equal to `sum(vector)/len(display)`
    rather than computed twice.
    """
    disp = M.display_words(text)
    obs = apply_displacement(obs)
    full = M.match_full(obs, disp, lang)
    matched, unmatched, resyncs = full["matched"], full["unmatched"], full["resyncs"]

    drift_by_disp, drift_all, drift_interior = {}, [], []
    for i in range(1, len(matched) - 1):
        prev, cur, nxt = matched[i - 1], matched[i], matched[i + 1]
        span_c = max(nxt["cs"] - prev["cs"], 1)
        span_t = max(nxt["s"] - prev["s"], 1e-6)
        predicted = prev["s"] + span_t * ((cur["cs"] - prev["cs"]) / span_c)
        d = abs(cur["s"] - predicted) * 1000.0
        drift_by_disp[cur["disp_idx"]] = d
        drift_all.append(d)
        if not H.SENT_END.search(text[prev["cs"]:nxt["cs"]]):
            drift_interior.append(d)

    bound = Mutation.drift_bound_ms
    outcome = [1 if drift_by_disp.get(i, float("inf")) <= bound else 0 for i in range(len(disp))]
    pct = 100.0 * sum(outcome) / len(disp) if disp else 0.0
    srt = sorted(drift_all)

    # ── MATCHER DESYNC — the gate, and what it now measures ──────────────────
    #
    # THE DEFECT THIS GATE WAS BUILT FOR IS FIXED. The matcher was a monotonic
    # greedy loop with a six-display-token lookahead and NO RE-SYNC PATH: when
    # the recogniser's output diverged from the page by more than that window the
    # display cursor could not catch up and NEVER RECOVERED. Measured, not
    # theorised — `fr-long-narrateur-r1.wav` produced a FULL 1267-token
    # transcript and the matcher stopped dead at display index 545 of 1185, with
    # coverage by decile [73, 74, 77, 62, 15, 0, 0, 0, 0, 0]. The audio was fine
    # and the recognition was fine.
    #
    # `worker/src/match/match.ts` has the re-sync path now: after three
    # consecutive observations the window cannot place, it looks for the nearest
    # position AHEAD of the cursor where the page reads the way the recogniser is
    # reading, and resumes there. Forward only, so §6.1's monotonicity survives
    # the recovery, and bounded, so a recovery cannot silently write off an
    # arbitrary amount of page.
    #
    # THE GATE STAYS, and it is not decoration. A re-sync path recovers from a
    # divergence; it cannot recover from a transcript that STOPS — nothing to
    # anchor to — and it deliberately refuses a recovery further than
    # `MAX_RESYNC_SKIP`. Both of those still produce an untracked tail, both are
    # still inadmissible, and CTL-DESYNC proves the gate fires on the first while
    # CTL-RESYNC proves it does not fire on the second. A gate deleted because
    # one cause of its condition was fixed is a gate deleted for the wrong reason.
    #
    # The tell was the one this spike has shown every time, inverted: the drift
    # DISTRIBUTION was untouched (medians 46-73 ms across every clip, good and
    # bad alike), and it was the NUMERATOR'S COVERAGE that collapsed. A reader
    # comparing medians would have seen nothing wrong.
    #
    # Thirds rather than deciles so the same rule works on a 24-token fixture and
    # an 1186-token one.
    n = len(disp)
    third = max(1, n // 3)
    placed = {m["disp_idx"] for m in matched}
    absent = asr_absence(obs, disp, lang)
    ceiling_pct = round(100.0 * (n - len(absent)) / n, 1) if n else 0.0
    head = sum(1 for i in range(third) if i in placed) / third
    tailc = sum(1 for i in range(n - third, n) if i in placed) / third
    desynced = bool(head > 0 and tailc < 0.5 * head)
    return {
        "match_rate_first_third_pct": round(100.0 * head, 1),
        "match_rate_last_third_pct": round(100.0 * tailc, 1),
        "tracking_ratio": round(tailc / head, 3) if head else None,
        "last_matched_display_idx": max(placed) if placed else None,
        # A desynced clip is INADMISSIBLE. It is reported with its numbers, never
        # silently dropped and never averaged in — the same discipline the
        # `provisional` grade exists to enforce one level up.
        "matcher_desynced": desynced,
        "admissible": not desynced,
        # ── THE CEILING. What NO matcher could beat on this transcript ───────
        #
        # Deliberately verbose key names. The two figures this decomposition was
        # first reported with — 92.2 and 89.5 — each collide with a DIFFERENT
        # quantity already on disk: 92.2 is `median_drift_ms` for `en` in
        # spike-a-resultssmall.json (milliseconds), and 89.5 is `match_rate_pct`
        # for this very clip. A reader grepping either number found a confident
        # hit that was the wrong quantity, which is the value-collision hazard
        # this project has now been bitten by four times. A key nobody can
        # confuse costs nothing.
        "asr_coverage_ceiling": {
            "display_tokens": len(disp),
            "display_tokens_absent_from_transcript": len(absent),
            "coverage_ceiling_pct_any_matcher": ceiling_pct,
            "coverage_ceiling_clears_bar": bool(ceiling_pct >= BAR_MATCHED_PCT),
            "coverage_ceiling_gap_to_bar_pp": round(BAR_MATCHED_PCT - ceiling_pct, 1),
            "unplaced_display_tokens": len(disp) - len(placed),
            "unplaced_but_present_in_transcript":
                (len(disp) - len(placed)) - len(absent),
            "absent_display_tokens_sample": [tok for _, tok in absent[:25]],
            "_derivation": (
                "coverage_ceiling_pct_any_matcher = 100 * (display_tokens - "
                "display_tokens_absent_from_transcript) / display_tokens. A display token "
                "counts as ABSENT when NO contiguous run of 1-3 observed tokens equals any "
                "sequence in that token's `forms` or `looseForms` from "
                "worker/src/normalize/spokenForms, and no grouped-digit form covering it "
                "matches an observed token's digits. Those are exactly the relaxations "
                "worker/src/match/matchTokens can apply, so a token absent here is one the "
                "recogniser did not emit in any form the matcher could accept, and NO "
                "matcher can place it. Order-free and one-to-many-free on purpose: it "
                "ignores monotonicity and lets one observation serve several display "
                "tokens, so it is a STRICT UPPER BOUND and a real matcher can only do "
                "worse. It is NOT a prediction of what a better matcher would score. "
                "The achieved figures are `match_rate_pct` (coverage this matcher reached) "
                "and `matched_within_drift_pct` (what survived the 250 ms bound); they are "
                "NOT restated here, so they cannot drift out of agreement with themselves. "
                "The load-bearing comparison is coverage_ceiling_pct_any_matcher against "
                "the bar: when the ceiling is below it, the bar is unreachable on this "
                "transcript no matter what the matcher does."),
        },
        # EVERY RECOVERY IS ON THE RECORD. A re-sync writes off the display
        # tokens it jumps over, so a clip that scores well after twenty of them
        # is not the same result as one that needed none, and a reader who cannot
        # see the difference cannot tell a matcher that tracked from a matcher
        # that kept re-acquiring. They stay in the denominator either way.
        "resyncs": len(resyncs),
        "resync_skipped_display_tokens": sum(r["skipped_display_tokens"] for r in resyncs),
        "resync_detail": resyncs,
        "display_words": len(disp),
        "observed_tokens": len(obs),
        "matched": len(matched),
        "matched_within_drift_pct": round(pct, 1),
        "match_rate_pct": round(100.0 * len(matched) / len(disp), 1) if disp else 0.0,
        "hallucination_rate": round(100.0 * len(unmatched) / len(obs), 1) if obs else 0.0,
        "drift_measurable_tokens": len(drift_all),
        "drift_admissible_tokens": len(drift_interior),
        "median_drift_ms": round(statistics.median(drift_all), 1) if drift_all else None,
        "p95_drift_ms": round(srt[int(0.95 * (len(srt) - 1))], 1) if srt else None,
        "median_drift_ms_sentence_excluded":
            round(statistics.median(drift_interior), 1) if drift_interior else None,
        "drift_bound_ms": bound,
        "passes_matched_bar": bool(pct >= BAR_MATCHED_PCT),
        "_outcome": outcome,
        "_drift_by_disp": drift_by_disp,
    }


def sentence_blocks(text: str):
    """Display indices grouped by sentence — the bootstrap's resampling unit."""
    disp = M.display_words(text)
    blocks, cur = [], []
    for i, (_, cs, ce) in enumerate(disp):
        cur.append(i)
        # SENT_END requires the terminator to be followed by whitespace, so the
        # slice runs one character past the token.
        if H.SENT_END.search(text[cs:ce + 1]):
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    return blocks


def cross_engine_agreement(wav: pathlib.Path, text: str, lang: str = "fr",
                           a: str = "base", b: str = "small") -> dict:
    """`agree_within_250ms_pct` — the SUBSTITUTED metric, computed honestly.

    Word-level on BOTH sides (two faster-whisper models, not a word stream against
    a segment stream, which is what produced 88.2 / 94.4 / 100), paired by DISPLAY
    INDEX rather than by surface-form uniqueness — the filter that deleted every
    function word and every numeral and drove n down to 14-21 (H26-M8).

    It is computed here for exactly one purpose: to show what it does and does not
    tell you about the bar. Two engines can agree perfectly on a timestamp that is
    wrong in the same way, and agreement has no term for a display word neither
    engine placed at all.
    """
    disp = M.display_words(text)
    oa, _ = decode(wav, lang, a)
    ob, _ = decode(wav, lang, b)
    ua = H.units_from_asr(oa, disp, lang)
    ub = H.units_from_asr(ob, disp, lang)
    pairs = H.pair_by_display(ua, ub)
    if not pairs:
        return {"agree_within_250ms_pct": None, "compared_words": 0}
    deltas = [abs(x["s"] - y["s"]) * 1000.0 for _, x, y in pairs]
    srt = sorted(deltas)
    return {
        "agree_within_250ms_pct": round(100.0 * sum(1 for d in deltas if d <= 250) / len(deltas), 1),
        "compared_words": len(pairs),
        "median_delta_ms": round(statistics.median(deltas), 1),
        "p95_delta_ms": round(srt[int(0.95 * (len(srt) - 1))], 1),
        "engine_a": a, "engine_b": b,
        "_note": ("Cross-engine agreement over words BOTH engines placed. Its denominator is "
                  "the intersection, so a display word neither engine placed is invisible to "
                  "it — which is why it can read 100 on a clip whose bar metric is 75."),
    }


# ── TTS ──────────────────────────────────────────────────────────────────────

def _fish_key() -> str:
    env_path = ROOT.parent.parent / ".env"
    if not env_path.exists():
        sys.exit("no .env at repo root")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("FISH_AUDIO_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("FISH_AUDIO_API_KEY not in .env")


def synth(text: str, reference_id: str, dest: pathlib.Path) -> dict:
    """One Fish `s2-pro` call, through the SHIPPED request shape.

    `tts.synth_fish` is imported rather than reimplemented: a second copy of a
    provider call is a second place for the request body to drift, and this
    repository's most recurrent defect by a wide margin is a fix landing in one
    of two copies.
    """
    import tts as T
    audio = T.synth_fish(text, reference_id, _fish_key())
    audio = H.repair_wav_header(audio)
    dest.write_bytes(audio)
    info = H.wav_info(dest)
    return {"path": dest.name, "bytes": len(audio), "seconds": round(info["seconds"], 2),
            "sample_rate": info["sample_rate"], "utf8_bytes_sent": len(text.encode("utf-8")),
            "chars_sent": len(text)}


def rebuild_manifest() -> None:
    """`tts.py --manifest` semantics, invoked in-process. No API call.

    Required, not optional: `[ART-STALE]` leg (i) fails the gate for any .wav in
    `out/` the manifest does not describe, and leg (ii) re-hashes every one. New
    audio that is not in the manifest is audio no result can be tied to.
    """
    import tts as T
    T.write_manifest()


# ── Self-test ────────────────────────────────────────────────────────────────

class ControlFailure(Exception):
    pass


def _check(ok: bool, cid: str, msg: str, log: list) -> None:
    log.append((cid, bool(ok), msg))
    if not ok:
        raise ControlFailure(f"{cid}: {msg}")


def self_test() -> int:
    """Mutate the measurement and require every control to break.

    Runs entirely on the COMMITTED audio, so it is executable on a fresh clone
    with no key and no spend. Five instruments in this spike shipped numbers that
    were the instrument's fault; the only defence that has ever worked here is a
    control proven to fail.
    """
    log: list = []
    committed = {r["lang"]: r for r in json.loads(
        (OUT / "spike-a-results.json").read_text(encoding="utf-8"))}
    fx = json.loads((ROOT / "fixtures.json").read_text(encoding="utf-8"))["languages"]

    # ---- CTL-EQUIV -----------------------------------------------------------
    # This file's scorer must BE the shipped scorer, not resemble it.
    Mutation.reset()
    cache = {}
    for lang in ("en", "es", "fr"):
        obs, _ = decode(OUT / f"{lang}.wav", lang)
        cache[lang] = obs
        s = score(obs, fx[lang]["text"], lang)
        want = committed[lang]["matched_within_drift_pct"]
        _check(s["matched_within_drift_pct"] == want, "CTL-EQUIV",
               f"{lang}: recomputed {s['matched_within_drift_pct']} vs committed {want}", log)
        _check(s["drift_measurable_tokens"] == committed[lang]["drift_measurable_tokens"],
               "CTL-EQUIV", f"{lang}: n_drift mismatch", log)
        _check(s["matched"] == committed[lang]["matched"], "CTL-EQUIV",
               f"{lang}: matched-token count mismatch", log)
        _check(abs(s["p95_drift_ms"] - committed[lang]["p95_drift_ms"]) < 1e-9,
               "CTL-EQUIV", f"{lang}: p95 mismatch", log)
        # the aggregate and the vector are the SAME quantity or one of them is wrong
        _check(round(100.0 * sum(s["_outcome"]) / s["display_words"], 1)
               == s["matched_within_drift_pct"], "CTL-EQUIV",
               f"{lang}: outcome vector disagrees with the aggregate", log)

    # ---- CTL-REPRO -----------------------------------------------------------
    # `median_drift_ms` for `fr` does NOT reproduce on this host: the committed
    # artifact says 76.4 and eight consecutive fresh processes return 80.0, while
    # matched_within_drift_pct, matched, drift_measurable_tokens and p95 are
    # identical to the byte in every one of them. Sorted, this run's 21 values put
    # 76.4 at rank 10 and 80.0 at rank 11 — the committed figure is the neighbour
    # of the recomputed one, so the divergence is ONE order-statistic step and one
    # word timestamp, not a different measurement.
    #
    # That is the bound this control asserts, and it is a real assertion: it fails
    # if the committed median is not even present in the recomputed distribution,
    # which is what a changed matcher, a changed bound or changed audio would look
    # like. It is NOT relaxed to "close enough" — a tolerance is how a instrument
    # drift gets absorbed instead of reported.
    #
    # The artifact records no library version, no host and no thread count, so
    # which of those moved cannot be recovered from it. That is the finding:
    # a reproducibility claim needs the environment written down beside the
    # number. REPORTED, not worked around — the voice comparison below is immune
    # because every clip in it is decoded in ONE process on ONE host, and the BAR
    # metric was stable across all eight runs anyway.
    for lang in ("en", "es", "fr"):
        s = score(cache[lang], fx[lang]["text"], lang)
        vals = {round(v, 1) for v in s["_drift_by_disp"].values()}
        want = committed[lang]["median_drift_ms"]
        _check(want in vals or abs(s["median_drift_ms"] - want) < 1e-9, "CTL-REPRO",
               f"{lang}: committed median {want} ms is not even a member of the recomputed "
               f"drift distribution — the divergence is larger than a rank shift", log)

    # ---- CTL-EQUIV, mutated --------------------------------------------------
    Mutation.drift_bound_ms = 1000
    broke = score(cache["fr"], fx["fr"]["text"], "fr")["matched_within_drift_pct"] != 75.0
    Mutation.reset()
    _check(broke, "CTL-EQUIV/mut",
           "moving the drift bound to 1000 ms did NOT change the figure — the bound is "
           "declared and not applied, which is H21-C3 verbatim", log)

    # ---- CTL-NULL ------------------------------------------------------------
    # The same audio, scored twice, presented as two voices. Anything but zero is
    # the harness inventing a difference.
    a = score(cache["fr"], fx["fr"]["text"], "fr")
    b = score(cache["fr"], fx["fr"]["text"], "fr")
    bb = sum(1 for x, y in zip(a["_outcome"], b["_outcome"]) if x and not y)
    cc = sum(1 for x, y in zip(a["_outcome"], b["_outcome"]) if y and not x)
    _check((bb, cc) == (0, 0), "CTL-NULL", f"identical input produced b={bb} c={cc}", log)
    _check(mcnemar_exact(bb, cc) == 1.0, "CTL-NULL", "p != 1 on identical input", log)
    _check(paired_diff_ci(bb, cc, a["display_words"]) == (0.0, 0.0), "CTL-NULL",
           "the CI on a zero difference is not [0, 0]", log)

    # ---- CTL-NULL, mutated ---------------------------------------------------
    # Displace one observed token far past the bound. The null control must stop
    # reporting zero, or it is checking nothing.
    Mutation.displace = ((5, 900),)
    b2 = score(cache["fr"], fx["fr"]["text"], "fr")
    Mutation.reset()
    d_b = sum(1 for x, y in zip(a["_outcome"], b2["_outcome"]) if x and not y)
    d_c = sum(1 for x, y in zip(a["_outcome"], b2["_outcome"]) if y and not x)
    _check(d_b + d_c > 0, "CTL-NULL/mut",
           "displacing a token by 900 ms produced no discordant pair — the outcome vector "
           "does not depend on the timestamps it claims to measure", log)

    # ---- CTL-POWER -----------------------------------------------------------
    # A one-token difference must NOT be called significant. This is the control
    # the original claim needed and did not have: 15/17 vs 17/18 is two tokens.
    _check(mcnemar_exact(1, 0) > 0.05, "CTL-POWER",
           "a single discordant token is being reported as significant", log)
    _check(mcnemar_exact(2, 0) > 0.05, "CTL-POWER",
           "two discordant tokens are being reported as significant — this is exactly the "
           "size of the Miriam/Mario/Robert difference", log)
    _check(mcnemar_exact(3, 0) > 0.05, "CTL-POWER", "three tokens called significant", log)
    _check(mcnemar_exact(6, 0) < 0.05, "CTL-POWER",
           "six discordant tokens one-way is NOT being detected — the test has no power at "
           "all and would never reject anything", log)

    # ---- CTL-BLIND -----------------------------------------------------------
    # A LOCAL drift measure is BLIND TO A CONSTANT OFFSET, by construction:
    # displace every token by the same amount and every neighbourhood keeps its
    # shape. This is not a bug in this file — it is a property of the metric the
    # roadmap chose, and it is asserted here so that it is a stated limitation
    # rather than something a later round discovers. A whole-clip lead or lag,
    # which is exactly what a wrong container offset or a trimmed leading silence
    # produces, does not move `matched_within_drift_pct` at all.
    base = score(cache["fr"], fx["fr"]["text"], "fr")
    Mutation.displace = tuple((i, 750) for i in range(len(cache["fr"])))
    allshift = score(cache["fr"], fx["fr"]["text"], "fr")
    Mutation.reset()
    _check(allshift["matched_within_drift_pct"] == base["matched_within_drift_pct"],
           "CTL-BLIND",
           "a uniform 750 ms offset of the WHOLE clip changed the metric; then the drift "
           "measure is not local and the published figures mean something else again", log)

    # ---- CTL-SHIFT -----------------------------------------------------------
    # Many displaced tokens must be detected, and the metric must fall. Alternate
    # tokens, not a contiguous block: CTL-BLIND is the reason a block would be a
    # weak mutation.
    Mutation.displace = tuple((i, 900) for i in range(2, 20, 2))
    shifted = score(cache["fr"], fx["fr"]["text"], "fr")
    Mutation.reset()
    _check(shifted["matched_within_drift_pct"] < base["matched_within_drift_pct"],
           "CTL-SHIFT", "displacing alternate tokens by 900 ms did not lower the metric", log)
    sb = sum(1 for x, y in zip(base["_outcome"], shifted["_outcome"]) if x and not y)
    sc = sum(1 for x, y in zip(base["_outcome"], shifted["_outcome"]) if y and not x)
    _check(mcnemar_exact(sb, sc) < 0.05, "CTL-SHIFT",
           f"a gross injected defect (b={sb} c={sc}) was not detected", log)

    # ---- CTL-TAIL ------------------------------------------------------------
    # THE TELL. Every defect this spike has found inflated the tail and left the
    # median alone. The harness must be able to see that shape, or it will miss
    # the next one the same way it missed the last five.
    Mutation.displace = ((9, 3000), (10, 3000))
    tail = score(cache["fr"], fx["fr"]["text"], "fr")
    Mutation.reset()
    _check(tail["p95_drift_ms"] > base["p95_drift_ms"] * 2, "CTL-TAIL",
           "a 3-second displacement of two tokens did not move p95", log)
    _check(tail["median_drift_ms"] <= base["median_drift_ms"] * 1.6, "CTL-TAIL",
           "the median moved as much as the tail, so this harness cannot distinguish a "
           "tail-only defect from a systematic one", log)
    _check(tail["matched_within_drift_pct"] < base["matched_within_drift_pct"], "CTL-TAIL",
           "a tail-only defect left the bar metric untouched", log)

    # ---- CTL-DESYNC ----------------------------------------------------------
    # The admissibility gate must fire on a matcher that stops tracking, and must
    # NOT fire on one that tracks to the end. Truncating the observed stream to
    # its first 40% reproduces the failure on committed audio: the head still
    # matches, the tail cannot.
    _check(not base["matcher_desynced"], "CTL-DESYNC",
           "the desync gate fired on a clip the matcher tracked to the end — it would "
           "discard good measurements", log)
    Mutation.truncate_obs = 0.4
    cut = score(cache["fr"], fx["fr"]["text"], "fr")
    Mutation.reset()
    _check(cut["matcher_desynced"], "CTL-DESYNC",
           "the matcher was given only the first 40% of the transcript and the gate did NOT "
           "fire — then it cannot see the failure that produced 29.1% on a 6-minute clip", log)
    _check(cut["tracking_ratio"] < base["tracking_ratio"], "CTL-DESYNC",
           "truncating the transcript did not lower the tracking ratio", log)

    # ---- CTL-RESYNC ----------------------------------------------------------
    # THE REPAIR, falsified on committed audio rather than asserted.
    #
    # Excise a RUN of seven observations from the middle of the transcript. Seven
    # is one more than the lookahead window, which is precisely the divergence
    # the old matcher could not span: it would stall at the excision and place
    # nothing after it. The matcher must instead re-acquire the page, reach the
    # LAST display token, and — this is the half that keeps the control honest —
    # leave the seven display tokens it jumped over UNMATCHED, because a recovery
    # that credited them would be a recovery that invented coverage.
    #
    # The negative direction is CTL-DESYNC above, on the same audio: a truncated
    # transcript has no tail to re-acquire, and the gate must still fire there.
    # A re-sync path that "recovered" from truncation would be finding anchors in
    # observations that do not exist.
    Mutation.drop_obs = (6, 7)
    gap = score(cache["fr"], fx["fr"]["text"], "fr")
    Mutation.reset()
    _check(gap["resyncs"] >= 1, "CTL-RESYNC",
           "seven observations were excised mid-stream and the matcher recorded NO re-sync — "
           "either the path did not fire or it is not reporting when it does", log)
    _check(not gap["matcher_desynced"], "CTL-RESYNC",
           "the matcher did not recover from a mid-stream gap one token wider than its "
           "lookahead window — this is the defect that produced 29.1% on a 6-minute clip", log)
    _check(gap["last_matched_display_idx"] == base["last_matched_display_idx"], "CTL-RESYNC",
           f"after the gap the matcher reached display index "
           f"{gap['last_matched_display_idx']}, not the {base['last_matched_display_idx']} it "
           f"reaches on the intact stream — it recovered partially, which is not recovery", log)
    _check(gap["matched"] < base["matched"], "CTL-RESYNC",
           "removing seven observations did not reduce the matched count — the recovery is "
           "crediting display tokens nobody said, which is worse than the desync it fixes", log)
    _check(gap["resync_skipped_display_tokens"] == base["matched"] - gap["matched"],
           "CTL-RESYNC",
           f"the {gap['resync_skipped_display_tokens']} display tokens the re-sync jumped over "
           f"do not account for the {base['matched'] - gap['matched']} the clip lost — the "
           f"write-off and the loss must be the same tokens", log)

    # ---- CTL-CEILING ---------------------------------------------------------
    # The ASR-absence ceiling is the number that reframes Phase 6 — "the bar is
    # not reachable by fixing the matcher" — so it gets a control, not a comment.
    #
    # Three properties, and the third is the one that matters. A quantity derived
    # from the transcript must MOVE when the transcript does; a "ceiling" that
    # ignores its own input would be a constant wearing a derivation.
    base_ceil = base["asr_coverage_ceiling"]
    _check(base_ceil["coverage_ceiling_pct_any_matcher"] >= base["match_rate_pct"],
           "CTL-CEILING",
           f"the ceiling ({base_ceil['coverage_ceiling_pct_any_matcher']}%) is BELOW what the "
           f"matcher actually placed ({base['match_rate_pct']}%) — an upper bound the run "
           f"already beat is not an upper bound", log)
    _check(base_ceil["unplaced_but_present_in_transcript"] >= 0, "CTL-CEILING",
           "more display tokens are absent from the transcript than are unplaced, which is "
           "arithmetically impossible: every absent token must also be unplaced", log)
    Mutation.truncate_obs = 0.5
    halved = score(cache["fr"], fx["fr"]["text"], "fr")
    Mutation.reset()
    _check(halved["asr_coverage_ceiling"]["coverage_ceiling_pct_any_matcher"]
           < base_ceil["coverage_ceiling_pct_any_matcher"], "CTL-CEILING",
           "half the transcript was removed and the ceiling did not fall — it is not being "
           "derived from the observations at all", log)

    # ---- CTL-STATS -----------------------------------------------------------
    # Hand-computable values. If these drift, every interval below is decoration.
    lo, hi = wilson_ci(18, 18)
    _check(hi == 100.0 and 80.0 < lo < 85.0, "CTL-STATS",
           f"Wilson(18/18) = [{lo}, {hi}]; expected lower bound near 82.4", log)
    _check(wilson_ci(17, 18)[0] < wilson_ci(18, 18)[0], "CTL-STATS",
           "a worse count produced a higher lower bound", log)
    _check(abs(mcnemar_exact(10, 0) - 0.001953125) < 1e-9, "CTL-STATS",
           "exact McNemar(10, 0) != 2 * 0.5^10", log)
    _check(mcnemar_exact(5, 5) == 1.0, "CTL-STATS", "McNemar(5, 5) != 1", log)
    _check(abs(mcnemar_exact(0, 0) - 1.0) < 1e-12, "CTL-STATS", "McNemar(0, 0) != 1", log)
    n17 = n_for_mcnemar(12.0, 0.20)
    _check(n17 > 17, "CTL-STATS",
           f"the sample size required for a 12-point effect came out as {n17}, which would "
           "mean the original n of 17 was adequate", log)
    _check(n_for_two_proportions(1.00, 0.88) > 17, "CTL-STATS",
           "unpaired sizing says n=17 suffices for 100 vs 88", log)

    # ---- CTL-BOOT ------------------------------------------------------------
    # A sentence-block bootstrap must be WIDER than one that resamples tokens
    # independently whenever outcomes are correlated within a sentence. If it is
    # not, the blocking is decorative and the intervals are the optimistic ones.
    corr_a = [1] * 40 + [0] * 40
    corr_b = [1] * 80
    blocks_corr = [list(range(0, 40)), list(range(40, 80))]
    blocks_ind = [[i] for i in range(80)]
    (blo, bhi), _ = block_bootstrap_diff(corr_a, corr_b, blocks_corr, iters=3000)
    (ilo, ihi), _ = block_bootstrap_diff(corr_a, corr_b, blocks_ind, iters=3000)
    _check((bhi - blo) > (ihi - ilo), "CTL-BOOT",
           f"blocked CI width {bhi - blo} is not wider than the independent-token CI width "
           f"{ihi - ilo} on perfectly correlated blocks — the blocking does nothing", log)
    _check(block_bootstrap_diff([1] * 50, [1] * 50, [[i] for i in range(50)],
                                iters=500)[0] == (0.0, 0.0), "CTL-BOOT",
           "the bootstrap reports a nonzero interval for two identical vectors", log)

    print(f"self-test: {len(log)} controls, all passed")
    by = {}
    for cid, _, _ in log:
        by[cid] = by.get(cid, 0) + 1
    for cid in sorted(by):
        print(f"  {cid:16} {by[cid]}")
    print("\n  Each control is asserted in BOTH directions: it holds on clean input and the")
    print("  '/mut' variants prove it breaks on a defect. A control that only ever passes")
    print("  is what this spike shipped five times.")
    return 0


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_probe() -> int:
    """ONE call. Then stop, and read the cost off the dashboard."""
    v = VOICES["locked"]
    dest = clip_path("locked", 1, "long")
    t0 = time.time()
    rec = synth(FR_LONG, v["reference_id"], dest)
    rec.update({"voice": "locked", "reference_id": v["reference_id"],
                "provider": "fish", "model": "s2-pro",
                "elapsed_seconds": round(time.time() - t0, 1),
                "text_sha256": _sha(FR_LONG)})
    disp = M.display_words(FR_LONG)
    rec["display_words_in_text"] = len(disp)
    rec["clears_clip_floor_300s"] = rec["seconds"] >= 300.0
    rec["truncated"] = rec["seconds"] < 240.0
    H.write_json(PROBE_ARTIFACT, rec)
    rebuild_manifest()
    print(f"  1 TTS call. {rec['bytes']} bytes / {rec['seconds']}s from "
          f"{rec['utf8_bytes_sent']} UTF-8 bytes of text, in {rec['elapsed_seconds']}s")
    print(f"  display words in the text: {rec['display_words_in_text']}")
    print(f"  clears the 300 s clip floor: {rec['clears_clip_floor_300s']}")
    if rec["truncated"]:
        print("  !! LOOKS TRUNCATED. Do not scale. Chunk the text and re-probe.")
    print("\n  STOPPING. Read the real cost off the Fish dashboard before scaling.")
    print("  Then: python voices.py --synth --yes")
    return 0


def cmd_synth(yes: bool) -> int:
    if not PROBE_ARTIFACT.exists():
        sys.exit("run --probe first, and read the cost. That is the owner's standing rule.")
    todo = [(v, r, k, t, p) for v, r, k, t, p in planned_clips() if not p.exists()]
    utf8 = sum(len(t.encode("utf-8")) for _, _, _, t, _ in todo)
    print(f"  {len(todo)} TTS call(s), {utf8} UTF-8 bytes of text:")
    for v, r, k, t, p in todo:
        print(f"    {p.name:32} {k:5} rep{r}  {len(t.encode('utf-8')):>6} bytes")
    if not yes:
        print("\n  --yes to spend it.")
        return 0
    rows = []
    for v, r, k, t, p in todo:
        t0 = time.time()
        rec = synth(t, VOICES[v]["reference_id"], p)
        rec.update({"voice": v, "kind": k, "replicate": r,
                    "reference_id": VOICES[v]["reference_id"],
                    "elapsed_seconds": round(time.time() - t0, 1)})
        rows.append(rec)
        print(f"    {p.name}: {rec['seconds']}s / {rec['bytes']} bytes in {rec['elapsed_seconds']}s")
    rebuild_manifest()
    print(f"\n  {len(rows)} call(s) spent. Manifest rebuilt (required by [ART-STALE]).")
    return 0


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cmd_measure(cross: bool) -> int:
    Mutation.reset()
    clips = planned_clips()
    missing = [p.name for _, _, _, _, p in clips if not p.exists()]
    if missing:
        print(f"  missing audio (scored as absent, not as zero): {missing}")

    scored, blocks_cache = {}, {}
    for v, r, k, text, p in clips:
        if not p.exists():
            continue
        obs, timing = decode(p, "fr")
        s = score(obs, text, "fr")
        info = H.wav_info(p)
        s.update({
            # NOT `lang` + `audio_seconds`. A result here is per-(lang, VOICE) —
            # the shape `voice_langs` is keyed by — and `${lang}.wav` cannot name
            # such a clip. The provenance is therefore carried EXPLICITLY, by
            # path and by hash. doc-check's [ART-STALE] reads this shape now, on
            # all three legs; see `_art_stale_gap` in the artifact for what
            # changed and what it quotes.
            "lang_code": "fr",
            "voice": v, "replicate": r, "kind": k,
            "reference_id": VOICES[v]["reference_id"],
            "provider_title": VOICES[v]["provider_title"],
            "audio_path": p.name,
            "audio_sha256": _sha_file(p),
            "clip_seconds": round(info["seconds"], 2),
            "clip_ms": int(round(info["seconds"] * 1000)),
            "cpu_seconds": round(timing["cpu_seconds"], 2),
        })
        scored[(v, r, k)] = s
        blocks_cache[k] = blocks_cache.get(k) or sentence_blocks(text)

    rows = []
    for key, s in scored.items():
        pub = {kk: vv for kk, vv in s.items() if not kk.startswith("_")}
        k_in = sum(s["_outcome"])
        pub["matched_within_drift_ci95"] = list(wilson_ci(k_in, s["display_words"]))
        pub["in_bound_tokens"] = k_in
        # The evidence floor, evaluated per clip, on this clip's own numbers.
        pub["floor_sync_matched_words_ge_200"] = bool(s["matched"] >= 200)
        pub["floor_clip_ms_ge_300000"] = bool(s["clip_ms"] >= 300000)
        pub["floor_metric_is_bar"] = True
        pub["voice_langs_grade_this_evidence_supports"] = (
            "at_or_above_bar" if (s["matched"] >= 200 and s["clip_ms"] >= 300000
                                  and s["passes_matched_bar"]) else
            "below_bar" if (s["matched"] >= 200 and s["clip_ms"] >= 300000) else
            "provisional")
        rows.append(pub)
    rows.sort(key=lambda r: (r["kind"], r["voice"], r["replicate"]))

    comparisons = []
    for kind in ("long", "short"):
        # INADMISSIBLE CLIPS ARE NOT COMPARED. A desynced clip's figure is a
        # reading of the matcher, not of the voice, and pairing it against a
        # tracked clip manufactures a 45-point "voice effect" out of a lookahead
        # window. They stay in `clips` with their numbers and their flag.
        keys = [k for k in scored if k[2] == kind and scored[k]["admissible"]]
        blocks = blocks_cache.get(kind) or []
        for i, ka in enumerate(keys):
            for kb in keys[i + 1:]:
                a, b = scored[ka], scored[kb]
                if a["display_words"] != b["display_words"]:
                    continue
                bb = sum(1 for x, y in zip(a["_outcome"], b["_outcome"]) if x and not y)
                cc = sum(1 for x, y in zip(a["_outcome"], b["_outcome"]) if y and not x)
                n = a["display_words"]
                boot, _ = block_bootstrap_diff(a["_outcome"], b["_outcome"], blocks) \
                    if blocks else ((None, None), 0)
                same_voice = ka[0] == kb[0]
                comparisons.append({
                    "kind": kind,
                    "a": f"{ka[0]}#r{ka[1]}", "b": f"{kb[0]}#r{kb[1]}",
                    "comparison_type": "within_voice_replicate" if same_voice else "between_voice",
                    "a_pct": a["matched_within_drift_pct"],
                    "b_pct": b["matched_within_drift_pct"],
                    "diff_pp": round(a["matched_within_drift_pct"] - b["matched_within_drift_pct"], 1),
                    "discordant_b": bb, "discordant_c": cc,
                    "discordance_rate": round((bb + cc) / n, 4) if n else None,
                    "mcnemar_exact_p": round(mcnemar_exact(bb, cc), 6),
                    "diff_ci95_conditional_pp": list(paired_diff_ci(bb, cc, n)),
                    "diff_ci95_sentence_block_bootstrap_pp": list(boot),
                    "significant_at_05": bool(mcnemar_exact(bb, cc) < 0.05),
                    "n_display_tokens": n,
                })

    # The question the whole exercise turns on: is the BETWEEN-voice spread
    # bigger than the WITHIN-voice spread? If it is not, "voice choice is a
    # word-sync variable" is a statement about the sampler's random seed.
    verdict = _verdict(comparisons, rows)

    cross_rows = []
    if cross:
        for v in VOICES:
            p = clip_path(v, 1, "long")
            if not p.exists():
                continue
            ce = cross_engine_agreement(p, FR_LONG)
            bar = scored[(v, 1, "long")]["matched_within_drift_pct"]
            ce.update({"voice": v, "audio_path": p.name, "matched_within_drift_pct": bar,
                       "gap_pp": round((ce["agree_within_250ms_pct"] or 0) - bar, 1)})
            cross_rows.append(ce)

    art = {
        "_subject": ("Per-(lang, voice) word-sync quality on the BAR's metric — "
                     "matched_within_drift_pct at 250 ms — with the effect size, its "
                     "uncertainty, and a within-voice noise floor."),
        "_supersedes": ("fixtures.json:19 (Miriam 88.2 / Mario 94.4 / Robert 100). Those are "
                        "agree_within_250ms_pct on a word-vs-SEGMENT comparison "
                        "(out/spike-a-crossengine.json:54), on n=17-18 from one 8-second clip. "
                        "They are not measurements of this metric and are not comparable to "
                        "anything below."),
        "_instrument": ("worker/src/match/matchTokens — THE PRODUCT MATCHER, reached through "
                        "its CLI, not a copy of it — plus the shipped local three-point "
                        "neighbour drift, imported not reimplemented. The matcher moved out of "
                        "measure.py in this round for the reason the normaliser moved before "
                        "it: a matcher that lives only in the instrument means the figure on "
                        "disk describes software nobody runs. --self-test asserts this file "
                        "still reproduces the committed 62.5 / 68.2 / 75.0 exactly across the "
                        "move, and asserts every control breaks under mutation."),
        "_mutation_active": bool(Mutation.displace) or Mutation.drift_bound_ms != DRIFT_MS
                            or Mutation.truncate_obs is not None or Mutation.drop_obs is not None,
        "drift_bound_ms": DRIFT_MS,
        "bar_matched_within_drift_pct": BAR_MATCHED_PCT,
        "long_fixture_sha256": _sha(FR_LONG),
        "long_fixture_display_words": len(M.display_words(FR_LONG)),
        "short_fixture_sha256": _sha(short_fr_text()),
        "voices": VOICES,
        "clips": rows,
        "comparisons": comparisons,
        "verdict": verdict,
        "cross_engine": cross_rows,
        # The KEY keeps its name even though the gap it named is closed, because
        # `tools/doc-check.mjs` refers to this field BY NAME in a comment
        # ("spike-a-voices.json's own `_art_stale_gap` note, not by review") and
        # `tools/` belongs to another agent this round. Renaming it here would
        # close one stale reference by opening another in a file this scope may
        # not edit — the exact seam CLAUDE.md's second sweep exists to catch.
        # Renaming both together is a follow-up, carried in the report.
        "_art_stale_gap": (
            "CLOSED, and this field records what closed it (J30-m5). It used to read that "
            "doc-check's [ART-STALE] leg (iii) resolved a scored row's audio as `${row.lang}"
            ".wav`, which hard-codes ONE clip per language and therefore cannot name a "
            "per-(lang, voice) row — the shape `voice_langs` is keyed by, and the shape the "
            "rows below are in. It carried a REPAIR line naming Forge as owner. That repair "
            "landed in two parts and the note outlived both, which is how a fixed defect goes "
            "on being reported as open: leg (iii) now resolves `const wanted = typeof "
            "row.audio_path === 'string' ? row.audio_path : `${row.lang}.wav`;`, and the "
            "ADMISSION rule that reaches it now accepts this artifact's spellings — "
            "`const LANG_KEYS = ['lang', 'lang_code'];` and `const SECONDS_KEYS = "
            "['audio_seconds', 'clip_seconds'];`. Quoted rather than cited by line, because a "
            "line number is a claim about a file someone else is editing. Every row below is "
            "therefore covered by all three legs: it is in the manifest, it is re-hashed, and "
            "its `clip_seconds` is checked against the manifest's duration for the exact "
            "`audio_path` it names."),
    }
    H.write_json(ARTIFACT, art)
    _print_measure(rows, comparisons, verdict, cross_rows)
    return 0


def _sha_file(p: pathlib.Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _verdict(comparisons, rows) -> dict:
    within = [c for c in comparisons if c["comparison_type"] == "within_voice_replicate"
              and c["kind"] == "long"]
    between = [c for c in comparisons if c["comparison_type"] == "between_voice"
               and c["kind"] == "long"]
    w_abs = [abs(c["diff_pp"]) for c in within]
    b_abs = [abs(c["diff_pp"]) for c in between]
    long_rows = [r for r in rows if r["kind"] == "long" and r["admissible"]]
    dropped = [r["audio_path"] for r in rows if not r["admissible"]]
    disc = [c["discordance_rate"] for c in between if c["discordance_rate"] is not None]
    mean_disc = sum(disc) / len(disc) if disc else 0.0
    n_needed_12 = n_for_mcnemar(12.0, mean_disc) if mean_disc else -1

    # ── J30-M8. THE BOUND MUST CARRY ITS OWN COVERAGE ────────────────────────
    #
    # `max_between_voice_abs_diff_pp` is computed over the pairs that HAPPENED to
    # be comparable, and a reader has no way to see which those were. When one of
    # three voices had zero admissible long clips, the published "<= 1.9 pp"
    # bound covered two voices and was read as covering three — and at the SHORT
    # length the same pair the bound excludes differ by 8.3 pp, 4.4x the bound.
    # A bound is a claim about a set; the set is now emitted beside it.
    covered = sorted({r["voice"] for r in long_rows})
    all_voices = sorted({r["voice"] for r in rows if r["kind"] == "long"})
    uncovered = [v for v in all_voices if v not in covered]
    # TWO different denominators, and conflating them is how "12 of the 3 pairs"
    # gets published. `between` counts CLIP pairs; the coverage claim is about
    # VOICE pairs, and one voice pair contributes up to four clip pairs at two
    # replicates each. Both are emitted, each with its own name.
    voice_pairs_seen = {tuple(sorted((c["a"].split("#")[0], c["b"].split("#")[0])))
                        for c in between}
    voice_pairs_possible = len(covered) * (len(covered) - 1) // 2
    short_between = [c for c in comparisons
                     if c["comparison_type"] == "between_voice" and c["kind"] == "short"]
    short_b_abs = [abs(c["diff_pp"]) for c in short_between]
    max_short = round(max(short_b_abs), 1) if short_b_abs else None
    max_long = round(max(b_abs), 1) if b_abs else None
    max_within = round(max(w_abs), 1) if w_abs else None
    sig_within = sum(1 for c in within if c["significant_at_05"])
    coverage = (
        f"The between-voice bound below is a claim about {len(covered)} of {len(all_voices)} "
        f"voices: {covered or 'none'}. "
        + (f"NOT COVERED: {uncovered} — no admissible long clip, so no long-length "
           f"between-voice difference involving {'them' if len(uncovered) > 1 else 'it'} was "
           f"measured and the bound says nothing about "
           f"{'them' if len(uncovered) > 1 else 'it'}. "
           if uncovered else "Every voice is covered. ")
        + f"It rests on {len(between)} clip pairs spanning {len(voice_pairs_seen)} of the "
          f"{voice_pairs_possible} voice pairs those voices admit. "
        + (f"AND IT IS LENGTH-SPECIFIC: at the SHORT length the largest between-voice "
           f"difference is {max_short} pp against {max_long} pp at the long length"
           f"{f' ({round(max_short / max_long, 1)}x)' if max_long else ''}. The short arm is "
           f"24 display tokens, where one token is 4.2 pp and a bound of this size cannot be "
           f"resolved there at all, so the two are not in contradiction — but a bound quoted "
           f"without its length is quoted without its meaning. "
           if max_short is not None and max_long else "")
        + (f"READ IT AGAINST THE NOISE FLOOR, NOT AGAINST ZERO: the same voice re-sampled "
           f"differs by up to {max_within} pp, and {sig_within} of {len(within)} within-voice "
           f"replicate pairs are themselves significant at .05. A between-voice difference "
           f"smaller than {max_within} pp is not evidence of a voice effect."
           if max_within is not None else ""))
    return {
        "bound_covers_voices": covered,
        "bound_does_not_cover_voices": uncovered,
        "between_voice_clip_pairs": len(between),
        "between_voice_pairs_seen": sorted("+".join(p) for p in voice_pairs_seen),
        "between_voice_pairs_possible": voice_pairs_possible,
        "max_between_voice_abs_diff_pp_short": max_short,
        "_coverage": coverage,
        "within_voice_abs_diff_pp": w_abs,
        "between_voice_abs_diff_pp": b_abs,
        "max_within_voice_abs_diff_pp": round(max(w_abs), 1) if w_abs else None,
        "max_between_voice_abs_diff_pp": round(max(b_abs), 1) if b_abs else None,
        "between_exceeds_within": bool(b_abs and w_abs and max(b_abs) > max(w_abs)),
        "significant_between_voice_pairs": sum(1 for c in between if c["significant_at_05"]),
        "between_voice_pairs": len(between),
        "significant_within_voice_pairs": sum(1 for c in within if c["significant_at_05"]),
        "within_voice_pairs": len(within),
        "mean_between_voice_discordance": round(mean_disc, 4),
        "display_tokens_needed_for_12pp_at_this_discordance": n_needed_12,
        "display_tokens_in_original_claim": 17,
        "inadmissible_clips_matcher_desync": dropped,
        "admissible_long_clips": len(long_rows),
        "any_clip_passes_bar": bool(any(r["passes_matched_bar"] for r in long_rows)),
        "best_long_clip_pct": max((r["matched_within_drift_pct"] for r in long_rows), default=None),
        "_reading": ("A between-voice difference is only evidence of a VOICE effect if it "
                     "exceeds what the same voice produces against itself. Fish s2-pro samples "
                     "at temperature 0.8, so the within-voice replicate pair is the noise "
                     "floor, and it is the control the original claim never ran."),
    }


def _print_measure(rows, comparisons, verdict, cross_rows) -> None:
    print(f"\n  per-(lang, voice) on the BAR's metric  (bar: >= {BAR_MATCHED_PCT}%, "
          f"bound {DRIFT_MS} ms)\n")
    print(f"  {'clip':28} {'n_disp':>6} {'matched':>7} {'pct':>6} {'ci95':>14} "
          f"{'med':>7} {'p95':>8} {'sec':>7}")
    for r in rows:
        lo, hi = r["matched_within_drift_ci95"]
        print(f"  {r['audio_path']:28} {r['display_words']:>6} {r['matched']:>7} "
              f"{r['matched_within_drift_pct']:>6} {f'[{lo}, {hi}]':>14} "
              f"{str(r['median_drift_ms']):>7} {str(r['p95_drift_ms']):>8} "
              f"{r['clip_seconds']:>7}")
    # The ceiling, beside the score it bounds. Printed for every clip because a
    # bound quoted from one clip is a bound quoted without its spread.
    print(f"\n  what NO matcher could beat on these transcripts "
          f"(bar: >= {BAR_MATCHED_PCT}%)\n")
    print(f"  {'clip':28} {'n_disp':>6} {'absent':>7} {'ceiling':>8} {'vs bar':>8} "
          f"{'placed':>7} {'in bound':>9}")
    for r in rows:
        c = r["asr_coverage_ceiling"]
        print(f"  {r['audio_path']:28} {c['display_tokens']:>6} "
              f"{c['display_tokens_absent_from_transcript']:>7} "
              f"{c['coverage_ceiling_pct_any_matcher']:>7}% "
              f"{-c['coverage_ceiling_gap_to_bar_pp']:>+7.1f} "
              f"{r['match_rate_pct']:>6}% {r['matched_within_drift_pct']:>8}%")
    print("  `absent` = display tokens the recogniser emitted in NO form the matcher can "
          "accept.\n  `ceiling` is a STRICT UPPER BOUND (order-free); see `_derivation` "
          "in the artifact.")

    print("\n  pairwise, paired on display index (same text, same tokens)\n")
    print(f"  {'kind':6} {'a':14} {'b':14} {'type':24} {'diff':>6} {'b/c':>9} "
          f"{'p':>9} {'block bootstrap 95%':>22}")
    for c in comparisons:
        blo, bhi = c["diff_ci95_sentence_block_bootstrap_pp"]
        bc = "{}/{}".format(c["discordant_b"], c["discordant_c"])
        boot = "[{}, {}]".format(blo, bhi)
        print(f"  {c['kind']:6} {c['a']:14} {c['b']:14} {c['comparison_type']:24} "
              f"{c['diff_pp']:>6} {bc:>9} {c['mcnemar_exact_p']:>9} {boot:>22}")
    v = verdict
    print(f"\n  within-voice (same voice, new sample) max |diff| = {v['max_within_voice_abs_diff_pp']} pp")
    print(f"  between-voice                        max |diff| = {v['max_between_voice_abs_diff_pp']} pp")
    print(f"  significant between-voice pairs: {v['significant_between_voice_pairs']}/{v['between_voice_pairs']}"
          f"   significant within-voice pairs: {v['significant_within_voice_pairs']}/{v['within_voice_pairs']}")
    print(f"  display tokens required to resolve a 12 pp effect at the observed discordance "
          f"({v['mean_between_voice_discordance']}): {v['display_tokens_needed_for_12pp_at_this_discordance']}"
          f"   — the original claim had {v['display_tokens_in_original_claim']}")
    # The bound is never printed without the set it is a claim about (J30-M8).
    print(f"\n  coverage: {v['_coverage']}")
    if v["inadmissible_clips_matcher_desync"]:
        print(f"  INADMISSIBLE (matcher desync): {v['inadmissible_clips_matcher_desync']}")
    if cross_rows:
        print("\n  the SUBSTITUTED metric on the same audio, computed honestly "
              "(word-level both sides)\n")
        for c in cross_rows:
            print(f"    {c['voice']:12} agree_within_250ms {c['agree_within_250ms_pct']:>6}%  "
                  f"vs bar metric {c['matched_within_drift_pct']:>6}%   gap {c['gap_pp']:+.1f} pp  "
                  f"(n={c['compared_words']})")
    print(f"\nwrote {ARTIFACT}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--probe", action="store_true")
    ap.add_argument("--synth", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--cross-engine", action="store_true",
                    help="also compute agree_within_250ms_pct (base vs small). Slow, free.")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.probe:
        return cmd_probe()
    if a.synth:
        return cmd_synth(a.yes)
    if a.measure:
        return cmd_measure(a.cross_engine)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
