# Bygdebladet Lokalfotball

Ei GitHub Pages-plattform for lokale fotballkampar frå G13/J13 og oppover.

## Språk og design

- Brukargrensesnittet skal vere på nynorsk.
- Hovudbakgrunnen er `#F7F3E9`.
- Tekst direkte på den lyse bakgrunnen skal vere svart eller raud.

## Automatisk dataflyt

Terminlista er grunnlaget for når systemet skal kontrollere nye data. Ein tidsstyrt GitHub Action køyrer kvart femte minutt, men gjer ingen eksterne oppslag når ingen kamp eller periodisk kontroll er moden.

Når ein kamp er venta ferdig, blir den aktuelle turneringa kontrollert. Eitt turneringsoppslag kan dermed oppdatere fleire resultat og den offisielle tabellen samtidig. Lokale kampar kan få eit avgrensa ekstra detaljoppslag når kampdetaljar er tilgjengelege.

- `data/fixture_schedule.csv.gz` – normalisert terminplan.
- `data/engine-state.json` – status, neste kontroll og oppdaga kamp-/turnerings-ID-ar.
- `data/matches.json` – ferdigspelte lokale kampar.
- `data/upcoming.json` – kommande lokale kampar.
- `data/competitions.json` – offisielle tabellar.
- `config/competitions.json` – turneringar og kontrollintervall.
- `config/sources.json` – generelle nettverks- og frekvensinnstillingar.
- `.github/workflows/source-sync.yml` – tidsstyrt synkronisering.
- `data/team-logos.json` – kopling mellom lagnamn og logo.
- `assets/team-logos/` – logofiler.

## Trafikkprinsipp

Systemet er terminbasert og skal halde talet på kjeldeoppslag så lågt som praktisk mogleg. Resultatkontroll blir gruppert per turnering, ferdige kampar blir ikkje kontrollerte på nytt utan grunn, og detaljoppslag har eige budsjett per køyring. Den daglege kontrollen fangar opp flytta kampar og tabellendringar.

Innhentingslaget sender ikkje personnamn, kontaktinformasjon, internt prosjektnamn, repository-namn eller eigendefinerte identifikatorar i HTTP-headerar eller kjeldeloggar.

## Publiseringsreglar

- G13/J13 og eldre, samt senior.
- Samarbeidslag blir tekne med når minst eitt av målklubbnamna inngår.
- Kamp blir ikkje publisert utan registrert sluttresultat.
- Mål, målminutt, spelarbyte, kort, dommar, lagoppstilling og andre detaljar blir berre viste når dei faktisk finst i kjeldedata.
- Manglande detaljar blir ikkje gjetta eller fylte ut.

## Kampvising

Kampdetaljen har tre faner:

- **Rapport** – kampforløp og kampfakta når data finst.
- **Tabell** – offisiell tabell frå den aktuelle turneringa.
- **Lag** – startoppstilling, formasjon og benk når data finst.

## Laglogoar

Berre personar med skrivetilgang til repositoryet kan laste opp eller endre logoar. Logoar blir lagde i `assets/team-logos/` og kopla til lagnamn i `data/team-logos.json`.

## Bildeinnsending

CTA-en for kampbilde peikar til Tally-skjemaet som er kopla til sida.
