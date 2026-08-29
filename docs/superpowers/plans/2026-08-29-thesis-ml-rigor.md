# Thesis ML Rigor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing F1 prediction ML pipeline into a rigorous, statistically-defensible experimental framework suitable for a bachelor's thesis.

**Architecture:** Add a leakage-safe statistical-evaluation module (race-cluster bootstrap + paired significance tests), a nested hyperparameter-search layer with predeclared budgets, ordinal/ranking and calibrated candidate models, and two leakage/parity fixes (grid proxy + weather removal). All results flow into new artifacts (`significance.json`, selected-config records) consumed by the Model Lab API and thesis documents. No random train/test splitting is introduced anywhere; the existing expanding rolling-origin folds and completed-season holdout are preserved as the only evaluation structure.

**Tech Stack:** Python 3.12, scikit-learn 1.5.0, XGBoost 2.0.3, LightGBM 4.3.0, pandas 2.2.2, NumPy 1.26.4, joblib 1.4.2, SQLAlchemy 2.0.30, Alembic 1.13.1, `unittest` (existing test convention), Docker Compose for verification. Optional new dependency `mord` (ordinal regression) — decision gate in Task 7.

**Spec:**
- `docs/ml-experiment-design.md` (authoritative methodology)
- `docs/final-experiment-results.md` (current reported results)
- The investigation summary produced in the prior session (tasks, features, metrics, current champions).

---

## Global Constraints

Every task's requirements implicitly include these (copied from the spec/docs):

- Only information available **before** the target race may feed any feature; every historical feature filter uses `race_date < target race_date`. Do not weaken this.
- Weather fields (`weather_is_wet`, `avg_track_temp_c`) are **excluded** from all thesis candidate feature sets until a pre-race forecast provenance is proven. Do not reintroduce them.
- Final holdout must be a **completed season only** (`2025`); it is **never** used for model selection, threshold selection, hyperparameter selection, or calibration.
- Validation is **expanding rolling origin by completed season** (`--min-train-seasons 1` → folds 2022/2023/2024). **Never** replace with random k-fold/`train_test_split`.
- Positive class is the named event (top-10 / podium). Podium primary metric is **PR-AUC**; top-10 primary is **ROC-AUC**; regression primary is **MAE**.
- Reproducibility: one master seed (`42`) with derived per-fold/per-model seeds; `n_jobs=1` everywhere; record package versions, Python/platform, and data SHA-256 fingerprints in the manifest.
- Selection rule: best **mean** primary validation metric across folds, **simpler-model tie-break**.
- Do not delete `models_store/experiments/*`; treat as reproducibility artifacts.
- Model estimators that are serialized with joblib must live in a **stable import path** under `app/ml/` (not `__main__`/`__mp_main__`).

---

## Statistical Methodology (justification, read first)

This plan adds two forms of uncertainty quantification. Both treat the **race** as the sampling unit, because drivers within a single race are strongly correlated (same circuit, weather, safety car, tyre window, competitors). Treating the ~20 driver-rows of one race as 20 independent observations understates variance and inflates false confidence.

1. **Race-cluster bootstrap confidence intervals.** The resampling unit is the race, not the driver-row. For regression tasks we compute one metric value *per race* (e.g., MAE within that race), then bootstrap the *mean* of those per-race values by resampling race indices with replacement. For classification tasks the primary metrics (ROC-AUC / PR-AUC) are pooled quantities that cannot always be computed within a single race (a race can be all-top-10 or no-podium), so we use a **pooled cluster bootstrap**: resample whole races with replacement, concatenate their rows, and recompute the pooled metric on the resampled sample. Both give a 2.5–97.5 percentile interval that correctly propagates within-race correlation.

2. **Paired significance tests (champion vs runner-up).** To ask "is model A really better than model B", we pair predictions by race and compute the per-race metric difference `d_r = metric_A(r) − metric_B(r)`. Pairing by race removes race-level difficulty as a confounder. We then run:
   - a **paired permutation test** (random sign-flip of `d_r`, two-sided; H0 = mean difference is zero) — requires only NumPy, no scipy;
   - a **paired bootstrap CI** on the mean of `d_r`.
   If the CI excludes zero *and* the p-value is below the predeclared threshold, we may claim a difference; otherwise the models are reported as statistically indistinguishable. For classification we use **per-race Brier score** as the paired quantity (a proper scoring rule computable for every race, including single-class races), while still reporting the primary ROC-AUC / PR-AUC CIs.

This matches `docs/ml-experiment-design.md` lines 16, 76, 117, 121, which mandate "clustering by race" and "race-cluster bootstrap 95% confidence intervals".

---

## File Structure (planned)

New files:
- `ml_pipeline/statistical_evaluation.py` — race-cluster bootstrap, per-race metrics, paired permutation + bootstrap tests, significance-report builder.
- `ml_pipeline/temporal_splits.py` — `TemporalFold` + `generate_temporal_folds` moved out of `train_models.py` to break a circular import with the search module.
- `ml_pipeline/preprocessing.py` — `build_preprocessor` + `build_pipeline` moved out of `train_models.py` so the search module can reuse the identical imputer/scaler pipeline without a circular import.
- `ml_pipeline/hyperparameter_search.py` — predeclared search spaces, `build_model_from_config`, `select_hyperparameters`.
- `app/ml/ordinal_models.py` — joblib-stable ranking wrappers (`LightGBMRankRegressor`, `XGBRankRegressor`) and (optional) ordinal adapters.
- `alembic/versions/20260829_XXXX_add_grid_position_source.py` — migration for the grid-proxy column.
- `tests/test_statistical_evaluation.py`, `tests/test_hyperparameter_search.py`, `tests/test_ordinal_models.py`, `tests/test_prediction_service_features.py`, `tests/test_grid_parity.py`.

Modified files:
- `ml_pipeline/train_models.py` — integrate significance artifacts, nested search, ranking/ordinal/calibrated candidates, rank-aware evaluation, re-export temporal-splits helpers.
- `app/models/ml_feature.py` — add `grid_position_source`.
- `ml_pipeline/feature_engineering.py` — emit consistent grid proxy + source marker.
- `app/services/prediction_service.py` — remove weather from `DEFAULT_FEATURE_COLS`.
- `requirements.txt` — (conditional) add `mord`.

---

## Phase A — Statistical rigor

### Task 1: Race-cluster bootstrap and paired tests module

**Files:**
- Create: `f1-platform/backend/ml_pipeline/statistical_evaluation.py`
- Test: `f1-platform/backend/tests/test_statistical_evaluation.py`

**Interfaces:**
- Produces (used by Task 2):
  - `per_race_metric(preds: pd.DataFrame, metric_fn) -> pd.Series`
  - `bootstrap_mean_of_per_race(per_race: pd.Series, n_boot=2000, seed=42) -> dict`
  - `cluster_bootstrap_pooled(preds: pd.DataFrame, metric_fn, n_boot=2000, seed=42) -> dict`
  - `pooled_mae(preds)`, `pooled_roc_auc(preds)`, `pooled_pr_auc(preds)`, `pooled_brier(preds)`
  - `per_race_mae(actual, pred) -> float`, `per_race_brier(actual, proba) -> float`
  - `paired_metric_differences(per_race_a, per_race_b) -> pd.Series`
  - `paired_permutation_test(differences, n_perm=5000, seed=42) -> float`
  - `paired_bootstrap_ci(differences, n_boot=2000, seed=42) -> dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_statistical_evaluation.py
import unittest
import numpy as np
import pandas as pd
from ml_pipeline.statistical_evaluation import (
    per_race_metric,
    bootstrap_mean_of_per_race,
    cluster_bootstrap_pooled,
    pooled_mae,
    pooled_roc_auc,
    per_race_mae,
    per_race_brier,
    paired_metric_differences,
    paired_permutation_test,
    paired_bootstrap_ci,
)


def _preds():
    # race 1: perfect predictions; race 2: poor predictions
    return pd.DataFrame({
        "race_id": [1, 1, 1, 2, 2, 2],
        "actual": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
        "prediction": [1.0, 2.0, 3.0, 3.0, 2.0, 1.0],
    })


class StatisticalEvaluationTests(unittest.TestCase):
    def test_per_race_metric_indexes_by_race(self):
        s = per_race_metric(_preds(), per_race_mae)
        self.assertEqual(sorted(s.index.tolist()), [1, 2])
        self.assertAlmostEqual(s.loc[1], 0.0)
        self.assertAlmostEqual(s.loc[2], (2.0 + 0.0 + 2.0) / 3.0)

    def test_bootstrap_mean_of_per_race_is_inside_ci(self):
        s = pd.Series([0.0, 4.0], index=[1, 2])
        ci = bootstrap_mean_of_per_race(s, n_boot=200, seed=1)
        self.assertLessEqual(ci["ci_low"], ci["mean"])
        self.assertLessEqual(ci["mean"], ci["ci_high"])
        self.assertAlmostEqual(ci["mean"], 2.0, places=0)

    def test_cluster_bootstrap_pooled_resamples_races(self):
        ci = cluster_bootstrap_pooled(_preds(), pooled_mae, n_boot=100, seed=1)
        self.assertGreater(ci["ci_low"], 0.0)  # pooled MAE is positive

    def test_pooled_roc_auc_nan_on_single_class(self):
        one_class = pd.DataFrame({"race_id": [1, 1], "actual": [1, 1], "probability": [0.9, 0.8]})
        self.assertTrue(np.isnan(pooled_roc_auc(one_class)))

    def test_per_race_brier_uses_probabilities(self):
        self.assertAlmostEqual(per_race_brier(np.array([1, 0]), np.array([0.8, 0.2])), 0.04, places=4)

    def test_paired_differences_align_on_common_races(self):
        a = pd.Series([1.0, 2.0], index=[1, 2])
        b = pd.Series([3.0, 2.0], index=[2, 3])
        d = paired_metric_differences(a, b)
        self.assertEqual(sorted(d.index.tolist()), [2])
        self.assertAlmostEqual(d.loc[2], 0.0)

    def test_paired_permutation_test_detects_real_difference(self):
        # champion consistently better by 1 position in every race
        diffs = pd.Series([-1.0] * 30)
        p = paired_permutation_test(diffs, n_perm=500, seed=42)
        self.assertLess(p, 0.05)

    def test_paired_bootstrap_ci_excludes_zero_for_clear_difference(self):
        diffs = pd.Series([-1.0] * 50)
        ci = paired_bootstrap_ci(diffs, n_boot=200, seed=42)
        self.assertGreater(ci["ci_high"], ci["ci_low"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T backend python -m unittest tests.test_statistical_evaluation -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ml_pipeline.statistical_evaluation'`.

