"""Scheme navigator: information assistance, NOT an official eligibility determination.

Outcomes:
  potentially_eligible            - every rule passes AND the scheme content is verified
  more_information_required       - at least one required answer is missing
  likely_not_eligible             - an exclusion matched or a requirement failed (preliminary)
  not_enough_verified_information - scheme rules are unverified seed content; result is only preliminary
"""
from ..models import Scheme

OUTCOME_LABELS = {
    "potentially_eligible": "Potentially eligible - confirm with the official department",
    "more_information_required": "More information required",
    "likely_not_eligible": "Based on your answers you may not qualify (not an official decision)",
    "not_enough_verified_information": "Not enough verified information to assess",
}


def _check(rule: dict, answer) -> bool:
    op, val = rule["op"], rule.get("value")
    if op == "eq":
        return answer == val
    if op == "in":
        return answer in val
    if op == "neq":
        return answer != val
    if op == "gte":
        return answer is not None and float(answer) >= float(val)
    if op == "lte":
        return answer is not None and float(answer) <= float(val)
    raise ValueError(f"unknown operator {op}")


def evaluate(scheme: Scheme, answers: dict) -> dict:
    reasons, missing, failed = [], [], []
    for rule in scheme.rules:
        q = rule["question"]
        ans = answers.get(q)
        if ans in (None, ""):
            missing.append(q)
            continue
        try:
            ok = _check(rule, ans)
        except (ValueError, TypeError):
            missing.append(q)
            continue
        if rule.get("type") == "exclusion":
            if ok:
                failed.append(q)
                reasons.append(f"Exclusion: {rule['explain']}")
            else:
                reasons.append(f"Passes: not excluded ({rule['explain']})")
        else:
            if ok:
                reasons.append(f"Meets: {rule['explain']}")
            else:
                failed.append(q)
                reasons.append(f"Does not meet: {rule['explain']}")
    if failed:
        rule_outcome = "likely_not_eligible"
    elif missing:
        rule_outcome = "more_information_required"
    else:
        rule_outcome = "potentially_eligible"
    outcome = rule_outcome
    if not scheme.verified and rule_outcome != "more_information_required":
        outcome = "not_enough_verified_information"
        reasons.append("These rules are unverified seed content and must be checked against the official notification.")
    return {
        "scheme_code": scheme.code, "outcome": outcome, "outcome_label": OUTCOME_LABELS[outcome],
        "preliminary_rule_check": rule_outcome, "reasons": reasons,
        "missing_questions": [q for q in scheme.questions if q["id"] in missing],
        "official_url": scheme.official_url or None,
        "source_note": scheme.source_note, "verified": scheme.verified, "version": scheme.version,
        "disclaimer": "This is information assistance only. Only the responsible department can decide eligibility.",
    }
