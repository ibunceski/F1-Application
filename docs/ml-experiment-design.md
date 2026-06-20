# ML Experiment Design: F1 Race Predictions

## Purpose and thesis contribution

This thesis evaluates whether conventional linear models and tree-based machine-learning models can make reliable, **pre-race** driver-level predictions for four existing Formula 1 tasks.  The contribution is a reproducible, leakage-safe comparison of the same candidate model families across two information contexts, rather than a claim that one single algorithm universally predicts Formula 1 outcomes.

Each observation is a driver entered for a grand prix.  The prediction point is either before qualifying or after qualifying but before the race.  The study uses only information that was available at that prediction point and evaluates chronological generalisation to an entirely later, completed season.

### Research questions

1. Across the four prediction tasks, which candidate model families improve on no-skill baselines under chronological, rolling-origin validation?
2. How much does the post-qualifying information set improve predictive performance over the pre-qualifying information set for each task?
3. Do validation-selected models retain their performance and probability calibration on a final, unseen, completed season?
4. For the Top 10 and podium tasks, are the predicted probabilities sufficiently discriminative and calibrated to support the probabilities shown in the application?

The unit of analysis is a driver-race row, but uncertainty estimation and any significance-style comparison must be clustered by race because the drivers in a race are not independent observations.

## Targets: fixed definitions

No experiment may redefine, transform, or silently exclude a target beyond the eligibility rules below.  Target values are derived from `race_results`, exactly as in `backend/ml_pipeline/train_models.py` and `backend/ml_pipeline/feature_engineering.py`.

| Task | Stored/training target | Definition | Eligible rows |
| --- | --- | --- | --- |
| Finishing-position regression | `actual_finishing_position` | `race_results.finishing_position` | A non-null finishing position |
| Top 10 classification | `finished_top10` | 1 iff `finishing_position <= 10`; otherwise 0 when a race-result row exists | A race-result row |
| Podium classification | `finished_podium` | 1 iff `finishing_position <= 3`; otherwise 0 when a race-result row exists | A race-result row |
| Position gain/loss regression | `position_gain_loss` | `grid_position - finishing_position`; positive means positions gained, negative means lost | Non-null grid and finishing positions |

`finishing_position` is the ingested classified finishing order, not a rank reconstructed from model predictions.  In particular, the current outcome semantics for non-finishers are preserved.  All target eligibility counts, class prevalence, and missing-target counts must be reported by season, context, task, and fold.

## Information sets and feature availability

The existing `MLFeature.feature_context` is the authoritative context label.  A model trained for one context must never receive features from the other.

| Feature | Pre-qualifying | Post-qualifying | Existing source and availability condition |
| --- | --- | --- | --- |
| `grid_position` | Not available / excluded | Available | Historical rows use `race_results.grid_position`; this must be the official pre-race grid. |
| `qualifying_position` | Not available / excluded | Available | `qualifying_results.position`, available after qualifying. |
| `gap_to_pole_ms` | Not available / excluded | Available | Derived from qualifying results; pole is set to 0. |
| `avg_race_pace_ms` | Available | Available | Mean of the driver's median clean-lap pace over up to three races dated before the target race. |
| `driver_recent_form` | Available | Available | Mean finishing position over up to five prior races. |
| `team_recent_form` | Available | Available | Mean finishing position for the team over its three prior races. |
| `circuit_history_avg_finish` | Available | Available | Driver's earlier results at the same circuit; historical fallback is 10.5 if no history. |
| `circuit_history_dnf_rate` | Available | Available | Driver's earlier DNF rate at the same circuit. |
| `dnf_rate_recent` | Available | Available | Driver DNF rate over up to ten earlier races. |
| `weather_is_wet`, `avg_track_temp_c` | Conditional; see below | Conditional; see below | Currently derived from `weather_data` for the target `race_id`. |

Thus the current model columns are:

- **Pre-qualifying:** `avg_race_pace_ms`, `driver_recent_form`, `team_recent_form`, `circuit_history_avg_finish`, `circuit_history_dnf_rate`, `dnf_rate_recent`, `weather_is_wet`, `avg_track_temp_c`.
- **Post-qualifying:** the three qualifying/grid fields above plus all pre-qualifying columns.

### Availability controls and known parity issue

The historical feature functions use prior race dates for pace, form, DNF rate, and circuit history; that temporal condition is required in every experiment.  For pre-qualifying rows, the expected entry list and team mapping come from the latest prior completed race, so late driver/team changes are a limitation rather than information the model is allowed to infer.

