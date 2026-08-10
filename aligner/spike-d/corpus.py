#!/usr/bin/env python3
"""
SPIKE D corpus — the source text every fixture is built from.

PROVENANCE, and why it is not a real paper.
==========================================
Every word below was written for this harness. It is not an excerpt, a
translation, or a paraphrase of any existing work. Phase 0.5 makes committed
fixtures public-domain-only, and the cheapest way to be certainly compliant is
to author the text rather than to argue about the status of something found.
The three passages are placed in the public domain (CC0) by the project.

That choice buys the legal question and costs realism, and the cost is stated in
the artifact `_limits` rather than left for a reader to discover:

  * No hyphenation at line breaks. Real typeset columns hyphenate, and a
    hyphenated word split across a line break is a known extractor failure. It
    is exercised as a MUTATION (`hyphen_split`) but not as a rendered fixture.
  * ASCII apostrophes, not typographic ones. One fewer encoding variable.
  * No formulae, no inline citations, no figures with captions, no footnotes.
    A real two-column paper has all four, and each is its own reading-order
    hazard. This corpus tests COLUMNS and FURNITURE only.

WHY THIS TEXT AND NOT LOREM IPSUM.
=================================
The metric assigns every recognised token to a ground-truth position, and that
assignment must be unambiguous or the order measurement is measuring the
assignment instead. `layout.assert_context_unique` proves uniqueness on the
(fold, +/-2 context) key for every fixture before any engine runs, and it can
only pass on text with real lexical variety. Repetitive filler would fail it.

The three languages are the three in scope (CLAUDE.md audience rubric: en, es,
fr). Spanish and French are here for their diacritics, which are the characters
an OCR engine loses first and which a WinAnsi PDF font encodes differently from
ASCII -- so they test the encoding path as well as the recogniser.

THE TRAP.
========
`en` is built so that the WRONG answer is fluent. Column 1 ends on a complete
sentence and column 2 opens on one, so an extractor that emits column 2 first
produces prose that reads correctly and says something the page does not. That
is the failure this spike exists for: a blind user cannot see the page to notice
it. `out/spike-d-results.json` carries the first 240 characters of the
column-swapped rendering under `_trap_demonstration` so the claim can be
checked by eye rather than taken on faith.

We do NOT claim to MEASURE fluency. That would need a language model and a
calibrated threshold, and neither is in this spike. The trap is demonstrated,
not scored -- see `_limits.fluency_not_measured`.
"""

# Furniture is rendered on the page and is deliberately NOT part of the
# ground-truth reading order. A running head or a page number spoken in the
# middle of a sentence is an accessibility defect, so the harness must be able
# to see it happen; that requires it to be on the page and out of the truth.
FURNITURE = {
    "en": {"head": "Coastal Dynamics Quarterly 14 (3)", "folio": "217"},
    "es": {"head": "Dinamica Costera Trimestral 14 (3)", "folio": "218"},
    "fr": {"head": "Dynamique Cotiere Trimestrielle 14 (3)", "folio": "219"},
}

