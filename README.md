# Leasing-Scraper — 9-Sitzer, 25.000 km/Jahr

Findet die **günstigsten Leasingangebote** für eine bestimmte Sitzanzahl und
Jahreslaufleistung und sortiert sie nach der **effektiven Monatsrate** —
also inklusive anteiliger Überführungs- und Zulassungskosten.

Standardsuche: **9 Sitze, 25.000 km/Jahr**.

## Tatsächliche Monatskosten

Leasingportale sortieren nach der beworbenen Rate. Das führt in die Irre, weil die
Einmalkosten separat anfallen und im Van-Segment **1.200–2.600 €** erreichen.
Der Scraper lädt darum zu jedem Treffer die Detailseite nach und rechnet:

```
pro Monat = Rate + (Überführung + Zulassung + Zuzahlungen) ÷ Laufzeit
pro Jahr  = pro Monat × 12
```

| Fahrzeug            | Beworben | Einmalkosten | **Pro Monat** | **Pro Jahr** |
|---------------------|---------:|-------------:|--------------:|-------------:|
| Ford Transit        |   356 €  |     2.290 €  |     **394 €** |  **4.734 €** |
| Citroën SpaceTourer |   404 €  |     1.660 €  |     **432 €** |  **5.180 €** |
| Nissan Primastar    |   415 €  |     1.604 €  |     **442 €** |  **5.305 €** |

Die Einmalkosten werden dabei über die **gesamte Laufzeit** verteilt, nicht dem ersten
Jahr zugeschlagen — sonst würden kurze Laufzeiten künstlich teuer aussehen. Wer die
echte Liquiditätsbelastung im ersten Jahr braucht, rechnet
`Rate × 12 + Einmalkosten` (Spalten `monthly_rate` und `transfer_costs` in der CSV).

### Fehlende Angaben

`transferCosts: null` heißt **„nicht angegeben"**, nicht „kostenlos". Solche Angebote
würden mit 0 € gerechnet zu weit oben landen, deshalb:

- sie werden mit `*` markiert und in der CSV über `costs_complete` ausgewiesen,
- ihr Wert ist eine **Untergrenze**, keine Zusage,
- mit `--schaetze-ueberfuehrung` wird stattdessen der Median der übrigen Angebote
  angesetzt (aktuell 1.290 €), um die Rangfolge realistisch zu prüfen.

**Nicht enthalten**, weil in den Inseraten nicht strukturiert vorhanden: Anzahlung/
Sonderzahlung (die geprüften Angebote hatten keine — `leaseTotalAmount` entspricht
Rate × Laufzeit), Versicherung, Wartung, Reifen und Sprit.

## Quelle

**leasingmarkt.de** (AutoScout24-Gruppe, ~46.000 Angebote, größter Leasing-Marktplatz
in Deutschland). Die Suche filtert serverseitig exakt nach dem, was gebraucht wird —
es wird also nicht der halbe Bestand geladen und lokal nachgefiltert:

| Parameter   | Bedeutung          | Verwendung        |
|-------------|--------------------|-------------------|
| `nsf`/`nst` | Sitzanzahl von/bis | `nsf=9&nst=9`     |
| `ym`        | km pro Jahr        | `ym=25000`        |
| `tg`        | Zielgruppe         | `PRIVATE`/`BUSINESS`/`ALL` |
| `mlpt`      | Rate bis           | `--max-rate`      |
| `sort`      | Sortierung         | `rate`            |

Die Daten liegen als JSON im serverseitig gerenderten Next.js-Payload — es wird
kein HTML gescraped und kein Browser benötigt, daher stabil und schnell.

*Hinweis: leasingtime.de wurde geprüft und verworfen — gehört zur selben GmbH
(LeasingMarkt.de GmbH) und liefert weitgehend denselben Bestand.*

## Installation

