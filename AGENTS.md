# AGENTS.md

Targeted guidance for Codex sessions working on this repository.

## Project snapshot

This is **ApexInsight / F1 Race Prediction Platform**, a full-stack Formula 1 analytics and race-prediction application.

High-level flow:

```text
FastF1 / Jolpica data
  -> ingestion CLIs
  -> PostgreSQL normalized F1 schema
  -> ML feature engineering
  -> temporal ML experiments and joblib champions
  -> FastAPI prediction/model-lab APIs
  -> React/Vite dashboard
```

Main stack:

- Backend: FastAPI, SQLAlchemy 2.0, Alembic, Pydantic Settings.
- Database: PostgreSQL 16 via Docker Compose.
- Data/ML: FastF1, Jolpica fallback in selected ingestion paths, pandas, NumPy, scikit-learn, XGBoost, LightGBM, joblib, matplotlib.
- Frontend: React 18, TypeScript, Vite, React Query, Recharts, Tailwind CSS.
- Container workflow: `f1-platform/docker-compose.yml`.

## Important directories

- `f1-platform/backend/app/`: FastAPI application.
  - `main.py`: app setup, health endpoint, router registration.
  - `routers/`: API route modules. Key routes include seasons, races, analysis, predictions, model lab.
  - `services/`: business logic for API endpoints.
  - `models/`: SQLAlchemy ORM models.
  - `schemas/`: Pydantic API schemas.
  - `ml/model_loader.py`: loads deployed joblib models and metadata.
  - `ml/baseline_models.py`: stable import location for simple baseline regressors used by joblib artifacts.
- `f1-platform/backend/ingestion/`: data ingestion CLIs.
  - `ingest_core.py`: seasons, races, teams, drivers.
  - `ingest_results.py`: qualifying and race results; includes fallback behavior for race results.
  - `ingest_laps.py`: lap and weather data.
  - `ingest_weekend.py`: safe refresh for upcoming weekend data without race-result ingestion.
- `f1-platform/backend/ml_pipeline/`:
  - `feature_engineering.py`: builds `MLFeature` rows for pre/post qualifying contexts.
  - `train_models.py`: reproducible temporal experiment runner, model training, metrics, artifacts, figures.
- `f1-platform/backend/models_store/`:
  - root files are deployed model artifacts loaded by the app.
  - `experiments/<experiment_id>/` contains immutable thesis/model-lab experiment artifacts.
- `f1-platform/frontend/src/`: React dashboard.
  - `api/`: API clients.
  - `pages/ModelLab/`: read-only persisted experiment UI.
  - `pages/RacePredictor/`, `NextRacePrediction/`, `PredictionComparison/`: prediction workflows.
  - `pages/RaceAnalysis/`, `TyreStrategy/`, `DriverComparison/`, `SeasonOverview/`: analytics pages.
- `docs/`: project and thesis documentation.
  - `ml-experiment-design.md`: authoritative intended thesis experiment methodology.
  - `model-lab-api.md`: read-only Model Lab API contract.
  - `final-experiment-results.md`: current final thesis experiment summary.

## Run location and Docker workflow

Run Docker Compose commands from:

```powershell
cd f1-platform
```

Common commands:

```powershell
docker compose up --build -d
docker compose ps
docker compose logs -f backend
docker compose run --rm ingestion alembic upgrade head
```

Core ingestion:

```powershell
docker compose run --rm ingestion python ingestion/ingest_core.py --seasons 2021 2022 2023 2024
docker compose run --rm ingestion python ingestion/ingest_results.py --seasons 2021 2022 2023 2024
docker compose run --rm ingestion python ingestion/ingest_laps.py --seasons 2021 2022 2023 2024
```

Feature engineering:

```powershell
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --seasons 2021 2022 2023 2024 --force
```

Thesis-style training command pattern:

```powershell
docker compose run --rm ingestion python ml_pipeline/train_models.py `
  --train-seasons 2021 2022 2023 2024 `
  --evaluation-seasons 2025 `
  --min-train-seasons 1 `
  --context all `
  --seed 42 `
  --artifact-output-dir models_store `
  --model-output-dir models_store `
  --generate-plots
```

