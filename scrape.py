#!/usr/bin/env python3
"""Findet die guenstigsten Leasingangebote nach Sitzanzahl und Jahreslaufleistung.

Standard: 9-Sitzer mit 25.000 km/Jahr.

    python scrape.py                          # 9 Sitze, 25.000 km, alle Zielgruppen
    python scrape.py --zielgruppe privat      # nur Privatkundenangebote
    python scrape.py --keine-details          # schnell, ohne Ueberfuehrungskosten
    python scrape.py --sitze 7 --km 20000     # andere Konfiguration
"""

from __future__ import annotations

import argparse
import statistics
import sys
from typing import List

from leasing.http import Fetcher
from leasing.model import Offer
from leasing.seen import Seen
from leasing.report import (
    limit_per_model, print_table, sort_offers, timestamp, write_csv, write_html,
    write_used_csv)
from leasing.sources import carvago, leasingmarkt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guenstigste Leasingangebote nach Sitzanzahl und km/Jahr.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--sitze", type=int, default=9, help="Sitzanzahl (Standard: 9)")
    parser.add_argument("--km", type=int, default=25000,
                        help="Jahreslaufleistung in km (Standard: 25000)")
    parser.add_argument("--zielgruppe", choices=["privat", "gewerbe", "alle"], default="alle",
                        help="Privat-, Gewerbe- oder alle Angebote (Standard: alle)")
    parser.add_argument("--max-rate", type=int, default=None,
                        help="Monatsrate brutto nach oben begrenzen, z. B. 500")
    parser.add_argument("--top", type=int, default=20, help="Anzahl Zeilen in der Konsole")
    parser.add_argument("--pro-modell", type=int, default=0, metavar="N",
                        help="Je Modell hoechstens N Angebote zeigen (0 = alle)")
    parser.add_argument("--seen", default="seen.json",
                        help="Datei mit den bereits gesehenen Angeboten")
    parser.add_argument("--alles-neu", action="store_true",
                        help="Gedächtnis ignorieren und alles als neu behandeln")
    parser.add_argument("--ohne-gebrauchte", action="store_true",
                        help="Gebrauchtwagensuche (carvago.com) überspringen")
    parser.add_argument("--haltedauer", type=int, default=60, metavar="MONATE",
                        help="Angenommene Haltedauer beim Kauf (Standard: 60)")
    parser.add_argument("--restwert", type=int, default=40, metavar="PROZENT",
                        help="Angenommener Restwert beim Kauf in %% des Kaufpreises "
                             "(Standard: 40)")
    parser.add_argument("--schaetze-ueberfuehrung", action="store_true",
                        help="Fehlende Ueberfuehrungskosten mit dem Median der "
                             "uebrigen Angebote ansetzen statt mit 0")
    parser.add_argument("--keine-details", action="store_true",
                        help="Detailseiten ueberspringen (keine Ueberfuehrungskosten/Sitzpruefung)")
    parser.add_argument("--max-details", type=int, default=None,
                        help="Detailseiten nur fuer die N guenstigsten Angebote laden")
    parser.add_argument("--csv", default="angebote.csv", help="CSV-Ausgabedatei")
    parser.add_argument("--html", default="angebote.html", help="HTML-Report")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Pause zwischen Requests in Sekunden (Standard: 1.0)")
    return parser.parse_args()


def enrich_offers(fetcher: Fetcher, offers: List[Offer], limit) -> None:
    """Laedt Detailseiten fuer die guenstigsten Angebote nach."""
    targets = sort_offers(offers)
    if limit:
        targets = targets[:limit]

    print("\nLade Detailseiten (Ueberfuehrung, Sitze, Auflagen) fuer %s Angebote ..."
          % len(targets))
    for index, offer in enumerate(targets, 1):
        leasingmarkt.enrich(fetcher, offer)
        if index % 10 == 0 or index == len(targets):
            print("  %s/%s" % (index, len(targets)))


