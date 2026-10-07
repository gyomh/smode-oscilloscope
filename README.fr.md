# Smode Oscilloscope

*[English version](README.md)*

> **Expérimental, pas un outil officiel Smode.** Construit par essais et erreurs sur l'API Oil (voir [smode-oil-reference](https://github.com/gyomh/smode-oil-reference)). Testé sur Smode Compose R15.

Un Script qui construit une Compo complète d'**oscilloscope CRT à phosphore** : un point lumineux balaie l'écran de
gauche à droite, oscille selon une bande de fréquence audio (par ex. depuis Voicemeeter) et laisse une trace verte
qui s'estompe, avec échos, flou, scintillement et un masque en forme d'écran.

L'écriture de la trace est faite par un second Script (voir [smode-trace-writer](https://github.com/gyomh/smode-trace-writer)),
créé dans la Compo. L'en-tête de `oscilloscope.py` décrit la structure et les pièges rencontrés (masques dont la
taille est recalculée après insertion, drapeaux `linked` des tailles, `CustomEnumeration`, `ParametricScalarFunction`...).

## Installation

1. Glissez `oscilloscope.py` dans votre projet Smode, **Launch Mode = Manual**.
2. Options : `nPoints` (points de la trace), `sweepPeriod` (secondes par balayage), `nEchoes`, `oscLabel`.
3. Exécutez : la Compo *Oscilloscope* est ajoutée à la scène avec ses Parameters (Frequency / Amplitude Min / Max,
   Trace Position Y, scintillement de l'écran).

## Licence

MIT — voir [LICENSE](LICENSE).