The weather fields require a hard provenance check before thesis experiments.  `weather_features()` currently aggregates all `weather_data` for the target race without filtering to a pre-race timestamp or a forecast available at the cutoff.  If those rows include race-session weather, they leak outcome-time information.  Until a timestamped, pre-race forecast/qualifying-weather source is demonstrated, both weather fields must be **excluded from every thesis candidate in both contexts**.  This is a feature-eligibility correction, not a target change.

There is also an inference-parity risk to resolve before deployment: historical post-qualifying rows use the recorded final `race_results.grid_position`, while upcoming rows currently fall back to qualifying position.  The experiment manifest must record which value was used, and the implementation must either obtain the official grid before inference or train/evaluate with the same qualifying-position proxy.  It must not mix the two silently.

All imputation, scaling, class weighting, calibration, and feature selection belong inside a pipeline fit only on the training portion of each fold.  The current global median imputation needs to remain fold-local through the existing scikit-learn pipeline.

## Candidate model matrix

A separate model is fitted for each combination of context and target; there is no multi-task target sharing in this study.  Every candidate receives the same leakage-approved columns for the relevant context and the same fold splits.

| Task type | Candidate families | Baseline |
| --- | --- | --- |
| Finishing position and position gain/loss regression | Constant baseline; Ridge; ElasticNet; Random Forest Regressor; XGBoost Regressor; LightGBM Regressor | Training-fold median target.  A reported supplementary post-qualifying operational baseline may predict finishing position from grid position and gain/loss as zero, but it is not tuned. |
| Top 10 and podium classification | Constant-prior baseline; Logistic Regression; Random Forest Classifier; XGBoost Classifier; LightGBM Classifier | Training-fold positive-class prevalence as the probability; the decision threshold is selected only within training data. |

The fixed candidate list is deliberately shared across tasks so that comparison is fair.  Ridge/ElasticNet and Logistic Regression use standardized numerical inputs.  Tree models receive the same imputed inputs but do not require scaling; retaining a common preprocessing pipeline is acceptable provided transformations are fit only to the fold training data.  Random Forest, XGBoost, and LightGBM use seeded estimators and controlled parallelism.

## Metrics and decision thresholds

Metrics are calculated from out-of-fold predictions and then aggregated both over all eligible driver rows and as a mean of per-race values.  The latter and race-cluster bootstrap confidence intervals are mandatory because a single race supplies many correlated rows.

| Task | Primary comparison metric | Secondary metrics |
| --- | --- | --- |
| Finishing-position regression | MAE (positions) | RMSE, R², mean race-wise Spearman rank correlation, and exact/within-2-position accuracy |
| Position gain/loss regression | MAE (positions) | RMSE, R², mean race-wise Spearman correlation, and three-way direction accuracy (gain / unchanged / loss) |
| Top 10 classification | ROC-AUC | PR-AUC (average precision), Brier score, log loss, precision, recall, F1, and thresholded accuracy |
| Podium classification | PR-AUC (average precision) | ROC-AUC, Brier score, log loss, precision, recall, F1, and thresholded accuracy |

The positive class is always the named event (Top 10 or podium).  The podium class is rare, so PR-AUC is primary there; accuracy alone is not a valid selection metric.  Lower is better for MAE, RMSE, Brier score, and log loss; higher is better for all other metrics.

For a classifier, probability metrics use raw predicted probabilities.  A single operating threshold per task/context/model is selected using only inner training validation predictions (default objective: maximize F1; ties choose the lower false-positive rate).  That frozen threshold is applied unchanged to outer validation and final-holdout predictions.  Calibration curves and Brier score must be reported; optional probability calibration is permitted only as an additional pipeline component fit within the inner training data.

## Chronological validation and final evaluation

### Season-completeness gate

An evaluation season is eligible only when a versioned `validate_completed_season` check passes before any split is created.  In this repository the check should use `seasons.total_races`, `races`, `race_results`, `qualifying_results`, and the ingestion snapshot timestamp, and should fail closed when any condition fails:

1. The number of distinct stored races equals `seasons.total_races`, and every expected round is present exactly once.
2. Every race date is strictly before the snapshot/run date; no scheduled future event is included.
3. Every scheduled race has a complete result set: rows have a non-empty status and non-negative laps; the count is plausible for the event, target eligibility is non-zero, and no required race-result import failed.  The validator records counts rather than silently dropping sparse rounds.
4. For post-qualifying evaluation, every evaluated race also has a complete qualifying set and a recorded pre-race grid/qualifying feature for every eligible prediction row.
5. The imported round list and result-row counts are reconciled with the source schedule/results response captured in the data snapshot.  Any discrepancy is an explicit exclusion and invalidates use of the season as a final holdout until resolved.

