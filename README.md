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
docker-compose up --build -d
```

4. Run core ingestion:

```bash
docker-compose run --rm ingestion python ingestion/ingest_core.py --seasons 2021 2022 2023 2024
```

5. Run result ingestion:

```bash
docker-compose run --rm ingestion python ingestion/ingest_results.py --seasons 2021 2022 2023 2024
```

6. Run lap and weather ingestion:

```bash
docker-compose run --rm ingestion python ingestion/ingest_laps.py --seasons 2021 2022 2023 2024
```

7. Run feature engineering:

```bash
docker-compose run --rm ingestion python ml_pipeline/feature_engineering.py --seasons 2021 2022 2023 2024
```

8. Train models:

```bash
docker-compose run --rm ingestion python ml_pipeline/train_models.py --train-seasons 2021 2022 2023 --test-season 2024
```

9. Open the dashboard:

```text
http://localhost:5173
```

API documentation is available at:

```text
http://localhost:8000/api/docs
```

Health check:

```text
http://localhost:8000/health
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
docker-compose ps
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose run --rm ingestion alembic upgrade head
```

The ingestion service is profile-gated under `tools`; `docker-compose run ingestion ...` starts it on demand without keeping it running as part of the normal app stack.

## Known Limitations

- Cannot predict safety cars, red flags, or race incidents.
- Cannot account for in-race weather changes not present in qualifying.
- Strategy changes during the race are not modeled.
- New drivers with fewer than 5 races of history have less accurate predictions.
- Wet races have higher uncertainty due to fewer historical examples.
- Predictions are for analytical purposes only and are not betting guidance.