CORPUS = {
    "en": {
        "title": "Tidal Asymmetry in Shallow Estuarine Basins",
        "col1": [
            "The measurements reported here were collected over nineteen consecutive "
            "spring tides at four stations along the northern shore. Each station "
            "carried a pressure sensor mounted on a steel frame, sampling at "
            "two-second intervals, and a paired turbidity probe fixed one metre above "
            "the bed. Instrument clocks were disciplined nightly against a shore "
            "reference, which bounds the timing uncertainty of any single record to "
            "under forty milliseconds.",
            "Depth series were detided using a harmonic fit over eleven constituents. "
            "The residual, which we call the subtidal component, retains the storm "
            "surge signal and the seasonal steric adjustment. Because the basin is "
            "shallow relative to its length, friction dominates the momentum balance, "
            "and the flood limb of the curve steepens as the wave propagates inland. "
            "That steepening is the asymmetry this paper attempts to quantify, and it "
            "is visible without any filtering at the two inner stations.",
            "Bed shear stress was not measured directly. We estimate it from the "
            "near-bed velocity profile under a logarithmic layer assumption, which "
            "holds for roughly eighty percent of the record and fails during the brief "
            "slack water intervals. Those intervals are excluded rather than "
            "interpolated, and the exclusion is marked in every figure so a reader can "
            "see where the estimate stops.",
            "A referee asked whether the frame itself perturbs the flow. Scour marks "
            "around three of the four frames suggest that it does, at least locally. We "
            "repeated the innermost deployment with a smaller frame for a single "
            "fortnight and found the asymmetry index unchanged to within the scatter of "
            "that shorter record, which is weak evidence but the only evidence "
            "available.",
        ],
        "col2": [
            "Turbidity responded to the flood limb far more sharply than to the ebb. At "
            "the innermost station the suspended load during a rising tide exceeded the "
            "falling load by a factor of three, and the ratio grew with the tidal range. "
            "We interpret this as evidence that resuspension is controlled by the peak "
            "bed shear stress rather than by the integrated energy of the cycle.",
            "Two caveats bound the conclusion. First, the turbidity probes saturate "
            "above roughly nine hundred formazin units, and saturation occurred on six "
            "occasions, all during the largest spring tides. Second, the northern shore "
            "receives a freshwater discharge whose gauge failed for eleven days in "
            "March. Neither gap falls inside the windows used for the regression, but "
            "both restrict how far the result may be extended toward the head of the "
            "estuary.",
            "The comparison with the older survey deserves care. That campaign sampled "
            "hourly rather than continuously, and an hourly sample cannot resolve the "
            "peak of a flood limb lasting under ninety minutes. Where the two datasets "
            "overlap, the older one underestimates that peak by between twelve and "
            "thirty percent, and the discrepancy is largest exactly where the asymmetry "
            "is largest.",
            "What follows for management is modest. If resuspension tracks peak stress, "
            "then dredging schedules built around mean energy will misallocate effort "
            "toward the calmer half of the cycle. We do not propose a revised schedule "
            "here; the basin geometry varies too much between reaches for any single "
            "rule, and four stations cannot support one.",
        ],
        "sidebar": [
            "Box 1. Station S4 was relocated twice during the campaign. The coordinates "
            "printed in Table 2 refer to the final position only, and earlier deployments "
            "must be read against the field log.",
        ],
    },
    "es": {
        "title": "Asimetria de marea en cuencas estuarinas someras",
        "col1": [
            "Las mediciones que se presentan fueron recogidas durante diecinueve mareas "
            "vivas consecutivas en cuatro estaciones de la orilla norte. Cada estacion "
            "disponia de un sensor de presion montado sobre un bastidor de acero, con un "
            "muestreo cada dos segundos, y de una sonda de turbidez situada un metro por "
            "encima del fondo. Los relojes de los instrumentos se ajustaban cada noche "
            "contra una referencia en tierra, lo que acota la incertidumbre temporal de "
            "cualquier registro individual por debajo de cuarenta milisegundos.",
            "Las series de profundidad se filtraron mediante un ajuste armonico de once "
            "componentes. El residuo, que denominamos componente submareal, conserva la "
            "senal de la marea meteorologica y el ajuste esterico estacional. Como la "
            "cuenca es somera respecto a su longitud, la friccion domina el balance de "
            "cantidad de movimiento y la rama de flujo se empina conforme la onda avanza "
            "hacia el interior.",
            "El esfuerzo cortante en el fondo no se midio directamente. Lo estimamos a "
            "partir del perfil de velocidad cercano al lecho suponiendo una capa "
            "logaritmica, hipotesis que se sostiene en cerca del ochenta por ciento del "
            "registro y falla durante los breves intervalos de repunte. Esos intervalos "
            "se excluyen en lugar de interpolarse, y la exclusion aparece marcada en "
            "cada figura.",
            "Un revisor pregunto si el propio bastidor perturba la corriente. Las marcas "
            "de socavacion alrededor de tres de los cuatro bastidores sugieren que si, "
            "al menos localmente. Repetimos el fondeo mas interior con un bastidor menor "
            "durante una quincena y hallamos el indice de asimetria sin cambios dentro "
            "de la dispersion de aquel registro breve.",
        ],
        "col2": [
            "La turbidez respondio a la rama de flujo con mucha mas intensidad que al "
            "reflujo. En la estacion mas interior, la carga en suspension durante una "
            "marea ascendente supero en un factor de tres a la registrada durante el "
            "descenso, y el cociente aumento con la amplitud.",
            "Dos salvedades limitan la conclusion. Primero, las sondas de turbidez se "
            "saturan por encima de unas novecientas unidades de formacina, y la "
            "saturacion ocurrio en seis ocasiones. Segundo, la orilla norte recibe una "
            "descarga de agua dulce cuyo aforo fallo durante once dias de marzo. Ninguna "
            "laguna cae dentro de las ventanas empleadas en la regresion, pero ambas "
            "restringen hasta donde puede extenderse el resultado.",
            "La comparacion con el sondeo anterior exige cautela. Aquella campana "
            "muestreaba cada hora y no de forma continua, y un muestreo horario no "
            "resuelve el pico de una rama ascendente que dura menos de noventa minutos. "
            "Donde ambos conjuntos se solapan, el antiguo subestima ese pico entre un "
            "doce y un treinta por ciento.",
            "Las consecuencias para la gestion son modestas. Si la resuspension sigue al "
            "esfuerzo maximo, los calendarios de dragado construidos sobre la energia "
            "media destinaran trabajo a la mitad mas tranquila del ciclo. No proponemos "
            "aqui un calendario revisado, porque la geometria de la cuenca varia "
            "demasiado entre tramos.",
        ],
        "sidebar": [
            "Recuadro 1. La estacion S4 se traslado dos veces durante la campana. Las "
            "coordenadas impresas en la tabla 2 corresponden unicamente a la posicion "
            "final.",
        ],
    },
    "fr": {
        "title": "Asymetrie de maree dans les bassins estuariens peu profonds",
        "col1": [
            "Les mesures presentees ici ont ete recueillies pendant dix-neuf marees de "
            "vive-eau consecutives, a quatre stations reparties le long de la rive nord. "
            "Chaque station comportait un capteur de pression fixe sur un cadre d'acier, "
            "echantillonnant toutes les deux secondes, ainsi qu'une sonde de turbidite "
            "placee un metre au-dessus du fond. Les horloges des instruments etaient "
            "recalees chaque nuit sur une reference a terre, ce qui borne l'incertitude "
            "temporelle de tout enregistrement isole a moins de quarante millisecondes.",
            "Les series de profondeur ont ete filtrees par un ajustement harmonique "
            "portant sur onze constituants. Le residu, que nous appelons composante "
            "infratidale, conserve la surcote de tempete et l'ajustement sterique "
            "saisonnier. Comme le bassin est peu profond au regard de sa longueur, le "
            "frottement domine le bilan de quantite de mouvement.",
            "La contrainte de cisaillement au fond n'a pas ete mesuree directement. Nous "
            "l'estimons a partir du profil de vitesse pres du lit en supposant une "
            "couche logarithmique, hypothese valable sur environ quatre-vingts pour cent "
            "de l'enregistrement et mise en defaut pendant les courts intervalles "
            "d'etale. Ces intervalles sont exclus plutot qu'interpoles.",
            "Un rapporteur a demande si le cadre lui-meme perturbe l'ecoulement. Les "
            "marques d'affouillement autour de trois des quatre cadres suggerent que "
            "oui, au moins localement. Nous avons repete le mouillage le plus interne "
            "avec un cadre plus petit pendant une quinzaine et trouve l'indice "
            "d'asymetrie inchange.",
        ],
        "col2": [
            "La turbidite a reagi beaucoup plus vivement au flot qu'au jusant. A la "
            "station la plus interne, la charge en suspension pendant une maree montante "
            "depassait d'un facteur trois celle mesuree a la descente, et le rapport "
            "croissait avec le marnage.",
            "Deux reserves limitent la conclusion. D'abord, les sondes de turbidite "
            "saturent au-dela d'environ neuf cents unites de formazine, et la saturation "
            "s'est produite a six reprises. Ensuite, la rive nord recoit un apport d'eau "
            "douce dont la station de jaugeage est tombee en panne pendant onze jours de "
            "mars. Aucune de ces lacunes ne tombe dans les fenetres utilisees pour la "
            "regression.",
            "La comparaison avec le leve precedent demande de la prudence. Cette "
            "campagne echantillonnait toutes les heures et non en continu, et un "
            "echantillonnage horaire ne resout pas le sommet d'une branche de flot qui "
            "dure moins de quatre-vingt-dix minutes. La ou les deux jeux se recouvrent, "
            "l'ancien sous-estime ce sommet.",
            "Les consequences pour la gestion restent modestes. Si la remise en "
            "suspension suit la contrainte maximale, les calendriers de dragage fondes "
            "sur l'energie moyenne affecteront le travail a la moitie la plus calme du "
            "cycle. Nous ne proposons pas ici de calendrier revise.",
        ],
        "sidebar": [
            "Encadre 1. La station S4 a ete deplacee deux fois pendant la campagne. Les "
            "coordonnees imprimees dans le tableau 2 renvoient uniquement a la position "
            "finale.",
        ],
    },
}

