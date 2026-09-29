# Repository guidance

## Project

ApexInsight is a BSc thesis F1 analytics and prediction platform:

`FastF1/Jolpica -> PostgreSQL -> temporal features -> ML experiments -> FastAPI -> React/Vite`.

Run Docker Compose commands from `f1-platform/`. Prefer Docker for Python checks; the local virtual environment is not the supported verification environment.

## Important paths

- `f1-platform/backend/app/`: API, services, schemas, ORM models, and inference.
- `f1-platform/backend/ingestion/`: data acquisition and Jolpica fallback.
- `f1-platform/backend/ml_pipeline/`: features, training, statistics, and artifact-only figures.
- `f1-platform/backend/alembic/`: database migrations.
- `f1-platform/backend/tests/`, `verification/`: regression and workflow checks.
- `f1-platform/frontend/src/`: dashboard pages, API clients, and types.
- `docs/ml-experiment-design.md`: implemented methodology and limitations.
- `docs/final-experiment-results.md`: authoritative results and provenance.
- `docs/model-lab-api.md`: persisted-evidence API contract.

## Authoritative thesis experiment

The public thesis bundle is `f1-2025holdout-20260831T185450Z`, under `backend/models_store/experiments/`. It contains 25 immutable files, including eight champions and four metadata/importance files. Runtime copies live at the model-store root and are ignored.

Development seasons: 2021–2024. Rolling folds: 2021 -> 2022, 2021–2022 -> 2023, 2021–2023 -> 2024. Final holdout: completed season 2025. Seed: 42. Use `--min-train-seasons 1` to obtain all three folds.

Earlier August 29 experiments are superseded historical runs, not current thesis evidence. Never relabel historical manifests or overwrite the frozen public bundle.

Feature contract:
- Both contexts use six historical features: pace, driver/team form, circuit finishing/DNF history, and recent DNF rate.
- Post-qualifying adds only `qualifying_position` and `gap_to_pole_ms`.
- `grid_position` is not an additional model predictor. Official grid still participates in the gain/loss target.
- Weather is excluded without proven pre-race provenance.
- Historical features must use races dated before the target race.
- Imputation, tuning, and threshold selection must stay within training data.

The 2022 results were recovered using Jolpica after FastF1 result loading failed. The thesis snapshot still lacks 2022 lap data. Feature engineering with `--force` deletes old race/context rows before regeneration; use it after re-ingesting results.

The manifest lacks a training Git commit/dirty-state record and the original database snapshot is not published. Do not claim exact historical retraining from live upstream data.

## Model and API contracts

Serialized custom estimators belong in stable modules under `app/ml/`, not script entry points. Keep legacy baseline compatibility in `model_loader.py`.

Model Lab is read-only: parse persisted artifacts only. Do not load joblibs for inference, retrain, write artifacts, or change deployed state from its endpoints. Select the thesis experiment explicitly when reproducing results; later local runs may become the default latest experiment.

If API schemas change, check frontend types and API clients. Before changing season availability, inspect backend data and hardcoded frontend choices.

## Verification

From `f1-platform/`:

```powershell
docker compose exec -T backend python -m unittest discover -s tests
docker compose exec -T frontend npm run lint
docker compose exec -T frontend npm run build
docker compose exec -T frontend npm run verify:prediction-routes
```

Run the five scripts in `backend/verification/` when prediction workflows change. See the README for commands and the eight-model load check.

Long ingestion/training runs require explicit authorization and a scope explanation. Do not run database resets as a test.

## Working conventions

- Use `rg` for searches and targeted patches for edits.
- Preserve existing local changes and research material.
- Keep caches, dependencies, backups, document workspaces, and older runs local.
- Do not commit, push, amend, rewrite history, create remote objects, or change Git author/committer configuration without explicit user instructions.
- Do not add author/co-author/sign-off attribution on anyone's behalf.
- Use only a per-command safe-directory override for authorized Git operations; do not change global Git configuration.
- Tests accompany ML behavior changes. State whether model regeneration is required.
- Preserve submitted thesis documents. Repository cleanup does not authorize revising the submitted thesis.
