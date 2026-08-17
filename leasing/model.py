"""Datenmodell fuer ein vergleichbares Leasingangebot."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

# Reihenfolge der CSV-Spalten
CSV_FIELDS = [
    "effective_monthly",
    "yearly_cost",
    "monthly_rate",
    "monthly_net_rate",
    "duration",
    "included_mileage",
    "total_cost",
    "costs_complete",
    "transfer_costs",
    "registration_costs",
    "extra_costs",
    "estimated_transfer",
    "leasing_factor",
    "make",
    "model",
    "headline",
    "seats",
    "body_type",
    "fuel",
    "hp",
    "transmission",
    "target_group",
    "availability",
    "car_type",
    "purchase_price",
    "gross_list_price",
    "discount",
    "discount_pct",
    "extra_km_cost",
    "refund_per_km",
    "bank",
    "dealer",
    "dealer_city",
    "special_conditions",
    "source",
    "url",
]


@dataclass
class Offer:
    """Ein Angebot, normalisiert auf die gewuenschte km-Laufleistung."""

    source: str
    listing_id: str
    url: str
    make: str = ""
    model: str = ""
    headline: str = ""
    body_type: str = ""
    fuel: str = ""
    hp: Optional[int] = None
    transmission: str = ""
    target_group: str = ""
    availability: str = ""
    car_type: str = ""
    gross_list_price: Optional[float] = None   # UVP / Bruttolistenpreis
    purchase_price: Optional[float] = None     # Brutto-Kaufpreis beim Händler

    # Konditionen der gewaehlten km-Variante
    monthly_rate: Optional[float] = None       # brutto, inkl. MwSt.
    monthly_net_rate: Optional[float] = None   # netto, zzgl. MwSt.
    duration: Optional[int] = None             # Monate
    included_mileage: Optional[int] = None     # km/Jahr
    leasing_factor: Optional[float] = None

    # Erst nach dem Detail-Abruf gefuellt
    seats: Optional[int] = None
    transfer_costs: Optional[float] = None      # None = nicht angegeben, nicht 0
    registration_costs: Optional[float] = None
    extra_costs: Optional[float] = None         # Betraege aus specialConditions
    estimated_transfer: Optional[float] = None  # nur via --schaetze-ueberfuehrung
    extra_km_cost: Optional[float] = None
    refund_per_km: Optional[float] = None
    bank: str = ""
    dealer: str = ""
    dealer_city: str = ""
    special_conditions: List[str] = field(default_factory=list)
    detail_fetched: bool = False

    @property
    def upfront_costs(self) -> float:
        """Summe der *bekannten* Einmalkosten neben der Monatsrate."""
        return (
            (self.transfer_costs or 0.0)
            + (self.registration_costs or 0.0)
            + (self.extra_costs or 0.0)
            + (self.estimated_transfer or 0.0)
        )

    @property
    def costs_complete(self) -> bool:
        """Ob die Ueberfuehrungskosten ueberhaupt angegeben sind.

        `transferCosts: null` heisst "vom Haendler nicht angegeben", nicht
        "kostenfrei". Ohne diese Unterscheidung ranken Angebote ohne Angabe
        faelschlich zu weit oben.
        """
        return self.transfer_costs is not None or self.estimated_transfer is not None

    @property
    def total_cost(self) -> Optional[float]:
        """Gesamtkosten ueber die Laufzeit inkl. Einmalkosten."""
        if self.monthly_rate is None or not self.duration:
            return None
        return self.monthly_rate * self.duration + self.upfront_costs

    @property
    def effective_monthly(self) -> Optional[float]:
        """Monatsrate inkl. anteiliger Ueberfuehrung/Zulassung.

        Das ist die einzige ehrlich vergleichbare Zahl: eine 380-EUR-Rate mit
        1.700 EUR Ueberfuehrung ist teurer als eine 400-EUR-Rate ohne.
        """
        total = self.total_cost
        if total is None or not self.duration:
            return None
        return total / self.duration

    # Das Portal kennt drei Zielgruppen: "Nur Privatkunden", "Nur Gewerbekunden"
    # und "Privat- & Gewerbekunden". Auf blosses "gewerbe" zu pruefen wuerde die
    # gemischte Gruppe faelschlich als reines Gewerbeangebot einstufen.
    @property
    def yearly_cost(self) -> Optional[float]:
        """Kosten pro Jahr inkl. anteiliger Einmalkosten.

        Die Einmalkosten werden ueber die Laufzeit verteilt, nicht dem ersten
        Jahr zugeschlagen - sonst waeren kurze Laufzeiten kuenstlich teuer.
        """
        monthly = self.effective_monthly
        return None if monthly is None else monthly * 12

    # --- Kaufseite -------------------------------------------------------
    # Die Kaufpreise stammen aus denselben Inseraten: Haendler nennen zu jedem
    # Leasingangebot den Brutto-Kaufpreis desselben Fahrzeugs.

    @property
    def discount(self) -> Optional[float]:
        """Nachlass auf die UVP in Euro."""
        if self.purchase_price is None or self.gross_list_price is None:
            return None
        return self.gross_list_price - self.purchase_price

    @property
    def discount_pct(self) -> Optional[float]:
        gap = self.discount
        if gap is None or not self.gross_list_price:
            return None
        return gap / self.gross_list_price * 100.0

    def purchase_monthly(self, months: int, residual_pct: float) -> Optional[float]:
        """Monatlicher Wertverlust beim Kauf ueber die Haltedauer.

        (Kaufpreis + Einmalkosten - erwarteter Restwert) / Monate. Kapitalbindung
        bzw. Finanzierungszinsen bleiben aussen vor - das ist der reine
        Wertverlust und damit die Groesse, die dem Leasingaufwand gegenuebersteht.
        """
        if self.purchase_price is None or not months:
            return None
        residual = self.purchase_price * residual_pct
        return (self.purchase_price + self.upfront_costs - residual) / months

    @property
    def is_commercial_only(self) -> bool:
        return "nur gewerbe" in self.target_group.lower()

    @property
    def is_private_only(self) -> bool:
        return "nur privat" in self.target_group.lower()

    @property
    def available_to_private(self) -> bool:
        return not self.is_commercial_only

    @property
    def group_label(self) -> str:
        if self.is_commercial_only:
            return "Gewerbe"
        if self.is_private_only:
            return "Privat"
        return "beide"

    def as_row(self) -> dict:
        data = asdict(self)
        data.pop("detail_fetched", None)
        data["effective_monthly"] = _round(self.effective_monthly)
        data["yearly_cost"] = _round(self.yearly_cost)
        data["total_cost"] = _round(self.total_cost)
        data["costs_complete"] = "ja" if self.costs_complete else "nein"
        data["discount"] = _round(self.discount)
        data["discount_pct"] = _round(self.discount_pct)
        data["special_conditions"] = " | ".join(self.special_conditions)
        data["url"] = self.url
        return {key: data.get(key, "") for key in CSV_FIELDS}


def _round(value: Optional[float]) -> Optional[float]:
    return None if value is None else round(value, 2)
