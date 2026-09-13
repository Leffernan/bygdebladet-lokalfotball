# Bygdebladet Lokalfotball – prototype

En statisk GitHub Pages-prototype for ferdigspilte lokale fotballkamper fra G13/J13 og oppover.

## Innhold
- `index.html` – side og semantisk struktur
- `styles.css` – visuelt design
- `app.js` – filtrering, kampkort, detaljmodal og statistikk
- `data/matches.json` – datakilden frontend leser

## Viktig
Kampene i `matches.json` er **DEMODATA**. Spiller- og kampdetaljer skal ikke publiseres før de er kontrollert mot autoriserte NFF/FIKS-data.

## Målklubber
Vestnes Varfjell, Tomrefjord, Fiksdal/Rekdal, Ørskog, Stordal, Skodje, Brattvåg, Ravn, Norborg, HaNo, Harøy, Lepsøy og Hildre. Samarbeidslag blir fanget opp når minst ett klubbnavn inngår.

## GitHub Pages
Prosjektet er laget for å kunne publiseres direkte fra `main`-branchen. Aktiver Pages i repository-innstillingene og velg deploy fra branch/root dersom dette ikke allerede er gjort.

## Neste tekniske trinn
1. Skaff godkjent NTB/NFF-datatilgang.
2. Lag `scripts/update_matches.py` som normaliserer data til formatet i `matches.json`.
3. Kjør scriptet tidsstyrt via GitHub Actions.
4. Legg API-nøkler i GitHub Secrets.
5. Koble `photoSubmitUrl` til bildeinnsendingsskjema.
6. Legg inn valideringsregler: ingen kamp uten sluttresultat; registrerte lokale målscorere tas med når de finnes.
