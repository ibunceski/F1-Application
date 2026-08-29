# Final Thesis Experiment Results

## Reproducibility record

- **Authoritative experiment ID:** `f1-2025holdout-20260829T221238Z`
- **Completion timestamp:** `2026-08-29T22:17:49Z`
- **Seed:** `42`
- **Contexts:** `pre_qualifying`, `post_qualifying`
- **Validation strategy:** expanding rolling origin by completed season
- **Artifact directory:** `f1-platform/backend/models_store/experiments/f1-2025holdout-20260829T221238Z/`
- **Artifact validation:** passed; 8 champion joblibs, 10 PNG figures, and a `significance.json` present.

The final experiment command was:

```bash
docker compose run --rm ingestion python ml_pipeline/train_models.py \
  --train-seasons 2021 2022 2023 2024 \
  --evaluation-seasons 2025 \
  --min-train-seasons 1 \
  --context all \
  --seed 42 \
  --artifact-output-dir models_store \
  --model-output-dir models_store \
  --generate-plots
```

`--min-train-seasons 1` produces the documented three-fold expanding design: each fold trains on all earlier completed seasons and validates on the next one.

### What changed relative to `f1-2025holdout-20260829T172358Z`

This experiment is the first with the full thesis-rigor framework:

1. **Grid-definition parity:** post-qualifying `grid_position` now always uses the qualifying position (the value genuinely available at the "post-qualifying, pre-race" prediction time), instead of the official final grid for historical rows. A `grid_position_source` marker is recorded. Feature rows were regenerated with `--force`.
2. **Nested hyperparameter search** with predeclared, bounded budgets (≈40 regression / ≈27 classification configurations), selected on an expanding inner split of each fold's training seasons only.
3. **New candidate families:** ordinal regression (`OrdinalRidge`, `LogisticAT` via `mord`), race-grouped ranking (`LGBMRank` lambdarank, `XGBRank` rank:pairwise), and calibrated classifiers (`RandomForestClassifierCalibrated`, `LGBMClassifierCalibrated`).
4. **Statistical uncertainty:** race-cluster bootstrap 95% confidence intervals and paired (race-aligned) permutation tests, persisted in `significance.json`.

Weather fields remain excluded from all candidates. The final held-out season was never used for any selection decision.

## Data audit and split

The database audit found 2021, 2022, 2023, 2024, and 2025 fully scheduled and with complete race/qualifying coverage. 2026 had future scheduled races and only partial results, so it was excluded from every partition.

| Purpose | Seasons | Reason |
| --- | --- | --- |
| Development pool | 2021, 2022, 2023, 2024 | Completed seasons with usable features and targets |
| Rolling validation folds | train 2021 → validate 2022; train 2021-2022 → validate 2023; train 2021-2023 → validate 2024 | Strictly chronological |
| Final held-out evaluation | 2025 | Latest completed season; never used for selection |

Feature-row counts after regeneration: 420/440/440/479/479 for pre-qualifying and 440/440/440/479/479 for post-qualifying in 2021/2022/2023/2024/2025. 2022 still has no lap data, so `avg_race_pace_ms` is median-filled for ~88% of 2022 rows.

## Validation-selected champions

Mean rolling-validation selection metric across the three folds (2022, 2023, 2024). Regression primary metric is MAE; Top 10 uses ROC-AUC; podium uses PR-AUC.

| Context | Task | Champion | Primary metric | Mean score | Std. dev. |
| --- | --- | --- | --- | ---: | ---: |
| Pre | Finishing position | **LogisticAT** (ordinal) | MAE | 3.603 | ±0.245 |
| Post | Finishing position | **LogisticAT** (ordinal) | MAE | 3.134 | ±0.409 |
| Pre | Top 10 | Logistic Regression | ROC-AUC | 0.820 | ±0.029 |
| Post | Top 10 | Logistic Regression | ROC-AUC | 0.863 | ±0.043 |
| Pre | Podium | Logistic Regression | PR-AUC | 0.540 | ±0.067 |
| Post | Podium | Logistic Regression | PR-AUC | 0.685 | ±0.043 |
| Pre | Position gain/loss | Zero-change baseline | MAE | 3.645 | ±0.664 |
| Post | Position gain/loss | Ridge | MAE | 3.577 | ±0.686 |

