"""Ausgabe: Konsolentabelle, CSV und HTML-Report."""

from __future__ import annotations

import csv
import html
from datetime import datetime
from typing import List, Optional

from .model import CSV_FIELDS, USED_CSV_FIELDS, Offer, UsedCar


def _euro(value: Optional[float], digits: int = 0) -> str:
    if value is None:
        return "-"
    text = ("{:,.%df}" % digits).format(value)
    return text.replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"


def sort_offers(offers: List[Offer]) -> List[Offer]:
    """Sortiert nach effektiver Monatsrate; Angebote ohne Rate ans Ende."""
    return sorted(
        offers,
        key=lambda o: (o.effective_monthly is None, o.effective_monthly or float("inf")),
    )


def limit_per_model(offers: List[Offer], per_model: int) -> List[Offer]:
    """Behaelt je Marke+Modell nur die guenstigsten N Angebote.

    Ohne das dominieren identisch bepreiste Inserate desselben Modells von
    verschiedenen Haendlern die Liste.
    """
    if not per_model:
        return offers
    counts: dict = {}
    kept = []
    for offer in sort_offers(offers):
        key = (offer.make.lower(), offer.model.lower())
        if counts.get(key, 0) >= per_model:
            continue
        counts[key] = counts.get(key, 0) + 1
        kept.append(offer)
    return kept


def print_table(offers: List[Offer], limit: int = 20) -> None:
    if not offers:
        print("\nKeine Angebote gefunden.")
        return

    ranked = sort_offers(offers)[:limit]

    print("\n%-3s %-11s %-12s %-9s %-9s %-25s %-4s %-8s %s" % (
        "#", "PRO MONAT", "PRO JAHR", "RATE", "+EINMAL", "FAHRZEUG", "MON", "GRUPPE", "GESAMT"))
    print("-" * 112)

    for index, offer in enumerate(ranked, 1):
        name = ("%s %s" % (offer.make, offer.model)).strip()[:25]
        # Sternchen: Ueberfuehrung nicht angegeben -> Wert ist eine Untergrenze
        marker = "" if offer.costs_complete else "*"
        print("%-3s %-11s %-12s %-9s %-9s %-25s %-4s %-8s %s" % (
            index,
            _euro(offer.effective_monthly) + marker,
            _euro(offer.yearly_cost) + marker,
            _euro(offer.monthly_rate),
            _euro(offer.upfront_costs) if offer.upfront_costs else "k. A." if not offer.costs_complete else "-",
            name,
            offer.duration or "-",
            offer.group_label,
            _euro(offer.total_cost),
        ))

    print("-" * 112)
    print("PRO MONAT = Rate + (Überführung + Zulassung + Zuzahlungen) ÷ Laufzeit.")
    print("PRO JAHR  = PRO MONAT × 12 (Einmalkosten über die Laufzeit verteilt).")
    print("GESAMT    = Kosten über die volle Laufzeit inkl. aller Einmalkosten.")
    incomplete = sum(1 for o in ranked if not o.costs_complete)
    if incomplete:
        print("* Bei %s Angebot(en) nennt der Händler keine Überführungskosten — der Wert" % incomplete)
        print("  ist eine Untergrenze. Mit --schaetze-ueberfuehrung wird der Median angesetzt.")
    print("Alle Raten brutto (inkl. MwSt.); Nettoraten stehen in der CSV.")


def write_used_csv(cars: List[UsedCar], path: str, months: int, residual_pct: float) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=USED_CSV_FIELDS)
        writer.writeheader()
        for car in sorted(cars, key=lambda c: c.price or float("inf")):
            writer.writerow(car.as_row(months, residual_pct))