- [ ] **Step 3: Write the module**

```python
"""Leakage-safe statistical evaluation for race-clustered predictions.

The race is the sampling unit because driver-rows within one race are correlated.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    mean_absolute_error,
    roc_auc_score,
)


def per_race_metric(preds: pd.DataFrame, metric_fn: Callable) -> pd.Series:
    values: dict[int, float] = {}
    for race_id, group in preds.groupby("race_id", sort=False):
        values[int(race_id)] = float(metric_fn(
            group["actual"].to_numpy(dtype=float),
            group["prediction"].to_numpy(dtype=float),
        ))
    return pd.Series(values, name="metric")


def bootstrap_mean_of_per_race(per_race: pd.Series, n_boot: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    values = per_race.to_numpy(dtype=float)
    means = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, len(values), size=len(values))
        means[b] = values[idx].mean()
    return {
        "mean": float(means.mean()),
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
    }


def cluster_bootstrap_pooled(preds: pd.DataFrame, metric_fn: Callable, n_boot: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    races = sorted(preds["race_id"].unique())
    by_race = {int(r): preds[preds["race_id"] == r] for r in races}
    stats = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, len(races), size=len(races))
        sample = pd.concat([by_race[int(races[i])] for i in idx], ignore_index=True)
        stats[b] = float(metric_fn(sample))
    return {
        "mean": float(stats.mean()),
        "ci_low": float(np.percentile(stats, 2.5)),
        "ci_high": float(np.percentile(stats, 97.5)),
    }


def pooled_mae(preds: pd.DataFrame) -> float:
    return float(mean_absolute_error(preds["actual"], preds["prediction"]))


def pooled_roc_auc(preds: pd.DataFrame) -> float:
    y = preds["actual"].astype(int).to_numpy()
    p = preds["probability"].to_numpy(dtype=float)
    return float(roc_auc_score(y, p)) if len(np.unique(y)) == 2 else float("nan")


def pooled_pr_auc(preds: pd.DataFrame) -> float:
    y = preds["actual"].astype(int).to_numpy()
    p = preds["probability"].to_numpy(dtype=float)
    return float(average_precision_score(y, p)) if len(np.unique(y)) == 2 else float("nan")


def pooled_brier(preds: pd.DataFrame) -> float:
    return float(brier_score_loss(preds["actual"].astype(int), preds["probability"]))


def per_race_mae(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(mean_absolute_error(actual, pred))


def per_race_brier(actual: np.ndarray, proba: np.ndarray) -> float:
    return float(brier_score_loss(actual.astype(int), np.clip(proba, 0.0, 1.0)))


def paired_metric_differences(per_race_a: pd.Series, per_race_b: pd.Series) -> pd.Series:
    frame = pd.concat([per_race_a.rename("a"), per_race_b.rename("b")], axis=1).dropna()
    return (frame["a"] - frame["b"]).rename("difference")


def paired_permutation_test(differences: pd.Series, n_perm: int = 5000, seed: int = 42) -> float:
    values = differences.to_numpy(dtype=float)
    if values.size < 2:
        return 1.0
    observed = abs(values.mean())
    rng = np.random.default_rng(seed)
    count = 0
    for _ in range(n_perm):
        signs = rng.choice(np.array([-1.0, 1.0]), size=values.size)
        if abs((signs * values).mean()) >= observed:
            count += 1
    return float((count + 1) / (n_perm + 1))


def paired_bootstrap_ci(differences: pd.Series, n_boot: int = 2000, seed: int = 42) -> dict:
    rng = np.random.default_rng(seed)
    values = differences.to_numpy(dtype=float)
    means = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idx = rng.integers(0, len(values), size=len(values))
        means[b] = values[idx].mean()
    return {
        "mean": float(means.mean()),
        "ci_low": float(np.percentile(means, 2.5)),
        "ci_high": float(np.percentile(means, 97.5)),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T backend python -m unittest tests.test_statistical_evaluation -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add f1-platform/backend/ml_pipeline/statistical_evaluation.py f1-platform/backend/tests/test_statistical_evaluation.py
git commit -m "feat(ml): add race-cluster bootstrap and paired significance tests"
```

**Integration:** Standalone module; consumed by `train_models.py` in Task 2.
**Leakage:** None — operates only on already-generated out-of-fold predictions.
**Reproducibility:** All randomness from a single `seed` passed through `numpy.random.default_rng`.
**Outputs:** CI dicts and p-values.
**Thesis use:** Confidence intervals for every leaderboard and holdout result.
**Risks/decisions:** None blocking. (Design note: 2000 bootstrap/5000 permutation default iterations are a speed/accuracy tradeoff; they are constants at top-level and recorded in the manifest.)

---

### Task 2: Wire significance artifacts into the experiment runner

**Files:**
- Modify: `f1-platform/backend/ml_pipeline/train_models.py` (add `build_significance_report` and call it in `run_experiment`; extend `write_experiment_artifacts`)
- Test: `f1-platform/backend/tests/test_train_models_experiment.py` (add one test)

**Interfaces:**
- Consumes: everything Task 1 produced.
- Produces: `build_significance_report(oof_predictions: pd.DataFrame, aggregate: pd.DataFrame, final_results: pd.DataFrame, seed: int) -> dict`; new artifact `significance.json`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_train_models_experiment.py (imports at top)
from ml_pipeline.train_models import build_significance_report

