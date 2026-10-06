"""Checks for post-write recommendation export manifest state."""

import json

import pandas as pd

from course_recommender import batch_export


class _FakeRecommender:
    course_popularity = pd.DataFrame(
        [{"course_encoded": 1, "train_popularity_count": 8}]
    )

    def recommend(self, user_id, _history, top_n):
        return {
            "recommendations": [
                {
                    "course_id": f"course-{user_id}",
                    "rank": 1,
                    "softmax_score": 0.9,
                    "softmax_score_percent": 90.0,
                    "similarity_score_0_1": 0.8,
                    "similarity_score_percent": 80.0,
                    "recommended_course": "Recommended course",
                }
            ][:top_n],
            "metadata": {"fallback_reason": None},
        }

    def validate_catalog_consistency(self):
        # This represents the pre-export state cached while artifacts load.
        return {"status": "OK", "checks": {"recommendation_export_found": False}}


def test_export_manifest_marks_written_recommendation_export_as_found(tmp_path, monkeypatch):
    history = pd.DataFrame(
        [
            {"user_id": "000123451", "canonical_course_id": "old", "sort_row_order": 0},
            {"user_id": "u2", "canonical_course_id": "old", "sort_row_order": 1},
        ]
    )
    monkeypatch.setattr(batch_export, "load_recommender", lambda _artifact_dir: _FakeRecommender())
    monkeypatch.setattr(
        batch_export,
        "load_user_history",
        lambda _data_dir: (history, ["000123451", "u2"]),
    )

    output_path = tmp_path / "export" / "recommendations.csv"
    fixture_path = tmp_path / "export" / "recommendations_fixture.csv"
    manifest = batch_export.generate_recommendation_export(
        artifact_dir=tmp_path / "artifacts",
        data_dir=tmp_path / "data",
        output_path=output_path,
        fixture_path=fixture_path,
        model_version="cre-lstm-attention-h2-seed42-fullmask-v1",
        top_k=20,
        max_users=None,
    )

    assert manifest["user_count"] == 2
    assert manifest["top_k"] == 20
    assert manifest["catalog_check"]["checks"]["recommendation_export_found"] is True
    assert output_path.exists()
    assert fixture_path.exists()

    saved = json.loads((output_path.parent / "recommendation_export_manifest.json").read_text())
    assert saved["catalog_check"]["checks"]["recommendation_export_found"] is True