The local backend `.venv` may not be reliable in Codex sessions. Prefer Docker for Python verification.

## Verification commands

Backend unit tests:

```powershell
docker compose exec -T backend python -m unittest tests.test_ingest_results tests.test_train_models_experiment tests.test_model_lab_api
```

Model-load smoke test:

```powershell
docker compose exec -T backend python -c "from app.ml.model_loader import load_all_models; load_all_models(); print('models load successfully')"
```

Frontend:

```powershell
docker compose exec -T frontend npm run build
docker compose exec -T frontend npm run lint
docker compose exec -T frontend npm run verify:prediction-routes
```

Use only the checks relevant to the change. Long ingestion/training runs need user approval when they require Docker/network access.

## Current thesis/ML context

The project predicts four driver-race targets in two information contexts:

- Contexts:
  - `pre_qualifying`
  - `post_qualifying`
- Targets:
  - finishing position regression
  - top-10 classification
  - podium classification
  - position gain/loss regression

Feature policy from `docs/ml-experiment-design.md`:

- Pre-qualifying excludes qualifying/grid features.
- Post-qualifying includes `grid_position`, `qualifying_position`, and `gap_to_pole_ms`.
- Historical features must be temporal: only prior races may feed form, pace, DNF rate, and circuit history.
- Weather fields are a known leakage risk unless proven to be available pre-race; thesis experiments should exclude them unless the provenance issue is explicitly resolved.
- Final holdout should be a completed season only. Incomplete future/current seasons must not be used as thesis validation/test evidence.

Current reported final experiment:

- Authoritative experiment ID: `f1-2025holdout-20260829T172358Z`
- Development seasons: `2021, 2022, 2023, 2024`
- Final held-out season: `2025`
- Seed: `42`
- Rolling validation folds: 3 (train→validate: 2021→2022, 2021-2022→2023, 2021-2023→2024)
- To reproduce the three-fold design, use `--min-train-seasons 1` (default `3` only produces one fold; `2` produces two folds at 2023/2024). The rebuild script and the thesis training command below already use `--min-train-seasons 1`.
- Reason 2026 was omitted: it was incomplete/in-progress at the time and must not be used as thesis holdout evidence.
- Previous experiments `thesis-final-2025-holdout-20260620-r3` (trained on 2021, 2023, 2024 only) and `f1-2025holdout-20260828T203629Z` (two-fold) are preserved in `models_store/experiments/` as historical references. They were superseded after 2022 race results were recovered via Jolpica fallback and re-ingested, and after the stale-feature-row fix below.

## 2022 season issue and fix notes

2022 was not deliberately skipped by the app. It was excluded by the ML completeness gate because the database had:

- 2022 qualifying rows present.
- 2022 race-result rows missing.

Observed root cause:

- `ingestion_results.log` showed `Season 2022: 440 qualifying results, 0 race results saved`.
- FastF1 race-result loading failed with `KeyError: 'DriverNumber'`.
- Before the fix, `ingest_race_results()` only tried the Jolpica fallback after a successful FastF1 session load with incomplete results. If `session.load()` itself raised, the outer exception returned `0`, so fallback was never reached.

Fix implemented in code:

- `f1-platform/backend/ingestion/ingest_results.py` now falls back to Jolpica when FastF1 race-result loading fails or is incomplete.
- Sprint points are applied to both FastF1 rows and fallback rows.
- `f1-platform/backend/tests/test_ingest_results.py` covers the FastF1-load-fails/Jolpica-fallback path.

2022 was subsequently re-ingested via the Jolpica fallback and is now included in the full ML process (see "Current reported final experiment"). Note that 2022 still has no lap data, so `avg_race_pace_ms` is median-filled for 2022 rows.

### Stale feature-row fix

`feature_engineering.py --force` previously upserted regenerated rows but never deleted rows whose entry disappeared (e.g. after 2022 race results were recovered, the pre-qualifying entry list for some 2022 races shrank). This left stale `MLFeature` rows that leaked into training. The fix in `process_race` deletes all `MLFeature` rows for the race/context before regenerating, so the snapshot always matches the current entry lists. Re-run feature engineering with `--force` after any re-ingestion.

