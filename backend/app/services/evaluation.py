"""Measured triage evaluation on the documented labelled dataset. Numbers shown in dashboards come from here."""
import uuid
from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..data.lexicon import EVAL_DATASET, EVAL_DATASET_NAME
from ..db import iso
from ..models import AiEvaluation, Tenant
from .triage import TriageError, run_triage


def run_eval(db: Session, tenant: Tenant) -> str:
    run_id = str(uuid.uuid4())
    for lang, text, exp_cat, exp_pri in EVAL_DATASET:
        try:
            r = run_triage(db, tenant, text, language_hint=lang, persist=False)
            pred_cat = "human_review" if r.human_review_required else (r.category_code or "human_review")
            pred_pri = r.priority if not r.human_review_required else None
            provider = r.provider
        except TriageError:
            pred_cat, pred_pri, provider = "error", None, "error"
        db.add(AiEvaluation(tenant_id=tenant.id, run_id=run_id, dataset=EVAL_DATASET_NAME, provider=provider,
                            language=lang, text=text, expected_category=exp_cat, predicted_category=pred_cat,
                            expected_priority=exp_pri or "-", predicted_priority=pred_pri or "-",
                            category_correct=pred_cat == exp_cat,
                            priority_correct=(pred_pri or "-") == (exp_pri or "-")))
    db.flush()
    return run_id


def summary(db: Session, tenant_id: str, run_id: str | None = None) -> dict | None:
    if not run_id:
        last = db.execute(select(AiEvaluation).where(AiEvaluation.tenant_id == tenant_id)
                          .order_by(AiEvaluation.id.desc()).limit(1)).scalar_one_or_none()
        if not last:
            return None
        run_id = last.run_id
    rows = db.execute(select(AiEvaluation).where(AiEvaluation.run_id == run_id)).scalars().all()
    if not rows:
        return None

    def acc(items):
        n = len(items)
        c = sum(1 for r in items if r.category_correct)
        p = sum(1 for r in items if r.priority_correct)
        return {"n": n, "category_correct": c, "priority_correct": p,
                "category_accuracy_pct": round(100 * c / n, 1) if n else None,
                "priority_accuracy_pct": round(100 * p / n, 1) if n else None}

    by_lang, by_cat = defaultdict(list), defaultdict(list)
    for r in rows:
        by_lang[r.language].append(r)
        by_cat[r.expected_category].append(r)
    return {"run_id": run_id, "dataset": rows[0].dataset, "provider": rows[0].provider, "run_at": iso(rows[0].created_at),
            "overall": acc(rows), "by_language": {k: acc(v) for k, v in sorted(by_lang.items())},
            "by_category": {k: acc(v) for k, v in sorted(by_cat.items())},
            "errors": [{"language": r.language, "text": r.text, "expected": r.expected_category, "predicted": r.predicted_category,
                        "expected_priority": r.expected_priority, "predicted_priority": r.predicted_priority}
                       for r in rows if not (r.category_correct and r.priority_correct)],
            "caveat": "Measured on a small synthetic demo dataset written by the project team. It is a regression check, "
                      "not evidence of real-world accuracy. Real accuracy needs reviewed production cases."}


def count_runs(db: Session, tenant_id: str) -> int:
    return db.scalar(select(func.count(func.distinct(AiEvaluation.run_id))).where(AiEvaluation.tenant_id == tenant_id)) or 0
