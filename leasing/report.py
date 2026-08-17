"""Ausgabe: Konsolentabelle, CSV und HTML-Report."""

from __future__ import annotations

import csv
import html
from datetime import datetime
from typing import List, Optional

from .model import CSV_FIELDS, Offer


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


def write_csv(offers: List[Offer], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for offer in sort_offers(offers):
            writer.writerow(offer.as_row())


_CSS = """
:root{--bg:#fbfbfa;--fg:#1a1a18;--muted:#6b6b66;--line:#e3e3df;--card:#fff;--accent:#1b6b4c;--warn:#8a5a12}
:root:not([data-theme=light]) {}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161614;--fg:#ededea;--muted:#9c9c95;--line:#2e2e2a;--card:#1e1e1b;--accent:#63c79c;--warn:#d8a441}}
:root[data-theme=dark]{--bg:#161614;--fg:#ededea;--muted:#9c9c95;--line:#2e2e2a;--card:#1e1e1b;--accent:#63c79c;--warn:#d8a441}
*{box-sizing:border-box}
body{margin:0;padding:2.2rem 1.2rem 4rem;background:var(--bg);color:var(--fg);
 font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1120px;margin:0 auto}
h1{font-size:1.7rem;margin:0 0 .3rem;letter-spacing:-.02em}
.sub{color:var(--muted);margin:0 0 1.6rem;font-size:.95rem}
.stats{display:flex;flex-wrap:wrap;gap:.7rem;margin-bottom:1.6rem}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.7rem 1rem;min-width:130px}
.stat b{display:block;font-size:1.3rem;letter-spacing:-.02em}
.stat span{color:var(--muted);font-size:.78rem;text-transform:uppercase;letter-spacing:.05em}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--card)}
table{border-collapse:collapse;width:100%;min-width:860px;font-size:.9rem}
th{text-align:left;padding:.7rem .8rem;border-bottom:1px solid var(--line);
 color:var(--muted);font-size:.74rem;text-transform:uppercase;letter-spacing:.05em;white-space:nowrap}
td{padding:.7rem .8rem;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
.eff{font-weight:700;color:var(--accent);white-space:nowrap}
.rate{color:var(--muted);font-size:.82rem;white-space:nowrap}
.car{font-weight:600}
.meta{color:var(--muted);font-size:.8rem}
.tag{display:inline-block;font-size:.7rem;padding:.12rem .45rem;border-radius:5px;
 border:1px solid var(--line);color:var(--muted);margin-right:.25rem;white-space:nowrap}
.tag.warn{color:var(--warn);border-color:var(--warn)}
a{color:inherit}
.note{margin-top:1.5rem;color:var(--muted);font-size:.83rem;line-height:1.7}
"""


def write_html(offers: List[Offer], path: str, title: str, subtitle: str) -> None:
    ranked = sort_offers(offers)
    cheapest = ranked[0].effective_monthly if ranked else None
    private_ok = sum(1 for o in ranked if o.available_to_private)

    rows = []
    for index, offer in enumerate(ranked, 1):
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

        name = html.escape(("%s %s" % (offer.make, offer.model)).strip())
        link = '<a href="%s" target="_blank" rel="noopener">%s</a>' % (
            html.escape(offer.url), name)
        group = "Privat & Gewerbe" if offer.group_label == "beide" else offer.group_label

        net = ""
        if not offer.is_private_only and offer.monthly_net_rate:
            net = "<br><span class=\"rate\">netto %s</span>" % _euro(offer.monthly_net_rate)

        # Einmalkosten aufschluesseln, damit die Herkunft des Aufschlags sichtbar ist
        parts = []
        if offer.transfer_costs:
            parts.append("Überführung %s" % _euro(offer.transfer_costs))
        if offer.registration_costs:
            parts.append("Zulassung %s" % _euro(offer.registration_costs))
        if offer.extra_costs:
            parts.append("Zuzahlung %s" % _euro(offer.extra_costs))
        if offer.estimated_transfer:
            parts.append("Überführung geschätzt %s" % _euro(offer.estimated_transfer))
        if not parts:
            parts.append("keine Angabe" if not offer.costs_complete else "keine")
        breakdown = "<br>".join(parts)

        surcharge = ""
        if offer.upfront_costs and offer.duration:
            surcharge = '<div class="meta">+%s/Mon.</div>' % _euro(
                offer.upfront_costs / offer.duration)

        rows.append(
            "<tr><td>%s</td>"
            '<td class="eff">%s%s</td>'
            '<td class="eff">%s%s</td>'
            '<td class="rate">%s%s</td>'
            "<td><div class=\"car\">%s</div><div class=\"meta\">%s</div>%s</td>"
            '<td class="meta">%s Mon.<br>%s km/J.</td>'
            '<td class="meta">%s</td>'
            '<td class="meta">%s%s</td>'
            '<td class="meta">%s</td></tr>'
            % (
                index,
                _euro(offer.effective_monthly),
                "" if offer.costs_complete else "*",
                _euro(offer.yearly_cost),
                "" if offer.costs_complete else "*",
                _euro(offer.monthly_rate),
                net,
                link,
                html.escape(offer.headline[:80]),
                " ".join(tags),
                offer.duration or "-",
                "{:,}".format(offer.included_mileage).replace(",", ".") if offer.included_mileage else "-",
                group,
                breakdown,
                surcharge,
                _euro(offer.total_cost),
            )
        )

    document = """<title>%s</title>
<style>%s</style>
<div class="wrap">
<h1>%s</h1>
<p class="sub">%s</p>
<div class="stats">
  <div class="stat"><b>%s</b><span>Angebote</span></div>
  <div class="stat"><b>%s</b><span>günstigste pro Monat</span></div>
  <div class="stat"><b>%s</b><span>günstigste pro Jahr</span></div>
  <div class="stat"><b>%s</b><span>für Privat buchbar</span></div>
</div>
<div class="scroll"><table>
<thead><tr><th>#</th><th>Pro Monat</th><th>Pro Jahr</th><th>Beworbene Rate</th><th>Fahrzeug</th>
<th>Laufzeit</th><th>Zielgruppe</th><th>Einmalkosten</th><th>Gesamt</th></tr></thead>
<tbody>%s</tbody></table></div>
<p class="note">
<b>Pro Monat</b> = beworbene Rate + (Überführung + Zulassung + Zuzahlungen)
÷ Laufzeit. Nur so sind Angebote mit niedriger Rate und hoher Einmalzahlung fair
vergleichbar. <b>Pro Jahr</b> = Pro Monat × 12; die Einmalkosten sind dabei über die
gesamte Laufzeit verteilt, nicht dem ersten Jahr zugeschlagen. <b>Gesamt</b> ist die
Summe über die volle Laufzeit.<br>
<b>*</b> = der Händler nennt <b>keine</b> Überführungskosten. Der Wert ist dann eine
<b>Untergrenze</b>, keine Zusage — im Van-Segment liegen die Kosten sonst bei
1.200–2.100&nbsp;€. Nachfragen lohnt sich.<br>
Alle Raten <b>brutto inkl. MwSt.</b> Gewerbeangebote werden von den Händlern meist netto
beworben — die Nettorate steht darunter.<br>
Orange markierte Tags sind <b>Auflagen</b> (z.&nbsp;B. Inzahlungnahme oder
Schwerbehindertenausweis erforderlich). Nicht enthalten sind Versicherung, Wartung,
Reifen und Sprit. Angebote ändern sich täglich; verbindlich ist immer der Händler.
</p>
</div>""" % (
        html.escape(title),
        _CSS,
        html.escape(title),
        html.escape(subtitle),
        len(ranked),
        _euro(cheapest),
        _euro(cheapest * 12 if cheapest is not None else None),
        private_ok,
        "".join(rows) or '<tr><td colspan="9">Keine Angebote gefunden.</td></tr>',
    )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(document)


def timestamp() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")