class SignificanceReportTests(unittest.TestCase):
    def test_build_significance_report_pairs_champion_and_runner_up(self):
        oof = pd.DataFrame([
            {"phase": "validation", "fold": "fold_1_2024", "context": "pre_qualifying",
             "task": "position_model", "algorithm": "Ridge", "analysis_type": "candidate_model",
             "race_id": 1, "driver_id": 1, "season_year": 2024, "actual": 1.0,
             "prediction": 1.0, "probability": np.nan, "threshold": np.nan},
            {"phase": "validation", "fold": "fold_1_2024", "context": "pre_qualifying",
             "task": "position_model", "algorithm": "Ridge", "analysis_type": "candidate_model",
             "race_id": 2, "driver_id": 2, "season_year": 2024, "actual": 2.0,
             "prediction": 2.0, "probability": np.nan, "threshold": np.nan},
            {"phase": "validation", "fold": "fold_1_2024", "context": "pre_qualifying",
             "task": "position_model", "algorithm": "ElasticNet", "analysis_type": "candidate_model",
             "race_id": 1, "driver_id": 1, "season_year": 2024, "actual": 1.0,
             "prediction": 8.0, "probability": np.nan, "threshold": np.nan},
            {"phase": "validation", "fold": "fold_1_2024", "context": "pre_qualifying",
             "task": "position_model", "algorithm": "ElasticNet", "analysis_type": "candidate_model",
             "race_id": 2, "driver_id": 2, "season_year": 2024, "actual": 2.0,
             "prediction": 9.0, "probability": np.nan, "threshold": np.nan},
        ])
        aggregate = pd.DataFrame([
            {"context": "pre_qualifying", "task": "position_model", "algorithm": "Ridge",
             "primary_metric": "mae", "primary_score": 1.0, "rank": 1.0, "champion": True},
            {"context": "pre_qualifying", "task": "position_model", "algorithm": "ElasticNet",
             "primary_metric": "mae", "primary_score": 7.0, "rank": 2.0, "champion": False},
        ])
        final = pd.DataFrame()
        report = build_significance_report(oof, aggregate, final, seed=42)
        key = "pre_qualifying:position_model"
        self.assertEqual(report[key]["champion"], "Ridge")
        self.assertEqual(report[key]["runner_up"], "ElasticNet")
        self.assertIn("paired_p_value", report[key])
        self.assertIn("champion_ci", report[key])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T backend python -m unittest tests.test_train_models_experiment.SignificanceReportTests -v`
Expected: FAIL with `ImportError: cannot import name 'build_significance_report'`.

- [ ] **Step 3: Implement `build_significance_report`**

Add the import near the other sklearn imports in `train_models.py`:

```python
from ml_pipeline.statistical_evaluation import (
    bootstrap_mean_of_per_race,
    cluster_bootstrap_pooled,
    paired_bootstrap_ci,
    paired_metric_differences,
    paired_permutation_test,
    per_race_brier,
    per_race_mae,
    per_race_metric,
    pooled_mae,
    pooled_pr_auc,
    pooled_roc_auc,
)
```

Add the function (place it near `aggregate_ablation_results`):

```python
def build_significance_report(
    oof_predictions: pd.DataFrame,
    aggregate: pd.DataFrame,
    final_results: pd.DataFrame,
    seed: int,
) -> dict[str, Any]:
    """Confidence intervals and paired champion-vs-runner-up tests, clustered by race."""
    validation = oof_predictions[
        (oof_predictions["phase"] == "validation")
        & (oof_predictions["analysis_type"] == "candidate_model")
    ]
    report: dict[str, Any] = {}
    for (context, task), group in aggregate.groupby(["context", "task"], sort=False):
        ranked = group[group["rank"].notna()].sort_values("rank")
        if len(ranked) < 2:
            continue
        champion = str(ranked.iloc[0]["algorithm"])
        runner_up = str(ranked.iloc[1]["algorithm"])
        primary = PRIMARY_METRIC[task]
        is_classification = task in {"top10_model", "podium_model"}

        champ = validation[
            (validation["context"] == context)
            & (validation["task"] == task)
            & (validation["algorithm"] == champion)
        ]
        runner = validation[
            (validation["context"] == context)
            & (validation["task"] == task)
            & (validation["algorithm"] == runner_up)
        ]
        if champ.empty or runner.empty:
            continue

        if is_classification:
            metric_fn = pooled_roc_auc if primary == "roc_auc" else pooled_pr_auc
            champ_ci = cluster_bootstrap_pooled(champ, metric_fn, seed=seed)
            runner_ci = cluster_bootstrap_pooled(runner, metric_fn, seed=seed)
            paired_a = per_race_metric(champ, per_race_brier)
            paired_b = per_race_metric(runner, per_race_brier)
        else:
            champ_ci = bootstrap_mean_of_per_race(per_race_metric(champ, per_race_mae), seed=seed)
            runner_ci = bootstrap_mean_of_per_race(per_race_metric(runner, per_race_mae), seed=seed)
            paired_a = per_race_metric(champ, per_race_mae)
            paired_b = per_race_metric(runner, per_race_mae)

        differences = paired_metric_differences(paired_a, paired_b)
        report[f"{context}:{task}"] = {
            "champion": champion,
            "runner_up": runner_up,
            "primary_metric": primary,
            "champion_ci": champ_ci,
            "runner_up_ci": runner_ci,
            "paired_p_value": paired_permutation_test(differences, seed=seed),
            "paired_difference_ci": paired_bootstrap_ci(differences, seed=seed),
            "paired_race_count": int(len(differences)),
        }
    return report
```

- [ ] **Step 4: Persist `significance.json` in `write_experiment_artifacts`**

Add a parameter `significance: dict | None = None` to `write_experiment_artifacts` (signature at ~`train_models.py:729`) and inside the body, before `write_markdown_report`:

```python
    write_json(experiment_dir / "significance.json", significance or {})
```

Add `"significance.json"` to the `required` set in `validate_artifact_schema` (~`train_models.py:766`).

Then in `run_experiment` (~`train_models.py:1104`), compute and pass it:

```python
    significance = build_significance_report(oof_predictions, aggregate, final_results, args.seed)
```

and add `significance=significance` to the `write_experiment_artifacts(...)` call.

- [ ] **Step 5: Run tests**

Run: `docker compose exec -T backend python -m unittest tests.test_train_models_experiment tests.test_statistical_evaluation -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add f1-platform/backend/ml_pipeline/train_models.py f1-platform/backend/tests/test_train_models_experiment.py
git commit -m "feat(ml): emit race-cluster bootstrap CIs and paired significance report"
```

**Integration:** `significance.json` is a first-class experiment artifact; Model Lab can later expose it (optional, not in this plan's scope).
**Leakage:** Only validation-phase predictions are used; final holdout never feeds the significance report's champion selection.
**Reproducibility:** Single `seed` threaded through; bootstrap/permutation counts are fixed constants.
**Outputs:** Per-context/task champion CI, runner-up CI, paired p-value, paired-difference CI.
**Thesis use:** Directly answers "which model is best, by how much, and is it significant".
**Risks/decisions:** `build_significance_report` requires at least two ranked candidates; baseline-only tasks (e.g., pre gain/loss where only one model is meaningfully better) still have 6 candidates, so `rank` is always present.

---

## Phase B — Nested hyperparameter search

### Task 3: Extract temporal-splits helper and add search module

**Files:**
- Create: `f1-platform/backend/ml_pipeline/temporal_splits.py`
- Create: `f1-platform/backend/ml_pipeline/preprocessing.py`
- Create: `f1-platform/backend/ml_pipeline/hyperparameter_search.py`
- Modify: `f1-platform/backend/ml_pipeline/train_models.py` (re-export `TemporalFold`, `generate_temporal_folds`, `build_preprocessor`, `build_pipeline`)
- Test: `f1-platform/backend/tests/test_hyperparameter_search.py`

**Interfaces:**
- Produces:
  - `temporal_splits.TemporalFold` (dataclass: `name`, `train_seasons: tuple[int, ...]`, `validation_season: int`)
  - `temporal_splits.generate_temporal_folds(seasons: list[int], min_train_seasons: int = 3) -> list[TemporalFold]`
  - `preprocessing.build_preprocessor(feature_cols) -> ColumnTransformer`
  - `preprocessing.build_pipeline(estimator, feature_cols) -> Pipeline`
  - `hyperparameter_search.REGRESSION_SEARCH_SPACES: dict[str, list[dict]]`
  - `hyperparameter_search.CLASSIFICATION_SEARCH_SPACES: dict[str, list[dict]]`
  - `hyperparameter_search.build_model_from_config(algorithm, config, seed, feature_cols, task, y) -> Any`
  - `hyperparameter_search.select_hyperparameters(algorithm, space, train_df, target, feature_cols, task, seed) -> tuple[dict, list[dict]]`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_hyperparameter_search.py
import unittest
import pandas as pd
from ml_pipeline.temporal_splits import generate_temporal_folds
from ml_pipeline.hyperparameter_search import (
    REGRESSION_SEARCH_SPACES,
    CLASSIFICATION_SEARCH_SPACES,
    build_model_from_config,
    select_hyperparameters,
)


class HyperparameterSearchTests(unittest.TestCase):
    def test_temporal_folds_match_original_behavior(self):
        folds = generate_temporal_folds([2021, 2022, 2023, 2024], min_train_seasons=1)
        self.assertEqual([f.validation_season for f in folds], [2022, 2023, 2024])
        self.assertEqual(folds[0].train_seasons, (2021,))

    def test_search_spaces_are_predeclared_and_bounded(self):
        self.assertGreaterEqual(len(REGRESSION_SEARCH_SPACES["Ridge"]), 1)
        self.assertGreaterEqual(len(CLASSIFICATION_SEARCH_SPACES["LogisticRegression"]), 1)
        for space in (REGRESSION_SEARCH_SPACES, CLASSIFICATION_SEARCH_SPACES):
            for name, configs in space.items():
                self.assertGreaterEqual(len(configs), 1)

    def test_build_model_from_config_is_sklearn_fittable(self):
        model = build_model_from_config(
            "Ridge", {"alpha": 1.0}, 42, ["driver_recent_form"], "position_model", pd.Series([1.0, 2.0])
        )
        X = pd.DataFrame({"driver_recent_form": [2.0, 3.0]})
        model.fit(X, pd.Series([1.0, 2.0]))
        self.assertEqual(model.predict(X).shape, (2,))

    def test_select_hyperparameters_returns_config_and_records(self):
        train = pd.DataFrame({
            "season_year": [2021, 2021, 2022, 2022, 2023, 2023],
            "driver_recent_form": [2.0, 12.0, 3.0, 13.0, 4.0, 14.0],
            "actual_finishing_position": [1.0, 11.0, 2.0, 12.0, 3.0, 13.0],
        })
        best, records = select_hyperparameters(
            "Ridge", REGRESSION_SEARCH_SPACES["Ridge"], train,
            "actual_finishing_position", ["driver_recent_form"], "position_model", seed=42,
        )
        self.assertIn("alpha", best)
        self.assertEqual(len(records), len(REGRESSION_SEARCH_SPACES["Ridge"]))
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend python -m unittest tests.test_hyperparameter_search -v`
Expected: FAIL (`No module named 'ml_pipeline.temporal_splits'`).

