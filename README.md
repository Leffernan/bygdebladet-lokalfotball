# Bygdebladet Lokalfotball

Ei statisk GitHub Pages-plattform for lokale fotballkampar frå G13/J13 og oppover.

## Språk og design

- Brukargrensesnittet skal vere på nynorsk.
- Hovudbakgrunnen er `#F7F3E9`, i tråd med Bygdebladet si nettavis.
- Tekst direkte på den lyse bakgrunnen skal vere svart eller raud.

## Dataflyt

- `data/nff-import.json` – redaksjonelt registrerte kampfakta.
- `scripts/build_matches.py` – validerer og normaliserer kampdata.
- `data/matches.json` – publiseringsfila frontenden les.
- `.github/workflows/build-football-data.yml` – byggjer ny publiseringsfil ved endringar.
- `data/upcoming.json` – kommande kampar til topplinja.
- `data/competitions.json` – komplett divisjonsdata/tabellar når dette er tilgjengeleg.
- `data/team-logos.json` – kopling mellom lagnamn og logo.
- `assets/team-logos/` – sjølve logofilene.

## Kjeldeprinsipp

Fotball.no/NFF er hovudkjelde for kampdato og sluttresultat. Deretter prioriterer vi klubbane sine offisielle sider og sosiale medium, truverdige liveresultattenester og redaktørstyrte medium. Vi publiserer aldri oppdikta spelarar, mål, minutt, kort, skadar, sjansar, kampbilde eller sitat. Dersom berre resultatet er sikkert, blir presentasjonen kort og nøktern.

Repoet inneheld ikkje automatisk scraping av fotball.no.

## Publiseringsreglar

- G13/J13 og eldre, samt senior.
- Samarbeidslag blir tekne med når minst eitt av dei definerte klubbnamna inngår.
- Kamp blir ikkje publisert utan registrert sluttresultat.
- Kampnummer og kjeldeadresse skal vere registrerte.
- Alder skal vere kjend; systemet gjettar ikkje aldersklasse.
- Mål, målminutt, spelarbyte, kort, dommar, lagoppstilling og andre detaljar blir berre viste når dei faktisk er registrerte.

## Kampvising

Kampdetaljen har tre faner:

- **Rapport** – kampforløp, kampfakta, bane, dommar, kort, byte og mål når dette finst.
- **Tabell** – kan rekne ut K–V–U–T, mål og poeng dynamisk når `data/competitions.json` inneheld eit komplett kampdatasett for divisjonen. Vi viser ikkje ein ufullstendig tabell som om han var korrekt.
- **Lag** – startoppstilling, formasjon og benk når data finst.

## Laglogoar

Berre personar med skrivetilgang til GitHub-repoet kan laste opp eller endre logoar.

1. Last opp PNG, SVG eller WebP i `assets/team-logos/`.
2. Legg filstien inn på rett klubb i `data/team-logos.json`.
3. GitHub Pages publiserer logoen saman med resten av sida.

Besøkande på nettsida har berre lesetilgang og kan ikkje laste opp logoar.

## Målklubbar

Vestnes Varfjell, Tomrefjord, Fiksdal/Rekdal, Ørskog, Stordal, Skodje, Brattvåg, Ravn, Norborg, HaNo, Harøy, Lepsøy og Hildre.

## Bildeinnsending

CTA-en for kampbilde peikar til Tally-skjemaet:

https://tally.so/r/aQRDJ9
