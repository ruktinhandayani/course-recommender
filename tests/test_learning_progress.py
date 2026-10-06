from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from course_recommender import api as api_module
from course_recommender.api import _add_recommendation_reasons
from course_recommender.config import MlServiceSettings
from course_recommender.export_store import RecommendationExportStore
from course_recommender.user_context import build_user_context


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def context_for(user_id: str):
    return build_user_context(
        data_dir=PROJECT_ROOT / "data",
        artifact_dir=PROJECT_ROOT / "course_recommender_artifacts_final",
        user_id=user_id,
        match_type="exact_match",
    )


def test_complete_progress_demo_uses_source_values():
    context = context_for("002156394")

    assert context.profile["employee_name"] == "Zuhdi Muafa Fattah"
    assert context.learning_progress["status_available"] is True
    assert context.learning_progress["tracked_course_count"] == 32
    assert context.learning_progress["completed_count"] == 27
    assert context.learning_progress["enrolled_count"] == 5
    assert context.learning_progress["completion_rate_percent"] == 84.38
    assert context.learning_progress["average_score"] == 74.93
    assert context.learning_progress["certificate_count"] == 8
    assert len(context.progress_items) == 32


def test_missing_progress_is_reported_without_inventing_values():
    context = context_for("002156217")

    assert context.learning_progress["status_available"] is False
    assert context.learning_progress["completion_rate_percent"] is None
    assert context.learning_progress["average_score"] is None
    assert context.progress_items == []


def test_recommendation_reason_is_explanation_only():
    rows = [
        {
            "rank": 1,
            "competency": "Operasi",
            "fallback_reason": "model_recommendation",
        }
    ]
    history = [
        {"competency": "Operasi"},
        {"competency": "Operasi"},
    ]
    attention = [{"course_name": "Pengenalan NPK Reaksi"}]

    _add_recommendation_reasons(rows, history, attention)

    reason = rows[0]["recommendation_reason"]
    assert "peringkat 1" in reason
    assert "2 course" in reason
    assert "Pengenalan NPK Reaksi" in reason


def test_ui_live_response_contains_progress_and_reason(tmp_path, monkeypatch):
    class FakeRecommender:
        course_popularity = pd.DataFrame(
            {"train_popularity_count": [100]}
        )

        def recommend(self, user_id, history, top_n=10):
            return {
                "metadata": {"fallback_reason": "model_recommendation"},
                "recommendations": [
                    {
                        "course_id": "1022",
                        "rank": 1,
                        "recommended_course": "Product Knowledge",
                        "competency": "Business Acumen",
                        "level": "Level 1",
                        "certificate_status": "not_certified",
                        "similarity_score_0_1": 0.7,
                        "similarity_score_percent": 70.0,
                        "softmax_score": 0.25,
                        "softmax_score_percent": 25.0,
                        "train_popularity_count": None,
                    }
                ],
            }

        def attention_for_user(self, user_id, history):
            return [
                {
                    "input_position": 10,
                    "course_id": "210",
                    "course_name": "Pengenalan NPK Reaksi",
                    "attention_weight": 0.2,
                }
            ]

    settings = MlServiceSettings(
        artifact_dir=PROJECT_ROOT / "course_recommender_artifacts_final",
        data_dir=PROJECT_ROOT / "data",
        export_dir=tmp_path,
        enable_test_ui=True,
        require_auth=False,
        admin_username="admin",
        admin_password="admin",
        session_secret="test-session-secret",
    )
    store = RecommendationExportStore(
        tmp_path / "recommendations.csv",
        tmp_path / "recommendations_fixture.csv",
        PROJECT_ROOT
        / "course_recommender_artifacts_final"
        / "tables"
        / "course_catalog.csv",
    )
    api_module.app.dependency_overrides[api_module.get_settings] = (
        lambda: settings
    )
    api_module.app.dependency_overrides[api_module.get_store] = lambda: store
    monkeypatch.setattr(
        api_module,
        "get_ui_recommender",
        lambda: FakeRecommender(),
    )

    try:
        client = TestClient(api_module.app)
        login = client.post(
            "/ui/api/auth/login",
            json={"username": "admin", "password": "admin"},
        )
        assert login.status_code == 200

        response = client.get(
            "/ui/api/recommendations/user/002156394?mode=normal"
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["learning_progress"]["completed_count"] == 27
        assert payload["learning_progress"]["completion_rate_percent"] == 84.38
        assert len(payload["progress_items"]) == 32
        assert "peringkat 1" in payload["recommendations"][0][
            "recommendation_reason"
        ]
        assert payload["actual_course"]["rank"] == 1
    finally:
        api_module.app.dependency_overrides.clear()
