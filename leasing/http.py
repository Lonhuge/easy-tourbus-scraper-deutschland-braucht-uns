"""Hoeflicher HTTP-Client: fester User-Agent, Drosselung, Retry mit Backoff."""

from __future__ import annotations

import random
import time
from typing import Optional

import requests

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class Fetcher:
    def __init__(self, delay: float = 1.0, timeout: int = 30, retries: int = 3, verbose: bool = False):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.verbose = verbose
        self._last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9",
            }
        )

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request
        wait = self.delay - elapsed
        if wait > 0:
            time.sleep(wait + random.uniform(0, 0.3))
        self._last_request = time.time()

    def get(self, url: str) -> Optional[str]:
        """Laedt eine Seite. Gibt None zurueck, wenn sie dauerhaft fehlschlaegt."""
        for attempt in range(1, self.retries + 1):
            self._throttle()
            try:
                response = self.session.get(url, timeout=self.timeout)
                if response.status_code == 200:
                    return response.text
                if response.status_code == 404:
                    return None
                if response.status_code in (429, 500, 502, 503, 504):
                    backoff = min(30, 2 ** attempt * 2)
                    if self.verbose:
                        print("  HTTP %s, warte %ss ..." % (response.status_code, backoff))
                    time.sleep(backoff)
                    continue
                return None
            except requests.RequestException as exc:
                if self.verbose:
                    print("  Netzwerkfehler (%s/%s): %s" % (attempt, self.retries, exc))
                time.sleep(min(30, 2 ** attempt))
        return None
