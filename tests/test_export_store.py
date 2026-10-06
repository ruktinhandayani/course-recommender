from pathlib import Path

import pandas as pd
import pytest

from course_recommender.export_store import InvalidCursorError, RecommendationExportStore


def write_export(path: Path) -> None:
    pd.DataFrame(
        [
            {
                "user_id": "u1",
                "canonical_course_id": "c1",
                "rank": 1,
                "score": 0.9,
                "reason_code": None,
                "model_version": "recmodel-v1.0.0",
                "generated_at": "2026-07-12T00:00:00+07:00",
            },
            {
                "user_id": "u1",
                "canonical_course_id": "c2",
                "rank": 2,
                "score": 0.8,
                "reason_code": None,
                "model_version": "recmodel-v1.0.0",
                "generated_at": "2026-07-12T00:00:00+07:00",
            },
            {
                "user_id": "u2",
                "canonical_course_id": "c3",
                "rank": 1,
                "score": 0.7,
                "reason_code": None,
                "model_version": "recmodel-v1.0.0",
                "generated_at": "2026-07-12T00:00:00+07:00",
            },
        ]
    ).to_csv(path, index=False)


def test_export_store_paginates_with_opaque_cursor(tmp_path):
    export_path = tmp_path / "recommendations.csv"
    write_export(export_path)
    store = RecommendationExportStore(export_path)

    first = store.page(limit=2, cursor=None, model_version="latest")
    assert first.has_more is True
    assert first.next_cursor is not None
    assert [row["canonical_course_id"] for row in first.rows] == ["c1", "c2"]

    second = store.page(limit=2, cursor=first.next_cursor, model_version="latest")
    assert second.has_more is False
    assert second.next_cursor is None
    assert [row["canonical_course_id"] for row in second.rows] == ["c3"]


def test_export_store_rejects_invalid_cursor(tmp_path):
    export_path = tmp_path / "recommendations.csv"
    write_export(export_path)
    store = RecommendationExportStore(export_path)

    with pytest.raises(InvalidCursorError):
        store.page(limit=2, cursor="not-valid", model_version="latest")


def test_export_store_returns_user_rows(tmp_path):
    export_path = tmp_path / "recommendations.csv"
    write_export(export_path)
    store = RecommendationExportStore(export_path)

    rows, generated_at, model_version = store.user_rows("u1", model_version="latest")

    assert generated_at == "2026-07-12T00:00:00+07:00"
    assert model_version == "recmodel-v1.0.0"
    assert [row["canonical_course_id"] for row in rows] == ["c1", "c2"]
