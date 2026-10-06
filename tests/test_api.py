import time
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from course_recommender.api import app, get_artifact_status, get_settings, get_store, resolve_user_id
from course_recommender.config import MlServiceSettings
from course_recommender.export_store import RecommendationExportStore
from course_recommender.security import build_signature


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
                "user_id": "u2",
                "canonical_course_id": "c2",
                "rank": 1,
                "score": 0.8,
                "reason_code": None,
                "model_version": "recmodel-v1.0.0",
                "generated_at": "2026-07-12T00:00:00+07:00",
            },
            {
                "user_id": "000123451",
                "canonical_course_id": "c3",
                "rank": 1,
                "score": 0.7,
                "reason_code": None,
                "model_version": "recmodel-v1.0.0",
                "generated_at": "2026-07-12T00:00:00+07:00",
            },
        ]
    ).to_csv(path, index=False)


def signed_headers(settings: MlServiceSettings, path: str, query: str, request_id: str = "test-req"):
    timestamp = str(int(time.time()))
    return {
        "Authorization": f"Bearer {settings.api_key}",
        "X-Request-Id": request_id,
        "X-Timestamp": timestamp,
        "X-Signature": build_signature(
            method="GET",
            path=path,
            query_string=query,
            timestamp=timestamp,
            request_id=request_id,
            secret=settings.hmac_secret,
        ),
    }


def make_client(tmp_path):
    export_path = tmp_path / "recommendations.csv"
    fixture_path = tmp_path / "recommendations_fixture.csv"
    write_export(export_path)
    write_export(fixture_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    pd.DataFrame(
        {
            "user_id": ["u1", "000123451", "000777777"],
            "full_name": ["One", "Leading zero", "Not in export"],
        }
    ).to_csv(
        data_dir / "users.csv", index=False
    )

    settings = MlServiceSettings(
        export_dir=tmp_path,
        export_file="recommendations.csv",
        fixture_file="recommendations_fixture.csv",
        data_dir=data_dir,
        api_key="test-key",
        hmac_secret="test-secret",
        timestamp_tolerance_seconds=60,
        require_auth=True,
        enable_test_ui=True,
        admin_password="admin",
        admin_password_hash="",
        session_secret="test-session-secret",
    )
    store = RecommendationExportStore(export_path, fixture_path)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_store] = lambda: store
    get_artifact_status.cache_clear()
    app.dependency_overrides[get_artifact_status] = lambda: {
        "status": "OK",
        "message": "Artifacts are consistent.",
        "issues": [],
        "critical": False,
    }
    return TestClient(app), settings


def teardown_function():
    app.dependency_overrides.clear()