The present reports name 2026 as the test season.  As of this design it is an in-progress season, so it must be excluded from all thesis validation and final-test folds.  The final holdout is the latest season that passes the gate—expected to be 2025 only after the gate succeeds.  If 2025 does not pass, use the most recent earlier passing season and document why.  Incomplete 2026 data may be used only for live, non-thesis inference demonstrations and must be labelled as such.

### Development model selection: expanding rolling origin

Let `H` be the reserved final completed season and let `C` be all completed seasons before `H`.  Order `C` chronologically.  Build expanding folds with a minimum of three completed training seasons:

```text
fold 1: train [C1, C2, C3]       -> validate C4
fold 2: train [C1, C2, C3, C4]   -> validate C5
...                               -> ...
```

If the available historical range does not permit this minimum, retain the earliest feasible expanding split, report the reduced evidence, and do not replace it with random cross-validation.  A validation fold contains all eligible driver-race rows from its validation season; no rows from a later season may appear in that fold's training, feature fitting, threshold selection, or imputation.

For each outer development fold, hyperparameters are selected using only an expanding inner split of that fold's training seasons.  The outer validation season is used solely for the fixed selected configuration.  The reported development score for a candidate is the mean and dispersion over outer folds, with the pooled out-of-fold prediction table retained for audit.

### Final held-out completed-season evaluation

`H` is never used to choose a feature set, algorithm, hyperparameter, probability threshold, calibration setting, or champion.  After all choices are frozen, refit each frozen candidate configuration on every completed season before `H`, generate one set of predictions for `H`, and publish the full metric table, per-race metrics, calibration plots, and race-cluster bootstrap 95% confidence intervals.

The final table may compare all frozen candidates, but it is confirmatory/descriptive only.  It must never be used to replace a development-selected winner with a model that happened to score better on `H`.

## Hyperparameter-selection rules

1. Define bounded search spaces and a search budget before the run; store them in the experiment configuration.  Linear models include regularization strength and ElasticNet mixing; forests include trees, depth, leaf size, and feature sampling; boosters include estimators, depth/leaves, learning rate, subsampling, and regularization.
2. Use the identical inner chronological splits and search budget for comparable candidates in one task/context.  Optimise the task's primary metric; probability classifiers may use a secondary Brier-score tie-break.
3. Do not inspect, tune on, calibrate on, or pick a threshold from the final holdout.  Do not tune separately on each test race.
4. For each context/task, choose the family and configuration by mean outer-development primary score.  If scores are within a predeclared practical tolerance, choose the simpler model (baseline, then linear/logistic, then forest, then booster) and record the tie.
5. Missing-data and class-prevalence diagnostics are calculated within each training fold.  Class weights, if used, are derived from that fold only.

## Reproducibility and artifacts

Every run receives an immutable `experiment_id`, for example `f1-2025holdout-20260620T120000Z-gitabc1234`, and persists its complete configuration before fitting.  A valid thesis result is reproducible from the same database snapshot, code commit, package lock, and random seeds.

Required controls:

- Use one recorded master seed and derived per-fold/per-model seeds for Python, NumPy, scikit-learn, XGBoost, LightGBM, and any search sampler.  Record worker counts and deterministic settings; use one worker where a library cannot provide reproducible parallel execution.
- Capture the Git commit (and dirty-worktree state), Python version/platform, and the exact package versions.  `backend/requirements.txt` currently pins the core ML stack and should remain part of the manifest.
- Capture a data snapshot/fingerprint before splitting: database schema/Alembic revision; snapshot timestamp; season/race/result/qualifying/feature row counts; allowed seasons; ordered primary keys with relevant `generated_at`/`data_cutoff_date`; and a SHA-256 of canonical exported training rows, target eligibility masks, and approved feature columns.  Never record secrets or database credentials.
- Persist exact folds, target definitions, feature policy (including the weather decision), search spaces, selected parameters, fitted thresholds/calibrators, metrics, predictions, and failure/exclusion logs.

Recommended layout, rooted at the existing backend model store:

