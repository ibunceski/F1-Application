"""Artifact-only thesis reporting and figure generation.

This module deliberately does not import training code or database models.  It
is intended to be called once an immutable experiment directory exists, so all
plots and comparison tables remain reproducible from the persisted CSV/JSON
evidence alone.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


PHASES = ("validation", "final_holdout")
CONTEXTS = ("pre_qualifying", "post_qualifying")
REGRESSION_TASKS = ("position_model", "position_gain_model")
CLASSIFICATION_TASKS = ("top10_model", "podium_model")
PRIMARY_METRICS = {
    "position_model": "mae",
    "top10_model": "roc_auc",
    "podium_model": "pr_auc",
    "position_gain_model": "mae",
}
BASELINE_BY_TASK = {
    "position_model": "MedianBaseline",
    "top10_model": "PrevalenceBaseline",
    "podium_model": "PrevalenceBaseline",
    "position_gain_model": "ZeroChangeBaseline",
}


def _configure_matplotlib():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "figure.dpi": 120,
            "savefig.dpi": 300,
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.grid": True,
            "grid.alpha": 0.25,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    return plt


def _read_csv(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame(columns=columns)
    return pd.read_csv(path)


def _load_artifacts(experiment_dir: Path) -> dict[str, Any]:
    manifest_path = experiment_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    predictions = _read_csv(experiment_dir / "out_of_fold_predictions.csv.gz")
    return {
        "manifest": manifest,
        "aggregate": _read_csv(experiment_dir / "aggregate_results.csv"),
        "model_results": _read_csv(experiment_dir / "model_results.csv"),
        "final_results": _read_csv(experiment_dir / "final_holdout_results.csv"),
        "predictions": predictions,
        "reliability": _read_csv(experiment_dir / "reliability_bins.csv"),
        "ablations": _read_csv(experiment_dir / "ablations" / "aggregate_results.csv"),
    }


def _as_binary(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.astype(int)
    return values.astype(str).str.strip().str.lower().map({"true": 1, "false": 0, "1": 1, "0": 0})


def _metric(task: str, rows: pd.DataFrame) -> float:
    actual = pd.to_numeric(rows.get("actual"), errors="coerce")
    if task in REGRESSION_TASKS:
        prediction = pd.to_numeric(rows.get("prediction"), errors="coerce")
        valid = actual.notna() & prediction.notna()
        if not valid.any():
            return float("nan")
        return float(np.abs(actual[valid] - prediction[valid]).mean())
    probability = pd.to_numeric(rows.get("probability"), errors="coerce")
    target = _as_binary(rows.get("actual", pd.Series(dtype=object)))
    valid = target.notna() & probability.notna()
    target, probability = target[valid].astype(int).to_numpy(), probability[valid].to_numpy(dtype=float)
    if len(np.unique(target)) != 2:
        return float("nan")
    if task == "top10_model":
        positives, negatives = int(target.sum()), int((1 - target).sum())
        order = np.argsort(probability, kind="stable")
        ranks = np.empty(len(order), dtype=float)
        ranks[order] = np.arange(1, len(order) + 1)
        # The Mann-Whitney formulation of ROC-AUC; ties are uncommon in
        # persisted probabilities and receive deterministic stable ranks.
        return float((ranks[target == 1].sum() - positives * (positives + 1) / 2) / (positives * negatives))
    order = np.argsort(-probability, kind="stable")
    sorted_target = target[order]
    precision = np.cumsum(sorted_target) / np.arange(1, len(sorted_target) + 1)
    return float((precision * sorted_target).sum() / sorted_target.sum())


def _champions(aggregate: pd.DataFrame) -> pd.DataFrame:
    required = {"context", "task", "algorithm"}
    if aggregate.empty or not required.issubset(aggregate.columns):
        return pd.DataFrame(columns=["context", "task", "algorithm"])
    if "champion" in aggregate.columns:
        champions = aggregate[aggregate["champion"].fillna(False)].copy()
        if not champions.empty:
            return champions
    if "rank" in aggregate.columns:
        return aggregate[pd.to_numeric(aggregate["rank"], errors="coerce") == 1].copy()
    return pd.DataFrame(columns=["context", "task", "algorithm"])


def _champion_predictions(predictions: pd.DataFrame, champions: pd.DataFrame, phase: str, task: str) -> pd.DataFrame:
    if predictions.empty or champions.empty:
        return pd.DataFrame()
    selected = champions[champions["task"] == task][["context", "task", "algorithm"]]
    rows = predictions[(predictions.get("phase") == phase) & (predictions.get("task") == task)].copy()
    if "analysis_type" in rows:
        rows = rows[rows["analysis_type"].fillna("candidate_model") == "candidate_model"]
    return rows.merge(selected, on=["context", "task", "algorithm"], how="inner")


def build_context_lift_summary(predictions: pd.DataFrame, aggregate: pd.DataFrame) -> pd.DataFrame:
    """Measure pre/post performance on the exact shared driver-race rows.

    The merge keys include phase, task, race and driver.  Consequently a
    pre-qualifying row can never be compared to a differently available
    post-qualifying row, and validation/holdout observations never mix.
    """
    champions = _champions(aggregate)
    output: list[dict[str, Any]] = []
    keys = ["phase", "task", "race_id", "driver_id"]
    for phase in PHASES:
        for task, metric in PRIMARY_METRICS.items():
            rows = _champion_predictions(predictions, champions, phase, task)
            pre = rows[rows.get("context") == "pre_qualifying"].copy()
            post = rows[rows.get("context") == "post_qualifying"].copy()
            if pre.empty or post.empty or not set(keys).issubset(rows.columns):
                continue
            merged = pre.merge(post, on=keys, suffixes=("_pre", "_post"), how="inner")
            if merged.empty:
                continue
            pre_rows = merged.rename(columns={"actual_pre": "actual", "prediction_pre": "prediction", "probability_pre": "probability"})
            post_rows = merged.rename(columns={"actual_post": "actual", "prediction_post": "prediction", "probability_post": "probability"})
            pre_score, post_score = _metric(task, pre_rows), _metric(task, post_rows)
            lift = pre_score - post_score if metric == "mae" else post_score - pre_score
            output.append(
                {
                    "phase": phase,
                    "task": task,
                    "metric": metric,
                    "common_driver_race_rows": int(len(merged)),
                    "pre_qualifying_score": pre_score,
                    "post_qualifying_score": post_score,
                    "context_lift": lift,
                    "positive_lift_definition": "MAE reduction" if metric == "mae" else "metric increase",
                }
            )
    return pd.DataFrame(output)


def build_champion_baseline_summary(aggregate: pd.DataFrame, model_results: pd.DataFrame) -> pd.DataFrame:
    """Create an auditable champion-versus-domain-baseline table.

    Validation baselines are candidate outputs persisted in the aggregate.
    The current experiment format may not persist final-holdout baseline fits;
    those rows are labelled unavailable rather than reconstructed with leakage.
    """
    champions = _champions(aggregate)
    rows: list[dict[str, Any]] = []
    for _, champion in champions.iterrows():
        context, task = champion["context"], champion["task"]
        baseline = "QualifyingPositionBaseline" if task == "position_model" and context == "post_qualifying" else BASELINE_BY_TASK[task]
        primary = PRIMARY_METRICS[task]
        baseline_rows = aggregate[(aggregate["context"] == context) & (aggregate["task"] == task) & (aggregate["algorithm"] == baseline)]
        baseline_score = baseline_rows.iloc[0].get("primary_score", np.nan) if not baseline_rows.empty else np.nan
        rows.append(
            {
                "phase": "validation",
                "context": context,
                "task": task,
                "metric": primary,
                "champion": champion["algorithm"],
                "champion_score": champion.get("primary_score", np.nan),
                "baseline": baseline,
                "baseline_score": baseline_score,
                "baseline_status": "persisted_candidate" if not baseline_rows.empty else "not_available",
            }
        )
        final = model_results[
            (model_results.get("phase") == "final_holdout")
            & (model_results.get("context") == context)
            & (model_results.get("task") == task)
        ]
        champion_final = final[final.get("algorithm") == champion["algorithm"]]
        baseline_final = final[final.get("algorithm") == baseline]
        rows.append(
            {
                "phase": "final_holdout",
                "context": context,
                "task": task,
                "metric": primary,
                "champion": champion["algorithm"],
                "champion_score": champion_final.iloc[0].get(primary, np.nan) if not champion_final.empty else np.nan,
                "baseline": baseline,
                "baseline_score": baseline_final.iloc[0].get(primary, np.nan) if not baseline_final.empty else np.nan,
                "baseline_status": "persisted_candidate" if not baseline_final.empty else "not_persisted_no_leakage_reconstruction",
            }
        )
    return pd.DataFrame(rows)


def _save(figure, output_dir: Path, stem: str, paths: list[Path]) -> None:
    png, svg = output_dir / f"{stem}.png", output_dir / f"{stem}.svg"
    figure.savefig(png, dpi=300, bbox_inches="tight")
    figure.savefig(svg, bbox_inches="tight")
    paths.extend([png, svg])


def _title(value: str) -> str:
    return value.replace("_model", "").replace("_", " ").title()


def _leaderboards(plt, aggregate: pd.DataFrame, final: pd.DataFrame, output: Path, paths: list[Path]) -> None:
    for phase in PHASES:
        source = aggregate if phase == "validation" else final
        if source.empty:
            continue
        for task in PRIMARY_METRICS:
            rows = source[source.get("task") == task].copy()
            if rows.empty:
                continue
            metric_columns = [PRIMARY_METRICS[task]]
            if task == "position_model" and (
                (phase == "validation" and "spearman_mean" in rows.columns)
                or (phase == "final_holdout" and "spearman" in rows.columns)
            ):
                metric_columns.append("spearman")
            figure, axes = plt.subplots(1, len(metric_columns), figsize=(7 * len(metric_columns), 5), squeeze=False)
            for axis, metric in zip(axes[0], metric_columns, strict=True):
                column = f"{metric}_mean" if phase == "validation" and f"{metric}_mean" in rows else metric
                if column not in rows:
                    axis.set_visible(False)
                    continue
                rows_for_metric = rows[pd.to_numeric(rows[column], errors="coerce").notna()].copy()
                if rows_for_metric.empty:
                    axis.set_visible(False)
                    continue
                ranking = rows_for_metric.sort_values(column, ascending=metric in {"mae", "rmse"})
                labels = (ranking["context"].str.replace("_", " ") + "\n" + ranking["algorithm"]).tolist()
                colors = ["#9a031e" if value in {"MedianBaseline", "QualifyingPositionBaseline", "PrevalenceBaseline", "ZeroChangeBaseline"} else "#005f73" for value in ranking["algorithm"]]
                axis.bar(np.arange(len(ranking)), pd.to_numeric(ranking[column], errors="coerce"), color=colors)
                axis.set_xticks(np.arange(len(ranking)), labels, rotation=35, ha="right")
                axis.set_ylabel(metric.replace("_", " ").upper())
                axis.set_title(f"{_title(task)} leaderboard")
            figure.suptitle(f"{_title(task)} — {phase.replace('_', ' ')}")
            figure.tight_layout()
            _save(figure, output, f"fig_leaderboard_{task}_{phase}", paths)
            plt.close(figure)


def _context_lift_plot(plt, summary: pd.DataFrame, output: Path, paths: list[Path]) -> None:
    for phase in PHASES:
        rows = summary[summary.get("phase") == phase] if not summary.empty else pd.DataFrame()
        if not rows.empty:
            rows = rows.replace([np.inf, -np.inf], np.nan).dropna(
                subset=["pre_qualifying_score", "post_qualifying_score", "context_lift"]
            )
        if rows.empty:
            continue
        figure, axis = plt.subplots(figsize=(10, 5))
        positions = np.arange(len(rows))
        bars = axis.barh(positions, rows["context_lift"], color="#005f73")
        axis.set_yticks(positions, [_title(task) + f" ({metric})" for task, metric in zip(rows["task"], rows["metric"], strict=True)])
        axis.axvline(0.0, color="#6c757d", linewidth=1)
        axis.set_xlabel("Post-qualifying improvement (task-specific metric units)")
        axis.set_title(f"Information-context lift on exact common driver-race rows — {phase.replace('_', ' ')}")
        for bar, (_, row) in zip(bars, rows.iterrows(), strict=True):
            axis.text(
                bar.get_width(),
                bar.get_y() + bar.get_height() / 2,
                f"  {row['pre_qualifying_score']:.3f} → {row['post_qualifying_score']:.3f}",
                va="center",
            )
        figure.tight_layout()
        _save(figure, output, f"fig_context_lift_all_{phase}", paths)
        plt.close(figure)


def _classification_figures(plt, artifacts: dict[str, Any], output: Path, paths: list[Path]) -> None:
    champions, predictions, reliability = _champions(artifacts["aggregate"]), artifacts["predictions"], artifacts["reliability"]
    for phase in PHASES:
        for task in CLASSIFICATION_TASKS:
            rows = _champion_predictions(predictions, champions, phase, task)
            if rows.empty:
                continue
            figure, axes = plt.subplots(1, 3, figsize=(15, 4.5))
            plotted = False
            for context, group in rows.groupby("context", sort=True):
                target = _as_binary(group["actual"])
                probability = pd.to_numeric(group["probability"], errors="coerce")
                valid = target.notna() & probability.notna()
                y, score = target[valid].astype(int).to_numpy(), probability[valid].to_numpy(dtype=float)
                if len(np.unique(y)) != 2:
                    continue
                thresholds = np.r_[np.inf, np.sort(np.unique(score))[::-1], -np.inf]
                tpr, fpr, precision, recall = [], [], [], []
                for threshold in thresholds:
                    predicted = score >= threshold
                    tp, fp = np.sum(predicted & (y == 1)), np.sum(predicted & (y == 0))
                    fn, tn = np.sum(~predicted & (y == 1)), np.sum(~predicted & (y == 0))
                    tpr.append(tp / (tp + fn) if tp + fn else 0.0)
                    fpr.append(fp / (fp + tn) if fp + tn else 0.0)
                    precision.append(tp / (tp + fp) if tp + fp else 1.0)
                    recall.append(tp / (tp + fn) if tp + fn else 0.0)
                axes[0].plot(fpr, tpr, label=context.replace("_", " "))
                axes[1].plot(recall, precision, label=context.replace("_", " "))
                axes[1].axhline(float(y.mean()), color="#6c757d", linestyle="--", linewidth=1)
                plotted = True
            if not plotted:
                plt.close(figure)
                continue
            axes[0].plot([0, 1], [0, 1], color="#6c757d", linestyle="--", linewidth=1)
            axes[0].set(xlabel="False positive rate", ylabel="True positive rate", title="ROC curve", xlim=(0, 1), ylim=(0, 1))
            axes[1].set(xlabel="Recall", ylabel="Precision", title="Precision–recall (dashed: prevalence)", xlim=(0, 1), ylim=(0, 1))
            rel = reliability[(reliability.get("phase") == phase) & (reliability.get("task") == task)] if not reliability.empty else pd.DataFrame()
            for context, group in rel.groupby("context", sort=True):
                group = group[pd.to_numeric(group["count"], errors="coerce") > 0]
                axes[2].plot(group["mean_predicted_probability"], group["observed_positive_rate"], marker="o", label=context.replace("_", " "))
            axes[2].plot([0, 1], [0, 1], color="#6c757d", linestyle="--", linewidth=1)
            axes[2].set(xlabel="Mean predicted probability", ylabel="Observed positive rate", title="Reliability", xlim=(0, 1), ylim=(0, 1))
            for axis in axes:
                axis.legend(loc="best")
            figure.suptitle(f"{_title(task)} classification diagnostics — {phase.replace('_', ' ')}")
            figure.tight_layout()
            _save(figure, output, f"fig_classification_{task}_{phase}", paths)
            plt.close(figure)


def _regression_figures(plt, artifacts: dict[str, Any], output: Path, paths: list[Path]) -> None:
    champions, predictions = _champions(artifacts["aggregate"]), artifacts["predictions"]
    for phase in PHASES:
        for task in REGRESSION_TASKS:
            rows = _champion_predictions(predictions, champions, phase, task)
            if rows.empty:
                continue
            figure, axes = plt.subplots(1, 2, figsize=(11, 4.5))
            values: list[float] = []
            for context, group in rows.groupby("context", sort=True):
                actual, predicted = pd.to_numeric(group["actual"], errors="coerce"), pd.to_numeric(group["prediction"], errors="coerce")
                valid = actual.notna() & predicted.notna()
                if not valid.any():
                    continue
                axes[0].scatter(actual[valid], predicted[valid], alpha=0.55, s=18, label=context.replace("_", " "))
                residual = actual[valid] - predicted[valid]
                axes[1].hist(residual, bins=20, alpha=0.5, label=context.replace("_", " "))
                values.extend(actual[valid].tolist() + predicted[valid].tolist())
            if not values:
                plt.close(figure)
                continue
            lower, upper = min(values), max(values)
            axes[0].plot([lower, upper], [lower, upper], color="#212529", linestyle="--", linewidth=1)
            axes[0].set(xlabel="Actual", ylabel="Predicted", title="Actual vs predicted")
            axes[1].axvline(0, color="#212529", linestyle="--", linewidth=1)
            axes[1].set(xlabel="Residual (actual − predicted)", ylabel="Driver-race rows", title="Residual distribution")
            for axis in axes:
                axis.legend(loc="best")
            figure.suptitle(f"{_title(task)} diagnostics — {phase.replace('_', ' ')}")
            figure.tight_layout()
            _save(figure, output, f"fig_regression_{task}_{phase}", paths)
            plt.close(figure)


def _feature_figures(plt, experiment_dir: Path, artifacts: dict[str, Any], output: Path, paths: list[Path]) -> None:
    for context in CONTEXTS:
        path = experiment_dir / "champions" / f"{context}_feature_importances.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for task, values in payload.items():
            importance = pd.Series(values, dtype=float).dropna().abs().sort_values().tail(15)
            if importance.empty:
                continue
            figure, axis = plt.subplots(figsize=(9, max(4, len(importance) * 0.35)))
            axis.barh(importance.index, importance.values, color="#005f73")
            axis.set(xlabel="Absolute importance", title=f"Top 15 features: {_title(task)} ({context.replace('_', ' ')})")
            figure.tight_layout()
            _save(figure, output, f"fig_feature_importance_{task}_{context}_final_holdout", paths)
            plt.close(figure)
    ablations = artifacts["ablations"]
    if ablations.empty or "primary_score" not in ablations:
        return
    if "ablation_champion" in ablations.columns:
        selected = ablations["ablation_champion"].astype(str).str.lower().isin({"true", "1"})
        ablations = ablations[selected].copy()
    for task, rows in ablations.groupby("task", sort=True):
        figure, axis = plt.subplots(figsize=(10, 5))
        for context, group in rows.groupby("context", sort=True):
            group = group.sort_values("primary_score", ascending=PRIMARY_METRICS.get(task) == "mae")
            axis.barh(group["ablation"].astype(str) + "\n" + context.replace("_", " "), group["primary_score"], label=context.replace("_", " "))
        axis.set(xlabel=PRIMARY_METRICS.get(task, "primary score"), title=f"Feature-family ablation impact: {_title(task)}")
        figure.tight_layout()
        _save(figure, output, f"fig_ablation_{task}_validation", paths)
        plt.close(figure)


def _temporal_figures(plt, artifacts: dict[str, Any], output: Path, paths: list[Path]) -> None:
    champions, predictions = _champions(artifacts["aggregate"]), artifacts["predictions"]
    rows = _champion_predictions(predictions, champions, "final_holdout", "position_model")
    if rows.empty:
        return
    rows = rows[pd.to_numeric(rows.get("season_year"), errors="coerce") == 2025]
    if rows.empty:
        return
    figure, axis = plt.subplots(figsize=(11, 4.5))
    for context, group in rows.groupby("context", sort=True):
        group = group.assign(error=(pd.to_numeric(group["actual"], errors="coerce") - pd.to_numeric(group["prediction"], errors="coerce")).abs())
        race_mae = group.groupby("race_id", sort=True)["error"].mean()
        axis.plot(range(1, len(race_mae) + 1), race_mae.values, marker="o", label=context.replace("_", " "))
    axis.set(xlabel="2025 race sequence", ylabel="Mean absolute error", title="Race-by-race 2025 finish-position MAE")
    axis.legend(loc="best")
    figure.tight_layout()
    _save(figure, output, "fig_temporal_position_model_final_holdout", paths)
    plt.close(figure)


def _write_markdown(path: Path, baselines: pd.DataFrame, lift: pd.DataFrame) -> None:
    lines = ["# Thesis figure package", "", "## Champion versus domain baseline", ""]
    if baselines.empty:
        lines.append("No champion/baseline comparisons were available in the persisted artifacts.")
    else:
        lines.extend(["| Phase | Context | Task | Champion | Champion score | Baseline | Baseline score | Baseline status |", "| --- | --- | --- | --- | ---: | --- | ---: | --- |"])
        for _, row in baselines.iterrows():
            lines.append(f"| {row['phase']} | {row['context']} | {row['task']} | {row['champion']} | {row['champion_score']:.4f} | {row['baseline']} | {row['baseline_score']:.4f} | {row['baseline_status']} |")
    lines.extend(["", "## Exact common-row pre/post comparison", ""])
    if lift.empty:
        lines.append("No common pre/post champion prediction rows were available.")
    else:
        lines.extend(["| Phase | Task | Metric | Common rows | Pre | Post | Lift |", "| --- | --- | --- | ---: | ---: | ---: | ---: |"])
        for _, row in lift.iterrows():
            lines.append(f"| {row['phase']} | {row['task']} | {row['metric']} | {row['common_driver_race_rows']} | {row['pre_qualifying_score']:.4f} | {row['post_qualifying_score']:.4f} | {row['context_lift']:.4f} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_thesis_visualization_package(experiment_dir: Path, output_dir: Path | None = None) -> list[Path]:
    """Export Sets A–F and reports from persisted experiment artifacts only.

    ``output_dir`` defaults to ``<experiment>/reports/thesis_figures``.  Pass
    ``Path('reports/thesis_figures')`` from the training orchestration when a
    repository-level package is desired.
    """
    experiment_dir = Path(experiment_dir)
    output = Path(output_dir) if output_dir is not None else experiment_dir / "reports" / "thesis_figures"
    output.mkdir(parents=True, exist_ok=True)
    artifacts, plt, paths = _load_artifacts(experiment_dir), _configure_matplotlib(), []
    lift = build_context_lift_summary(artifacts["predictions"], artifacts["aggregate"])
    baselines = build_champion_baseline_summary(artifacts["aggregate"], artifacts["model_results"])
    lift.to_csv(output / "context_lift_common_subset.csv", index=False)
    baselines.to_csv(output / "champion_vs_baseline_summary.csv", index=False)
    _write_markdown(output / "champion_vs_baseline_summary.md", baselines, lift)
    _leaderboards(plt, artifacts["aggregate"], artifacts["final_results"], output, paths)
    _context_lift_plot(plt, lift, output, paths)
    _classification_figures(plt, artifacts, output, paths)
    _regression_figures(plt, artifacts, output, paths)
    _feature_figures(plt, experiment_dir, artifacts, output, paths)
    _temporal_figures(plt, artifacts, output, paths)
    manifest = {
        "experiment_id": artifacts["manifest"].get("experiment_id"),
        "output_directory": str(output),
        "dpi": 300,
        "formats": ["png", "svg"],
        "phase_separation": "Every figure filename and plotting call is scoped to one phase; contexts may share an axis only within that phase.",
        "common_subset_table": "context_lift_common_subset.csv",
        "figures": [path.name for path in paths],
    }
    (output / "figure_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return paths
