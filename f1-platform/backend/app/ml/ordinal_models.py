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
