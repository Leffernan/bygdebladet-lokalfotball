# Bygdebladet Lokalfotball – prototype

En statisk GitHub Pages-plattform for ferdigspilte lokale fotballkamper fra G13/J13 og oppover.

## Innhold
- `index.html` – side og semantisk struktur
- `styles.css` – visuelt design
- `app.js` – filtrering, kampkort, detaljmodal og statistikk
- `data/matches.json` – datakilden frontend leser
- `data/nff-import.json` – redaksjonelt registrerte, NFF-verifiserte kampfakta
- `config/nff.json` – målklubber, alias og publiseringsregler
- `scripts/build_matches.py` – validerer og normaliserer kampdata
- `.github/workflows/build-football-data.yml` – bygger og publiserer ved endringer

## Autoritativ kilde
NFF/fotball.no er fasit for kampdato og sluttresultat. Ingen kamp publiseres uten NFF-verifisert sluttresultat.

NFF opplyser at gjenbruk av innhold krever avtale og at automatiserte roboter/spidere ikke er tillatt på fotball.no. Repoet inneholder derfor ikke automatisk scraping av fotball.no. Dersom NFF senere gir tillatelse eller tilgang til en egnet datakilde, kan innhentingen kobles inn foran den eksisterende validerings-/publiseringspipeline uten at frontenden må bygges om.

## Publiseringsregler
- G13/J13 og eldre, samt senior.
- Samarbeidslag tas med når minst ett av de definerte klubbnavnene inngår.
- Kamp publiseres aldri uten registrert sluttresultat.
- Hver kamp må ha FIKS-ID og kilde-URL på fotball.no.
- Alder skal være kjent; systemet gjetter ikke aldersklasse.
- Spillere, mål, målminutt, pauseresultat og øvrige hendelser publiseres bare når de er stadfestet.
- Dersom bare resultatet er sikkert, skal kampen presenteres kort og nøkternt.

## Målklubber
Vestnes Varfjell, Tomrefjord, Fiksdal/Rekdal, Ørskog, Stordal, Skodje, Brattvåg, Ravn, Norborg, HaNo, Harøy, Lepsøy og Hildre.

## GitHub Actions
Når `data/nff-import.json`, NFF-konfigurasjonen eller valideringsscriptet endres, kjører GitHub Actions automatisk `scripts/build_matches.py`.

Scriptet validerer kilden og kampdataene. Dersom alt er gyldig, bygges `data/matches.json` og committes automatisk. GitHub Pages publiserer deretter den nye versjonen.

## Nåværende status
`data/matches.json` inneholder foreløpig demodata. `data/nff-import.json` er tom. Produksjonsdata aktiveres først når vi har en tillatt måte å registrere eller hente NFF-data på.