# ---------------------------------------------------------------------------
# ACCENTED VARIANTS.
#
# The bodies above are deliberately UNACCENTED so that the reading-order result
# is never confounded with an encoding failure -- if `turbidite` comes back as
# `turbidit`, that is a recogniser problem and it would silently depress the
# order score by removing a token from the assignment.
#
# Diacritics are therefore tested SEPARATELY and explicitly, as a short accented
# strip rendered on every es/fr page. `accent_recall` is reported as its own
# number and is NOT mixed into `token_recall`. Confounding the two is how a
# spike concludes "the engine cannot read columns" when what it cannot read is
# an e-acute.
# ---------------------------------------------------------------------------
ACCENT_STRIP = {
    "en": [],
    "es": ["Resumen: la estacion mas proxima registro una anomalia termica",
           "de 0,4 grados; vease la seccion 3.2 y el apendice tecnico."],
    "fr": ["Resume: la station la plus proche a enregistre une anomalie",
           "thermique de 0,4 degre; voir la section 3.2 et l'annexe technique."],
}

# The accented forms of the strip above, applied at render time. Kept as an
# explicit parallel list rather than generated, so the ground truth for the
# accent test is written down rather than derived by the same code that would
# have to be trusted to be right.
ACCENT_STRIP_ACCENTED = {
    "en": [],
    "es": ["Resumen: la estación más próxima registró una anomalía térmica",
           "de 0,4 grados; véase la sección 3.2 y el apéndice técnico."],
    "fr": ["Résumé: la station la plus proche a enregistré une anomalie",
           "thermique de 0,4 degré; voir la section 3.2 et l'annexe technique."],
}

LANGS = ("en", "es", "fr")
