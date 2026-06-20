# Model Lab API

The read-only Model Lab API exposes persisted experiment evidence under `models_store/experiments/<experiment_id>/`. It never loads a joblib model for inference, retrains a model, writes an artifact, or changes the existing prediction API.

All routes are under `/api/v1/model-lab` and have typed request/response schemas in the OpenAPI document at `/api/openapi.json`.

## Latest successful experiment

For routes with an optional `experiment_id`, omitting it resolves the **latest successful** experiment. A directory is successful only when its `manifest.json` is valid, declares a completed (or legacy-compatible absent) status, contains valid contexts and a final evaluation season, and contains the required candidate artifact files: `manifest.json`, `aggregate_results.csv`, `model_results.csv`, and `out_of_fold_predictions.csv.gz`.

The newest valid `completed_at` timestamp wins; the experiment ID is a deterministic tie-breaker. Malformed directories are listed with status `malformed`, are never selected as latest, and produce a 422 response if requested explicitly. Missing experiment IDs produce 404 responses.

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET /experiments` | Lists valid and malformed artifact directories and identifies the latest successful ID. |
| `GET /overview?experiment_id=` | Returns methodology/configuration, data provenance summary, validation champions, and the candidate leaderboard. |
| `GET /results?experiment_id=&task=&context=&algorithm=&evaluation_season=` | Filters candidate-model fold/final results. |
| `GET /ablations?experiment_id=&task=&context=&algorithm=` | Returns context-specific feature sets and feature-ablation leaderboard rows. |
| `GET /artifacts?experiment_id=` | Lists safe relative-path metadata for tables, reports, figures, and model artifacts; it does not serve file contents. |

`task` and `context` use typed OpenAPI enums. Unknown enums are rejected by FastAPI validation. Experiment IDs are constrained to one artifact-directory name, preventing path traversal.
