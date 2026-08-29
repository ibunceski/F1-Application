# Final Thesis Experiment Results

## Reproducibility record

- **Authoritative experiment ID:** `f1-2025holdout-20260829T172358Z`
- **Completion timestamp:** `2026-08-29T17:27:02.672669+00:00`
- **Seed:** `42`
- **Contexts:** `pre_qualifying`, `post_qualifying`
- **Validation strategy:** expanding rolling origin by completed season
- **Artifact directory:** `f1-platform/backend/models_store/experiments/f1-2025holdout-20260829T172358Z/`
- **Artifact validation:** passed; 8 champion joblibs and 10 PNG figures are present.

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

This experiment supersedes the earlier two-fold run `f1-2025holdout-20260828T203629Z` (which used `--min-train-seasons 2`, producing folds at 2023 and 2024 only). The three-fold design includes a 2021 -> 2022 validation fold, which is the stronger and previously documented methodology. The older run is preserved in `models_store/experiments/` as a historical reference. It was superseded in two ways:

1. The 2022 season gap was closed (see below).
2. A stale-feature-row bug in `feature_engineering.py` was fixed: `--force` previously upserted new rows but never deleted rows whose entry disappeared after 2022 race results were recovered. The feature snapshot is now consistent with the current entry lists.

## Data audit and split

The database audit found 2021, 2022, 2023, 2024, and 2025 fully scheduled and with complete race/qualifying coverage. Season 2026 had future scheduled races and only partial results, so it was excluded from every training, validation, and test partition.

| Purpose | Seasons | Reason |
| --- | --- | --- |
| Development pool | 2021, 2022, 2023, 2024 | Completed seasons with usable features and targets |
| Rolling validation folds | train: 2021 -> validate: 2022; train: 2021-2022 -> validate: 2023; train: 2021-2023 -> validate: 2024 | Strictly chronological, no later race in training |
| Final held-out evaluation | 2025 | Latest completed season; never used for selection or threshold fitting |

This experiment uses **three rolling validation folds**, providing robust champion selection across multiple seasons. The manifest records the exact fold splits:

```text
fold_1_2022: train [2021]      -> validate 2022
fold_2_2023: train [2021, 2022] -> validate 2023
fold_3_2024: train [2021, 2022, 2023] -> validate 2024
```

Note on 2022 pace features: lap data was not ingested for 2022 (only race results and qualifying results were available), so `avg_race_pace_ms` is missing for ~88% of 2022 rows and is median-filled during feature engineering. This degrades pace-based features for the 2022 validation fold (and for 2022 training rows in later folds) but does not affect the validity of the other features or the final 2025 holdout evaluation.

Feature-row counts in the final snapshot were 420/440/440/479/479 for pre-qualifying and 440/440/440/479/479 for post-qualifying in 2021/2022/2023/2024/2025 respectively. These counts match the manifest's `data_fingerprints.season_counts` and were regenerated with the stale-row fix so no obsolete rows leak into training. No missing target label was imputed: finishing-position and gain/loss models used only their defined eligible rows, while classifiers used existing race-result labels.

## Validation-selected champions

The table reports the mean rolling-validation selection metric across all three folds (2022, 2023, 2024). Regression primary metric is MAE; Top 10 uses ROC-AUC; podium uses PR-AUC.

| Context | Task | Champion | Primary validation metric | Mean score | Std. dev. |
| --- | --- | --- | --- | ---: | ---: |
| Pre | Finishing position | Ridge | MAE | 3.705 | ±0.240 |
| Post | Finishing position | Ridge | MAE | 3.251 | ±0.372 |
| Pre | Top 10 | Logistic Regression | ROC-AUC | 0.820 | ±0.029 |
| Post | Top 10 | Logistic Regression | ROC-AUC | 0.862 | ±0.044 |
| Pre | Podium | Logistic Regression | PR-AUC | 0.539 | ±0.067 |
| Post | Podium | Logistic Regression | PR-AUC | 0.687 | ±0.050 |
| Pre | Position gain/loss | Zero-change baseline | MAE | 3.645 | ±0.664 |
| Post | Position gain/loss | Ridge | MAE | 3.250 | ±0.372 |

The pre-qualifying gain/loss result is intentionally reported as a weak result: a no-change baseline won validation, so there is no support for claiming learned pre-qualifying gain/loss skill. Compared to the two-fold run, the champions are unchanged in family (Ridge for regression, Logistic Regression for classification), and the three-fold mean validation scores are broadly consistent (within ~0.1 MAE / ~0.01-0.02 PR-AUC), confirming that the additional 2022 validation fold did not destabilise model selection.

## Final 2025 held-out results

These metrics are confirmatory: selection was frozen before 2025 was evaluated.

| Context | Task | Champion | MAE | RMSE | R² | Rank/Scores |
| --- | --- | --- | ---: | ---: | ---: | --- |
| Pre | Finishing position | Ridge | 3.918 | 4.868 | 0.284 | mean race Spearman 0.506 |
| Post | Finishing position | Ridge | 3.283 | 4.256 | 0.451 | mean race Spearman 0.647 |
| Pre | Position gain/loss | Zero-change baseline | 3.322 | 4.775 | -0.000 | sign accuracy 0.182 |
| Post | Position gain/loss | Ridge | 3.283 | 4.256 | 0.217 | sign accuracy 0.538 |
| Pre | Top 10 | Logistic Regression | — | — | — | ROC-AUC 0.759; PR-AUC 0.764; F1 0.662; Brier 0.199 |
| Post | Top 10 | Logistic Regression | — | — | — | ROC-AUC 0.837; PR-AUC 0.839; F1 0.763; Brier 0.163 |
| Pre | Podium | Logistic Regression | — | — | — | PR-AUC 0.580; ROC-AUC 0.892; F1 0.602; Brier 0.133 |
| Post | Podium | Logistic Regression | — | — | — | PR-AUC 0.766; ROC-AUC 0.941; F1 0.706; Brier 0.102 |

