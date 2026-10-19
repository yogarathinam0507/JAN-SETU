# Database

- **Migrations:** `backend/migrations/` (Alembic). Apply with `cd backend && alembic upgrade head`.
  Initial schema: `backend/migrations/versions/0001_initial_schema.py`.
- **Seed / demo data:** `backend/app/seed.py` (deterministic) using configuration in `backend/app/data/seed_data.py`.
  Run `python -m app.seed` (or `--reset`). Refuses to run when `APP_ENV=production`.
- **Engines:** SQLite (default, `backend/data/jansetu.db`) and PostgreSQL (`DATABASE_URL=postgresql+psycopg://...`), both tested.
