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
code path — `measure.match` for placement and the identical local three-point
neighbour interpolation for drift. Not a reimplementation with the same name:
`--self-test` asserts this file reproduces the committed 62.5 / 68.2 / 75.0 for
`en` / `es` / `fr` EXACTLY, off the committed audio, and fails if it does not.

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

import measure as M          # noqa: E402  the shipped matcher and drift bound
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
    active = False

    @classmethod
    def reset(cls):
        cls.drift_bound_ms = DRIFT_MS
        cls.displace = ()
        cls.truncate_obs = None
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
    if not Mutation.displace:
        return obs
    out = [dict(o) for o in obs]
    for idx, ms in Mutation.displace:
        if 0 <= idx < len(out):
            out[idx]["s"] += ms / 1000.0
            out[idx]["e"] += ms / 1000.0
    return out


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
    matched, unmatched = M.match(obs, disp, lang)

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

    # ── MATCHER DESYNC (the sixth instrument defect in this spike) ────────────
    #
    # `measure.match` is a monotonic greedy loop with a SIX-DISPLAY-TOKEN
    # lookahead. When the recogniser's output diverges from the display text by
    # more than that window — a dropped clause, a run of numerals heard as words,
    # a repetition — the display cursor cannot catch up, and it NEVER RECOVERS.
    # Every remaining observed token is consumed as an unmatched "hallucination"
    # and every remaining display token is left unplaced.
    #
    # Measured, not theorised: `fr-long-narrateur-r1.wav` produced a FULL 1267-
    # token transcript — the same count as the clips that scored 70% — and the
    # matcher stopped dead at display index 545 of 1185. Coverage by decile:
    # [73, 74, 77, 62, 15, 0, 0, 0, 0, 0]. The audio is fine and the recognition
    # is fine; the matcher is not.
    #
    # WHY THIS MATTERS MORE THAN THE NUMBER IT BREAKS. This defect CANNOT OCCUR
    # on an 8-second clip: there is nowhere to desync to. It appears only at the
    # clip lengths the evidence floor requires, which means the floor's own
    # 300 000 ms condition is what exposed it — and it means no measurement taken
    # at the floor can be trusted until the matcher can re-synchronise.
    #
    # The tell was the one this spike has shown every time, inverted: the drift
    # DISTRIBUTION is untouched (medians 46-73 ms across every clip, good and
    # bad alike), and it is the NUMERATOR'S COVERAGE that collapses. A reader
    # comparing medians would have seen nothing wrong.
    #
    # Thirds rather than deciles so the same rule works on a 24-token fixture and
    # an 1186-token one.
    n = len(disp)
    third = max(1, n // 3)
    placed = {m["disp_idx"] for m in matched}
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
            # NOT `lang` + `audio_seconds`. See `_art_stale_gap` in the artifact:
            # doc-check's [ART-STALE] leg (iii) resolves a scored row's audio as
            # `${row.lang}.wav`, which cannot name a per-VOICE clip. Emitting
            # those two key names here would make the gate red for a reason that
            # is not a defect in this measurement, and hide the real gap. The
            # provenance is therefore carried EXPLICITLY, by path and by hash.
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
        "_instrument": ("measure.match + the shipped local three-point neighbour drift, "
                        "imported not reimplemented. --self-test asserts this file reproduces "
                        "the committed 62.5 / 68.2 / 75.0 exactly and asserts every control "
                        "breaks under mutation."),
        "_mutation_active": bool(Mutation.displace) or Mutation.drift_bound_ms != DRIFT_MS,
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
        "_art_stale_gap": (
            "doc-check [ART-STALE] leg (iii) resolves a scored row's audio as `${row.lang}.wav` "
            "(tools/doc-check.mjs:1308). That hard-codes ONE audio file per language. The "
            "roadmap requires the four numbers per (lang, voice) and voice_langs is keyed "
            "(voice_id, lang), so a per-voice row cannot be expressed in the form this guard "
            "reads: emitting `lang` + `audio_seconds` here makes the gate red for correct "
            "rows. Rows below therefore carry `lang_code`, `clip_seconds`, `audio_path` and "
            "`audio_sha256`, and are covered by legs (i) and (ii) — every wav is in the "
            "manifest and re-hashed. Leg (iii) covers nothing here. REPAIR: resolve by an "
            "explicit `audio_path` field when present, falling back to `${lang}.wav`. Owner: "
            "Forge (tools/doc-check.mjs)."),
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
    return {
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
