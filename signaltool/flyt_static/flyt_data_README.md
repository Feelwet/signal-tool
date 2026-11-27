Flyt-data. noder.json, kanter.json og scenarioer.json skrives av
`python3 -m signaltool.flyt_build` fra CSV (standard: /workspace/flyt-nhy-2711/).

Ikke legg inn oppdiktede tall her. Syntetiske fixtures ligger bare i tests/fixtures/flyt/
og skal aldri publiseres.

publisert på hver kant er false som standard. Byggesteget fra CSV setter aldri true.
True settes bare fra flyt/godkjent.csv (kant-id, lag, dato, kontroll),
via signaltool.flyt_build.apply_godkjent_file.
