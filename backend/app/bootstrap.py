"""First-start initialisation: migrate the schema and (in non-production) load demo data if the DB is empty.
This is what makes `python start.py` / `uvicorn app.main:app` work on a brand-new machine or host."""
import logging

from sqlalchemy import inspect, select

from .config import BACKEND_DIR, get_settings
from .db import SessionLocal, engine

log = logging.getLogger("jansetu.bootstrap")


def migrate() -> None:
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")


def init_db() -> dict:
    s = get_settings()
    result = {"migrated": False, "seeded": False}
    if not s.auto_init_db:
        return result
    migrate()
    result["migrated"] = True
    from .models import Tenant, User
    with SessionLocal() as db:
        empty = db.execute(select(Tenant)).first() is None
        # Test data from an earlier build (no officer designations, "(demo)" names): replace it with the current seed.
        stale = (not empty and not s.is_production and s.auto_seed_demo and
                 db.execute(select(User).where(User.is_demo.is_(True), User.designation != "")).first() is None and
                 db.execute(select(User).where(User.is_demo.is_(False), User.role != "citizen")).first() is None)
    if stale:
        from .models import Base
        log.warning("Old test data from an earlier version found - recreating the database with the current test data.")
        Base.metadata.drop_all(engine)
        with engine.begin() as conn:
            conn.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
        migrate()
        empty = True
    if empty and s.auto_seed_demo and not s.is_production:
        from .seed import seed_all
        seed_all()
        result["seeded"] = True
        log.info("Empty database - demo data loaded (password Demo@1234).")
    elif empty:
        log.warning("Database is empty. Create tenants/users or run `python -m app.seed` on a staging copy.")
    return result


def tables_exist() -> bool:
    return "tenants" in inspect(engine).get_table_names()
