"""Quelle: leasingmarkt.de (AutoScout24-Gruppe, groesster Leasing-Marktplatz DE).

Die Suche unter /listing filtert serverseitig exakt nach dem, was wir brauchen:

    nsf / nst   Sitzanzahl von/bis   -> nsf=9&nst=9 fuer echte 9-Sitzer
    ym          km pro Jahr          -> ym=25000
    tg          Zielgruppe           -> PRIVATE | BUSINESS | ALL
    sort        Sortierung           -> rate (Rate aufsteigend)
    p           Seite

Die Trefferliste liefert pro Inserat alle Laufzeit-/km-Varianten in `offers[]`;
wir waehlen daraus gezielt die Variante mit der gewuenschten Laufleistung.
Ueberfuehrungskosten, Sitzanzahl und Sonderbedingungen stehen nur auf der
Detailseite - die wird optional nachgeladen.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from urllib.parse import urlencode

from ..flight import decode_flight, extract, scalar
from ..http import Fetcher
from ..model import Offer

BASE = "https://www.leasingmarkt.de"
NAME = "leasingmarkt"

TARGET_GROUPS = {"privat": "PRIVATE", "gewerbe": "BUSINESS", "alle": "ALL"}


def _search_url(seats: int, mileage: int, target_group: str, page: int,
                max_rate: Optional[int] = None) -> str:
    params = {
        "nsf": seats,
        "nst": seats,
        "ym": mileage,
        "tg": TARGET_GROUPS.get(target_group, "ALL"),
        "sort": "rate",
        "p": page,
    }
    if max_rate:
        params["mlpt"] = max_rate
    return "%s/listing?%s" % (BASE, urlencode(params))


def _pick_variant(listing: Dict, mileage: int) -> Optional[Dict]:
    """Waehlt die guenstigste Angebotsvariante mit der gewuenschten Laufleistung."""
    variants = listing.get("offers") or []
    matching = [v for v in variants if v.get("includedMileage") == mileage]
    if not matching:
        # Fallback: die vom Portal vorselektierte Variante
        default = listing.get("leasingOffer")
        if default and default.get("includedMileage") == mileage:
            return default
        return None
    return min(matching, key=lambda v: v.get("monthlyRate") or float("inf"))


def _to_offer(listing: Dict, variant: Dict) -> Offer:
    engine = listing.get("engine") or {}
    power = engine.get("power") or {}
    condition = listing.get("condition") or {}
    url = listing.get("url") or ""

    return Offer(
        source=NAME,
        listing_id=str(listing.get("id", "")),
        url=BASE + url if url.startswith("/") else url,
        make=listing.get("makeName") or "",
        model=listing.get("modelName") or "",
        headline=listing.get("headline") or "",
        body_type=listing.get("bodyType") or "",
        fuel=listing.get("fuelCategory") or "",
        hp=power.get("hp"),
        transmission=engine.get("transmissionType") or "",
        target_group=listing.get("targetGroup") or "",
        availability=listing.get("availability") or "",
        car_type=condition.get("carType") or "",
        gross_list_price=listing.get("grossListPriceInEUR"),
        monthly_rate=variant.get("monthlyRate"),
        monthly_net_rate=variant.get("monthlyNetRate"),
        duration=variant.get("duration"),
        included_mileage=variant.get("includedMileage"),
        leasing_factor=variant.get("leasingFactor"),
    )


def search(fetcher: Fetcher, seats: int = 9, mileage: int = 25000,
           target_group: str = "alle", max_rate: Optional[int] = None,
           max_pages: Optional[int] = None, verbose: bool = True) -> List[Offer]:
    """Blaettert die Trefferliste durch und gibt normalisierte Angebote zurueck."""
    offers: List[Offer] = []
    seen = set()
    page = 1
    total_pages = 1

    while page <= total_pages:
        if max_pages and page > max_pages:
            break
        html = fetcher.get(_search_url(seats, mileage, target_group, page, max_rate))
        if not html:
            if verbose:
                print("  Seite %s nicht abrufbar - Abbruch." % page)
            break

        blob = decode_flight(html)
        result = extract(blob, "initialResult")
        if result is None:
            if verbose:
                print("  Seite %s: keine Daten im Payload gefunden." % page)
            break

        if page == 1:
            total_pages = result.get("totalPages") or 1
            if verbose:
                print("  %s Treffer auf %s Seiten." % (result.get("totalResults", "?"), total_pages))

        listings = result.get("listings") or []
        if not listings:
            break

        for listing in listings:
            variant = _pick_variant(listing, mileage)
            if variant is None:
                continue
            offer = _to_offer(listing, variant)
            if offer.listing_id in seen:
                continue
            seen.add(offer.listing_id)
            offers.append(offer)

        if verbose:
            print("  Seite %s/%s -> %s Angebote" % (page, total_pages, len(offers)))
        page += 1

    return offers


def enrich(fetcher: Fetcher, offer: Offer) -> Offer:
    """Laedt die Detailseite und ergaenzt Sitze, Ueberfuehrung, Haendler, Auflagen."""
    html = fetcher.get(offer.url)
    if not html:
        return offer

    blob = decode_flight(html)

    interior = extract(blob, "interior") or {}
    if isinstance(interior, dict) and interior.get("numberOfSeats"):
        offer.seats = interior["numberOfSeats"]

    for attribute, key in (
        ("transfer_costs", "transferCosts"),
        ("registration_costs", "registrationCosts"),
        ("extra_km_cost", "additionalDistanceCostPerKm"),
        ("refund_per_km", "refundForLessDistancePerKm"),
    ):
        value = scalar(blob, key)
        if isinstance(value, (int, float)):
            setattr(offer, attribute, float(value))

    bank = scalar(blob, "bank")
    if isinstance(bank, str):
        offer.bank = bank

    dealers = extract(blob, "dealers")
    if isinstance(dealers, list) and dealers:
        first = dealers[0] or {}
        offer.dealer = first.get("companyName") or ""
        # `address` ist ein Fliesstext; Ort und PLZ stehen strukturiert daneben.
        detailed = first.get("detailedAddress") or first.get("location") or {}
        if isinstance(detailed, dict):
            city = detailed.get("city") or ""
            zip_code = detailed.get("zipCode") or detailed.get("zip") or ""
            offer.dealer_city = ("%s %s" % (zip_code, city)).strip()

    conditions = extract(blob, "specialConditions")
    if isinstance(conditions, list):
        offer.special_conditions = [
            c.get("title", "") for c in conditions if isinstance(c, dict) and c.get("title")
        ]
        # Manche Auflagen tragen einen Betrag (Praemien, Zuzahlungen).
        amounts = [
            c.get("amount") for c in conditions
            if isinstance(c, dict) and isinstance(c.get("amount"), (int, float))
        ]
        total = sum(a for a in amounts if a)
        if total:
            offer.extra_costs = float(total)

    offer.detail_fetched = True
    return offer