The headline change is that **ordinal regression (proportional-odds logistic, `LogisticAT`) now wins the finishing-position task in both contexts**, displacing Ridge. The two ordinal models (`LogisticAT`, `OrdinalRidge`) occupy ranks 1 and 2 in both contexts:

| Context | rank 1 | rank 2 | rank 3 (prev. champion) |
| --- | --- | --- | --- |
| Post | LogisticAT 3.134 | OrdinalRidge 3.236 | Ridge 3.253 |
| Pre | LogisticAT 3.603 | OrdinalRidge 3.697 | Ridge 3.705 |

## Statistical significance and confidence intervals

`significance.json` records race-cluster bootstrap 95% CIs for each champion and runner-up, plus a paired (race-aligned) permutation test. Interpretation follows the thesis rule: report effect sizes, CIs, and p-values together; p < 0.05 is evidence of a real difference, not the sole arbiter.

| Context | Task | Champion vs runner-up | Paired p-value | Significant (p<0.05)? |
| --- | --- | --- | ---: | --- |
| Post | Position | LogisticAT vs OrdinalRidge | 0.0002 | yes |
| Pre | Position | LogisticAT vs OrdinalRidge | 0.0004 | yes |
| Post | Top 10 | Logistic Regression vs LGBM | 0.080 | no |
| Pre | Top 10 | Logistic Regression vs RF | 0.140 | no |
| Post | Podium | Logistic Regression vs RF | 0.0002 | yes |
| Pre | Podium | Logistic Regression vs RF-calibrated | 0.0002 | yes |
| Post | Gain/loss | Ridge vs LGBM | 0.235 | no |
| Pre | Gain/loss | Zero-change vs ElasticNet | 0.0002 | yes |

Notably, the Top-10 comparisons are **not** statistically significant: the linear/logistic and tree models are indistinguishable on ROC-AUC in this small-data regime. The finish-position and podium differences are statistically significant.

## Final 2025 held-out results

Confirmatory: selection was frozen before 2025 was evaluated.

| Context | Task | Champion | MAE | RMSE | R² | Rank / classification detail |
| --- | --- | --- | ---: | ---: | ---: | --- |
| Pre | Position | LogisticAT | 3.896 | 4.981 | 0.250 | race Spearman 0.506; within-2 acc 0.390 |
| Post | Position | LogisticAT | 3.186 | 4.326 | 0.433 | race Spearman 0.653; within-2 acc 0.517 |
| Pre | Gain/loss | Zero-change | 3.322 | 4.775 | ~0.000 | sign acc 0.182 |
| Post | Gain/loss | Ridge | 3.277 | 4.333 | 0.188 | sign acc 0.561 |
| Pre | Top 10 | LogReg | — | — | — | ROC-AUC 0.759; PR-AUC 0.764; F1 0.662; Brier 0.199 |
| Post | Top 10 | LogReg | — | — | — | ROC-AUC 0.837; PR-AUC 0.839; F1 0.766; Brier 0.163 |
| Pre | Podium | LogReg | — | — | — | PR-AUC 0.580; ROC-AUC 0.892; F1 0.602; Brier 0.133 |
| Post | Podium | LogReg | — | — | — | PR-AUC 0.765; ROC-AUC 0.941; F1 0.701; Brier 0.102 |

Frozen classification thresholds: pre top-10 0.55, pre podium 0.65, post top-10 0.40, post podium 0.80.

## Model-family comparison findings

- **Ordinal regression wins finishing position.** `LogisticAT` (proportional-odds) and `OrdinalRidge` are the two best position models in both contexts, ahead of Ridge/ElasticNet and the tree/boosters. This is consistent with the target being inherently ordered (1st < 2nd < …). Holdout MAE improved from 3.918 (prior pre Ridge) to 3.896 and from 3.283 (prior post Ridge) to 3.186.
- **Ranking objectives underperformed.** `LGBMRank` (MAE 8.13) and `XGBRank` (MAE 8.85) are the worst position models. Their relevance scores do not map to absolute finishing positions, so the rank→position conversion produces poor MAE. This is a negative finding: listwise/pairwise ranking did not help this small-data, absolute-position task.
- **Calibration did not change champions.** The calibrated tree variants did not win any task; logistic regression (already well calibrated) remains the champion classifier. The calibrated Random Forest was the runner-up for pre-qualifying podium.
- **Simple linear/logistic models still dominate** top-10, podium, and gain/loss, confirming the earlier finding that more complex boosters are not automatically better on ~1,700 rows.

