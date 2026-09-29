# F1 ML Experiment Report

- Experiment ID: `f1-2025holdout-20260831T185450Z`
- Completed at: `2026-08-31T19:01:26.328224+00:00`
- Development seasons: `[2021, 2022, 2023, 2024]`
- Final held-out season: `2025`
- Seed: `42`

## Rolling-origin validation champions

| Context | Task | Champion | Primary metric | Mean validation score | Std. dev. |
| --- | --- | --- | --- | ---: | ---: |
| post_qualifying | podium_model | LogisticRegression | pr_auc | 0.6738 | 0.0420 |
| post_qualifying | position_gain_model | ElasticNet | mae | 3.5479 | 0.6630 |
| post_qualifying | position_model | LogisticAT | mae | 3.1749 | 0.4906 |
| post_qualifying | top10_model | RandomForestClassifierCalibrated | roc_auc | 0.8588 | 0.0436 |
| pre_qualifying | podium_model | RandomForestClassifierCalibrated | pr_auc | 0.5454 | 0.0610 |
| pre_qualifying | position_gain_model | ZeroChangeBaseline | mae | 3.6449 | 0.6643 |
| pre_qualifying | position_model | LogisticAT | mae | 3.5939 | 0.3167 |
| pre_qualifying | top10_model | LGBMClassifier | roc_auc | 0.8223 | 0.0369 |

## Final completed-season evaluation

| Context | Task | Algorithm | Primary metric | Score |
| --- | --- | --- | --- | ---: |
| pre_qualifying | position_model | LogisticAT | mae | 3.7521 |
| pre_qualifying | position_model | MedianBaseline | mae | 4.9746 |
| pre_qualifying | top10_model | LGBMClassifier | roc_auc | 0.7810 |
| pre_qualifying | top10_model | PrevalenceBaseline | roc_auc | 0.5000 |
| pre_qualifying | podium_model | RandomForestClassifierCalibrated | pr_auc | 0.5834 |
| pre_qualifying | podium_model | PrevalenceBaseline | pr_auc | 0.1525 |
| pre_qualifying | position_gain_model | ZeroChangeBaseline | mae | 3.3220 |
| post_qualifying | position_model | LogisticAT | mae | 3.1130 |
| post_qualifying | position_model | QualifyingPositionBaseline | mae | 3.3431 |
| post_qualifying | top10_model | RandomForestClassifierCalibrated | roc_auc | 0.8364 |
| post_qualifying | top10_model | PrevalenceBaseline | roc_auc | 0.5000 |
| post_qualifying | podium_model | LogisticRegression | pr_auc | 0.7832 |
| post_qualifying | podium_model | PrevalenceBaseline | pr_auc | 0.1506 |
| post_qualifying | position_gain_model | ElasticNet | mae | 3.2354 |
| post_qualifying | position_gain_model | ZeroChangeBaseline | mae | 3.3473 |

## Reproducibility notes

This report was generated using only completed seasons that passed the database completeness gate. Weather fields were excluded because their current target-race provenance is not bounded by the prediction cutoff. The final held-out season was not used for model family selection or classification-threshold selection.