- [ ] **Step 3: Create `temporal_splits.py`** (move `TemporalFold` + `generate_temporal_folds` verbatim from `train_models.py:126-228`)

```python
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class TemporalFold:
    name: str
    train_seasons: tuple[int, ...]
    validation_season: int


def generate_temporal_folds(seasons: list[int], min_train_seasons: int = 3) -> list[TemporalFold]:
    ordered = sorted(set(seasons))
    if len(ordered) != len(seasons):
        raise ValueError("Temporal folds require unique seasons.")
    if len(ordered) <= min_train_seasons:
        raise ValueError("Insufficient seasons for an expanding temporal validation fold.")
    return [
        TemporalFold(
            name=f"fold_{index - min_train_seasons + 1}_{season}",
            train_seasons=tuple(ordered[:index]),
            validation_season=season,
        )
        for index, season in enumerate(ordered)
        if index >= min_train_seasons
    ]
```

- [ ] **Step 4: Create `preprocessing.py`** (move `build_preprocessor` + `build_pipeline` verbatim from `train_models.py:330-338`)

```python
from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def build_preprocessor(feature_cols: list[str]) -> ColumnTransformer:
    return ColumnTransformer(
        [("numeric", Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler())]), feature_cols)],
        remainder="drop",
    )


def build_pipeline(estimator, feature_cols: list[str]) -> Pipeline:
    return Pipeline([("preprocessor", build_preprocessor(feature_cols)), ("model", estimator)])
```

- [ ] **Step 5: Re-export in `train_models.py`**

Replace the existing `TemporalFold`/`generate_temporal_folds` definitions (lines ~126-228) **and** the `build_preprocessor`/`build_pipeline` definitions (lines ~330-338) with re-exports (keep the dataclass/`ColumnTransformer`/`Pipeline`/`SimpleImputer`/`StandardScaler` imports removed as appropriate):

```python
from ml_pipeline.temporal_splits import TemporalFold, generate_temporal_folds
from ml_pipeline.preprocessing import build_pipeline, build_preprocessor
```

Update the existing import at the top of `tests/test_train_models_experiment.py` if needed (it already imports `generate_temporal_folds` from `ml_pipeline.train_models`; the re-export keeps it working).

- [ ] **Step 6: Create `hyperparameter_search.py`**

```python
"""Predeclared hyperparameter search spaces and inner chronological selection."""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import ElasticNet, LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, mean_absolute_error, roc_auc_score
from xgboost import XGBClassifier, XGBRegressor

from ml_pipeline.preprocessing import build_pipeline
from ml_pipeline.temporal_splits import generate_temporal_folds

REGRESSION_SEARCH_SPACES: dict[str, list[dict[str, Any]]] = {
    "Ridge": [{"alpha": a} for a in (0.1, 1.0, 10.0, 100.0)],
    "ElasticNet": [
        {"alpha": a, "l1_ratio": r}
        for a in (0.01, 0.05, 0.1, 1.0)
        for r in (0.1, 0.5, 0.9)
    ],
    "RandomForestRegressor": [
        {"n_estimators": 300, "max_depth": d, "min_samples_leaf": s}
        for d in (None, 4, 8)
        for s in (1, 4)
    ],
    "XGBRegressor": [
        {"n_estimators": 250, "max_depth": d, "learning_rate": lr}
        for d in (3, 5, 7)
        for lr in (0.02, 0.04, 0.08)
    ],
    "LGBMRegressor": [
        {"n_estimators": 250, "max_depth": d, "learning_rate": lr}
        for d in (3, 6, -1)
        for lr in (0.02, 0.04, 0.08)
    ],
}

CLASSIFICATION_SEARCH_SPACES: dict[str, list[dict[str, Any]]] = {
    "LogisticRegression": [{"C": c} for c in (0.1, 1.0, 10.0)],
    "RandomForestClassifier": [
        {"n_estimators": 300, "max_depth": d, "min_samples_leaf": s}
        for d in (None, 4, 8)
        for s in (1, 4)
    ],
    "XGBClassifier": [
        {"n_estimators": 250, "max_depth": d, "learning_rate": lr}
        for d in (3, 5, 7)
        for lr in (0.02, 0.04, 0.08)
    ],
    "LGBMClassifier": [
        {"n_estimators": 250, "max_depth": d, "learning_rate": lr}
        for d in (3, 6, -1)
        for lr in (0.02, 0.04, 0.08)
    ],
}

_CLASSIFICATION = {"top10_model", "podium_model"}


def _class_weight_scale(y: pd.Series) -> float:
    positives = int((y.astype(int) == 1).sum())
    negatives = int((y.astype(int) == 0).sum())
    return float(negatives / positives) if positives else 1.0


def build_model_from_config(
    algorithm: str,
    config: dict[str, Any],
    seed: int,
    feature_cols: list[str],
    task: str,
    y: pd.Series,
) -> Any:
    """Construct an (unfitted) sklearn-compatible model for a specific config."""
    if algorithm == "Ridge":
        return Ridge(alpha=config["alpha"], random_state=seed)
    if algorithm == "ElasticNet":
        return ElasticNet(alpha=config["alpha"], l1_ratio=config["l1_ratio"], max_iter=10000, random_state=seed)
    if algorithm == "RandomForestRegressor":
        return RandomForestRegressor(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                                    min_samples_leaf=config["min_samples_leaf"], random_state=seed, n_jobs=1)
    if algorithm == "RandomForestClassifier":
        return RandomForestClassifier(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                                      min_samples_leaf=config["min_samples_leaf"], class_weight="balanced",
                                      random_state=seed, n_jobs=1)
    if algorithm == "XGBRegressor":
        return XGBRegressor(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                            learning_rate=config["learning_rate"], subsample=0.85, colsample_bytree=0.9,
                            reg_lambda=1.0, random_state=seed, n_jobs=1)
    if algorithm == "XGBClassifier":
        return XGBClassifier(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                             learning_rate=config["learning_rate"], subsample=0.85, colsample_bytree=0.9,
                             reg_lambda=1.0, scale_pos_weight=_class_weight_scale(y),
                             random_state=seed, n_jobs=1, eval_metric="logloss")
    if algorithm == "LGBMRegressor":
        return LGBMRegressor(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                             learning_rate=config["learning_rate"], subsample=0.85, colsample_bytree=0.9,
                             reg_lambda=1.0, random_state=seed, n_jobs=1, verbose=-1)
    if algorithm == "LGBMClassifier":
        return LGBMClassifier(n_estimators=config["n_estimators"], max_depth=config["max_depth"],
                              learning_rate=config["learning_rate"], subsample=0.85, colsample_bytree=0.9,
                              reg_lambda=1.0, class_weight="balanced", random_state=seed, n_jobs=1, verbose=-1)
    if algorithm == "LogisticRegression":
        return LogisticRegression(C=config["C"], max_iter=3000, class_weight="balanced", random_state=seed)
    raise ValueError(f"Unknown search algorithm: {algorithm}")


def select_hyperparameters(
    algorithm: str,
    space: list[dict[str, Any]],
    train_df: pd.DataFrame,
    target: str,
    feature_cols: list[str],
    task: str,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Select best config on an expanding inner split of train_df's seasons only."""
    is_classification = task in _CLASSIFICATION
    seasons = sorted(train_df["season_year"].unique().tolist())
    inner_folds = generate_temporal_folds(seasons, min_train_seasons=1)
    if not inner_folds:
        return space[0], [{"config": space[0], "inner_score_mean": None, "inner_scores": []}]

    records: list[dict[str, Any]] = []
    for config in space:
        scores: list[float] = []
        for fold in inner_folds:
            it = train_df[train_df["season_year"].isin(fold.train_seasons) & train_df[target].notna()]
            iv = train_df[(train_df["season_year"] == fold.validation_season) & train_df[target].notna()]
            if it.empty or iv.empty or (is_classification and (it[target].nunique() < 2 or iv[target].nunique() < 2)):
                continue
            model = build_pipeline(build_model_from_config(algorithm, config, seed, feature_cols, task, it[target]), feature_cols)
            model.fit(it[feature_cols], it[target].astype(int) if is_classification else it[target].astype(float))
            if is_classification:
                proba = model.predict_proba(iv[feature_cols])[:, 1]
                if task == "podium_model":
                    score = average_precision_score(iv[target].astype(int), proba)
                else:
                    score = roc_auc_score(iv[target].astype(int), proba) if iv[target].nunique() == 2 else 0.5
            else:
                score = mean_absolute_error(iv[target].astype(float), model.predict(iv[feature_cols]))
            scores.append(float(score))
        records.append({"config": config, "inner_score_mean": float(np.mean(scores)) if scores else None,
                        "inner_scores": scores})

    valid = [r for r in records if r["inner_score_mean"] is not None]
    if not valid:
        return space[0], records
    # lower-is-better for MAE; higher-is-better for ROC-AUC / PR-AUC
    lower_is_better = not is_classification
    best = min(valid, key=lambda r: r["inner_score_mean"]) if lower_is_better else max(
        valid, key=lambda r: r["inner_score_mean"]
    )
    return best["config"], records
```

