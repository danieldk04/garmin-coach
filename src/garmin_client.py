"""Gedeelde Garmin Connect verbinding.

Logt in met opgeslagen tokens (~/.garmin-coach/tokens). Die tokens worden
eenmalig aangemaakt door scripts/login.py; daarna is er geen wachtwoord meer
nodig tot Garmin de sessie laat verlopen (ongeveer een jaar).
"""

from __future__ import annotations

import os
import threading
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from garminconnect import Garmin

TOKENSTORE = os.path.expanduser(os.getenv("GARMIN_TOKENSTORE", "~/.garmin-coach/tokens"))

_lock = threading.Lock()
_client: Garmin | None = None
_cache: dict[tuple, tuple[float, Any]] = {}
CACHE_TTL = 60.0  # seconden; houdt antwoorden vers maar spaart Garmin


class NietIngelogd(RuntimeError):
    pass


def client() -> Garmin:
    """Geef een ingelogde client terug (eenmalig opgezet, daarna hergebruikt)."""
    global _client
    with _lock:
        if _client is not None:
            return _client
        vanuit_omgeving = os.getenv("GARMIN_TOKEN_JSON")
        if vanuit_omgeving:
            g = Garmin()
            g.login(vanuit_omgeving)
            _client = g
            return g
        if not Path(TOKENSTORE).exists():
            raise NietIngelogd(
                "Nog niet ingelogd bij Garmin. Draai eenmalig: "
                "~/Documents/garmin-coach/.venv/bin/python "
                "~/Documents/garmin-coach/scripts/login.py"
            )
        g = Garmin()
        g.login(TOKENSTORE)
        _client = g
        return g


def call(naam: str, *args, **kwargs) -> Any:
    """Roep een Garmin methode aan met korte cache en één hernieuwde login bij 401."""
    sleutel = (naam, args, tuple(sorted(kwargs.items())))
    nu = time.time()
    geraakt = _cache.get(sleutel)
    if geraakt and nu - geraakt[0] < CACHE_TTL:
        return geraakt[1]

    global _client
    try:
        uitkomst = getattr(client(), naam)(*args, **kwargs)
    except NietIngelogd:
        raise
    except Exception as fout:  # sessie kan verlopen zijn: één keer opnieuw proberen
        if "401" in str(fout) or "403" in str(fout) or "Unauthorized" in str(fout):
            with _lock:
                _client = None
            uitkomst = getattr(client(), naam)(*args, **kwargs)
        else:
            raise

    _cache[sleutel] = (nu, uitkomst)
    return uitkomst


def vandaag() -> str:
    return date.today().isoformat()


def dagen_terug(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def schoon(waarde: Any, velden: list[str]) -> dict:
    """Houd alleen de velden over die ertoe doen, scheelt ruis in het antwoord."""
    if not isinstance(waarde, dict):
        return {}
    return {v: waarde.get(v) for v in velden if waarde.get(v) is not None}
