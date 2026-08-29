from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TemporalFold:
    name: str
    train_seasons: tuple[int, ...]
    validation_season: int


def generate_temporal_folds(seasons: list[int], min_train_seasons: int = 3) -> list[TemporalFold]:
    """Return expanding, season-level folds with no contemporaneous leakage."""
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