```bash
cd leasing-scraper && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

## Verwendung

Standardlauf (9-Sitzer, 25.000 km, alle Zielgruppen):

```bash
.venv/bin/python scrape.py
```

Nur was Privatkunden auch wirklich buchen können:

```bash
.venv/bin/python scrape.py --zielgruppe privat
```

Übersichtlich — nur das günstigste Angebot je Modell:

```bash
.venv/bin/python scrape.py --pro-modell 1
```

Schnelldurchlauf ohne Detailseiten (keine Überführungskosten, keine Sitzprüfung):

```bash
.venv/bin/python scrape.py --keine-details
```

### Optionen

| Flag              | Wirkung                                                    |
|-------------------|------------------------------------------------------------|
| `--sitze N`       | Sitzanzahl (Standard 9)                                     |
| `--km N`          | Jahreslaufleistung (Standard 25000)                         |
| `--zielgruppe`    | `privat` \| `gewerbe` \| `alle`                             |
| `--max-rate N`    | Bruttorate nach oben begrenzen                              |
| `--pro-modell N`  | Je Modell höchstens N Angebote anzeigen                     |
| `--schaetze-ueberfuehrung` | Fehlende Überführung mit dem Median ansetzen       |
| `--max-details N` | Detailseiten nur für die N günstigsten laden (spart Zeit)   |
| `--keine-details` | Detailabruf komplett überspringen                           |
| `--top N`         | Zeilen in der Konsolenausgabe                               |
| `--delay S`       | Pause zwischen Requests (Standard 1.0 s)                    |
| `--csv` / `--html`| Ausgabepfade                                                |

## Ausgabe

- **Konsole** — Rangliste nach effektiver Rate
- **`angebote.csv`** — alle 29 Felder, u. a. Netto-/Bruttorate, Leasingfaktor,
  Mehrkilometerkosten, Bank, Händler, Auflagen
- **`angebote.html`** — Report mit Dark-Mode-Unterstützung, verlinkt auf die Inserate

Die CSV enthält immer **alle** Treffer; `--pro-modell` und `--top` betreffen nur
die Anzeige.

## Beim Lesen der Ergebnisse beachten

- **Brutto vs. netto.** Verglichen wird durchgängig die **Bruttorate** (inkl. MwSt.),
  denn nur die ist zielgruppenübergreifend vergleichbar. Händler bewerben
  Gewerbeangebote üblicherweise netto — diese Rate steht in `monthly_net_rate`
  bzw. klein unter der Bruttorate im HTML-Report.
- **Zielgruppe.** `Nur Gewerbekunden` heißt: als Privatperson nicht buchbar. Die
  günstigsten Angebote fallen häufig in diese Kategorie.
- **Auflagen.** Die Spalte `special_conditions` (im Report orange markiert) nennt
  Bedingungen wie *Inzahlungnahme* oder *Schwerbehindertenausweis*. Ohne deren
  Erfüllung gilt der Preis nicht.
- **Laufzeiten vergleichen.** Die Spalte `total_cost` ist die Summe über die volle
  Laufzeit — bei 48 Monaten naturgemäß niedriger als bei 60. Vergleichsmaßstab sind
  die Monatskosten, nicht die Gesamtsumme.
- Angebote und Verfügbarkeiten ändern sich täglich — verbindlich ist der Händler.

## Technik

```
scrape.py                      CLI
leasing/flight.py              Decoder für den Next.js-RSC-Payload
leasing/http.py                Drosselung, Retry mit Backoff (429-fest)
leasing/model.py               Offer-Datenmodell + Effektivkostenrechnung
leasing/report.py              Konsole, CSV, HTML
leasing/sources/leasingmarkt.py  Suche + Detailanreicherung
```

Weitere Portale lassen sich als Modul in `leasing/sources/` mit `search()` und
`enrich()` ergänzen; das Ranking arbeitet quellenübergreifend.

Der Client hält 1 s Abstand zwischen Requests und weicht bei HTTP 429 mit
exponentiellem Backoff aus. Bei `--delay` unter ~0.7 s antwortet leasingmarkt.de
zeitweise mit 429; der Standardwert ist bewusst konservativ.
