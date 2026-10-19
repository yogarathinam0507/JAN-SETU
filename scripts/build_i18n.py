"""Build frontend/i18n/*.json from the Python string tables and report coverage per language."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from i18n_en import EN  # noqa: E402
from i18n_hi import HI  # noqa: E402
from i18n_kn import KN  # noqa: E402
from i18n_ta import TA  # noqa: E402

out = Path(__file__).resolve().parent.parent / "frontend" / "i18n"
out.mkdir(parents=True, exist_ok=True)
report = {}
for code, table in {"en": EN, "kn": KN, "hi": HI, "ta": TA}.items():
    unknown = set(table) - set(EN)
    if unknown:
        raise SystemExit(f"{code}: keys not in English source: {sorted(unknown)}")
    (out / f"{code}.json").write_text(json.dumps(table, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    citizen_keys = [k for k in EN if k.split(".")[0] in {"nav", "common", "home", "citizen", "ts", "tickets", "status", "priority", "benefits", "assist"}]
    report[code] = {"keys": len(table), "total": len(EN), "citizen_core_pct": round(100 * sum(k in table for k in citizen_keys) / len(citizen_keys), 1)}
(out / "coverage.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
print(json.dumps(report, indent=1))