## Joblib baseline model loading issue

The backend previously failed health checks because deployed joblib artifacts referenced baseline classes serialized from a script run as `__main__` / `__mp_main__`, e.g. `ZeroChangeRegressor`.

Fix implemented:

- Stable baseline classes live in `f1-platform/backend/app/ml/baseline_models.py`.
- `ml_pipeline/train_models.py` imports those classes from that stable module.
- `app/ml/model_loader.py` registers compatibility aliases for legacy `__main__` / `__mp_main__` joblib artifacts before loading.

If backend health fails during model loading, check:

```powershell
docker compose logs backend
docker compose exec -T backend python -c "from app.ml.model_loader import load_all_models; load_all_models(); print('models load successfully')"
```

Pydantic warnings about `model_*` protected namespaces are warnings, not the root cause of that historical unhealthy-container failure.

## Model Lab contract

The Model Lab API is read-only and exposes persisted experiment evidence under:

```text
f1-platform/backend/models_store/experiments/<experiment_id>/
```

Do not make Model Lab routes retrain models, load joblibs for inference, write artifacts, or mutate deployed state. It should list/parse/report persisted experiment metadata, results, ablations, and artifact inventories.

Main endpoints under `/api/v1/model-lab`:

- `/experiments`
- `/overview`
- `/results`
- `/ablations`
- `/artifacts`

See `docs/model-lab-api.md` for exact contract.

## Frontend notes

The frontend is a Vite/React dashboard. Main pages include:

- Season overview
- Race analysis
- Tyre strategy
- Driver comparison
- Race predictor
- Next race prediction
- Prediction comparison
- Model explanation
- Model Lab

Some season lists may be hardcoded in UI components. Known locations that have contained season arrays:

- `f1-platform/frontend/src/components/layout/Sidebar.tsx`
- `f1-platform/frontend/src/pages/DriverComparison/ComparisonSelector.tsx`

Before changing season availability, confirm whether the backend data exists and whether the frontend is using API-driven or hardcoded season choices.

## Working conventions for future Codex sessions

- Prefer `rg` / `rg --files` for searches.
- Use Docker-based Python commands rather than the local virtualenv unless the venv is confirmed working.
- Use `apply_patch` for file edits.
- Preserve existing user changes; do not clean, reset, or overwrite unrelated work.
- Do not commit, push, or modify global Git config unless the user explicitly asks.
- If Git reports "dubious ownership," do not automatically run `git config --global --add safe.directory ...`; ask first if Git operations are necessary.
- Ingestion/training can be slow and may require network access. Explain the scope before running long data jobs.
- Treat `models_store/experiments/*` as reproducibility artifacts. Do not delete old experiment directories unless explicitly requested.
- If changing ML behavior, update or add tests and record whether deployed model artifacts must be regenerated.
- If changing API schemas, check corresponding frontend types/API clients.

## Compact project summary for handoff

This repository is an F1 analytics and prediction platform. It ingests historical F1 data into PostgreSQL, engineers pre-qualifying and post-qualifying driver-race feature rows, trains chronological ML experiments for finishing position/top-10/podium/gain-loss, serves deployed model predictions through FastAPI, and displays analysis/model evidence in a React dashboard. The thesis methodology emphasizes leakage-safe temporal validation, completed-season holdout evaluation, reproducible artifacts, and careful separation of pre- vs post-qualifying information.

The most important current operational context is that the reported final thesis experiment is `f1-2025holdout-20260829T172358Z`, trained on `2021, 2022, 2023, 2024` with 2025 held out, using three rolling validation folds (2022/2023/2024) via `--min-train-seasons 1`. The 2022 season is now fully included: it was originally excluded because race results were missing after a FastF1 `DriverNumber` load failure, and the ingestion code now falls back to Jolpica when FastF1 race-result loading fails. Feature engineering with `--force` deletes stale rows before regenerating, so the feature snapshot always matches the current entry lists.
