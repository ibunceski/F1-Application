"""Unit tests for race-result DNF semantics used by ML feature history."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml_pipeline.feature_engineering import circuit_history, dnf_rate_recent, is_dnf  # noqa: E402


def result(
    *,
    finishing_position: int | None,
    classified_position: str | None,
    status: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        finishing_position=finishing_position,
        classified_position=classified_position,
        status=status,
    )


class DnfSemanticsTests(unittest.TestCase):
    def test_retirement_mechanical_and_incident_statuses_are_dnfs(self) -> None:
        cases = [
            result(finishing_position=17, classified_position="17", status="Retired"),
            result(finishing_position=18, classified_position="18", status="Engine"),
            result(finishing_position=19, classified_position="19", status="Collision"),
            result(finishing_position=20, classified_position="20", status="Accident"),
        ]
        self.assertTrue(all(is_dnf(item) for item in cases))

    def test_non_classified_codes_are_dnfs_even_when_status_is_inconsistent(self) -> None:
        for classification in ("DNF", "NC", "Not Classified", "DSQ"):
            with self.subTest(classification=classification):
                self.assertTrue(
                    is_dnf(result(finishing_position=20, classified_position=classification, status="Finished"))
                )

    def test_clean_and_lapped_classified_finishes_are_not_dnfs(self) -> None:
        cases = [
            result(finishing_position=1, classified_position="1", status="Finished"),
            result(finishing_position=15, classified_position="15", status="+1 Lap"),
            result(finishing_position=None, classified_position="18", status="Lapped"),
        ]
        self.assertFalse(any(is_dnf(item) for item in cases))

    def test_recent_dnf_rate_uses_status_semantics(self) -> None:
        history = [
            result(finishing_position=17, classified_position="17", status="Engine"),
            result(finishing_position=2, classified_position="2", status="Finished"),
            result(finishing_position=18, classified_position="18", status="+1 Lap"),
        ]
        with patch("ml_pipeline.feature_engineering.prior_driver_results", return_value=history):
            self.assertAlmostEqual(dnf_rate_recent(None, driver_id=1, before_date=None), 1 / 3)

    def test_circuit_history_uses_stable_location_and_country_identity(self) -> None:
        history = [
            result(finishing_position=2, classified_position="2", status="Finished"),
            result(finishing_position=18, classified_position="18", status="Engine"),
        ]
        db = Mock()
        db.execute.return_value.scalars.return_value.all.return_value = history
        race = SimpleNamespace(
            circuit_name="FORMULA 1 GULF AIR BAHRAIN GRAND PRIX 2025",
            circuit_location="Sakhir",
            circuit_country="Bahrain",
            race_date=date(2025, 3, 1),
        )

        avg_finish, dnf_rate = circuit_history(db, driver_id=1, current_race=race)

        statement = str(db.execute.call_args.args[0])
        self.assertIn("races.circuit_location", statement)
        self.assertIn("races.circuit_country", statement)
        self.assertAlmostEqual(avg_finish, 10.0)
        self.assertAlmostEqual(dnf_rate, 0.5)


if __name__ == "__main__":
    unittest.main()
