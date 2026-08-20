"""Quelle: carvago.com - europaweiter Gebrauchtwagenmarkt (~1 Mio. Fahrzeuge).

Warum ausgerechnet Carvago: die naheliegenden Kaufportale sind zu, und zwar
per Ansage, nicht zufaellig -

    AutoScout24      robots.txt sperrt /ergebnisse? und /lst? fuer alle Clients
                     und ClaudeBot komplett
    mobile.de        403 (DataDome), AutoUncle ebenso
    heycar           robots.txt: "Disallow: /*?" - alle Filter-URLs gesperrt
    auto.de          robots.txt sperrt /search
    gebrauchtwagen.de  rendert rein clientseitig, keine Daten im HTML

Carvagos robots.txt erlaubt dagegen ausdruecklich alles ("Disallow:" leer).

Zugriffsweg: die SEO-Modellseiten /cars/<marke>/<modell> liefern die Treffer
serverseitig als JSON in __NEXT_DATA__. Sie nehmen allerdings *keine* Query-
Parameter an - weder Filter noch Seite noch Sortierung (getestet: seats_from,
page, order, sort laufen alle ins Leere bzw. in einen 308). Pro Modell sind
damit die 20 vom Portal vorsortierten Fahrzeuge erreichbar, aus denen lokal
die 9-Sitzer gefiltert werden. Das ist eine Stichprobe, keine Vollabdeckung -
der Aufrufer muss das kenntlich machen.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from ..http import Fetcher
from ..model import UsedCar

BASE = "https://carvago.com"
NAME = "carvago"

_NEXT_DATA = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.S)

# Modelle, die es ueberhaupt als 9-Sitzer gibt (aus Carvagos Sitemap).
# Reine Kastenwagen ohne Personenvariante sind bewusst nicht dabei.
VAN_MODELS = [
    "volkswagen/caravelle", "volkswagen/t5-caravelle", "volkswagen/t6-caravelle",
    "volkswagen/transporter", "volkswagen/t5-transporter", "volkswagen/t6-transporter",
    "volkswagen/t7-transporter", "volkswagen/t5-multivan", "volkswagen/t6-multivan",
    "volkswagen/t7-multivan", "volkswagen/crafter",
    "mercedes-benz/vito", "mercedes-benz/sprinter",
    "ford/tourneo", "ford/tourneo-custom", "ford/grand-tourneo",
    "ford/transit", "ford/transit-custom",
    "opel/vivaro", "opel/zafira", "opel/movano",
    "peugeot/traveller", "peugeot/expert", "peugeot/expert-tepee", "peugeot/boxer",
    "citroen/spacetourer", "citroen/jumpy", "citroen/jumper",
    "toyota/proace", "toyota/proace-verso",
    "renault/trafic", "renault/master",
    "nissan/primastar", "nissan/nv300", "nissan/nv400",
    "hyundai/staria", "hyundai/h-1", "hyundai/h-1-starex",
    "fiat/ducato", "fiat/talento",
]


def _parse(html: str) -> List[Dict]:
    match = _NEXT_DATA.search(html)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except ValueError:
        return []
    results = data.get("props", {}).get("pageProps", {}).get("searchResults", {})
    return results.get("cars") or []


def _label(value) -> str:
    if isinstance(value, dict):
        return value.get("label") or value.get("name") or ""
    return value or ""


def _to_used_car(car: Dict) -> Optional[UsedCar]:
    price = car.get("exact_price") or car.get("price")
    if not price:
        return None

    slug = car.get("slug") or ""
    registration = car.get("registration_date") or ""
    year = None
    if registration[:4].isdigit():
        year = int(registration[:4])

    location = car.get("location_country") or {}
    seller = car.get("seller") or {}

    # Kraftstoff steckt in den Katalog-Features
    fuel = ""
    for feature in car.get("catalog_features") or []:
        key = str(feature.get("const_key", ""))
        if key.startswith("FUELTYPE_"):
            fuel = feature.get("label") or ""
            break

    return UsedCar(
        source=NAME,
        listing_id=str(car.get("id", "")),
        # Detailseite ist /de/auto/<id>/<slug> - der Slug allein ergibt 404.
        url=("%s/de/auto/%s/%s" % (BASE, car.get("id"), slug)
             if slug and car.get("id") else BASE),
        make=_label(car.get("make")),
        model=_label(car.get("model")),
        title=car.get("title") or "",
        price=float(price),
        price_without_vat=car.get("price_without_vat"),
        vat_reclaimable=bool(car.get("vat_reclaimable")),
        mileage=car.get("mileage"),
        first_registration=registration[:7],
        year=year,
        seats=car.get("number_of_seats"),
        hp=car.get("power_hp"),
        fuel=fuel,
        city=car.get("location_city") or "",
        country=location.get("iso_code") or "",
        seller_type=_label((seller.get("type") or {})),
        published_at=str(car.get("created_at") or car.get("first_crawl") or "")[:10],
    )


def search(fetcher: Fetcher, seats: int = 9, models: Optional[List[str]] = None,
           verbose: bool = True) -> List[UsedCar]:
    """Laeuft die Van-Modellseiten ab und behaelt die Fahrzeuge mit `seats` Sitzen."""
    found: List[UsedCar] = []
    seen = set()
    targets = models or VAN_MODELS

    for index, path in enumerate(targets, 1):
        html = fetcher.get("%s/cars/%s" % (BASE, path))
        if not html:
            continue
        cars = _parse(html)
        hits = 0
        for car in cars:
            if car.get("number_of_seats") != seats:
                continue
            used = _to_used_car(car)
            if used is None or used.listing_id in seen:
                continue
            seen.add(used.listing_id)
            found.append(used)
            hits += 1
        if verbose and hits:
            print("  %-32s %2s von %2s Fahrzeugen mit %s Sitzen"
                  % (path, hits, len(cars), seats))
        elif verbose and index % 10 == 0:
            print("  ... %s/%s Modelle geprüft" % (index, len(targets)))

    return found
