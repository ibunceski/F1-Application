# F1 Race Prediction Platform

A full-stack Formula 1 analytics and prediction platform with FastAPI, PostgreSQL, FastF1 ingestion, machine learning pipelines, and a React dashboard for race analysis, tyre strategy, driver comparison, and model explanations.

## Architecture

```text
                +----------------+
                |   FastF1 API   |
                | historical F1  |
                +-------+--------+
                        |
                        v
+----------------+  +---+----------------+  +----------------+
| Ingestion CLI  +->+    PostgreSQL      +->+ Feature Eng.   |
| seasons/results|  | normalized schema  |  | ML feature rows|
+----------------+  +---+----------------+  +-------+--------+
                        ^                           |
                        |                           v
                  +-----+------+            +-------+--------+
                  | FastAPI    |<-----------+ Model Training |
                  | REST API   | predictions| joblib models  |
                  +-----+------+            +----------------+
                        |
                        v
                 +------+-------+
                 | React/Vite   |
                 | Dashboard    |
                 +--------------+
```

## Tech Stack

- Backend: FastAPI, Uvicorn, Pydantic Settings
- Database: PostgreSQL 16, SQLAlchemy 2.0, Alembic
- Data and ML: FastF1, pandas, NumPy, scikit-learn, XGBoost, LightGBM, joblib
- Frontend: React, TypeScript, Vite, React Query, Recharts, Tailwind CSS
- Containers: Docker, Docker Compose

## Setup

1. Clone the repository.

2. Copy the environment template and fill in local values:

```bash
cp .env.example .env
```

3. Start the database, backend, and frontend:

```bash
docker compose up --build -d
```

4. Run core ingestion:

```bash
docker compose run --rm ingestion python ingestion/ingest_core.py --seasons 2021 2022 2023 2024 2025 2026
```

5. Run result ingestion:

```bash
docker compose run --rm ingestion python ingestion/ingest_results.py --seasons 2021 2022 2023 2024 2025 2026
```

6. Refresh qualifying during a race weekend:

```bash
docker compose run --rm ingestion python ingestion/ingest_weekend.py --next-race
docker compose run --rm ingestion python ingestion/ingest_weekend.py --season 2026 --round 8
docker compose run --rm ingestion python ingestion/ingest_weekend.py --next-race --qualifying-only --generate-features
```

This weekend refresh only ingests qualifying data when it is available. It never ingests race results.

7. Run lap and weather ingestion:

```bash
docker compose run --rm ingestion python ingestion/ingest_laps.py --seasons 2021 2022 2023 2024 2025 2026
```

8. Run feature engineering:

```bash
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --seasons 2021 2022 2023 2024 2025 2026
```

Use `--context pre_qualifying` or `--context post_qualifying` to generate a single prediction context. The default generates both.

Target a specific race or the next upcoming race:

```bash
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --race-id 42 --context pre_qualifying
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --race-id 42 --context post_qualifying
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --next-race --context pre_qualifying
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --next-race --context post_qualifying --fallback-pre-qualifying
```

Use `--force` to regenerate existing feature rows for the same race and context.

9. Train models:

```bash
docker compose run --rm ingestion python ml_pipeline/train_models.py --context post_qualifying --train-seasons 2021 2022 2023 2024 --test-season 2025
```

Train a pre-qualifying model with `--context pre_qualifying`, or train both model families with `--context all`. When 2026 has final labels, promote it through the same CLI arguments, for example `--context all --train-seasons 2021 2022 2023 2024 2025 --test-season 2026`.

```bash
docker compose run --rm ingestion python ml_pipeline/train_models.py --train-seasons 2021 2022 2023 2024 --test-season 2025 --context pre_qualifying
docker compose run --rm ingestion python ml_pipeline/train_models.py --train-seasons 2021 2022 2023 2024 --test-season 2025 --context post_qualifying
docker compose run --rm ingestion python ml_pipeline/train_models.py --train-seasons 2021 2022 2023 2024 2025 --test-season 2026 --context all
```

10. Open the dashboard:

```text
http://localhost:5173
```

API documentation is available at:

```text
http://localhost:8000/api/docs
```

Next-race prediction endpoints:

```text
GET  /api/v1/predictions/next-race/context
POST /api/v1/predictions/next-race/generate
GET  /api/v1/predictions/next-race
GET  /api/v1/predictions/races/{race_id}/comparison
```

Health check:

```text
http://localhost:8000/health
```