```text
backend/models_store/
  experiments/<experiment_id>/
    manifest.json                 # commit, package versions, seeds, data fingerprint
    config.json                   # targets, feature policy, candidate matrix, search spaces
    season_completeness.json
    splits.json
    development/<context>/<task>/
      candidate_summary.csv
      fold_metrics.csv
      oof_predictions.parquet
      selected_config.json
    final_holdout/<context>/<task>/
      metrics.json
      predictions.parquet
      calibration.json
      bootstrap_intervals.json
    champions/<context>_<task>.joblib
    champions/metadata.json
  deployed/<deployment_id>/
    pre_qualifying_position_model.joblib
    pre_qualifying_top10_model.joblib
    pre_qualifying_podium_model.joblib
    pre_qualifying_position_gain_model.joblib
    post_qualifying_position_model.joblib
    post_qualifying_top10_model.joblib
    post_qualifying_podium_model.joblib
    post_qualifying_position_gain_model.joblib
    pre_qualifying_model_metadata.json
    post_qualifying_model_metadata.json
```

The deployment directory deliberately retains the filenames expected by `app/ml/model_loader.py`.  `metadata.json` must expose the experiment ID, data fingerprint, context, task, selected algorithm/configuration, development and final metrics, eligibility policy, and calibration/threshold so FastAPI and React never display an unexplained timestamp as a model version.

## Champion and deployment decision

A **champion is selected separately for each of the eight context-task combinations**.  It is the frozen configuration with the best primary rolling-origin development score, subject to the predeclared practical-tie rule.  The final holdout is a one-time confirmation, not a selector.

Promotion to `deployed/<deployment_id>` additionally requires all of the following:

- the season-completeness and feature-availability checks pass;
- no leakage-policy violation is recorded;
- the candidate is at least as good as the baseline on the primary final-holdout metric within its race-cluster bootstrap interval, with the minimum practical improvement declared before the run;
- classification champions meet an explicit calibration gate (reported Brier score and calibration curve; any acceptance bound is declared before the run);
- the artifact and metadata load successfully through the existing FastAPI `ModelStore` contract.

If the gate fails, the development champion is still reported as a research result, but the production deployment remains on the previous approved artifact (or the baseline if no approved artifact exists).  The deployment is a versioned set of four models per context, so the API never mixes models from different experiments without an explicit recorded decision.

## Limitations and threats to validity

- Formula 1 races are strongly affected by safety cars, red flags, collisions, reliability failures, strategy, and intra-race weather; these are not observed at the prediction cutoff.
- The sample is small at the season level, regulations and competitive order change, and observations within a race are dependent.  Chronological folds reduce but cannot remove distribution shift.
- Podium events are rare, making variance high and naive accuracy misleading; confidence intervals and PR-AUC are essential.
- The data sources, missing lap data, driver substitutions, team changes, and circuit-name matching can introduce measurement error or selection bias.  Early-career drivers have limited prior history.
- The current target-race weather aggregation and historical-grid/upcoming-qualifying mismatch are concrete leakage/parity threats and must be resolved as described above before results are claimed as pre-race performance.
- Hyperparameter search across several families can overfit the available development seasons.  Predeclared search budgets, nested chronological validation, a reserved completed season, and a simpler-model tie rule mitigate but do not eliminate this risk.
- Results generalise only to the defined data snapshot, eligible seasons, and target semantics.  They are analytical forecasts, not betting advice or causal claims.

## Implementation plan (no code changes in this design step)

1. Extend `backend/ml_pipeline/train_models.py` with an experiment runner that implements the completeness gate, approved feature policy, nested expanding folds, the full candidate matrix, metrics, and artifact layout.  Keep the four existing targets unchanged.
2. Add a reusable season/data-fingerprint validator alongside `backend/ingestion/ingest_core.py`, `backend/ingestion/ingest_results.py`, and `backend/ml_pipeline/feature_engineering.py`; then make training fail closed for incomplete seasons and weather/provenance violations.
3. Align and test the feature contract in `backend/ml_pipeline/feature_engineering.py` and `backend/app/services/prediction_service.py`, especially weather cutoff provenance and the historical-vs-upcoming post-qualifying grid semantics.
4. Update `backend/app/ml/model_loader.py`, prediction metadata schemas/routes, and `backend/app/services/prediction_service.py` to load a versioned deployed experiment and expose champion, data-fingerprint, context, threshold, and evaluation metadata.
5. Update `frontend/src/types/index.ts`, `frontend/src/pages/ModelExplanation/*`, and `frontend/src/pages/PredictionComparison/*` to show the experiment ID, held-out completed season, primary/secondary metrics, calibration status, and context-specific champion—without presenting incomplete 2026 evaluation as thesis evidence.
