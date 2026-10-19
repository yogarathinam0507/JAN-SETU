"""Deterministic demo seed. Usage (from backend/):  python -m app.seed [--reset] [--force]

Refuses to run when APP_ENV=production unless --force is given. All seeded records are flagged as demo/sample.
"""
import argparse
import random
import sys
from datetime import timedelta

from sqlalchemy import select

from .config import get_settings
from .data import seed_data as S
from .db import SessionLocal, engine, utcnow
from .models import (Base, Category, Department, DocumentTemplate, EscalationRule, Grievance, IntegrationConfig,
                     Interaction, Jurisdiction, Language, MonitoredService, OfficerFile, FileMovement, Role,
                     RolePermission, Scheme, SlaPolicy, Tenant, TicketEvent, User, Vendor, WorkOrder)
from .security import PERMISSIONS, ROLES, hash_password
from .services import evaluation, kb, monitoring, workflow
from .services.language import LANGUAGES, current_support
from .services.triage import run_triage

DEMO_PASSWORD = "Demo@1234"


def seed_global(db) -> None:
    for code, (name, desc) in ROLES.items():
        db.merge(Role(code=code, name=name, description=desc))
    db.flush()
    for role, perms in PERMISSIONS.items():
        for p in perms:
            if not db.execute(select(RolePermission).where(RolePermission.role_code == role,
                                                           RolePermission.permission == p)).first():
                db.add(RolePermission(role_code=role, permission=p))
    for (code, name, native, script, direction, eighth, classical, tier, speech, ui, kw) in LANGUAGES:
        note = ""
        if not ui:
            note = "Interface falls back to English; triage needs a translation provider. Not yet tested end-to-end."
        if direction == "rtl":
            note += " RTL layout supported by the UI shell."
        db.merge(Language(code=code, name=name, native_name=native, script=script, direction=direction,
                          eighth_schedule=eighth, classical=classical, planned_tier=tier,
                          current_support=current_support(ui, kw), speech_code=speech, ui_strings=ui,
                          triage_keywords=kw, notes=note.strip()))
    for code, name, kind, state, adapter, notes in S.INTEGRATIONS:
        if not db.execute(select(IntegrationConfig).where(IntegrationConfig.code == code)).first():
            db.add(IntegrationConfig(tenant_id=None, code=code, name=name, kind=kind, state=state, adapter=adapter,
                                     notes=notes, last_verified_at=utcnow() if state == "connected_tested" else None))
    db.flush()


CITIZEN_NAMES = {
    "ka": ["Shwetha R.", "Anil Kumar", "Prema Nagesh", "Rahul Desai", "Fathima Banu", "Girish Bhat", "Sunitha M.",
           "Venkatesh K.", "Nandini Rao", "Joseph D'Souza", "Harsha V.", "Mallika S."],
    "tn": ["Lakshmi Priya", "Karthik R.", "Fathima S.", "Senthil M.", "Revathi K.", "Ramesh Babu", "Divya Bharathi",
           "Mohammed Yusuf", "Saranya P.", "Vignesh T.", "Anand Raj", "Kavitha S."],
}
RESOLVE_NOTES = {
    "streetlight": "Faulty lamp and choke replaced; light checked after dusk.",
    "water_supply": "Valve repaired and supply restored; pressure checked at the last house.",
    "water_quality": "Pipeline flushed and chlorinated; water sample tested within limits.",
    "sewage": "Line de-silted with jetting machine and manhole cover replaced.",
    "garbage": "Black spot cleared and added to the daily collection route.",
    "roads": "Pothole filled with bituminous mix and compacted.",
    "power_outage": "Fuse at the distribution transformer replaced; supply restored.",
    "power_hazard": "Area isolated, cable re-terminated and pole straightened.",
    "storm_drain": "Silt removed from the drain; water flow restored.",
    "fallen_tree": "Tree cut and cleared from the carriageway.",
    "mosquito": "Anti-larval treatment and fogging carried out in the street.",
    "stray_animals": "Animal birth control team picked up the animals.",
}


