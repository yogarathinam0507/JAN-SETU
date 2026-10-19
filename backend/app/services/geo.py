"""Ward/zone resolution. Uses configured boundary polygons (demo boundaries are flagged) or name/alias
matching in the complaint text. Never assigns a default ward."""
import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Jurisdiction


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def point_in_polygon(lat: float, lng: float, poly: list[list[float]]) -> bool:
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if ((xi > lng) != (xj > lng)) and (lat < (yj - yi) * (lng - xi) / ((xj - xi) or 1e-12) + yi):
            inside = not inside
        j = i
    return inside


def resolve_jurisdiction(db: Session, tenant_id: str, lat: float | None, lng: float | None,
                         text: str) -> tuple[Jurisdiction | None, str]:
    wards = db.execute(select(Jurisdiction).where(Jurisdiction.tenant_id == tenant_id,
                                                  Jurisdiction.kind == "ward")).scalars().all()
    if lat is not None and lng is not None:
        for w in wards:
            if w.polygon and point_in_polygon(lat, lng, w.polygon):
                return w, "gps-in-boundary" + (" (demo boundary)" if w.is_demo_boundary else "")
    lowered = (text or "").lower()
    for w in wards:
        for name in [w.name, *w.aliases]:
            if not name:
                continue
            # Latin names need word boundaries; Indic-script names are matched as substrings because
            # case suffixes attach directly (e.g. ಜಯನಗರದಲ್ಲಿ = "in Jayanagar").
            hit = (name in text) if not name.isascii() else \
                re.search(r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)", lowered)
            if hit:
                return w, f"text-match:'{name}'"
    return None, "not-determined"


def extract_location_text(text: str) -> str:
    m = re.search(r"\b(?:near|at|in|on|opposite|behind|beside)\s+((?:the\s+)?[\w\s'.-]{2,60}?"
                  r"(?:road|street|st|nagar|layout|cross|main|circle|colony|market|park|school|stop|station|underpass|"
                  r"avenue|block|sector|stage|phase|junction|lane|temple))\b", text, re.I)
    if m:
        return m.group(1).strip()
    return ""
