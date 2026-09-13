# Bygdebladet Lokalfotball – prototype

En statisk GitHub Pages-plattform for ferdigspilte lokale fotballkamper fra G13/J13 og oppover.

## Innhold
- `index.html` – side og semantisk struktur
- `styles.css` – visuelt design
- `app.js` – filtrering, kampkort, detaljmodal og statistikk
- `data/matches.json` – datakilden frontend leser
- `config/fotballdata.json` – målklubber, alias og FIKS-klubb-ID-er
- `scripts/update_matches.py` – henter og normaliserer kampdata
- `.github/workflows/update-football-data.yml` – automatisert oppdatering hver time

## Datakilde
Integrasjonen er klargjort for Fotballdata fra Garnes Data AS. Fotballdata opplyser at dataene deres hentes fra NFF/FIKS.

Fotballdata er ikke konfigurert i dette repoet ennå. Tjenesten krever `cid` og `cwd`, og bruksvilkår/pris for Bygdebladets bruk på tvers av flere klubber må avklares med Garnes Data før produksjonssetting.

Når tilgang er på plass, legges følgende inn som GitHub Actions secrets:

- `FOTBALLDATA_CID`
- `FOTBALLDATA_CWD`

Deretter legges offisielle FIKS-klubb-ID-er inn som `clubId` i `config/fotballdata.json`.

## Publiseringsregler
- G13/J13 og eldre.
- Samarbeidslag tas med når minst ett av de definerte klubbnavnene inngår.
- Kamp publiseres aldri uten registrert sluttresultat.
- Alder skal kunne identifiseres; scriptet gjetter ikke aldersklasse.
- Målscorere og hendelser skal bare publiseres når feltene er verifisert mot den faktiske API-responsen.
- Eksisterende data overskrives ikke dersom en API-kjøring gir null publiserbare kamper.

## Målklubber
Vestnes Varfjell, Tomrefjord, Fiksdal/Rekdal, Ørskog, Stordal, Skodje, Brattvåg, Ravn, Norborg, HaNo, Harøy, Lepsøy og Hildre.

## GitHub Pages
Siden publiseres fra `main`. Når GitHub Action finner nye kampdata, committer boten ny `data/matches.json`, og Pages publiserer den oppdaterte versjonen.

## Nåværende status
`data/matches.json` inneholder foreløpig demodata. Produksjonsdata aktiveres først når Fotballdata-tilgang, brukstillatelse og klubb-ID-er er på plass og API-feltene er testet.