- [ ] **Step 7: Run tests**

Run: `docker compose exec -T backend python -m unittest tests.test_hyperparameter_search tests.test_train_models_experiment -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add f1-platform/backend/ml_pipeline/temporal_splits.py f1-platform/backend/ml_pipeline/preprocessing.py f1-platform/backend/ml_pipeline/hyperparameter_search.py f1-platform/backend/ml_pipeline/train_models.py f1-platform/backend/tests/test_hyperparameter_search.py
git commit -m "feat(ml): add predeclared nested hyperparameter search and temporal-splits module"
```

**Integration:** `build_model_from_config` mirrors the fixed configs already in `candidate_factories`, so search results are directly comparable to the current experiment.
**Leakage:** `select_hyperparameters` uses **only `train_df`** (the fold's training seasons) via an inner expanding split; the outer validation season is never touched.
**Reproducibility:** Spaces are literal, ordered lists (deterministic); seeds derived from the master seed; `n_jobs=1`.
**Outputs:** Selected config + per-config inner scores (recorded in the manifest under `selected_hyperparameters`).
**Thesis use:** A defensible "these were the predeclared budgets" statement; prevents tuning-until-a-model-wins.
**Risks/decisions:** `generate_temporal_folds` moved module; re-export preserves the public import path. Baseline models (`MedianBaseline`, `ZeroChangeBaseline`, `GridPositionBaseline`, `PrevalenceBaseline`) have **no** search space (they are constants).

---

### Task 4: Run nested search inside the experiment

**Files:**
- Modify: `f1-platform/backend/ml_pipeline/train_models.py` (extend `Candidate` with `space`; attach spaces in `candidate_factories`; add `hyperparams` to `evaluate_candidate`; search per fold in `run_experiment`; record selected configs)
- Test: `f1-platform/backend/tests/test_train_models_experiment.py` (one test that a candidate with a space records selected config)

**Interfaces:**
- Consumes: Task 3 modules.
- Produces: `Candidate.space: tuple[dict, ...]`; `evaluate_candidate(..., hyperparams: dict | None = None)`; manifest key `selected_hyperparameters`.

- [ ] **Step 1: Write failing test**

```python
# append to tests/test_train_models_experiment.py
from ml_pipeline.train_models import Candidate

class SearchIntegrationTests(unittest.TestCase):
    def test_candidate_carries_a_search_space(self):
        cands = candidate_factories("position_model", "pre_qualifying", ["driver_recent_form"])
        ridge = next(c for c in cands if c.name == "Ridge")
        self.assertGreaterEqual(len(ridge.space), 1)
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend python -m unittest tests.test_train_models_experiment.SearchIntegrationTests -v`
Expected: FAIL (`AttributeError: 'Candidate' object has no attribute 'space'`).

- [ ] **Step 3: Extend `Candidate` and `candidate_factories`**

Add `space` to the `Candidate` dataclass (`train_models.py:133`):

```python
@dataclass(frozen=True)
class Candidate:
    name: str
    complexity: int
    factory: Callable[[pd.Series, int], Any]
    space: tuple[dict[str, Any], ...] = ()
```

Import and attach spaces at the top of `candidate_factories` (`train_models.py:347`):

```python
from ml_pipeline.hyperparameter_search import (
    CLASSIFICATION_SEARCH_SPACES,
    REGRESSION_SEARCH_SPACES,
    build_model_from_config,
    select_hyperparameters,
)
```

For each non-baseline candidate, pass `space=tuple(SPACE[algorithm])`. Example (regression branch):

```python
        candidates.extend(
            [
                Candidate("Ridge", 1, lambda _y, _seed: build_pipeline(Ridge(alpha=1.0), feature_cols), tuple(REGRESSION_SEARCH_SPACES["Ridge"])),
                Candidate("ElasticNet", 2, lambda _y, _seed: build_pipeline(ElasticNet(alpha=0.05, l1_ratio=0.5, max_iter=10000), feature_cols), tuple(REGRESSION_SEARCH_SPACES["ElasticNet"])),
                Candidate("RandomForestRegressor", 3, lambda _y, seed: build_pipeline(RandomForestRegressor(n_estimators=300, max_depth=10, min_samples_leaf=2, random_state=seed, n_jobs=1), feature_cols), tuple(REGRESSION_SEARCH_SPACES["RandomForestRegressor"])),
                Candidate("XGBRegressor", 4, lambda _y, seed: build_pipeline(XGBRegressor(n_estimators=250, max_depth=5, learning_rate=0.04, subsample=0.85, colsample_bytree=0.9, reg_lambda=1.0, random_state=seed, n_jobs=1), feature_cols), tuple(REGRESSION_SEARCH_SPACES["XGBRegressor"])),
                Candidate("LGBMRegressor", 4, lambda _y, seed: build_pipeline(LGBMRegressor(n_estimators=250, max_depth=6, learning_rate=0.04, subsample=0.85, colsample_bytree=0.9, reg_lambda=1.0, random_state=seed, n_jobs=1, verbose=-1), feature_cols), tuple(REGRESSION_SEARCH_SPACES["LGBMRegressor"])),
            ]
        )
```

Apply the analogous `space=tuple(CLASSIFICATION_SEARCH_SPACES[...])` to the classification candidates.

- [ ] **Step 4: Add `hyperparams` to `evaluate_candidate`**

Change the signature (`train_models.py:487`) to accept `hyperparams: dict | None = None` and, when provided, build the model from config instead of the fixed factory:

```python
    model = (
        build_pipeline(build_model_from_config(candidate.name, hyperparams, seed, feature_cols, task, y_train), feature_cols)
        if hyperparams is not None and candidate.space
        else candidate.factory(y_train, seed)
    )
```

- [ ] **Step 5: Search per fold in `run_experiment`**

Inside the fold/candidate loop (`train_models.py:1003`), select the config before evaluation:

```python
                hyperparams = None
                if candidate.space:
                    hyperparams, _records = select_hyperparameters(
                        candidate.name, list(candidate.space), train_df, TASK_TARGETS[task],
                        CONTEXT_FEATURE_COLS[context], task, args.seed + fold_number * 100 + candidate_number,
                    )
                result, prediction_df, _ = evaluate_candidate(
                    candidate, task, context, train_df, validation_df, CONTEXT_FEATURE_COLS[context], fold.name,
                    args.seed + fold_number * 100 + candidate_number, "validation", hyperparams=hyperparams,
                )
```

Record the selected configs into the manifest (`train_models.py:1095` region):

```python
        "selected_hyperparameters": { ... }  # (context, task, fold, algorithm) -> config
```

Because this is generated inside the loop, accumulate a `selected_configs: dict` in `run_experiment` and add it to the `manifest` before `write_experiment_artifacts`.

**Ablations:** keep ablation candidates running with **fixed** configs (no search) to bound compute. The ablation loop (`train_models.py:1047`) calls `evaluate_candidate` without `hyperparams`, so it is unaffected.

- [ ] **Step 6: Run tests**

Run: `docker compose exec -T backend python -m unittest tests.test_train_models_experiment tests.test_hyperparameter_search -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add f1-platform/backend/ml_pipeline/train_models.py f1-platform/backend/tests/test_train_models_experiment.py
git commit -m "feat(ml): run nested hyperparameter search within each temporal fold"
```

**Integration:** Final-holdout refit (`train_models.py:1029`) still uses the frozen, now **search-selected** champion config — selection happened only on development folds, so the holdout remains confirmatory.
**Leakage:** Search uses only the fold's training seasons; threshold selection still uses the inner season (unchanged).
**Reproducibility:** Selected configs are recorded; seeds derived per (fold, candidate).
**Outputs:** `selected_hyperparameters` in the manifest.
**Thesis use:** A real, bounded tuning protocol instead of hand-picked defaults.
**Risks/decisions:** Compute grows (see section F). Ablations intentionally stay un-searched.

---

## Phase C — Grid-proxy parity fix

### Task 5: Make post-qualifying grid feature use the pre-race-available proxy consistently

**Files:**
- Create: `f1-platform/backend/alembic/versions/20260829_2100_add_grid_position_source.py`
- Modify: `f1-platform/backend/app/models/ml_feature.py`
- Modify: `f1-platform/backend/ml_pipeline/feature_engineering.py`
- Test: `f1-platform/backend/tests/test_grid_parity.py`

**Interfaces:**
- Consumes: `MLFeature` model, `post_qualifying_entries`.
- Produces: `MLFeature.grid_position_source: Optional[str]`; post-qualifying rows always use `qualifying_result.position` as `grid_position`.

**Decision (approval gate):** The current code uses the **official final grid** (`race_results.grid_position`) for historical rows but falls back to **qualifying position** for upcoming rows — a train/serve mismatch and a subtle leakage of post-qualifying-but-post-cutoff information. The proposed fix is to use **qualifying position as `grid_position` for every post-qualifying row** (the value genuinely available at the "post-qualifying, pre-race" prediction time), and record `grid_position_source="qualifying_position"`. The official grid remains available in `race_results.grid_position` for post-hoc analysis. This is the conservative, leakage-safe choice; if you prefer keeping the official grid, stop here and approve the alternative (use official grid only when available *and* pre-race, otherwise proxy, and record the source per row).

- [ ] **Step 1: Write failing test**

```python
# tests/test_grid_parity.py
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from ml_pipeline import feature_engineering


class GridParityTests(unittest.TestCase):
    def test_post_qualifying_grid_uses_qualifying_position_not_race_result(self):
        race = SimpleNamespace(id=9, round_number=1, race_date=date(2024, 3, 2), circuit_name="X", race_name="X GP")
        qr = SimpleNamespace(driver_id=1, position=3, gap_to_pole_ms=150.0)
        rr = SimpleNamespace(driver_id=1, grid_position=6, team_id=7)
        with (
            patch.object(feature_engineering, "qualifying_results_for_race", return_value=[qr]),
            patch.object(feature_engineering, "is_upcoming_race", return_value=False),
            patch.object(feature_engineering, "current_race_result", return_value=rr),
            patch.object(feature_engineering, "latest_prior_team_id", return_value=7),
        ):
            entries = feature_engineering.post_qualifying_entries(MagicMock(), race)
        self.assertEqual(entries[0]["grid_position"], 3.0)
        self.assertEqual(entries[0]["grid_position_source"], "qualifying_position")
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend python -m unittest tests.test_grid_parity -v`
Expected: FAIL (asserts `grid_position == 3.0` but current code returns `6` and lacks `grid_position_source`).

- [ ] **Step 3: Add the column to the model** (`app/models/ml_feature.py`, after `gap_to_pole_ms`)

```python
    grid_position_source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
```

- [ ] **Step 4: Add the migration**

```python
# alembic/versions/20260829_2100_add_grid_position_source.py
"""add grid position source to ml features

Revision ID: 20260829_2100
Revises: 20260617_2030
Create Date: 2026-08-29 21:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "20260829_2100"
down_revision = "20260617_2030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "ml_features",
        sa.Column("grid_position_source", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("ml_features", "grid_position_source")
```

- [ ] **Step 5: Change `post_qualifying_entries`** (`feature_engineering.py:436`)

Replace the `grid_position` assignment (line ~440) with the qualifying-position proxy and add the source marker:

```python
        grid_position = qualifying_result.position
        ...
        entries.append(
            {
                "driver_id": qualifying_result.driver_id,
                "team_id": team_id,
                "grid_position": float(grid_position) if grid_position is not None else None,
                "grid_position_source": "qualifying_position",
                "qualifying_position": (...unchanged...),
                "gap_to_pole_ms": gap_to_pole_ms,
                "data_cutoff_date": race.race_date,
            }
        )
```

And in `build_feature_row` (`feature_engineering.py:528`), add `"grid_position_source": entry.get("grid_position_source"),` to the returned dict so `upsert` persists it.

- [ ] **Step 6: Run tests + migration check**

Run: `docker compose exec -T backend python -m unittest tests.test_grid_parity tests.test_feature_engineering -v`
Expected: PASS.

Run migration in a non-destructive way (verify it is applied, not on prod DB until re-run): `docker compose run --rm ingestion alembic upgrade head`

- [ ] **Step 7: Commit**

```bash
git add f1-platform/backend/alembic/versions/20260829_2100_add_grid_position_source.py f1-platform/backend/app/models/ml_feature.py f1-platform/backend/ml_pipeline/feature_engineering.py f1-platform/backend/tests/test_grid_parity.py
git commit -m "fix(ml): use qualifying-position grid proxy for all post-qualifying rows"
```

**Integration:** Post-qualifying training and serving now use identical feature semantics; `qualifying_position` and `grid_position` become equal (both = qualifying classification). This slightly changes results vs the current experiment and requires a full re-run (Task 9).
**Leakage:** Removes the official-grid (post-cutoff) information from the feature set; keeps `race_date`-based temporality intact.
**Reproducibility:** `grid_position_source` recorded per row and in the manifest policy.
**Outputs:** New column + consistent feature.
**Thesis use:** A clean "pre-race" claim for the post-qualifying context.
**Risks/decisions:** Feature engineering must be re-run with `--force` (stale-row delete already handles this). Alternative semantics (official grid kept) require approval (see the decision gate above).

---

## Phase D — Weather removal from serving defaults

### Task 6: Remove weather from `prediction_service` feature defaults

**Files:**
- Modify: `f1-platform/backend/app/services/prediction_service.py`
- Test: `f1-platform/backend/tests/test_prediction_service_features.py`

**Interfaces:**
- Consumes: `DEFAULT_FEATURE_COLS` in `prediction_service.py`.
- Produces: `DEFAULT_FEATURE_COLS` matching the training feature lists (no weather).

- [ ] **Step 1: Write failing test**

```python
# tests/test_prediction_service_features.py
import unittest
from app.services.prediction_service import DEFAULT_FEATURE_COLS

EXPECTED_PRE = [
    "avg_race_pace_ms", "driver_recent_form", "team_recent_form",
    "circuit_history_avg_finish", "circuit_history_dnf_rate", "dnf_rate_recent",
]
EXPECTED_POST = [
    "grid_position", "qualifying_position", "gap_to_pole_ms",
    *EXPECTED_PRE,
]


class PredictionServiceFeaturesTests(unittest.TestCase):
    def test_default_feature_cols_match_training_and_exclude_weather(self):
        self.assertEqual(DEFAULT_FEATURE_COLS["pre_qualifying"], EXPECTED_PRE)
        self.assertEqual(DEFAULT_FEATURE_COLS["post_qualifying"], EXPECTED_POST)
        for cols in DEFAULT_FEATURE_COLS.values():
            self.assertNotIn("weather_is_wet", cols)
            self.assertNotIn("avg_track_temp_c", cols)
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend python -m unittest tests.test_prediction_service_features -v`
Expected: FAIL (current lists include `weather_is_wet` and `avg_track_temp_c`).

- [ ] **Step 3: Edit `DEFAULT_FEATURE_COLS`** (`prediction_service.py:25-52`)

Remove `"weather_is_wet"` and `"avg_track_temp_c"` from both `PRE_QUALIFYING_FEATURE_COLS` and `POST_QUALIFYING_FEATURE_COLS`. Do **not** change `get_race_features` (weather is still returned for display but never used as a model feature).

- [ ] **Step 4: Run test**

Run: `docker compose exec -T backend python -m unittest tests.test_prediction_service_features -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add f1-platform/backend/app/services/prediction_service.py f1-platform/backend/tests/test_prediction_service_features.py
git commit -m "fix(serving): align prediction feature defaults with training (drop weather)"
```

**Integration:** `_feature_columns` already prefers metadata `feature_columns`; this only fixes the fallback path so it can never inject weather.
**Leakage:** Eliminates a latent train/serve mismatch.
**Reproducibility:** No change to trained artifacts; purely a serving-consistency fix.
**Thesis use:** Documents that the serving feature contract matches the training feature policy.

---

## Phase E — Ordinal and ranking models

### Task 7: Add ranking (and optionally ordinal) candidates for finishing position

**Files:**
- Create: `f1-platform/backend/app/ml/ordinal_models.py`
- Modify: `f1-platform/backend/ml_pipeline/train_models.py` (add candidates + rank-aware evaluation + group-aware fit)
- Modify (conditional): `f1-platform/backend/requirements.txt`
- Test: `f1-platform/backend/tests/test_ordinal_models.py`

**Interfaces:**
- Consumes: `evaluate_candidate`, `Candidate`, `regression_metrics`.
- Produces: `LightGBMRankRegressor`, `XGBRankRegressor` (sklearn-compatible, joblib-stable); new position-task candidates `LGBMRank`, `XGBRank`; helper `ranked_position_predictions(preds) -> np.ndarray`.

**Decision (approval gate):** Two candidate families are proposed:
- **Ranking (no new dependency):** `LGBMRank` (LightGBM `lambdarank`) and `XGBRank` (XGBoost `rank:pairwise`), grouped by race. These optimize the within-race ordering the application actually consumes. Their raw output is a relevance score; evaluation ranks within a race and compares ranks to actual finishing position (rank = position in a race), so MAE and race-Spearman remain valid.
- **Ordinal (new dependency `mord`):** `mord.LogisticAT` (proportional-odds logistic) and `mord.OrdinalRidge`. These model the natural ordering of finishing positions and integrate cleanly with `fit`/`predict` and `model.predict` (no special eval needed). **Requires adding `mord` to `requirements.txt` and rebuilding the ingestion/backend images.** If you do not want a new dependency, this task can ship ranking models only and defer ordinal models.

- [ ] **Step 1: Write failing test**

```python
# tests/test_ordinal_models.py
import unittest
import numpy as np
import pandas as pd
from app.ml.ordinal_models import LightGBMRankRegressor


class OrdinalRankingTests(unittest.TestCase):
    def test_lightgbm_rank_regressor_fits_with_group_and_predicts(self):
        X = pd.DataFrame({"form": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]})
        y = pd.Series([1.0, 2.0, 3.0, 1.0, 2.0, 3.0])
        group = [3, 3]
        model = LightGBMRankRegressor(n_estimators=10, random_state=0)
        model.fit(X, y, group=group)
        preds = model.predict(X)
        self.assertEqual(preds.shape, (6,))
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend python -m unittest tests.test_ordinal_models -v`
Expected: FAIL (`No module named 'app.ml.ordinal_models'`).

- [ ] **Step 3: Create `app/ml/ordinal_models.py`**

```python
"""Joblib-stable ranking estimators. Must live under app/ml for stable imports."""
from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMRanker
from sklearn.base import BaseEstimator, RegressorMixin
from xgboost import XGBRanker


class LightGBMRankRegressor(BaseEstimator, RegressorMixin):
    def __init__(self, n_estimators=250, max_depth=6, learning_rate=0.04, random_state=42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.random_state = random_state

    def fit(self, X, y, group=None):
        if group is not None:
            group_arr = np.asarray(group)
            order = np.argsort(group_arr, kind="stable")
            X_sorted = pd.DataFrame(X).iloc[order].reset_index(drop=True)
            y_sorted = pd.Series(y).iloc[order].reset_index(drop=True)
            _, group_sizes = np.unique(group_arr[order], return_counts=True)
            group_sizes = group_sizes.tolist()
        else:
            X_sorted = pd.DataFrame(X)
            y_sorted = pd.Series(y)
            group_sizes = [len(y_sorted)]
        self.model_ = LGBMRanker(
            objective="lambdarank", n_estimators=self.n_estimators, max_depth=self.max_depth,
            learning_rate=self.learning_rate, random_state=self.random_state, n_jobs=1, verbose=-1,
        )
        self.model_.fit(X_sorted, y_sorted, group=group_sizes)
        return self

    def predict(self, X):
        return self.model_.predict(X)

    @property
    def feature_importances_(self):
        return getattr(self.model_, "feature_importances_", None)


class XGBRankRegressor(BaseEstimator, RegressorMixin):
    def __init__(self, n_estimators=250, max_depth=5, learning_rate=0.04, random_state=42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.random_state = random_state

    def fit(self, X, y, group=None):
        self.model_ = XGBRanker(
            objective="rank:pairwise", n_estimators=self.n_estimators, max_depth=self.max_depth,
            learning_rate=self.learning_rate, random_state=self.random_state, n_jobs=1,
        )
        self.model_.fit(X, y, qid=group)
        return self

    def predict(self, X):
        return self.model_.predict(X)

    @property
    def feature_importances_(self):
        return getattr(self.model_, "feature_importances_", None)
```

- [ ] **Step 4: Run test**

Run: `docker compose exec -T backend python -m unittest tests.test_ordinal_models -v`
Expected: PASS.

- [ ] **Step 5: Add candidates and group-aware evaluation in `train_models.py`**

Add a `ranked` flag to `Candidate` (default `False`) and import the wrappers. Add to the regression `candidate_factories` for `position_model` only:

```python
        if task == "position_model":
            candidates.append(Candidate("LGBMRank", 5, lambda _y, seed: build_pipeline(LightGBMRankRegressor(random_state=seed), feature_cols), ranked=True))
            candidates.append(Candidate("XGBRank", 5, lambda _y, seed: build_pipeline(XGBRankRegressor(random_state=seed), feature_cols), ranked=True))
```

In `evaluate_candidate`, thread the race-group into `fit` when `candidate.ranked` (both wrappers accept `group=`; the XGB wrapper maps it to `qid` internally):

```python
    if candidate.ranked:
        groups = train_target["race_id"].to_numpy()
        model = candidate.factory(y_train, seed)
        model.fit(train_target[feature_cols], y_train, group=groups)
        raw = np.asarray(model.predict(validation_target[feature_cols]), dtype=float)
        predictions = ranked_position_predictions(validation_target["race_id"], raw)
    else:
        model = candidate.factory(y_train, seed)
        model.fit(train_target[feature_cols], y_train)
        predictions = np.asarray(model.predict(validation_target[feature_cols]), dtype=float)
```

Add the rank helper (place near `mean_per_race_spearman`):

```python
def ranked_position_predictions(race_ids: pd.Series, scores: np.ndarray) -> np.ndarray:
    """Convert ranking scores to within-race predicted positions (rank 1 = best)."""
    frame = pd.DataFrame({"race_id": race_ids.to_numpy(), "score": np.asarray(scores)})
    return frame.groupby("race_id")["score"].rank(method="first", ascending=False).to_numpy(dtype=float)
```

Note: ranking candidates must be excluded from the hyperparameter search in Task 4 (they are not in `SEARCH_SPACES`), and `feature_importances` works through the `feature_importances_` property.

- [ ] **Step 6: Run tests**

Run: `docker compose exec -T backend python -m unittest tests.test_ordinal_models tests.test_train_models_experiment -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add f1-platform/backend/app/ml/ordinal_models.py f1-platform/backend/ml_pipeline/train_models.py f1-platform/backend/tests/test_ordinal_models.py
git commit -m "feat(ml): add race-grouped ranking candidates for finishing position"
```

**Integration:** Ranking models reuse the existing `evaluate_candidate`/`regression_metrics` path via the rank-conversion helper; champion selection and holdout logic are unchanged.
**Leakage:** Grouping by `race_id` uses only the race label (not the target), and ranking models are fit on the fold's training rows only.
**Reproducibility:** `n_jobs=1`, seeded estimators, stable `app/ml` import path.
**Outputs:** Two extra position-model candidates in the leaderboard.
**Thesis use:** Tests whether a ranking objective beats point regression for the ordering the app actually serves.
**Risks/decisions:** Ranker output is a score, so MAE is computed on the rank conversion; document this in the thesis methods. Ordinal (`mord`) is optional and gated on the dependency decision.

---

## Phase F — Probability calibration

### Task 8: Add calibrated classification candidates

**Files:**
- Modify: `f1-platform/backend/ml_pipeline/train_models.py`
- Test: `f1-platform/backend/tests/test_train_models_experiment.py`

**Interfaces:**
- Consumes: `candidate_factories`, `build_pipeline`.
- Produces: calibrated classifier candidates for `top10_model` and `podium_model`.

- [ ] **Step 1: Write failing test**

```python
# append to tests/test_train_models_experiment.py
class CalibrationCandidateTests(unittest.TestCase):
    def test_calibrated_candidates_are_present_for_classification(self):
        cands = candidate_factories("top10_model", "pre_qualifying", ["driver_recent_form"])
        names = {c.name for c in cands}
        self.assertIn("RandomForestClassifierCalibrated", names)
        self.assertIn("LGBMClassifierCalibrated", names)
```

- [ ] **Step 2: Run to verify failure**

Run: `docker compose exec -T backend python -m unittest tests.test_train_models_experiment.CalibrationCandidateTests -v`
Expected: FAIL (names absent).

- [ ] **Step 3: Add calibrated candidates**

Import `CalibratedClassifierCV` and append to the classification branch of `candidate_factories`:

```python
from sklearn.calibration import CalibratedClassifierCV
...
        Candidate("RandomForestClassifierCalibrated", 5,
                  lambda _y, seed: build_pipeline(CalibratedClassifierCV(RandomForestClassifier(n_estimators=300, max_depth=10, min_samples_leaf=2, class_weight="balanced", random_state=seed, n_jobs=1), method="sigmoid", cv=3, n_jobs=1), feature_cols)),
        Candidate("LGBMClassifierCalibrated", 5,
                  lambda _y, seed: build_pipeline(CalibratedClassifierCV(LGBMClassifier(n_estimators=250, max_depth=6, learning_rate=0.04, subsample=0.85, colsample_bytree=0.9, reg_lambda=1.0, class_weight="balanced", random_state=seed, n_jobs=1, verbose=-1), method="sigmoid", cv=3, n_jobs=1), feature_cols)),
```

Calibrated candidates are intentionally **not** given a search space (the base model configs stay fixed), keeping compute bounded.

- [ ] **Step 4: Run tests**

Run: `docker compose exec -T backend python -m unittest tests.test_train_models_experiment -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add f1-platform/backend/ml_pipeline/train_models.py f1-platform/backend/tests/test_train_models_experiment.py
git commit -m "feat(ml): add calibrated classification candidates (Platt/isotonic-style)"
```

**Integration:** Calibrated models produce probabilities consumed by `classification_metrics` and `build_calibration_artifacts`; the reliability/Brier outputs now reflect post-calibration quality.
**Leakage:** `CalibratedClassifierCV(cv=3)` fits the calibration mapping on the fold's training data only (internal CV is a calibration detail, not model selection). Document this in the thesis.
**Reproducibility:** Seeded, `n_jobs=1`.
**Outputs:** Calibrated vs uncalibrated Brier/reliability comparison.
**Thesis use:** Directly addresses research question 4 (are displayed probabilities calibrated).

---

## Phase G — Full re-run and final results

### Task 9: Regenerate features, re-run the experiment, update docs

**Files:**
- Modify: `f1-platform/backend/models_store/` (new experiment artifacts, via the runner — not manual)
- Modify: `docs/final-experiment-results.md`

**Prerequisites:** All of Tasks 1–8 merged; database migrated (`alembic upgrade head`).

- [ ] **Step 1: Re-run feature engineering with `--force`** (required after the grid-parity change)

```bash
docker compose run --rm ingestion python ml_pipeline/feature_engineering.py --seasons 2021 2022 2023 2024 2025 --force
```

- [ ] **Step 2: Run the full experiment** (this requires Docker/DB/network and may take 30–60 min; get user approval before running)

```bash
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

- [ ] **Step 3: Verify artifacts and model loading**

```bash
docker compose exec -T backend python -m unittest tests.test_train_models_experiment tests.test_model_lab_api
docker compose exec -T backend python -c "from app.ml.model_loader import load_all_models; load_all_models(); print('models load successfully')"
```

- [ ] **Step 4: Inspect the new experiment's `significance.json`, `aggregate_results.csv`, and `final_holdout_results.csv`; update `docs/final-experiment-results.md`** with: the new champions, per-model CIs, paired p-values, selected hyperparameters, and calibrated-vs-uncalibrated and ranking-vs-regression findings. Preserve the "Historical experiment reference" section.

- [ ] **Step 5: Commit**

```bash
git add docs/final-experiment-results.md
git commit -m "docs: report final thesis experiment with CIs, significance, search, ranking, calibration"
```

**Note:** Do **not** commit large `.joblib`/`.csv.gz` artifacts if the repo has an ignore rule for `models_store/`; confirm with `git status` first.

---

## A. Architecture/implementation plan

Four new backend modules plus targeted fixes, all funneling into the existing `train_models.py` experiment runner and the existing artifact store:

1. `statistical_evaluation.py` — race-cluster bootstrap + paired tests (pure functions).
2. `temporal_splits.py` — extracted fold generator (removes circular import).
3. `hyperparameter_search.py` — predeclared spaces + inner chronological selection.
4. `app/ml/ordinal_models.py` — joblib-stable ranking wrappers.

The experiment runner gains: nested search, significance artifacts, ranking/calibrated candidates, and the grid-parity/weather fixes in the feature and serving layers.

## B. Experiment methodology

Unchanged core: expanding rolling-origin (3 folds) + completed-season 2025 holdout; no random splits. Added: (a) nested inner search per fold with predeclared budgets; (b) race-cluster bootstrap CIs and paired permutation tests for champion-vs-runner-up; (c) ranking and calibrated candidates; (d) a consistent pre-race grid proxy; (e) weather removed from serving fallback. All randomness is seeded and recorded.

## C. Files to modify

- `ml_pipeline/train_models.py` (Tasks 2, 4, 5*, 7, 8)
- `ml_pipeline/feature_engineering.py` (Task 5)
- `app/models/ml_feature.py` (Task 5)
- `app/services/prediction_service.py` (Task 6)
- `requirements.txt` (Task 7, conditional)
- New: `statistical_evaluation.py`, `temporal_splits.py`, `hyperparameter_search.py`, `app/ml/ordinal_models.py`, one Alembic migration, five test files.
- `docs/final-experiment-results.md` (Task 9)

## D. Tests to add

- `test_statistical_evaluation.py` (8 tests — bootstrap, pooled metrics, paired tests)
- `test_hyperparameter_search.py` (4 tests — folds, spaces, model build, selection)
- `test_ordinal_models.py` (1 test — ranker fit/predict)
- `test_prediction_service_features.py` (1 test — weather removed)
- `test_grid_parity.py` (1 test — qualifying-position proxy)
- Extensions to `test_train_models_experiment.py` (significance report, search-space presence, calibrated candidates)

## E. Execution order

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 (strictly sequential; each is independently committable).

## F. Estimated computational cost

- **Current baseline:** ~150 small model fits (seconds–minutes).
- **After nested search (Task 4):** regression spaces total 40 configs (Ridge 4, ElasticNet 12, RF 6, XGB 9, LGBM 9); classification 27 (LogReg 3, RF 6, XGB 9, LGBM 9). Inner folds per outer fold sum to 3 (0+1+2). Regression: 2 tasks × 2 contexts × 40 × 3 ≈ 480 fits; classification: 2 × 2 × 27 × 3 ≈ 324 fits; plus 8 champions + ~2× the candidate set for holdout refits and the un-searched ablation matrix. Total roughly **~1,500–2,000 small model fits**, each ≤ ~1,300 rows × 6–9 features, `n_jobs=1`. Estimated **~30–60 minutes single-threaded** in Docker. Search runs are deterministic and can be split by context/task if needed.

## G. Decisions to approve before implementation

1. **Grid parity semantics (Task 5):** use qualifying position as the post-qualifying grid proxy for all rows (recommended), OR keep the official grid with a per-row source marker and mixed semantics.
2. **`mord` dependency (Task 7):** add ordinal regression (`mord`) to `requirements.txt` + rebuild images (recommended for a stronger thesis), OR ship ranking models only and skip ordinal.
3. **Significance thresholds:** adopt `p < 0.05` paired permutation and 95% paired-bootstrap CIs as the predeclared significance rule (recommended).
4. **Search budgets:** confirm the exact config counts in `REGRESSION_SEARCH_SPACES`/`CLASSIFICATION_SEARCH_SPACES` (the values above) — smaller budgets are possible if runtime must be reduced.
5. **Artifact policy (Task 9):** confirm whether `models_store/experiments/*` joblibs/CSVs are committed or gitignored.

---

Plan complete and saved to `docs/superpowers/plans/2026-08-29-thesis-ml-rigor.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