def main() -> int:
    args = parse_args()
    fetcher = Fetcher(delay=args.delay, verbose=True)

    label = "%s-Sitzer, %s km/Jahr" % (args.sitze, "{:,}".format(args.km).replace(",", "."))
    print("Suche: %s (%s)" % (label, args.zielgruppe))
    print("Quelle: leasingmarkt.de")

    offers = leasingmarkt.search(
        fetcher,
        seats=args.sitze,
        mileage=args.km,
        target_group=args.zielgruppe,
        max_rate=args.max_rate,
    )

    if not offers:
        print("\nKeine Angebote gefunden. Filter lockern (--km, --sitze) und erneut versuchen.")
        return 1

    print("\n%s Angebote mit passender %s-km-Variante gefunden."
          % (len(offers), "{:,}".format(args.km).replace(",", ".")))

    if not args.keine_details:
        enrich_offers(fetcher, offers, args.max_details)

        # Sitzanzahl gegenpruefen: der Portalfilter ist gut, aber nicht unfehlbar.
        checked = [o for o in offers if o.detail_fetched and o.seats is not None]
        mismatched = [o for o in checked if o.seats != args.sitze]
        if mismatched:
            print("\nHinweis: %s Angebote weichen laut Detailseite von %s Sitzen ab "
                  "und wurden entfernt." % (len(mismatched), args.sitze))
            offers = [o for o in offers if o not in mismatched]

    known = [o.transfer_costs for o in offers if o.transfer_costs is not None]
    missing = [o for o in offers if o.transfer_costs is None]
    if known and missing:
        median = statistics.median(known)
        print("\nÜberführungskosten: %s von %s Angeboten mit Angabe "
              "(Median %.0f EUR, Spanne %.0f-%.0f EUR)."
              % (len(known), len(offers), median, min(known), max(known)))
        if args.schaetze_ueberfuehrung:
            for offer in missing:
                offer.estimated_transfer = median
            print("  %s Angebote ohne Angabe werden mit dem Median gerechnet." % len(missing))
        else:
            print("  %s Angebote ohne Angabe werden mit 0 EUR gerechnet und mit * markiert."
                  % len(missing))

    used_cars = []
    if not args.ohne_gebrauchte:
        print("\nGebrauchtwagen suchen (carvago.com) ...")
        used_cars = carvago.search(fetcher, seats=args.sitze)
        print("  %s gebrauchte %s-Sitzer aus %s Modellreihen."
              % (len(used_cars), args.sitze,
                 len({(c.make, c.model) for c in used_cars})))

    seen = Seen(args.seen)
    baseline = seen.is_first_run and not args.alles_neu
    fresh = 0
    for item in list(offers) + list(used_cars):
        # Portalseitiges Datum als Ersteintrag nutzen, wenn vorhanden - sonst heute.
        was_unknown = seen.mark(item.source, item.listing_id, item.published_at or None)
        item.first_seen = seen.first_seen(item.source, item.listing_id) or ""
        # Beim allerersten Lauf waere sonst der komplette Bestand "neu".
        item.is_new = was_unknown and not baseline
        if item.is_new:
            fresh += 1
    seen.save()

    if baseline:
        print("\nErster Lauf mit Gedächtnis: %s Angebote als Ausgangsbestand vermerkt."
              % len(seen.entries))
        print("  Ab dem nächsten Update erscheinen Neuzugänge oben und als NEU markiert.")
    else:
        print("\n%s Neuzugänge seit dem letzten Lauf (%s)."
              % (fresh, seen.last_run or "unbekannt"))

    # Die CSV behaelt immer alles; gefiltert wird nur, was angezeigt wird.
    shown = limit_per_model(offers, args.pro_modell)
    if args.pro_modell and len(shown) < len(offers):
        print("\nAnzeige auf max. %s Angebot(e) je Modell reduziert: %s von %s."
              % (args.pro_modell, len(shown), len(offers)))

    print_table(shown, limit=args.top)

    priced = [o for o in shown if o.purchase_price]
    if priced:
        residual = args.restwert / 100.0
        priced.sort(key=lambda o: o.purchase_monthly(args.haltedauer, residual) or 1e9)
        print("\nKAUF — dieselben Fahrzeuge, Brutto-Kaufpreis der Händler")
        print("(Wertverlust = (Kaufpreis + Einmalkosten − %s%% Restwert) ÷ %s Monate)"
              % (args.restwert, args.haltedauer))
        print("-" * 112)
        print("%-3s %-13s %-14s %-13s %s" % (
            "#", "KAUFPREIS", "WERTVERL./MON", "UNTER UVP", "FAHRZEUG"))
        for index, offer in enumerate(priced[: args.top], 1):
            gap = offer.discount_pct
            print("%-3s %-13s %-14s %-13s %s" % (
                index,
                "%.0f EUR" % offer.purchase_price,
                "%.0f EUR" % (offer.purchase_monthly(args.haltedauer, residual) or 0),
                ("%.0f %%" % gap) if gap and gap > 0 else "-",
                ("%s %s" % (offer.make, offer.model)).strip()[:40],
            ))
        print("-" * 112)

    write_csv(offers, args.csv)
    write_html(
        shown,
        args.html,
        title="%s-Sitzer Leasingvergleich" % args.sitze,
        subtitle="%s Angebote mit %s km/Jahr von leasingmarkt.de, sortiert nach den "
                 "tatsächlichen Monatskosten statt nach der beworbenen Rate. Stand: %s"
                 % (len(shown), "{:,}".format(args.km).replace(",", "."), timestamp()),
        hold_months=args.haltedauer,
        residual_pct=args.restwert / 100.0,
        used_cars=used_cars,
    )
    if used_cars:
        write_used_csv(used_cars, "gebrauchtwagen.csv",
                       args.haltedauer, args.restwert / 100.0)
        residual = args.restwert / 100.0
        print("\nGEBRAUCHT — echte Gebrauchtwagen von carvago.com")
        print("-" * 112)
        print("%-3s %-13s %-14s %-12s %-11s %s" % (
            "#", "KAUFPREIS", "WERTVERL./MON", "KM-STAND", "ERSTZUL.", "FAHRZEUG"))
        ordered = sorted(used_cars, key=lambda c: (not c.is_new, c.price or 1e9))
        for index, car in enumerate(ordered[: args.top], 1):
            print("%-3s %-13s %-14s %-12s %-11s %s" % (
                index,
                "%.0f EUR" % (car.price or 0),
                "%.0f EUR" % (car.monthly_loss(args.haltedauer, residual) or 0),
                "{:,}".format(car.mileage).replace(",", ".") if car.mileage is not None else "-",
                car.first_registration or "-",
                (("NEU " if car.is_new else "")
                 + ("%s %s" % (car.make, car.model)).strip()[:30])
                + ("" if car.country == "DE" else "  [%s]" % car.country),
            ))
        print("-" * 112)
    print("\nGeschrieben: %s und %s" % (args.csv, args.html))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(130)
