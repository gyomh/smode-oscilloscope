# Smode Oscilloscope

*[Version française](README.fr.md)*

> **Experimental, not an official Smode tool.** Built by trial and error against the Oil API (see [smode-oil-reference](https://github.com/gyomh/smode-oil-reference)). Tested on Smode Compose R15.

A Script that builds a complete **phosphor CRT oscilloscope** Compo: a bright point sweeps the screen left to right,
moves up and down with an audio frequency band (e.g. from Voicemeeter) and leaves a fading green trace, with echoes,
blur, flicker and a screen-shaped mask.

The writing of the trace is done by a second Script (see [smode-trace-writer](https://github.com/gyomh/smode-trace-writer)),
created inside the Compo. The header of `oscilloscope.py` lists the structure and the gotchas found on the way
(masks resetting their size after insertion, `linked` size flags, `CustomEnumeration`, `ParametricScalarFunction`...).

## Install

1. Drag `oscilloscope.py` into your Smode project, **Launch Mode = Manual**.
2. Options: `nPoints` (trace points), `sweepPeriod` (seconds per sweep), `nEchoes`, `oscLabel`.
3. Execute: the *Oscilloscope* Compo is added to the scene with its Parameters (Frequency / Amplitude Min / Max,
   Trace Position Y, screen flicker).

## License

MIT — see [LICENSE](LICENSE).