def box(lat: float, lng: float, d: float = 0.008) -> list[list[float]]:
    return [[lat - d, lng - d], [lat - d, lng + d], [lat + d, lng + d], [lat + d, lng - d]]


def weighted(rng: random.Random, mix: dict) -> str:
    keys = list(mix)
    return rng.choices(keys, weights=[mix[k] for k in keys], k=1)[0]


def seed_tenant(db, spec: dict, rng: random.Random) -> None:
    t = Tenant(code=spec["code"], name=spec["name"], state=spec["state"], default_language=spec["default_language"],
               languages=spec["languages"], branding=spec["branding"], emergency_contacts=spec["emergency_contacts"])
    db.add(t)
    db.flush()
    p = spec["prefix"]
    depts = {}
    for code, (names, parent, contact) in spec["departments"].items():
        d = Department(tenant_id=t.id, code=code, names=names, parent_body=parent, contact=contact,
                       working_hours="Mon-Sat 10:00-17:30", name_verified=False)
        db.add(d)
        depts[code] = d
    db.flush()
    cats = {}
    for code, (dcode, pri, family, names, photo) in S.CATEGORIES.items():
        c = Category(tenant_id=t.id, department_id=depts[dcode].id, code=code, names=names, family=family,
                     default_priority=pri, requires_photo_verification=photo)
        db.add(c)
        cats[code] = c
    for pri, fr, res, desc in S.SLA:
        db.add(SlaPolicy(tenant_id=t.id, priority=pri, first_response_hours=fr, resolve_hours=res, description=desc))
    for level, role, frac, desc in S.ESCALATION:
        db.add(EscalationRule(tenant_id=t.id, level=level, role=role, sla_fraction=frac, description=desc))
    wards = {}
    zones = {}
    for zcode, (zname, wlist) in spec["zones"].items():
        z = Jurisdiction(tenant_id=t.id, code=zcode, name=zname, kind="zone")
        db.add(z)
        db.flush()
        zones[zcode] = z
        for wcode, wname, (lat, lng), aliases in wlist:
            w = Jurisdiction(tenant_id=t.id, code=wcode, name=wname, kind="ward", parent_id=z.id,
                             polygon=box(lat, lng), aliases=aliases, is_demo_boundary=True)
            db.add(w)
            wards[wcode] = (w, lat, lng)
    vendor = Vendor(tenant_id=t.id, name=spec["vendor_name"], is_sample=True)
    db.add(vendor)
    db.flush()
    people = spec["people"]

    def mk(username, name, designation, role, is_demo=True, **kw):
        u = User(tenant_id=t.id, username=f"{p}.{username}", full_name=name, designation=designation, role=role,
                 password_hash=hash_password(DEMO_PASSWORD), language=kw.pop("language", spec["default_language"]),
                 is_demo=is_demo, **kw)
        db.add(u)
        return u

    def person(key, role, **kw):
        name, desig = people[key]
        return mk(key, name, desig, role, **kw)
    c1 = person("citizen1", "citizen", phone=f"98450{'10001' if p == 'ka' else '20001'}")
    c2 = person("citizen2", "citizen", phone=f"98450{'10002' if p == 'ka' else '20002'}", language="en")
    agent1 = person("agent1", "agent", language="en")
    person("agent2", "agent", language="en")
    officers = {}
    for code, d in depts.items():
        name, desig = spec["officers"][code]
        officers[code] = mk(f"officer.{code.lower()}", name, desig, "officer", department_id=d.id, language="en")
    person("nodal", "nodal", language="en")
    person("nodal.south", "nodal", jurisdiction_id=zones["SOUTH"].id, language="en")
    person("hod", "hod", language="en")
    person("vendor", "vendor", vendor_id=vendor.id, language="en")
    auditor = person("auditor", "auditor", language="en")
    person("content", "content", language="en")
    person("admin", "admin", language="en")
    # Additional registered citizens (no published password) so complaints come from many residents.
    citizens = [c1, c2]
    for k, name in enumerate(CITIZEN_NAMES[p]):
        citizens.append(mk(f"resident{k + 1:02d}", name, "", "citizen", is_demo=False,
                           phone=f"9{rng.randint(100000000, 999999999)}", language=rng.choice([spec["default_language"], "en"])))
    db.flush()

    # Knowledge base, schemes, templates
    for key, title, dcode, lang, verified, sample, src, body in S.KB_DOCS[spec["code"]]:
        kb.add_version(db, tenant_id=t.id, doc_key=key, title=title, body=body, actor_id=None, department_code=dcode,
                       language=lang, verified=verified, is_sample=sample, source_filename=src, published_date="2026-10-01")
    for sch in S.SCHEMES[spec["code"]]:
        db.add(Scheme(tenant_id=t.id, verified=False, official_url="",
                      source_note="Summary written from general knowledge. A content manager must verify "
                                  "every rule against the current official notification and add the official URL.", **sch))
    for cat, title in S.DIRECTORY:
        db.add(Scheme(tenant_id=t.id, code=f"dir_{cat}", names={"en": title}, service_category=cat,
                      department="Responsible department (to be configured)",
                      summary="Directory entry. Verified scheme content has not been added yet - ask a human helper.",
                      verified=False, source_note="Placeholder - no rules, no eligibility assessment."))
    for doc_type, lang, title, body in S.TEMPLATES:
        if lang in spec["languages"]:
            db.add(DocumentTemplate(tenant_id=t.id, doc_type=doc_type, language=lang, title=title, body=body,
                                    is_sample=True, approved=False))
    db.flush()

    # ---- Synthetic, correctly located complaints, filed through the real pipeline
    now = utcnow()
    ward_codes = list(wards)
    jobs = []
    for _ in range(S.SYNTHETIC_PER_TENANT):
        cat = weighted(rng, S.CATEGORY_MIX)
        tpl = rng.choice(S.TEMPLATES_BY_CATEGORY[cat])
        wcode = rng.choice(ward_codes)
        text = tpl.format(lm=rng.choice(spec["landmarks"]), d=rng.randint(2, 6)) + f", {wards[wcode][0].name}"
        final = weighted(rng, S.STATUS_MIX)
        # Open work is mostly recent (some of it overdue); finished work is spread over the last two months.
        if final in {"submitted", "accepted", "in_progress", "reopened"}:
            days_ago = min(20.0, rng.expovariate(1 / 1.6))
        else:
            days_ago = min(59.0, 1.5 + rng.expovariate(1 / 14))
        jobs.append((text, "en", wcode, days_ago, final))
    for text, lang, wcode in S.EXTRA_GRIEVANCES[spec["code"]]:
        jobs.append((text, lang, wcode, rng.uniform(0.2, 6), "submitted"))
    jobs.sort(key=lambda j: -j[3])  # oldest first so duplicate detection sees history in order
    work_orders = 0
    for idx, (text, lang, wcode, days_ago, final) in enumerate(jobs):
        lat = lng = None
        if wcode:
            _, wl, wg = wards[wcode]
            lat, lng = round(wl + rng.uniform(-0.0065, 0.0065), 6), round(wg + rng.uniform(-0.0065, 0.0065), 6)
        created = now - timedelta(days=days_ago, minutes=rng.randint(0, 50))
        if days_ago < 0.15:
            final = "submitted"  # too new to have moved
        elif days_ago < 1.0 and final == "reopened":
            final = "in_progress"
        tri = run_triage(db, t, text, language_hint=lang, lat=lat, lng=lng).model_dump()
        citizen = citizens[0] if idx % 7 == 0 else citizens[1] if idx % 7 == 3 else rng.choice(citizens[2:])
        channel = rng.choice(["web", "web", "web", "mobile", "assistant", "voice", "whatsapp"])
        actor = agent1 if channel == "voice" else citizen
        g = workflow.create_grievance(db, tenant_id=t.id, triage=tri, text=text, actor=actor, citizen=citizen,
                                      channel=channel, input_mode="text", transcript_confirmed=True,
                                      contact_name=citizen.full_name, contact_phone=citizen.phone or "", lat=lat,
                                      lng=lng, location_text="", consent=True, is_demo=True, created_at=created)
        db.flush()
        officer = db.get(User, g.assigned_officer_id) if g.assigned_officer_id else None
        if officer and final != "submitted":
            workflow.transition(db, g, "accept", officer)
            if final in {"in_progress", "resolved", "closed", "reopened"}:
                workflow.transition(db, g, "start", officer)
            cat_code = next((c for c, obj in cats.items() if obj.id == g.category_id), "")
            if final in {"resolved", "closed", "reopened"}:
                workflow.transition(db, g, "resolve", officer,
                                    RESOLVE_NOTES.get(cat_code, "Site inspected and the issue has been attended to."))
            if final == "closed":
                workflow.transition(db, g, "confirm_closure", citizen, rng.choice(["Thank you, resolved.", "Work done, thanks.",
                                                                                   "Fixed. Thank you for the quick action."]))
                g.citizen_rating = rng.choice([3, 4, 4, 5, 5, 5])
            if final == "reopened":
                workflow.transition(db, g, "reject_closure", citizen, "The problem has started again, please check.")
            if final == "rejected":
                workflow.transition(db, g, "reject", officer,
                                    "Inspection found this is on private property; the owner has been informed.")
            if cat_code == "roads" and final == "in_progress" and work_orders < 6:
                work_orders += 1
                db.add(WorkOrder(tenant_id=t.id, grievance_id=g.id, vendor_id=vendor.id,
                                 description=f"Pothole patch work - {g.public_id}",
                                 boq=[{"item": "Bituminous mix", "qty": round(rng.uniform(0.4, 1.6), 1), "unit": "m3"},
                                      {"item": "Labour", "qty": rng.randint(1, 3), "unit": "man-day"}],
                                 due_at=created + timedelta(days=3), created_by=officer.id,
                                 created_at=created + timedelta(hours=6)))
        # Spread the event history realistically between creation and now.
        span_h = max(0.5, min(days_ago * 24 - 0.2, rng.uniform(4, 96)))
        evs = db.execute(select(TicketEvent).where(TicketEvent.grievance_id == g.id)
                         .order_by(TicketEvent.created_at)).scalars().all()
        later = [e for e in evs if e.created_at > created + timedelta(minutes=1) or e.event_type not in {"created", "assigned"}]
        step_h = span_h / (len(later) + 1)
        for k, e in enumerate(evs):
            if e not in later:
                e.created_at = created
        stamp = {}
        for k, e in enumerate(later, start=1):
            e.created_at = min(created + timedelta(hours=step_h * k), now)
            stamp.setdefault(e.event_type, e.created_at)
        if "accept" in stamp:
            g.first_response_at = stamp["accept"]
        if g.resolved_at:
            g.resolved_at = stamp.get("resolve", g.resolved_at)
        if g.closed_at:
            g.closed_at = stamp.get("confirm_closure", g.closed_at)
        g.updated_at = max([e.created_at for e in evs] + [created])
    db.flush()
    workflow.run_escalations(db, t.id, backdate=True)

    # e-file
    f = OfficerFile(tenant_id=t.id, subject="Monsoon preparedness - storm water drain desilting, all zones",
                    department_id=depts["SWD"].id, current_holder_id=officers["SWD"].id, created_by=officers["SWD"].id)
    db.add(f)
    db.flush()
    db.add(FileMovement(file_id=f.id, to_user_id=officers["SWD"].id, to_department_id=depts["SWD"].id, action="opened",
                        note="File opened"))

    # Call-centre history
    callers = CITIZEN_NAMES[p]
    lines = ["I want to know the status of my complaint.", "Garbage has not been collected in our street.",
             "There is no water since yesterday.", "Is my pension application approved?"]
    for k in range(10):
        q = now - timedelta(days=k // 2, hours=rng.randint(1, 8))
        i = Interaction(tenant_id=t.id, channel=rng.choice(["voice", "voice", "web_chat", "whatsapp"]),
                        caller_name=callers[k % len(callers)], caller_phone=f"9{rng.randint(100000000, 999999999)}",
                        language=spec["default_language"], status="closed", agent_id=agent1.id, queued_at=q,
                        started_at=q + timedelta(seconds=rng.randint(20, 240)),
                        ended_at=q + timedelta(minutes=rng.randint(3, 12)), simulated=True,
                        disposition=rng.choice(["grievance_registered", "information_provided", "status_enquiry"]),
                        summary="Caller query handled by the helpline executive.",
                        sentiment=rng.choice(["neutral", "negative", "positive"]),
                        transcript=[{"speaker": "caller", "text": rng.choice(lines), "at": q.isoformat() + "Z",
                                     "source": "call-log"}])
        if k < 4:
            i.qa_review = {"scores": {"greeting": 2, "verification": 2, "accuracy": rng.choice([1, 2]), "empathy": 2,
                                      "resolution": rng.choice([1, 2]), "closure": 2}, "total": 11, "max": 12, "percent": 91.7,
                           "comments": "Courteous call; verification done.", "reviewer": auditor.full_name,
                           "at": q.isoformat() + "Z"}
        db.add(i)
    db.add(Interaction(tenant_id=t.id, channel="callback_request", caller_name=callers[1], caller_phone="9845012345",
                       language=spec["default_language"], status="queued", simulated=True, priority="Medium",
                       queued_at=now - timedelta(minutes=14),
                       transcript=[{"speaker": "caller", "text": "Please call me about my pension status.",
                                    "at": now.isoformat() + "Z", "source": "web-form"}]))
    db.flush()

    # Monitoring registry
    db.add(MonitoredService(tenant_id=t.id, name="JanSetu portal - database & API", endpoint="in-process",
                            owner_team="Platform team", environment="this deployment", criticality="high",
                            check_mode="in_process", authorized=True, latency_threshold_ms=500, slo_target=99.5))
    sims = [("Citizen Services Portal", "fast degrade-evening", "high"),
            ("Land Records Service", "outage-night", "high"),
            ("Online Payments Gateway", "fast", "medium")]
    for name, notes, crit in sims:
        s = MonitoredService(tenant_id=t.id, name=name, endpoint="", owner_team="Service owner (to confirm)",
                             environment="synthetic probe", criticality=crit, check_mode="simulated", authorized=False,
                             notes=notes, latency_threshold_ms=1500)
        db.add(s)
        db.flush()
        monitoring.seed_history(db, s, hours=48, step_min=10)
    planned = (["Seva Sindhu", "Kaveri 2.0", "Kutumba"] if p == "ka" else ["TN e-Sevai", "GCC online services"])
    for name in planned:
        db.add(MonitoredService(tenant_id=t.id, name=f"{name} (awaiting authorization)", endpoint="",
                                owner_team="Owning department (to confirm)", environment="production", criticality="high",
                                check_mode="planned", authorized=False, enabled=False,
                                notes="Not connected and never probed. Requires written authorization and an agreed health endpoint."))
    db.flush()
    for s in db.execute(select(MonitoredService).where(MonitoredService.tenant_id == t.id,
                                                       MonitoredService.check_mode == "in_process")).scalars():
        for _ in range(3):
            monitoring.run_check(db, s)
    evaluation.run_eval(db, t)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="drop all tables and recreate before seeding")
    ap.add_argument("--force", action="store_true", help="allow seeding when APP_ENV=production")
    args = ap.parse_args(argv)
    s = get_settings()
    if s.is_production and not args.force:
        print("Refusing to seed demo data in production (use --force only for a staging copy).")
        return 2
    if args.reset:
        Base.metadata.drop_all(engine)
        from alembic import command
        from alembic.config import Config
        from .config import BACKEND_DIR
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        command.upgrade(cfg, "head")
    with SessionLocal() as db:
        if db.execute(select(Tenant)).first():
            print("Database already seeded. Use --reset to recreate demo data.")
            return 0
    n = seed_all()
    print(f"Seed complete: {len(S.TENANTS)} tenants, {n} grievances. Test account password: {DEMO_PASSWORD}")
    return 0


def seed_all() -> int:
    rng = random.Random(20261018)
    with SessionLocal() as db:
        seed_global(db)
        for spec in S.TENANTS:
            seed_tenant(db, spec, rng)
        db.commit()
        return db.query(Grievance).count()


if __name__ == "__main__":
    sys.exit(main())
