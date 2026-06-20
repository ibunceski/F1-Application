# Final Thesis Experiment Results

## Reproducibility record

- **Authoritative experiment ID:** `thesis-final-2025-holdout-20260620-r3`
- **Completion timestamp:** `2026-06-19T23:52:23.553445+00:00`
- **Seed:** `42`
- **Contexts:** `pre_qualifying`, `post_qualifying`
- **Artifact directory:** `f1-platform/backend/models_store/experiments/thesis-final-2025-holdout-20260620-r3/`
- **Artifact validation:** passed; 8 champion joblibs and 10 CSV-derived figures are present.

The final experiment command was:

```bash
docker compose run --rm ingestion python ml_pipeline/train_models.py \
  --train-seasons 2021 2023 2024 \
  --evaluation-seasons 2025 \
  --min-train-seasons 2 \
  --context all \
  --experiment-id thesis-final-2025-holdout-20260620-r3 \
  --seed 42 \
  --artifact-output-dir models_store \
  --model-output-dir models_store
```

Figures were generated afterwards from the saved CSV artifacts, not hard-coded values:

```bash
docker compose run --rm ingestion python -c "from pathlib import Path; from ml_pipeline.train_models import generate_thesis_figures; generate_thesis_figures(Path('models_store/experiments/thesis-final-2025-holdout-20260620-r3'))"
```

The run completed successfully before deployment promotion. The configured production filenames were updated only by the successful `r3` run. Two earlier immutable experiment directories (`...-r1` and `...-r2`) were left as incomplete pre-promotion attempts after optional plot-rendering errors; they are not the reported experiment and are not eligible as successful Model Lab artifacts.

## Data audit and split

The database audit found 2021, 2023, 2024, and 2025 fully scheduled and with complete race/qualifying coverage. Season 2022 had all qualifying rows but no race-result rows, so it was excluded. Season 2026 had future scheduled races and only partial results, so it was excluded from every training, validation, and test partition.

| Purpose | Seasons | Reason |
| --- | --- | --- |
| Development pool | 2021, 2023, 2024 | Completed seasons with usable features and targets |
| Rolling validation fold | train: 2021, 2023 → validate: 2024 | Strictly chronological, no later race in training |
| Final held-out evaluation | 2025 | Latest completed season; never used for selection or threshold fitting |

This is a reduced-evidence design: the missing 2022 race results leave only **one outer validation fold**. `--min-train-seasons 2` was therefore necessary. The final 2025 holdout remains valid, but cross-season uncertainty is higher than in the original three-training-season-per-fold design.

Feature-row counts in the final snapshot were 420/440/479/479 for pre-qualifying and 439/440/479/479 for post-qualifying in 2021/2023/2024/2025 respectively. No missing target label was imputed: finishing-position and gain/loss models used only their defined eligible rows, while classifiers used existing race-result labels.

## Validation-selected champions

The table reports the rolling-validation selection metric on 2024. Regression primary metric is MAE; Top 10 uses ROC-AUC; podium uses PR-AUC.

| Context | Task | Champion | Primary validation metric | Score |
| --- | --- | --- | --- | ---: |
| Pre | Finishing position | Ridge | MAE | 3.426 |
| Post | Finishing position | Ridge | MAE | 2.804 |
| Pre | Top 10 | Logistic Regression | ROC-AUC | 0.853 |
| Post | Top 10 | Logistic Regression | ROC-AUC | 0.912 |
| Pre | Podium | Random Forest Classifier | PR-AUC | 0.494 |
| Post | Podium | Random Forest Classifier | PR-AUC | 0.689 |
| Pre | Position gain/loss | Zero-change baseline | MAE | 2.898 |
| Post | Position gain/loss | ElasticNet | MAE | 2.797 |

The pre-qualifying gain/loss result is intentionally reported as a weak result: a no-change baseline won validation, so there is no support for claiming learned pre-qualifying gain/loss skill.

## Final 2025 held-out results

These metrics are confirmatory: selection was frozen before 2025 was evaluated.

| Context | Task | Champion | MAE | RMSE | R² | Rank/Scores |
| --- | --- | --- | ---: | ---: | ---: | --- |
| Pre | Finishing position | Ridge | 3.904 | 4.861 | 0.286 | mean race Spearman 0.510 |
| Post | Finishing position | Ridge | 3.258 | 4.251 | 0.452 | mean race Spearman 0.649 |
| Pre | Position gain/loss | Zero-change baseline | 3.322 | 4.775 | -0.000 | sign accuracy 0.182 |
| Post | Position gain/loss | ElasticNet | 3.261 | 4.249 | 0.219 | sign accuracy 0.544 |
| Pre | Top 10 | Logistic Regression | — | — | — | ROC-AUC 0.759; PR-AUC 0.765; F1 0.679; Brier 0.199 |
| Post | Top 10 | Logistic Regression | — | — | — | ROC-AUC 0.837; PR-AUC 0.840; F1 0.766; Brier 0.164 |
| Pre | Podium | Random Forest Classifier | — | — | — | PR-AUC 0.523; ROC-AUC 0.887; F1 0.578; Brier 0.097 |
| Post | Podium | Random Forest Classifier | — | — | — | PR-AUC 0.750; ROC-AUC 0.945; F1 0.734; Brier 0.067 |