def test_export_endpoint_returns_contract_response(tmp_path):
    client, settings = make_client(tmp_path)
    query = "limit=1"
    response = client.get(
        f"/recommendations/export?{query}",
        headers=signed_headers(settings, "/recommendations/export", query),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_id"] == "test-req"
    assert payload["model_version"] == "recmodel-v1.0.0"
    assert payload["page"]["limit"] == 1
    assert payload["page"]["has_more"] is True
    first_row = payload["recommendations"][0]
    assert first_row["user_id"] == "000123451"
    assert first_row["canonical_course_id"] == "c3"
    assert first_row["rank"] == 1
    assert first_row["score"] == 0.7
    assert first_row["reason_code"] is None
    assert "course_title" in first_row


def test_export_endpoint_accepts_second_page_with_canonical_query(tmp_path):
    client, settings = make_client(tmp_path)
    first_query = "limit=1"
    first = client.get(
        f"/recommendations/export?{first_query}",
        headers=signed_headers(settings, "/recommendations/export", first_query, "first-page"),
    )
    cursor = first.json()["page"]["next_cursor"]
    second_query = f"cursor={cursor}&limit=1"

    response = client.get(
        f"/recommendations/export?{second_query}",
        headers=signed_headers(settings, "/recommendations/export", second_query, "second-page"),
    )

    assert response.status_code == 200
    assert response.json()["recommendations"][0]["canonical_course_id"] == "c1"


def test_export_endpoint_supports_fixture_mode(tmp_path):
    client, settings = make_client(tmp_path)
    query = "limit=10&mode=test"
    response = client.get(
        f"/recommendations/export?{query}",
        headers=signed_headers(settings, "/recommendations/export", query, "fixture-page"),
    )

    assert response.status_code == 200
    assert len(response.json()["recommendations"]) == 3


def test_export_endpoint_rejects_missing_auth(tmp_path):
    client, _ = make_client(tmp_path)
    response = client.get("/recommendations/export?limit=1")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_API_KEY"


def test_export_endpoint_rejects_bad_signature(tmp_path):
    client, settings = make_client(tmp_path)
    headers = signed_headers(settings, "/recommendations/export", "limit=1")
    headers["X-Signature"] = "bad"

    response = client.get("/recommendations/export?limit=1", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INVALID_SIGNATURE"


def test_user_endpoint_returns_user_rows(tmp_path):
    client, settings = make_client(tmp_path)
    response = client.get(
        "/recommendations/user/u1",
        headers=signed_headers(settings, "/recommendations/user/u1", ""),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "u1"
    assert payload["recommendations"][0]["canonical_course_id"] == "c1"


def test_exact_user_id_match_preserves_canonical_leading_zeroes(tmp_path):
    client, settings = make_client(tmp_path)
    path = "/recommendations/user/000123451"
    response = client.get(path, headers=signed_headers(settings, path, ""))

    assert response.status_code == 200
    assert response.json()["user_id"] == "000123451"
    assert response.json()["canonical_user_id"] == "000123451"
    assert response.json()["match_type"] == "exact_match"


def test_normalized_unique_user_id_match_preserves_canonical_leading_zeroes(tmp_path):
    client, settings = make_client(tmp_path)
    path = "/recommendations/user/123451"
    response = client.get(path, headers=signed_headers(settings, path, ""))

    assert response.status_code == 200
    assert response.json()["requested_user_id"] == "123451"
    assert response.json()["canonical_user_id"] == "000123451"
    assert response.json()["user_id"] == "000123451"
    assert response.json()["match_type"] == "normalized_unique_match"


def test_ambiguous_normalized_user_id_is_not_resolved_automatically():
    resolution = resolve_user_id("123451", ["000123451", "0123451"])

    assert resolution == {"status": "ambiguous", "canonical_user_id": None}


def test_ambiguous_normalized_user_id_returns_api_status(tmp_path):
    client, settings = make_client(tmp_path)
    export = pd.read_csv(settings.export_path, dtype={"user_id": str})
    export.loc[len(export)] = {
        "user_id": "0123451",
        "canonical_course_id": "c4",
        "rank": 1,
        "score": 0.6,
        "reason_code": None,
        "model_version": "recmodel-v1.0.0",
        "generated_at": "2026-07-12T00:00:00+07:00",
    }
    export.to_csv(settings.export_path, index=False)
    app.dependency_overrides[get_store]().clear_cache()

    path = "/recommendations/user/123451"
    response = client.get(path, headers=signed_headers(settings, path, ""))

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "USER_ID_AMBIGUOUS"


def test_non_numeric_user_id_uses_exact_match_only():
    assert resolve_user_id("employee-1", ["employee-1"]) == {
        "status": "exact_match",
        "canonical_user_id": "employee-1",
    }
    assert resolve_user_id("EMPLOYEE-1", ["employee-1"])["status"] == "not_found"


def test_user_not_in_active_export_is_distinguished(tmp_path):
    client, settings = make_client(tmp_path)
    path = "/recommendations/user/000777777"
    response = client.get(path, headers=signed_headers(settings, path, ""))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_IN_ACTIVE_EXPORT"
    assert response.json()["error"]["canonical_user_id"] == "000777777"


def test_unknown_user_is_reported_as_missing_from_source(tmp_path):
    client, settings = make_client(tmp_path)
    path = "/recommendations/user/999999"
    response = client.get(path, headers=signed_headers(settings, path, ""))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "USER_NOT_FOUND"


def login_ui(client):
    response = client.post("/ui/api/auth/login", json={"username": "admin", "password": "admin"})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_ui_endpoints_require_admin_session(tmp_path):
    client, _ = make_client(tmp_path)

    response = client.get("/ui/api/recommendations/export?limit=1")

    assert response.status_code == 401


def test_ui_endpoints_return_data_without_hmac_headers_after_login(tmp_path):
    client, _ = make_client(tmp_path)
    login_ui(client)

    user_response = client.get("/ui/api/recommendations/user/u1?mode=test")
    export_response = client.get("/ui/api/recommendations/export?limit=1&mode=test")

    assert user_response.status_code == 200
    assert user_response.json()["user_id"] == "u1"
    assert export_response.status_code == 200
    assert export_response.json()["page"]["has_more"] is True
    assert export_response.json()["request_id"]


def test_ui_endpoints_are_hidden_when_disabled(tmp_path):
    client, settings = make_client(tmp_path)
    disabled_settings = settings.model_copy(update={"enable_test_ui": False})
    app.dependency_overrides[get_settings] = lambda: disabled_settings

    response = client.get("/ui/api/recommendations/export?limit=1")

    assert response.status_code == 404


def test_ui_auth_me_reports_session_state(tmp_path):
    client, _ = make_client(tmp_path)

    anonymous = client.get("/ui/api/auth/me")
    assert anonymous.status_code == 200
    assert anonymous.json()["authenticated"] is False

    login_ui(client)
    authenticated = client.get("/ui/api/auth/me")
    assert authenticated.status_code == 200
    assert authenticated.json()["authenticated"] is True


def test_ui_evaluation_endpoint_returns_shape(tmp_path):
    client, _ = make_client(tmp_path)
    login_ui(client)

    response = client.get("/ui/api/evaluation/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["model_version"] == "cre-lstm-attention-h2-seed42-fullmask-v1"
    assert "overall_metrics" in payload
    assert "metric_tables" in payload