Additional final classification detail:

| Context | Task | Precision | Recall | Balanced accuracy | Log loss |
| --- | --- | ---: | ---: | ---: | ---: |
| Pre | Top 10 | 0.754 | 0.590 | 0.696 | 0.584 |
| Post | Top 10 | 0.730 | 0.800 | 0.751 | 0.497 |
| Pre | Podium | 0.491 | 0.778 | 0.816 | 0.420 |
| Post | Podium | 0.667 | 0.750 | 0.842 | 0.319 |

## Pre- versus post-qualifying comparison

Post-qualifying information materially improved three tasks on the 2025 holdout:

- Finishing-position MAE improved by **0.635 positions** (3.918 -> 3.283), with rank correlation improving from 0.506 to 0.647.
- Top 10 ROC-AUC improved by **0.078** (0.759 -> 0.837), while Brier score fell from 0.199 to 0.163.
- Podium PR-AUC improved by **0.186** (0.580 -> 0.766), the strongest information-context result.
- Position-gain MAE improved by only **0.039 positions** (3.322 -> 3.283). The post-qualifying Ridge model has meaningful sign accuracy (0.538), but the pre-qualifying model does not beat zero change.

The evidence supports stating that qualifying/grid information is especially valuable for finishing order and podium discrimination. It does **not** support a strong claim that pre-race information alone reliably predicts position gain/loss.

## Feature-ablation findings

The ablation results below are based on the multi-fold validation matrix. Scores are means across folds.

| Context | Task | Best subset | Metric | Score | Interpretation |
| --- | --- | --- | --- | ---: | --- |
| Post | Finishing position | All, including grid/qualifying | MAE | 3.251 | Clear improvement over form-only |
| Post | Top 10 | All, including grid/qualifying | ROC-AUC | 0.862 | Above form-only |
| Post | Podium | All, including grid/qualifying | PR-AUC | 0.687 | Above form-only |
| Post | Gain/loss | All, including grid/qualifying | MAE | 3.250 | Small gain over form-only |
| Pre | Finishing position | Form only | MAE | 3.703 | Essentially tied with all features |
| Pre | Top 10 | Form only | ROC-AUC | 0.820 | Essentially tied with all features |
| Pre | Podium | All features | PR-AUC | 0.539 | Modest gain over form-only |
| Pre | Gain/loss | Any subset; zero-change baseline | MAE | 3.645 | No demonstrated feature contribution |

## Appropriate thesis use

### Abstract

Use the held-out 2025 finding that post-qualifying models improved finishing-position MAE from 3.918 to 3.283 and podium PR-AUC from 0.580 to 0.766 relative to the pre-qualifying context. State that the comparison is chronological and held out, validated across three rolling folds on seasons 2022-2024.

### Results chapter

Use the complete champion and final-holdout tables above, calibration metrics (Brier/log loss), and generated artifacts under `figures/`. Emphasize that Ridge and Logistic Regression won every task, showing that more complex boosters were not automatically better. Include the zero-change pre-qualifying gain/loss winner as a negative finding. Note the 3-fold validation design as a key methodological strength over earlier iterations.

### Limitations section

State all of the following:

- Lap data was not ingested for 2022, so `avg_race_pace_ms` is median-filled for 2022 training rows; pace-based historical features are less informative for the first validation fold.
- Race incidents, safety cars, red flags, reliability failures, and strategy decisions are not observed at prediction time.
- Weather remains uncertain; target-race weather fields were excluded pending leakage-safe forecast provenance.
- Podium classification is class-imbalanced; PR-AUC, calibration, and confidence intervals matter more than raw accuracy.
- Competitive order and regulations change between seasons, so a 2025 holdout does not guarantee stability under future rule/car changes.
- Historical post-qualifying grid values must remain aligned with the live official-grid feature contract.

## Artifact inventory

The experiment contains `manifest.json`, `config.json`, candidate and ablation result tables, row-level out-of-fold predictions, calibration/reliability files, final-holdout results, eight promoted champion joblibs, and ten PNG figures. The manifest fingerprints are:

- Pre-qualifying: `87f54a1c7f5a5985d83be77829b5e602cbeb11cd87891210be4a6e4587aa89ca`
- Post-qualifying: `62fc42015aaf6724844ff9fc5a29bcb18623bb07b962e50bcfc5ea0f88ba8d89`

## Historical experiment reference

Two earlier experiments are preserved in `f1-platform/backend/models_store/experiments/` for reference:

- `thesis-final-2025-holdout-20260620-r3` (trained on 2021, 2023, 2024 with 2025 held out) predates the 2022 recovery.
- `f1-2025holdout-20260828T203629Z` is the two-fold run (`--min-train-seasons 2`) whose validation folds were 2023 and 2024 only. Its holdout metrics are closely consistent with the final three-fold experiment (within 0.005 MAE and 0.01 PR-AUC on all tasks), confirming that the added 2022 fold and the stale-row cleanup did not destabilise the learned models.