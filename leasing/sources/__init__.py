from . import carvago, leasingmarkt

SOURCES = {
    leasingmarkt.NAME: leasingmarkt,
    carvago.NAME: carvago,
}

__all__ = ["SOURCES", "leasingmarkt", "carvago"]
