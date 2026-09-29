"""Joblib-stable ranking estimators. Must live under app/ml for stable imports."""
from __future__ import annotations

import numpy as np
import pandas as pd
from lightgbm import LGBMRanker
from mord import LogisticAT, OrdinalRidge
from sklearn.base import BaseEstimator, RegressorMixin
from xgboost import XGBRanker


def finishing_positions_to_relevance(
    finishing_positions,
    group_ids=None,
) -> np.ndarray:
    """Map finishing positions to LambdaRank relevance labels per race.

    Lower finishing positions are better in F1, whereas ranking estimators
    expect larger labels to be more relevant.  The transformation is computed
    independently for every query/race so that, for example, position one is
    never less relevant merely because another race had more classified
    drivers.
    """
    positions = np.asarray(finishing_positions, dtype=float).reshape(-1)
    if not len(positions):
        return positions
    if not np.isfinite(positions).all():
        raise ValueError("Ranking targets must be finite finishing positions.")

    if group_ids is None:
        groups = np.zeros(len(positions), dtype=int)
    else:
        groups = np.asarray(group_ids).reshape(-1)
        if len(groups) != len(positions):
            raise ValueError("group_ids and finishing_positions must have the same length.")
        if pd.isna(groups).any():
            raise ValueError("Ranking group identifiers must not be null.")

    frame = pd.DataFrame({"group": groups, "position": positions})
    max_position = frame.groupby("group", sort=False)["position"].transform("max")
    # position 1 gets the largest relevance: max_position - 1 + 1.
    return (max_position - frame["position"] + 1.0).to_numpy(dtype=float)


def _sort_ranking_query(X, y, group):
    """Keep query rows contiguous while retaining their stable within-race order."""
    X_frame = pd.DataFrame(X)
    y_series = pd.Series(y).reset_index(drop=True)
    if len(X_frame) != len(y_series):
        raise ValueError("X and y must contain the same number of rows.")
    if group is None:
        group_values = np.zeros(len(y_series), dtype=int)
    else:
        supplied_group = np.asarray(group).reshape(-1)
        if len(supplied_group) == len(y_series):
            group_values = supplied_group
        elif (
            len(supplied_group)
            and np.issubdtype(supplied_group.dtype, np.number)
            and np.all(supplied_group > 0)
            and int(supplied_group.sum()) == len(y_series)
        ):
            # Scikit/LightGBM callers historically pass query sizes such as
            # [20, 20], while the experiment runner passes one race id per row.
            group_values = np.repeat(np.arange(len(supplied_group)), supplied_group.astype(int))
        else:
            raise ValueError("group must contain one id per row or positive query sizes summing to len(y).")
        if pd.isna(group_values).any():
            raise ValueError("Ranking group identifiers must not be null.")

    order = np.argsort(group_values, kind="stable")
    sorted_groups = group_values[order]
    X_sorted = X_frame.iloc[order].reset_index(drop=True)
    positions_sorted = y_series.iloc[order].reset_index(drop=True)
    relevance_sorted = finishing_positions_to_relevance(positions_sorted, sorted_groups)
    _, group_sizes = np.unique(sorted_groups, return_counts=True)
    return X_sorted, relevance_sorted, sorted_groups, group_sizes.tolist()


class LightGBMRankRegressor(BaseEstimator, RegressorMixin):
    def __init__(self, n_estimators=250, max_depth=6, learning_rate=0.04, random_state=42):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.random_state = random_state

    def fit(self, X, y, group=None):
        X_sorted, relevance_sorted, _, group_sizes = _sort_ranking_query(X, y, group)
        self.model_ = LGBMRanker(
            objective="lambdarank", n_estimators=self.n_estimators, max_depth=self.max_depth,
            learning_rate=self.learning_rate, random_state=self.random_state, n_jobs=1, verbose=-1,
        )
        self.model_.fit(X_sorted, relevance_sorted, group=group_sizes)
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
        X_sorted, relevance_sorted, qid, _ = _sort_ranking_query(X, y, group)
        self.model_ = XGBRanker(
            objective="rank:pairwise", n_estimators=self.n_estimators, max_depth=self.max_depth,
            learning_rate=self.learning_rate, random_state=self.random_state, n_jobs=1,
        )
        self.model_.fit(X_sorted, relevance_sorted, qid=qid)
        return self

    def predict(self, X):
        return self.model_.predict(X)

    @property
    def feature_importances_(self):
        return getattr(self.model_, "feature_importances_", None)


class OrdinalRidgeRegressor(BaseEstimator, RegressorMixin):
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, X, y):
        y_arr = np.asarray(y)
        self.classes_ = np.unique(y_arr)
        y_idx = np.searchsorted(self.classes_, y_arr).astype(int)
        self.model_ = OrdinalRidge(alpha=self.alpha)
        self.model_.fit(X, y_idx)
        return self

    def predict(self, X):
        idx = np.clip(np.asarray(self.model_.predict(X), dtype=int), 0, len(self.classes_) - 1)
        return self.classes_[idx].astype(float)

    @property
    def coef_(self):
        return getattr(self.model_, "coef_", None)


class LogisticATRegressor(BaseEstimator, RegressorMixin):
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, X, y):
        y_arr = np.asarray(y)
        self.classes_ = np.unique(y_arr)
        y_idx = np.searchsorted(self.classes_, y_arr).astype(int)
        self.model_ = LogisticAT(alpha=self.alpha)
        self.model_.fit(X, y_idx)
        return self

    def predict(self, X):
        idx = np.clip(np.asarray(self.model_.predict(X), dtype=int), 0, len(self.classes_) - 1)
        return self.classes_[idx].astype(float)

    @property
    def coef_(self):
        return getattr(self.model_, "coef_", None)