## Pre- versus post-qualifying comparison

Post-qualifying information materially improves three tasks on the 2025 holdout:

- Finishing-position MAE improved by **0.710 positions** (3.896 → 3.186), race Spearman 0.506 → 0.653.
- Top-10 ROC-AUC improved by **0.078** (0.759 → 0.837); Brier fell 0.199 → 0.163.
- Podium PR-AUC improved by **0.185** (0.580 → 0.765), the strongest information-context result.
- Position-gain MAE improved by only **0.045 positions** (3.322 → 3.277); the pre-qualifying model still does not beat zero change.

## Feature-ablation findings

The ablation results (multi-fold validation matrix) are consistent with the prior experiment and remain available under `ablations/`. The all-feature post-qualifying set (including grid/qualifying) is the strongest for position, top-10, and podium; pre-qualifying form-only is essentially tied with the full pre-qualifying set for position and top-10.

## Appropriate thesis use

### Abstract

Use the held-out 2025 finding that post-qualifying models improved finishing-position MAE from 3.896 to 3.186 and podium PR-AUC from 0.580 to 0.765 relative to the pre-qualifying context, and that **ordinal regression (`LogisticAT`) is the best model for finishing position in both contexts**, beating point regression and ranking objectives. State that the comparison is chronological and held out, validated across three rolling folds (2022–2024) with race-cluster bootstrap CIs and paired permutation tests.

### Results chapter

Use the champion and final-holdout tables above, the significance table (CIs + p-values), calibration metrics (Brier/log loss), and the generated figures under `figures/`. Emphasize (1) ordinal regression wins the position task; (2) ranking objectives underperform; (3) simple linear/logistic models still win the remaining tasks; (4) Top-10 differences are not statistically significant, so the "which model" claim there must be qualified. Include the zero-change pre-qualifying gain/loss winner as a negative finding.

### Limitations section

State all of the following:

- Lap data was not ingested for 2022, so `avg_race_pace_ms` is median-filled for ~88% of 2022 training rows.
- Race incidents, safety cars, red flags, reliability failures, and strategy are not observed at prediction time.
- Weather remains uncertain; target-race weather fields were excluded pending leakage-safe forecast provenance.
- Podium classification is class-imbalanced; PR-AUC, calibration, and confidence intervals matter more than raw accuracy.
- Competitive order and regulations change between seasons; a 2025 holdout does not guarantee stability under future rule/car changes.
- Ranking-model MAE is computed on rank-derived positions (rank 1 = best), not raw scores, which inflates their absolute MAE.
- Classification thresholds are selected on the candidate's default configuration, not the search-tuned one; primary ROC-AUC/PR-AUC are threshold-independent.
- Calibration mapping uses internal random cross-validation (cv=3) within each fold's training data (a non-temporal calibration step, not model selection).
- Search spaces are predeclared in code (`ml_pipeline/hyperparameter_search.py`); the manifest records the selected configs and data fingerprints.

## Artifact inventory

The experiment contains `manifest.json`, `config.json`, `significance.json`, candidate and ablation result tables, row-level out-of-fold predictions, calibration/reliability files, final-holdout results, eight promoted champion joblibs, and ten PNG figures.

## Historical experiment reference

Earlier experiments are preserved in `f1-platform/backend/models_store/experiments/` for reference and are superseded by this run:

- `thesis-final-2025-holdout-20260620-r3` (2021/2023/2024 only) predates the 2022 recovery.
- `f1-2025holdout-20260828T203629Z` is the two-fold run (`--min-train-seasons 2`).
- `f1-2025holdout-20260829T172358Z` is the three-fold run before the grid-parity fix, nested search, and new candidate families. Its Ridge/LogisticRegression champions are preserved as the pre-rigor baseline; this experiment's ordinal-model champion supersedes Ridge for finishing position.
