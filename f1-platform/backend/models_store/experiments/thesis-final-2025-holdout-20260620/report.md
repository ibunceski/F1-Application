# F1 ML Experiment Report

- Experiment ID: `thesis-final-2025-holdout-20260620`
- Completed at: `2026-06-19T23:48:39.461358+00:00`
- Development seasons: `[2021, 2023, 2024]`
- Final held-out season: `2025`
- Seed: `42`

## Rolling-origin validation champions

| Context | Task | Champion | Primary metric | Mean validation score | Std. dev. |
| --- | --- | --- | --- | ---: | ---: |
| post_qualifying | podium_model | RandomForestClassifier | pr_auc | 0.6888 | nan |
| post_qualifying | position_gain_model | ElasticNet | mae | 2.7966 | nan |
| post_qualifying | position_model | Ridge | mae | 2.8037 | nan |
| post_qualifying | top10_model | LogisticRegression | roc_auc | 0.9125 | nan |
| pre_qualifying | podium_model | RandomForestClassifier | pr_auc | 0.4943 | nan |
| pre_qualifying | position_gain_model | ZeroChangeBaseline | mae | 2.8977 | nan |
| pre_qualifying | position_model | Ridge | mae | 3.4263 | nan |
| pre_qualifying | top10_model | LogisticRegression | roc_auc | 0.8527 | nan |

## Final completed-season evaluation

| Context | Task | Algorithm | Primary metric | Score |
| --- | --- | --- | --- | ---: |
| pre_qualifying | position_model | Ridge | mae | 3.9042 |
| pre_qualifying | top10_model | LogisticRegression | roc_auc | 0.7595 |
| pre_qualifying | podium_model | RandomForestClassifier | pr_auc | 0.5228 |
| pre_qualifying | position_gain_model | ZeroChangeBaseline | mae | 3.3220 |
| post_qualifying | position_model | Ridge | mae | 3.2581 |
| post_qualifying | top10_model | LogisticRegression | roc_auc | 0.8368 |
| post_qualifying | podium_model | RandomForestClassifier | pr_auc | 0.7501 |
| post_qualifying | position_gain_model | ElasticNet | mae | 3.2606 |

## Reproducibility notes

This report was generated using only completed seasons that passed the database completeness gate. Weather fields were excluded because their current target-race provenance is not bounded by the prediction cutoff. The final held-out season was not used for model family selection or classification-threshold selection.
