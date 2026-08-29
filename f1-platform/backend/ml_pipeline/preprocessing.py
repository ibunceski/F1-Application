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
