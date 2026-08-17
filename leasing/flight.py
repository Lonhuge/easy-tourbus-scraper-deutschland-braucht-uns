"""Dekodiert den RSC-Flight-Payload von Next.js-Seiten.

LeasingMarkt.de rendert serverseitig und schiebt die kompletten Angebotsdaten als
JS-escapte Strings in `self.__next_f.push([1,"..."])`. Zusammengesetzt ergeben die
Fragmente ein (nicht ganz valides) JSON-Dokument, aus dem sich einzelne Objekte
sauber herausschneiden lassen.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

_PUSH = re.compile(r"self\.__next_f\.push\(\[1,")
_DECODER = json.JSONDecoder()


def decode_flight(html: str) -> str:
    """Fügt alle Flight-Fragmente einer Seite zu einem Blob zusammen."""
    parts = []
    for match in _PUSH.finditer(html):
        try:
            chunk, _ = _DECODER.raw_decode(html, match.end())
        except ValueError:
            continue
        if isinstance(chunk, str):
            parts.append(chunk)
    return "".join(parts)


def _balanced_slice(blob: str, start: int) -> Optional[str]:
    """Schneidet ab `start` ein balanciertes {...} bzw. [...] heraus.

    Zählt Klammern nur ausserhalb von Strings - Angebotstitel wie
    "SpaceTourer XL| PLUS [Aktion]" wuerden eine naive Zaehlung sonst zerlegen.
    """
    opener = blob[start]
    closer = {"{": "}", "[": "]"}.get(opener)
    if closer is None:
        return None

    depth = 0
    in_string = False
    escaped = False

    for i in range(start, len(blob)):
        char = blob[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return blob[start : i + 1]
    return None


def extract(blob: str, key: str, after: int = 0) -> Optional[Any]:
    """Liest den Wert von `"key":` als geparstes JSON-Objekt/Array."""
    needle = '"%s":' % key
    pos = blob.find(needle, after)
    if pos < 0:
        return None
    start = pos + len(needle)
    while start < len(blob) and blob[start] in " \n\t":
        start += 1
    if start >= len(blob) or blob[start] not in "{[":
        return None
    raw = _balanced_slice(blob, start)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def scalar(blob: str, key: str) -> Optional[Any]:
    """Liest einen skalaren Wert (Zahl, String, bool, null) zu `key`."""
    match = re.search(r'"%s":\s*("(?:[^"\\]|\\.)*"|-?[\d.]+|true|false|null)' % re.escape(key), blob)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except ValueError:
        return None
