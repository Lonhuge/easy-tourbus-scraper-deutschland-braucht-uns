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
from leasing.report import (
    limit_per_model, print_table, sort_offers, timestamp, write_csv, write_html)
from leasing.sources import leasingmarkt


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

    # Die CSV behaelt immer alles; gefiltert wird nur, was angezeigt wird.
    shown = limit_per_model(offers, args.pro_modell)
    if args.pro_modell and len(shown) < len(offers):
        print("\nAnzeige auf max. %s Angebot(e) je Modell reduziert: %s von %s."
              % (args.pro_modell, len(shown), len(offers)))

    print_table(shown, limit=args.top)

    write_csv(offers, args.csv)
    write_html(
        shown,
        args.html,
        title="%s-Sitzer Leasingvergleich" % args.sitze,
        subtitle="%s Angebote mit %s km/Jahr von leasingmarkt.de, sortiert nach den "
                 "tatsächlichen Monatskosten statt nach der beworbenen Rate. Stand: %s"
                 % (len(shown), "{:,}".format(args.km).replace(",", "."), timestamp()),
    )
    print("\nGeschrieben: %s und %s" % (args.csv, args.html))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(130)
