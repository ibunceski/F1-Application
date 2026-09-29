# ML experiment design

This document describes the methodology represented by the authoritative thesis experiment, `f1-2025holdout-20260831T185450Z`. The study compares driver-race predictions across pre-qualifying and post-qualifying information sets. The research questions are which model families outperform simple baselines, how qualifying information changes performance, and whether validation-selected models retain useful performance in a later completed season.

## Targets and eligibility

| Task | Target | Primary selection metric |
| --- | --- | --- |
| Finishing position | Ingested finishing position | MAE, lower is better |
| Top 10 | Finishing position <= 10 | ROC-AUC, higher is better |
| Podium | Finishing position <= 3 | PR-AUC (average precision), higher is better |
| Position gain/loss | Official grid position minus finishing position | MAE, lower is better |

Training uses rows with a non-null task target; post-qualifying rows additionally require a qualifying position. Missing historical predictors remain a training-fold imputation concern. A positive gain/loss value means positions gained. Official grid is used to define the gain/loss outcome; it is not included as an additional predictor. Incidents and non-finishes are not removed simply to improve reported errors.

Feature-row counts and eligible evaluation counts differ. The saved 2025 holdout has 472 valid pre-qualifying rows and 478 post-qualifying rows. A direct context comparison uses their intersection of 471 driver-race rows. Never compare a common-subset model score with a full-population baseline score as though they used the same records.

## Features available at prediction time

| Feature | Pre-qualifying | Post-qualifying |
| --- | --- | --- |
| `avg_race_pace_ms` | Included | Included |
| `driver_recent_form` | Included | Included |
| `team_recent_form` | Included | Included |
| `circuit_history_avg_finish` | Included | Included |
| `circuit_history_dnf_rate` | Included | Included |
| `dnf_rate_recent` | Included | Included |
| `qualifying_position` | Excluded | Included |
| `gap_to_pole_ms` | Excluded | Included |
| `grid_position` | Excluded | Excluded |
| Target-race weather | Excluded | Excluded |

Pace and form use only prior races. Circuit history matches circuit location and country, rather than year-dependent sponsored event names. DNF features interpret provider status/classification text rather than treating every numeric finishing order as a finish. Pre-qualifying entry/team assumptions derive from earlier available data and may miss late changes.

Post-qualifying feature construction uses the qualifying-position proxy consistently for historical/upcoming rows, with a source marker in the schema. The fitted model consumes `qualifying_position` once; duplicating it as `grid_position` would repeat the same signal. Grid penalties or subsequent starting-order changes are outside this information set.

Target-race weather is excluded because the stored observations do not establish a forecast available at prediction cutoff. Missing values are imputed inside each training pipeline. The thesis snapshot contains no 2022 lap data, so missing historical pace values depend on training-fold medians.

## Temporal development and holdout

The completed development seasons are 2021–2024. The held-out season is 2025; incomplete 2026 observations are not thesis evaluation evidence.

| Fold | Training seasons | Validation season |
| --- | --- | --- |
| 1 | 2021 | 2022 |
| 2 | 2021, 2022 | 2023 |
| 3 | 2021, 2022, 2023 | 2024 |

The runner checks season completeness using stored schedules, dates, results, and qualifying coverage before accepting the partitions. This is an audit of the ingested data, not a guarantee that a later upstream download will have the same contents.

Use `--min-train-seasons 1`; the default of 3 produces only one outer fold for this development period. Hyperparameter selection uses expanding inner splits confined to the current training seasons and bounded search spaces in `hyperparameter_search.py`. The earliest outer fold has one training season and cannot support a season-based inner split; the code uses its documented fallback configuration.

Champions are selected separately for all eight context/task combinations by mean outer-validation primary metric, with a simpler-model tie-break. Final refit parameters are selected using expanding inner validation across the full development pool. The holdout is used for evaluation of frozen champions and domain baselines, not to select an alternative champion.

## Models and baselines

- Position: Ridge, ElasticNet, Random Forest, XGBoost, LightGBM, OrdinalRidge, LogisticAT, LGBMRank, and XGBRank.
- Gain/loss: linear and tree regressors.
- Classification: Logistic Regression, Random Forest, XGBoost, LightGBM, and calibrated Random Forest/LightGBM variants.
- Baselines: training median for pre-qualifying position, qualifying position for post-qualifying position, class prevalence for classification, and zero change for gain/loss.

Rankers group rows by race. Better finishing positions receive greater relevance labels; higher predicted scores map to better predicted ranks. Custom estimators have stable import paths in `app/ml/`.

Classification thresholds maximize F1 on the last inner training season, without using outer validation/holdout labels. Threshold candidates run from 0.05 to 0.95; ties choose the first (lower) threshold. When no valid inner threshold split exists, the fallback is 0.5. Calibrated classifiers use internal `cv=3` within training data; this is not chronological calibration and remains a limitation.

## Metrics and uncertainty

Regression also reports RMSE, R², race-wise Spearman, within-two-position accuracy, and gain/loss direction accuracy. Classification also reports PR-AUC/ROC-AUC, Brier score, log loss, precision, recall, F1, and accuracy.

Do not interchange these aggregations:
- Candidate selection: average of season-level outer-fold primary scores.
- Classification ROC/PR curves: pooled predictions for the indicated phase.
- Paired comparisons: race-level losses on the same races.
- Direct pre/post comparison: the intersection of available driver-race rows.

Saved statistical evidence uses 2,000 race-cluster bootstrap samples and 5,000 paired permutations with seed 42. Paired differences are champion minus runner-up: MAE for regression and Brier for classification. Negative differences favor the champion on the tested loss. A significant Brier difference is not proof of a significant ROC-AUC/PR-AUC advantage. The comparisons supplement validation selection and do not establish superiority against every candidate or correct for every multiple comparison.

## Reproducibility and artifacts

The frozen bundle is stored at:

```text
f1-platform/backend/models_store/experiments/f1-2025holdout-20260831T185450Z/
  manifest.json, config.json, report.md
  aggregate_results.csv, model_results.csv, final_holdout_results.csv
  out_of_fold_predictions.csv.gz
  calibration_predictions.csv.gz, reliability_bins.csv, significance.json
  ablations/                       # three result/prediction files
  champions/                       # eight joblibs and four metadata files
```

The manifest records seed 42, folds, feature columns, sample counts, data fingerprints, package versions, platform, and selected parameters. The runtime model store uses copies of the champion files at `backend/models_store/`; this implementation does not use a separate versioned `deployed/` directory.

The training Git commit/dirty state and original database snapshot were not captured in the published bundle. Consequently the saved predictions support evaluation checks, but a new ingestion/training run cannot be promised to reproduce the exact historical models. Future runs should capture source revision and schema/snapshot provenance without retroactively inventing it for this experiment.

The README provides the complete setup and training commands. New experiments get new IDs; the public frozen bundle and historical manifests must remain unchanged. Model Lab only reads persisted evidence.

## Limitations

The historical data covers a small number of seasons; drivers within races are correlated. Competitive order and regulations change. Missing 2022 lap data, entry-list assumptions, non-temporal internal calibration, and differences between qualifying and the final grid constrain the claims. Race strategy, weather changes, safety cars, and incidents are not observable at prediction time. Search across many candidates can overfit development evidence even with nested validation. Interpret results as retrospective predictive evidence, not causal effects or guaranteed future performance.