Additional final classification detail:

| Context | Task | Precision | Recall | Balanced accuracy | Log loss |
| --- | --- | ---: | ---: | ---: | ---: |
| Pre | Top 10 | 0.739 | 0.628 | 0.700 | 0.584 |
| Post | Top 10 | 0.731 | 0.804 | 0.753 | 0.498 |
| Pre | Podium | 0.447 | 0.819 | 0.818 | 0.303 |
| Post | Podium | 0.639 | 0.861 | 0.887 | 0.222 |

## Pre- versus post-qualifying comparison

Post-qualifying information materially improved three tasks on the 2025 holdout:

- Finishing-position MAE improved by **0.646 positions** (3.904 → 3.258), with rank correlation improving from 0.510 to 0.649.
- Top 10 ROC-AUC improved by **0.077** (0.759 → 0.837), while Brier score fell from 0.199 to 0.164.
- Podium PR-AUC improved by **0.227** (0.523 → 0.750), the strongest information-context result.
- Position-gain MAE improved by only **0.061 positions** (3.322 → 3.261). The post-qualifying ElasticNet has meaningful sign accuracy (0.544), but the pre-qualifying model does not beat zero change.

The evidence supports stating that qualifying/grid information is especially valuable for finishing order and podium discrimination. It does **not** support a strong claim that pre-race information alone reliably predicts position gain/loss.

## Feature-ablation findings

The following are the best validation feature subsets for each context/task. They use the same temporal fold and candidate matrix, so they are descriptive but based on a single validation season.

| Context | Task | Best subset | Metric | Score | Interpretation |
| --- | --- | --- | --- | ---: | --- |
| Post | Finishing position | All, including grid/qualifying | MAE | 2.804 | Clear improvement over form-only MAE 3.422 |
| Post | Top 10 | All, including grid/qualifying | ROC-AUC | 0.912 | Above form-only 0.848 |
| Post | Podium | All, including grid/qualifying | PR-AUC | 0.688 | Above form-only 0.469 |
| Post | Gain/loss | All, including grid/qualifying | MAE | 2.797 | Small gain over zero-change/form-only 2.906 |
| Pre | Finishing position | Form only | MAE | 3.423 | Essentially tied with all features (3.426) |
| Pre | Top 10 | Form only | ROC-AUC | 0.853 | Essentially tied with all features (0.853) |
| Pre | Podium | All features | PR-AUC | 0.507 | Modest gain over form-only 0.473 |
| Pre | Gain/loss | Any subset; zero-change baseline | MAE | 2.898 | No demonstrated feature contribution |

## Appropriate thesis use

### Abstract

Use the held-out 2025 finding that post-qualifying models improved finishing-position MAE from 3.904 to 3.258 and podium PR-AUC from 0.523 to 0.750 relative to the pre-qualifying context. State that the comparison is chronological and held out, but based on one outer validation fold.

### Results chapter

Use the complete champion and final-holdout tables above, calibration metrics (Brier/log loss), and generated artifacts under `figures/`. Emphasize that Ridge and Logistic Regression won several tasks, showing that more complex boosters were not automatically better. Include the zero-change pre-qualifying gain/loss winner as a negative finding.

### Limitations section

State all of the following:

- The missing 2022 race-result season reduced rolling validation to one fold.
- Race incidents, safety cars, red flags, reliability failures, and strategy decisions are not observed at prediction time.
- Weather remains uncertain; target-race weather fields were excluded pending leakage-safe forecast provenance.
- Podium classification is class-imbalanced; PR-AUC, calibration, and confidence intervals matter more than raw accuracy.
- Competitive order and regulations change between seasons, so a 2025 holdout does not guarantee stability under future rule/car changes.
- Historical post-qualifying grid values must remain aligned with the live official-grid feature contract.

## Artifact inventory

The experiment contains `manifest.json`, `config.json`, candidate and ablation result tables, row-level out-of-fold predictions, calibration/reliability files, final-holdout results, eight promoted champion joblibs, and ten PNG figures. The manifest fingerprints are:

- Pre-qualifying: `6acc990da748796a87633f3ce4bbd3a08eba187ef800706bc50a1db4e960e311`
- Post-qualifying: `587ad2f9edc1f1598fc5f0802f3f8ae91009e8a2da90f12e4ef561b4d68df0c3`