Result, lap, and weather jobs skip upcoming races based on the current date. Future races are stored as calendar rows by core ingestion; pre-qualifying feature rows may be generated from prior weekends, while post-qualifying feature rows require qualifying data and no future row implies race results, lap data, weather data, or training labels exist.

## Predicting the Next Race

The next-race flow is date-driven and uses the race calendar stored in the database. Core ingestion must run through the current and future seasons so the next race exists even before qualifying or race results are available.

```bash
docker compose run --rm ingestion python ingestion/ingest_core.py --seasons 2021 2022 2023 2024 2025 2026
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --next-race --context pre_qualifying
docker compose run --rm ingestion python ml_pipeline/train_models.py --train-seasons 2021 2022 2023 2024 2025 --test-season 2026 --context all
```

During a race weekend, refresh qualifying without ingesting race results:

```bash
docker compose run --rm ingestion python ingestion/ingest_weekend.py --next-race --qualifying-only --generate-features
```

The frontend dashboard and `/predictions/next-race` page call:

```text
GET  /api/v1/predictions/next-race/context
POST /api/v1/predictions/next-race/generate
GET  /api/v1/predictions/next-race
```

With `context=auto`, the API uses `pre_qualifying` before qualifying exists and `post_qualifying` once qualifying rows exist.

## Pre-Qualifying vs Post-Qualifying Models

`pre_qualifying` predictions use only information available before the target weekend: previous race results, recent form, pace, reliability, team form, circuit history, and available weather context. Current-race grid, qualifying position, gap to pole, and race results must be null or excluded.

`post_qualifying` predictions use the same historical inputs plus current-race qualifying/grid fields. They still must not use race result labels, lap outcomes, points, or finishing positions from the target race.

Generate context-specific feature rows with:

```bash
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --next-race --context pre_qualifying
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --next-race --context post_qualifying --fallback-pre-qualifying
```

Train both model families with:

```bash
docker compose run --rm ingestion python ml_pipeline/train_models.py --train-seasons 2021 2022 2023 2024 2025 --test-season 2026 --context all
```

## Comparing Predictions to Actual Results

After a race has results, compare stored predictions with actual classifications:

```text
GET /api/v1/predictions/races/{race_id}/comparison?context=latest
```

The comparison endpoint returns summary metrics such as MAE, RMSE, top-10 accuracy, podium accuracy, and whether the predicted winner was correct. It does not mutate predictions. If race results are missing it returns a clear 400 response; if predictions are missing it returns a clear 404 response. The frontend comparison route is:

```text
/seasons/{year}/races/{race_id}/prediction-comparison
```

Verify future race handling:

```bash
docker compose run --rm ingestion python verification/verify_future_races.py
docker compose run --rm ingestion python verification/verify_prediction_contexts.py
docker compose run --rm ingestion python verification/verify_prediction_workflow_e2e.py
```

Frontend route smoke checks:

```bash
docker compose run --rm frontend npm run verify:prediction-routes
```

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `POSTGRES_DB` | Yes | PostgreSQL database name used by Docker Compose |
| `POSTGRES_USER` | Yes | PostgreSQL user used by Docker Compose |
| `POSTGRES_PASSWORD` | Yes | PostgreSQL password used by Docker Compose |
| `DATABASE_URL` | Yes | SQLAlchemy database URL for backend and CLI scripts |
| `API_KEY` | Production | Required for `X-API-Key` auth when `ENVIRONMENT=production` |
| `SECRET_KEY` | Yes | Application secret placeholder for production hardening |
| `ENVIRONMENT` | Yes | `development`, `production`, or `test` |
| `FASTF1_CACHE_PATH` | Yes | FastF1 cache directory inside the backend container |
| `MODELS_STORE_PATH` | Yes | Directory where trained model files are loaded from |
| `CORS_ORIGINS` | Yes | JSON list of allowed frontend origins |
| `VITE_API_URL` | Frontend | Frontend API base URL, configured in `frontend/.env.example` |

## Useful Commands

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose run --rm ingestion alembic upgrade head
```

The ingestion service is profile-gated under `tools`; `docker compose run ingestion ...` starts it on demand without keeping it running as part of the normal app stack.

## Known Limitations

- Cannot predict safety cars, red flags, or race incidents.
- Cannot account for in-race weather changes not present in qualifying.
- Strategy changes during the race are not modeled.
- New drivers with fewer than 5 races of history have less accurate predictions.
- Wet races have higher uncertainty due to fewer historical examples.
- Predictions are for analytical purposes only and are not betting guidance.