def write_csv(offers: List[Offer], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for offer in sort_offers(offers):
            writer.writerow(offer.as_row())

# Palette: kuehle, leicht blaustichige Neutrals; Autobahnblau als einziger Akzent;
# Bernstein ausschliesslich fuer fehlende Angaben (semantisch, nicht dekorativ).
_CSS = """
:root{
 --bg:#f4f6f9; --surface:#fff; --surface-2:#eef1f6; --ink:#111820; --muted:#5c6878;
 --line:#dde3ec; --accent:#0b4f9e; --accent-soft:#dbe7f6; --warn:#a86a00;
 --warn-soft:#f7ecd8; --bar-base:#b9c6d8;
}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){
 --bg:#0d1218; --surface:#151d27; --surface-2:#1c2530; --ink:#e6ecf4; --muted:#8d9aab;
 --line:#26313e; --accent:#69a9f5; --accent-soft:#16283f; --warn:#e0a63a;
 --warn-soft:#33280f; --bar-base:#33404f;
}}
:root[data-theme=dark]{
 --bg:#0d1218; --surface:#151d27; --surface-2:#1c2530; --ink:#e6ecf4; --muted:#8d9aab;
 --line:#26313e; --accent:#69a9f5; --accent-soft:#16283f; --warn:#e0a63a;
 --warn-soft:#33280f; --bar-base:#33404f;
}
*{box-sizing:border-box}
body{margin:0;padding:2.4rem 1.2rem 4rem;background:var(--bg);color:var(--ink);
 font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,sans-serif;
 -webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;display:flex;flex-direction:column;gap:1.5rem}
.head{display:flex;flex-direction:column;gap:.35rem}
h1{font-size:clamp(1.5rem,3.2vw,2rem);margin:0;letter-spacing:-.025em;text-wrap:balance}
.sub{color:var(--muted);margin:0;font-size:.92rem;max-width:65ch}
.num{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 font-variant-numeric:tabular-nums;white-space:nowrap}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem}
.stat{background:var(--surface);border:1px solid var(--line);border-radius:12px;
 padding:.85rem 1rem;display:flex;flex-direction:column;gap:.15rem}
.stat b{font-size:1.45rem;letter-spacing:-.02em;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;
 font-variant-numeric:tabular-nums}
.stat span{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.06em}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--surface)}
table{border-collapse:collapse;width:100%;min-width:900px;font-size:.9rem}
thead th{position:sticky;top:0;background:var(--surface-2);text-align:left;
 padding:.65rem .85rem;border-bottom:1px solid var(--line);color:var(--muted);
 font-size:.71rem;text-transform:uppercase;letter-spacing:.06em;white-space:nowrap}
th.r,td.r{text-align:right}
td{padding:.8rem .85rem;border-bottom:1px solid var(--line);vertical-align:top}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover{background:var(--surface-2)}
.rank{color:var(--muted);font-size:.85rem;font-variant-numeric:tabular-nums}
.car{font-weight:600;letter-spacing:-.01em}
.car a{color:inherit;text-decoration:none;border-bottom:1px solid var(--line)}
.car a:hover,.car a:focus-visible{border-bottom-color:var(--accent);color:var(--accent)}
.desc{color:var(--muted);font-size:.79rem;margin-top:.15rem;line-height:1.4}
.big{font-weight:700;font-size:1.02rem;color:var(--accent)}
.sub-rate{color:var(--muted);font-size:.78rem;margin-top:.1rem}
/* Balken: Anteil beworbene Rate vs. Einmalkosten-Aufschlag */
.bar{height:5px;border-radius:3px;background:var(--surface-2);margin-top:.4rem;
 overflow:hidden;display:flex;min-width:90px}
.bar i{display:block;height:100%}
.bar .base{background:var(--bar-base)}
.bar .add{background:var(--accent)}
.tags{display:flex;flex-wrap:wrap;gap:.25rem;margin-top:.4rem}
.tag{font-size:.69rem;padding:.14rem .45rem;border-radius:999px;
 background:var(--surface-2);color:var(--muted);white-space:nowrap}
.tag.warn{background:var(--warn-soft);color:var(--warn);font-weight:600}
.cost{font-size:.79rem;color:var(--muted);line-height:1.5}
.cost b{color:var(--ink);font-weight:600}
/* Umschalter Leasing/Kauf */
.switch{display:inline-flex;gap:.2rem;padding:.25rem;background:var(--surface-2);
 border:1px solid var(--line);border-radius:999px;align-self:flex-start}
.switch button{appearance:none;border:0;background:transparent;color:var(--muted);
 font:inherit;font-size:.88rem;font-weight:600;padding:.45rem 1.15rem;border-radius:999px;
 cursor:pointer;transition:background .15s,color .15s}
.switch button:hover{color:var(--ink)}
.switch button.on{background:var(--surface);color:var(--accent);
 box-shadow:0 1px 2px rgba(0,0,0,.08)}
section{display:flex;flex-direction:column;gap:1.2rem}
section[hidden]{display:none}
.note{color:var(--muted);font-size:.82rem;line-height:1.75;max-width:78ch}
.note b{color:var(--ink)}
.legend{display:flex;flex-wrap:wrap;gap:1.1rem;font-size:.78rem;color:var(--muted);
 align-items:center}
.key{display:inline-flex;align-items:center;gap:.4rem}
.key i{width:14px;height:5px;border-radius:3px;display:block}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

def _bar(value: Optional[float], scale: float, base_share: float = 100.0) -> str:
    """Balken: grauer Teil = Grundkosten, blauer Teil = Aufschlag."""
    if not value or not scale:
        return ""
    width = max(6.0, min(100.0, value / scale * 100.0))
    base = max(0.0, min(100.0, base_share))
    return ('<div class="bar" style="width:%.1f%%">'
            '<i class="base" style="width:%.1f%%"></i>'
            '<i class="add" style="width:%.1f%%"></i></div>'
            % (width, base, 100.0 - base))


def _tags(offer: Offer) -> str:
    tags = []
    if offer.seats:
        tags.append('<span class="tag">%s Sitze</span>' % offer.seats)
    if offer.availability:
        tags.append('<span class="tag">%s</span>' % html.escape(
            offer.availability.replace("Verfügbar: ", "")))
    if not offer.costs_complete:
        tags.append('<span class="tag warn">Überführung k.&nbsp;A.</span>')
    for condition in offer.special_conditions:
        tags.append('<span class="tag warn">%s</span>' % html.escape(condition))
    return "".join(tags)


def _car_cell(offer: Offer) -> str:
    return ('<td><div class="car"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
            '<div class="desc">%s</div><div class="tags">%s</div></td>'
            % (html.escape(offer.url),
               html.escape(("%s %s" % (offer.make, offer.model)).strip()),
               html.escape(offer.headline[:90]),
               _tags(offer)))


def _cost_parts(offer: Offer) -> str:
    parts = []
    if offer.transfer_costs:
        parts.append("Überführung <b>%s</b>" % _euro(offer.transfer_costs))
    if offer.registration_costs:
        parts.append("Zulassung <b>%s</b>" % _euro(offer.registration_costs))
    if offer.extra_costs:
        parts.append("Zuzahlung <b>%s</b>" % _euro(offer.extra_costs))
    if offer.estimated_transfer:
        parts.append("Überführung geschätzt <b>%s</b>" % _euro(offer.estimated_transfer))
    if not parts:
        parts.append("keine Angabe" if not offer.costs_complete else "keine")
    return " · ".join(parts)


def _leasing_rows(ranked: List[Offer]) -> str:
    scale = max((o.effective_monthly or 0) for o in ranked) if ranked else 0
    rows = []
    for index, offer in enumerate(ranked, 1):
        marker = "" if offer.costs_complete else "*"
        net = ""
        if not offer.is_private_only and offer.monthly_net_rate:
            net = " · netto %s" % _euro(offer.monthly_net_rate)
        share = ((offer.monthly_rate or 0) / offer.effective_monthly * 100.0
                 if offer.effective_monthly else 100.0)
        extra = ('<span class="num">+%s/Mon.</span>'
                 % _euro(offer.upfront_costs / offer.duration)
                 if offer.upfront_costs and offer.duration else "")
        rows.append(
            '<tr><td class="rank num">%s</td>%s'
            '<td class="r"><div class="big num">%s%s</div>'
            '<div class="sub-rate num">Rate %s</div>%s</td>'
            '<td class="r num">%s%s</td>'
            '<td class="cost">%s %s</td>'
            '<td class="num">%s Mon.<br><span class="desc">%s</span></td>'
            '<td class="r num">%s</td></tr>'
            % (index, _car_cell(offer),
               _euro(offer.effective_monthly), marker, _euro(offer.monthly_rate),
               _bar(offer.effective_monthly, scale, share),
               _euro(offer.yearly_cost), marker,
               _cost_parts(offer), extra,
               offer.duration or "-",
               html.escape(offer.group_label) + net,
               _euro(offer.total_cost)))
    return "".join(rows)


def _buy_rows(ranked: List[Offer], months: int, residual_pct: float) -> str:
    priced = [o for o in ranked if o.purchase_price]
    priced.sort(key=lambda o: o.purchase_monthly(months, residual_pct) or float("inf"))
    scale = max((o.purchase_monthly(months, residual_pct) or 0) for o in priced) if priced else 0
    rows = []
    for index, offer in enumerate(priced, 1):
        monthly = offer.purchase_monthly(months, residual_pct)
        residual = (offer.purchase_price or 0) * residual_pct
        gap = offer.discount_pct
        saving = ('<div class="desc">%s unter UVP (%s)</div>'
                  % (_euro(offer.discount), ("%.0f %%" % gap) if gap else "-")
                  if offer.discount and offer.discount > 0 else "")
        # Balken: Anteil reiner Wertverlust vs. Einmalkosten
        loss = (offer.purchase_price or 0) - residual
        share = (loss / (loss + offer.upfront_costs) * 100.0
                 if (loss + offer.upfront_costs) else 100.0)
        rows.append(
            '<tr><td class="rank num">%s</td>%s'
            '<td class="r"><div class="big num">%s</div>'
            '<div class="sub-rate num">UVP %s</div>%s</td>'
            '<td class="r num">%s</td>'
            '<td class="r num">%s<div class="desc">Restwert</div></td>'
            '<td class="cost">%s</td>'
            '<td class="r num">%s</td></tr>'
            % (index, _car_cell(offer),
               _euro(offer.purchase_price), _euro(offer.gross_list_price), saving,
               _euro(monthly),
               _euro(residual),
               _cost_parts(offer),
               _euro((offer.purchase_price or 0) + offer.upfront_costs)))
    return "".join(rows)


def _used_rows(cars: List["UsedCar"], months: int, residual_pct: float) -> str:
    ranked = sorted(cars, key=lambda c: c.price or float("inf"))
    scale = max((c.monthly_loss(months, residual_pct) or 0) for c in ranked) if ranked else 0
    rows = []
    for index, car in enumerate(ranked, 1):
        tags = []
        if car.seats:
            tags.append('<span class="tag">%s Sitze</span>' % car.seats)
        if car.fuel:
            tags.append('<span class="tag">%s</span>' % html.escape(car.fuel))
        if car.vat_reclaimable:
            tags.append('<span class="tag">MwSt. ausweisbar</span>')
        if car.country and car.country != "DE":
            tags.append('<span class="tag warn">Import %s</span>' % html.escape(car.country))

        km = ("{:,}".format(car.mileage).replace(",", ".") + " km") if car.mileage is not None else "-"
        age = ("%.0f J." % car.age_years) if car.age_years is not None else "-"
        place = ", ".join(p for p in (car.city, car.country) if p)

        rows.append(
            '<tr><td class="rank num">%s</td>'
            '<td><div class="car"><a href="%s" target="_blank" rel="noopener">%s</a></div>'
            '<div class="desc">%s</div><div class="tags">%s</div></td>'
            '<td class="r"><div class="big num">%s</div>%s</td>'
            '<td class="r num">%s</td>'
            '<td class="r num">%s<div class="desc">EZ %s · %s</div></td>'
            '<td class="num">%s PS</td>'
            '<td class="desc">%s</td></tr>'
            % (index,
               html.escape(car.url),
               html.escape(("%s %s" % (car.make, car.model)).strip()),
               html.escape(car.title[:90]),
               "".join(tags),
               _euro(car.price),
               _bar(car.monthly_loss(months, residual_pct), scale, 100.0),
               _euro(car.monthly_loss(months, residual_pct)),
               km, html.escape(car.first_registration or "-"), age,
               car.hp or "-",
               html.escape(place) or "-"))
    return "".join(rows)


def write_html(offers: List[Offer], path: str, title: str, subtitle: str,
               hold_months: int = 60, residual_pct: float = 0.40,
               used_cars: Optional[List["UsedCar"]] = None) -> None:
    ranked = sort_offers(offers)
    cheapest = ranked[0].effective_monthly if ranked else None
    private_ok = sum(1 for o in ranked if o.available_to_private)
    incomplete = sum(1 for o in ranked if not o.costs_complete)

    priced = [o for o in ranked if o.purchase_price]
    buy_cheapest = min((o.purchase_monthly(hold_months, residual_pct) or float("inf"))
                       for o in priced) if priced else None
    buy_price_min = min((o.purchase_price or 0) for o in priced) if priced else None

    used = list(used_cars or [])
    used_price_min = min((c.price or 0) for c in used) if used else None
    used_loss_min = (min((c.monthly_loss(hold_months, residual_pct) or float("inf"))
                         for c in used) if used else None)
    if used_loss_min == float("inf"):
        used_loss_min = None
    seats_label = str(used[0].seats) if used and used[0].seats else "9"
    used_models = len({(c.make, c.model) for c in used})

    footnote = ""
    if incomplete:
        footnote = (
            '<br><b>*</b> Bei %s Angebot%s nennt der Händler <b>keine</b> '
            'Überführungskosten. Der Wert ist dann eine <b>Untergrenze</b>, keine Zusage — '
            'im Van-Segment liegen die Kosten sonst bei 1.200–2.600&nbsp;€. Nachfragen lohnt.'
            % (incomplete, "" if incomplete == 1 else "en"))

    document = """<title>%s</title>
<style>%s</style>
<div class="wrap">
<div class="head">
  <h1>%s</h1>
  <p class="sub">%s</p>
</div>

<div class="switch" role="tablist" aria-label="Leasing oder Kauf">
  <button role="tab" id="tab-lease" aria-controls="panel-lease" aria-selected="true"
   class="on" data-panel="lease">Leasing</button>
  <button role="tab" id="tab-used" aria-controls="panel-used" aria-selected="false"
   data-panel="used">Gebraucht kaufen</button>
  <button role="tab" id="tab-buy" aria-controls="panel-buy" aria-selected="false"
   data-panel="buy">Neu kaufen</button>
</div>

<section id="panel-lease" role="tabpanel" aria-labelledby="tab-lease">
<div class="stats">
  <div class="stat"><b>%s</b><span>Angebote</span></div>
  <div class="stat"><b>%s</b><span>ab / Monat</span></div>
  <div class="stat"><b>%s</b><span>ab / Jahr</span></div>
  <div class="stat"><b>%s</b><span>für Privat buchbar</span></div>
</div>
<div class="legend">
  <span class="key"><i style="background:var(--bar-base)"></i> beworbene Rate</span>
  <span class="key"><i style="background:var(--accent)"></i> Aufschlag durch Einmalkosten</span>
  <span>Balkenlänge = tatsächliche Monatskosten im Vergleich</span>
</div>
<div class="scroll"><table>
<thead><tr><th>#</th><th>Fahrzeug</th><th class="r">Pro Monat</th><th class="r">Pro Jahr</th>
<th>Einmalkosten</th><th>Vertrag</th><th class="r">Gesamt</th></tr></thead>
<tbody>%s</tbody></table></div>
<p class="note">
<b>Pro Monat</b> = beworbene Rate + (Überführung + Zulassung + Zuzahlungen) ÷ Laufzeit.
Nur so sind Angebote mit niedriger Rate und hoher Einmalzahlung fair vergleichbar.
<b>Pro Jahr</b> = Pro Monat × 12; die Einmalkosten sind über die gesamte Laufzeit
verteilt, nicht dem ersten Jahr zugeschlagen. <b>Gesamt</b> ist die Summe über die volle
Laufzeit — bei 48 Monaten naturgemäß niedriger als bei 60, Vergleichsmaßstab sind
deshalb die Monatskosten.%s<br>
Alle Raten <b>brutto inkl. MwSt.</b>; Gewerbeangebote werden meist netto beworben, die
Nettorate steht daneben. <b>Nur Gewerbekunden</b> heißt: als Privatperson nicht buchbar.
Bernstein markierte Angaben sind <b>Auflagen</b> (z.&nbsp;B. Inzahlungnahme).
Nicht enthalten sind Versicherung, Wartung, Reifen und Sprit.
</p>
</section>

<section id="panel-used" role="tabpanel" aria-labelledby="tab-used" hidden>
<div class="stats">
  <div class="stat"><b>%s</b><span>Gebrauchte %s-Sitzer</span></div>
  <div class="stat"><b>%s</b><span>ab Kaufpreis</span></div>
  <div class="stat"><b>%s</b><span>ab Wertverlust / Monat</span></div>
  <div class="stat"><b>%s</b><span>davon in Deutschland</span></div>
</div>
<div class="legend">
  <span class="key"><i style="background:var(--bar-base)"></i> Wertverlust pro Monat</span>
  <span>sortiert nach Kaufpreis · Quelle carvago.com</span>
</div>
<div class="scroll"><table>
<thead><tr><th>#</th><th>Fahrzeug</th><th class="r">Kaufpreis</th>
<th class="r">Wertverlust/Mon.</th><th class="r">Laufleistung</th>
<th>Leistung</th><th>Standort</th></tr></thead>
<tbody>%s</tbody></table></div>
<p class="note">
<b>Echte Gebrauchtwagen</b> von carvago.com, einem europaweiten Marktplatz.
Die Sitzanzahl ist je Fahrzeug hinterlegt und wurde auf exakt %s geprüft.<br>
<b>Wichtige Einschränkung:</b> Carvagos Modellseiten geben pro Modell nur die
<b>ersten 20 Fahrzeuge</b> heraus und nehmen keine Filter- oder Seitenparameter an.
Das hier ist deshalb eine <b>Stichprobe über %s Van-Modelle</b>, keine vollständige
Marktübersicht — es gibt mit Sicherheit günstigere Angebote, die diese Liste nicht zeigt.
Sie taugt zur Orientierung über Preisniveau und Fahrzeugalter, nicht als Beweis für
das beste Angebot.<br>
Fahrzeuge außerhalb Deutschlands sind als <b>Import</b> markiert: dort kommen
Überführung, Zulassung und ggf. Umsatzsteuerfragen hinzu. <b>MwSt. ausweisbar</b>
ist für Gewerbetreibende relevant. Der Wertverlust nutzt dieselbe Annahme wie die
anderen Ansichten (%s&nbsp;%% Restwert nach %s Monaten) — bei einem gebrauchten
Fahrzeug ist das besonders grob, weil der stärkste Wertverlust bereits hinter ihm liegt.
</p>
</section>

<section id="panel-buy" role="tabpanel" aria-labelledby="tab-buy" hidden>
<div class="stats">
  <div class="stat"><b>%s</b><span>mit Kaufpreis</span></div>
  <div class="stat"><b>%s</b><span>ab Kaufpreis</span></div>
  <div class="stat"><b>%s</b><span>ab Wertverlust / Monat</span></div>
  <div class="stat"><b>%s Mon.</b><span>angenommene Haltedauer</span></div>
</div>
<div class="legend">
  <span class="key"><i style="background:var(--bar-base)"></i> Wertverlust</span>
  <span class="key"><i style="background:var(--accent)"></i> Einmalkosten</span>
  <span>Restwert angenommen mit %s&nbsp;%% des Kaufpreises nach %s Monaten</span>
</div>
<div class="scroll"><table>
<thead><tr><th>#</th><th>Fahrzeug</th><th class="r">Kaufpreis</th>
<th class="r">Wertverlust/Mon.</th><th class="r">Restwert</th>
<th>Einmalkosten</th><th class="r">Gesamt sofort</th></tr></thead>
<tbody>%s</tbody></table></div>
<p class="note">
<b>Woher die Kaufpreise stammen:</b> dieselben Inserate. Händler nennen zu jedem
Leasingangebot den Brutto-Kaufpreis desselben Fahrzeugs — es sind also
<b>Neu- und Lagerwagen</b>, keine Gebrauchtwagenangebote.<br>
<b>Wertverlust/Mon.</b> = (Kaufpreis + Einmalkosten − erwarteter Restwert) ÷ Haltedauer.
Das ist die Größe, die dem Leasingaufwand gegenübersteht. <b>Nicht</b> enthalten sind
Finanzierungszinsen und die Kapitalbindung — wer bar kauft, bindet den vollen Betrag.
<b>Gesamt sofort</b> ist der Betrag, der bei Übergabe fällig wird.<br>
Der <b>Restwert ist eine Annahme</b>, keine Prognose: %s&nbsp;%% nach %s Monaten. Der
tatsächliche Wiederverkaufswert hängt an Laufleistung, Zustand und Marktlage. Bei
25.000&nbsp;km/Jahr — also %s&nbsp;km über die Haltedauer — liegt er eher am unteren Rand.
</p>
</section>
</div>
<script>
(function(){
  var tabs=[].slice.call(document.querySelectorAll('.switch button'));
  function show(name){
    tabs.forEach(function(t){
      var on=t.dataset.panel===name;
      t.classList.toggle('on',on);
      t.setAttribute('aria-selected',on?'true':'false');
    });
    tabs.forEach(function(t){
      var p=document.getElementById('panel-'+t.dataset.panel);
      if(p)p.hidden=(t.dataset.panel!==name);
    });
    try{location.hash=name}catch(e){}
  }
  tabs.forEach(function(t){t.addEventListener('click',function(){show(t.dataset.panel)})});
  var h=(location.hash||'').replace('#','');
  if(h==='buy'||h==='used')show(h);
})();
</script>""" % (
        html.escape(title), _CSS, html.escape(title), html.escape(subtitle),
        len(ranked), _euro(cheapest),
        _euro(cheapest * 12 if cheapest is not None else None), private_ok,
        _leasing_rows(ranked) or '<tr><td colspan="7">Keine Angebote gefunden.</td></tr>',
        footnote,
        # --- Gebrauchtwagen ---
        len(used), seats_label,
        _euro(used_price_min), _euro(used_loss_min),
        sum(1 for c in used if c.country == "DE"),
        _used_rows(used, hold_months, residual_pct)
        or '<tr><td colspan="7">Keine Gebrauchtwagen gefunden.</td></tr>',
        seats_label, used_models,
        "%.0f" % (residual_pct * 100), hold_months,
        # --- Neuwagen ---
        len(priced), _euro(buy_price_min),
        _euro(buy_cheapest if buy_cheapest not in (None, float("inf")) else None),
        hold_months,
        "%.0f" % (residual_pct * 100), hold_months,
        _buy_rows(ranked, hold_months, residual_pct)
        or '<tr><td colspan="7">Keine Kaufpreise verfügbar.</td></tr>',
        "%.0f" % (residual_pct * 100), hold_months,
        "{:,}".format(int(hold_months / 12 * 25000)).replace(",", "."),
    )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(document)


def timestamp() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")
