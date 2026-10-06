"""FastAPI app for the CRE Pre-MVP ML Recommendation Service."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import create_session_token, request_has_admin_session, validate_admin_credentials
from .batch_export import generate_recommendation_export
from .cre_contract import (
    AuthUserResponse,
    EvaluationResponse,
    ExportResponse,
    HealthResponse,
    LoginRequest,
    PageInfo,
    ResearchSummaryResponse,
    RefreshJobResponse,
    RefreshStartRequest,
    UserResponse,
    error_response,
)
from .config import MlServiceSettings
from .export_store import InvalidCursorError, RecommendationExportStore
from .security import validate_request_security
from .service import load_recommender
from .user_context import build_user_context


@lru_cache(maxsize=1)
def get_settings() -> MlServiceSettings:
    return MlServiceSettings()


@lru_cache(maxsize=1)
def get_store() -> RecommendationExportStore:
    settings = get_settings()
    return RecommendationExportStore(
        settings.export_path,
        settings.fixture_path,
        settings.artifact_dir / "tables" / "course_catalog.csv",
    )


@lru_cache(maxsize=1)
def get_artifact_status() -> dict:
    settings = get_settings()
    try:
        recommender = load_recommender(settings.artifact_dir)
        return recommender.catalog_check
    except Exception as exc:
        return {
            "status": "CRITICAL",
            "message": str(exc),
            "issues": [str(exc)],
            "critical": True,
        }


@lru_cache(maxsize=1)
def get_ui_recommender():
    """Load the active model only when the UI needs live inference."""
    settings = get_settings()
    return load_recommender(settings.artifact_dir)


def artifact_status_for_settings(settings: MlServiceSettings) -> dict:
    """Use artifact metadata as the version source and flag env drift clearly."""
    artifact_status = dict(get_artifact_status())
    artifact_version = str(artifact_status.get("model_version") or "").strip()
    configured_version = str(settings.model_version or "").strip()

    if artifact_version and configured_version and artifact_version != configured_version:
        checks = dict(artifact_status.get("checks") or {})
        checks["model_version_match"] = False
        issues = list(artifact_status.get("issues") or [])
        issues.append(
            "ARTIFACT VERSION MISMATCH: configured model version "
            f"'{configured_version}' does not match active artifact version '{artifact_version}'."
        )
        artifact_status.update(
            {
                "status": "CRITICAL",
                "message": "ARTIFACT VERSION MISMATCH",
                "issues": issues,
                "critical": True,
                "checks": checks,
            }
        )
    return artifact_status


@lru_cache(maxsize=4)
def _source_user_ids(data_dir: str) -> frozenset[str]:
    """Return source user IDs as exact strings, preserving leading zeroes."""
    source_dir = Path(data_dir)
    user_ids: set[str] = set()
    for filename in ("users.csv", "interactions.csv"):
        path = source_dir / filename
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path, usecols=["user_id"], dtype={"user_id": str})
        except (OSError, ValueError):
            continue
        user_ids.update(frame["user_id"].dropna().astype(str).str.strip())
    return frozenset(user_ids)


def normalize_numeric_user_id(value: str) -> str:
    """Normalize numeric IDs only for a relaxed lookup; never for storage."""
    normalized = str(value).strip()
    return normalized.lstrip("0") or "0" if normalized.isdigit() else normalized


def resolve_user_id(input_user_id: str, available_user_ids: list[str] | frozenset[str]) -> dict[str, str | None]:
    """Resolve an entered ID to one canonical stored ID without guessing length."""
    query = str(input_user_id).strip()
    canonical_ids = [str(user_id).strip() for user_id in available_user_ids]
    if query in canonical_ids:
        return {"status": "exact_match", "canonical_user_id": query}
    if not query.isdigit():
        return {"status": "not_found", "canonical_user_id": None}

    normalized_query = normalize_numeric_user_id(query)
    matches = [
        user_id
        for user_id in canonical_ids
        if user_id.isdigit() and normalize_numeric_user_id(user_id) == normalized_query
    ]
    if len(matches) == 1:
        return {"status": "normalized_unique_match", "canonical_user_id": matches[0]}
    if len(matches) > 1:
        return {"status": "ambiguous", "canonical_user_id": None}
    return {"status": "not_found", "canonical_user_id": None}


def _resolve_export_or_source_user_id(
    input_user_id: str,
    *,
    model_version: str,
    mode: str,
    settings: MlServiceSettings,
    store: RecommendationExportStore,
) -> tuple[dict[str, str | None], bool]:
    """Resolve export IDs first, then source IDs for informative missing statuses."""
    export_match = resolve_user_id(
        input_user_id,
        store.available_user_ids(model_version=model_version, mode=mode),  # type: ignore[arg-type]
    )
    if export_match["status"] != "not_found":
        return export_match, True
    source_match = resolve_user_id(input_user_id, _source_user_ids(str(settings.data_dir.resolve())))
    return source_match, False


def _user_lookup_error(
    *,
    request_id: str,
    requested_user_id: str,
    resolution: dict[str, str | None],
) -> JSONResponse:
    if resolution["status"] == "ambiguous":
        return error_response(
            409,
            request_id,
            "USER_ID_AMBIGUOUS",
            "Multiple User IDs match this input. Please enter the complete User ID including leading zeros.",
            {"requested_user_id": requested_user_id, "match_type": "ambiguous"},
        )
    if resolution["canonical_user_id"]:
        return error_response(
            404,
            request_id,
            "USER_NOT_IN_ACTIVE_EXPORT",
            "Recommendation not available in active export. This User ID may still exist in the source dataset.",
            {
                "requested_user_id": requested_user_id,
                "canonical_user_id": resolution["canonical_user_id"],
                "match_type": resolution["status"],
            },
        )
    return error_response(
        404,
        request_id,
        "USER_NOT_FOUND",
        "User ID was not found in source data or history.",
        {"requested_user_id": requested_user_id, "match_type": "not_found"},
    )


def _update_actual_course_status(
    actual_course: dict | None,
    recommendation_rows: list[dict],
) -> None:
    """Compare the held-out next course with the displayed Top-10 rows."""
    if actual_course is None:
        return

    actual_id = str(actual_course.get("course_id") or "")
    actual_name = str(actual_course.get("course_name") or "")
    rank_match = next(
        (
            int(row["rank"])
            for row in recommendation_rows
            if str(row.get("canonical_course_id") or "") == actual_id
            or str(row.get("course_title") or "") == actual_name
        ),
        None,
    )
    actual_course["rank"] = rank_match
    if rank_match == 1:
        actual_course["status"] = (
            "Berhasil - course aktual berada di peringkat 1."
        )
    elif rank_match is not None and rank_match <= 10:
        actual_course["status"] = (
            "Berhasil - course aktual masuk dalam Top-10."
        )
    else:
        actual_course["status"] = "Course aktual tidak masuk dalam Top-10."


def _add_recommendation_reasons(
    recommendation_rows: list[dict],
    history_rows: list[dict],
    attention_rows: list[dict],
) -> None:
    """Add a plain-language explanation without changing model ranking."""
    competency_counts: dict[str, int] = {}
    # The deployed model reads at most the ten most recent pre-target courses.
    for history in history_rows[-10:]:
        competency = str(history.get("competency") or "").strip()
        if competency and competency != "Tidak tersedia":
            competency_counts[competency] = (
                competency_counts.get(competency, 0) + 1
            )

    top_attention = attention_rows[0] if attention_rows else None
    for row in recommendation_rows:
        rank = int(row.get("rank") or 0)
        fallback_reason = str(row.get("fallback_reason") or "")
        if fallback_reason.startswith("model_recommendation"):
            parts = [
                (
                    f"Model menempatkan course ini pada peringkat {rank} "
                    "berdasarkan pola riwayat belajar."
                )
            ]
        else:
            parts = [
                (
                    f"Course ini berada pada peringkat {rank} dari hasil "
                    "rekomendasi yang tersedia."
                )
            ]

        competency = str(row.get("competency") or "").strip()
        related_count = competency_counts.get(competency, 0)
        if competency and competency != "Tidak tersedia":
            if related_count > 0:
                parts.append(
                    f"Kompetensi {competency} juga muncul pada "
                    f"{related_count} course pada riwayat yang dibaca model."
                )
            else:
                parts.append(
                    f"Course ini menambah pembelajaran pada kompetensi "
                    f"{competency}."
                )

        if top_attention:
            parts.append(
                "Saat membuat prediksi, riwayat yang paling diperhatikan "
                f"model adalah {top_attention['course_name']}."
            )

        row["recommendation_reason"] = " ".join(parts)


def request_id_from(request: Request) -> str:
    return request.headers.get("x-request-id", "")


def require_security(request: Request, settings: MlServiceSettings = Depends(get_settings)) -> None | JSONResponse:
    ok, status_code, code, message = validate_request_security(request, settings)
    if ok:
        return None
    return error_response(status_code, request_id_from(request), code, message)


app = FastAPI(
    title="CRE ML Recommendation Service",
    version="1.0.0",
    description="Pre-MVP ML service exposing paginated recommendation candidates.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().test_ui_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Accept", "Content-Type"],
)


def require_test_ui(settings: MlServiceSettings = Depends(get_settings)) -> None:
    if not settings.enable_test_ui:
        raise HTTPException(status_code=404, detail="Not found")


def require_admin_session(
    request: Request,
    settings: MlServiceSettings = Depends(get_settings),
) -> None:
    if not request_has_admin_session(request, settings):
        raise HTTPException(status_code=401, detail="Admin login required.")


def _set_session_cookie(response: Response, token: str, settings: MlServiceSettings) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_max_age_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


@app.post("/ui/api/auth/login", response_model=AuthUserResponse, dependencies=[Depends(require_test_ui)])
def ui_login(
    payload: LoginRequest,
    response: Response,
    settings: MlServiceSettings = Depends(get_settings),
) -> AuthUserResponse:
    if not validate_admin_credentials(payload.username, payload.password, settings):
        raise HTTPException(status_code=401, detail="Invalid admin username or password.")
    _set_session_cookie(response, create_session_token(settings), settings)
    return AuthUserResponse(authenticated=True, username=settings.admin_username)


@app.post("/ui/api/auth/logout", response_model=AuthUserResponse, dependencies=[Depends(require_test_ui)])
def ui_logout(
    response: Response,
    settings: MlServiceSettings = Depends(get_settings),
) -> AuthUserResponse:
    response.delete_cookie(settings.session_cookie_name, samesite="lax")
    return AuthUserResponse(authenticated=False, username=None)


@app.get("/ui/api/auth/me", response_model=AuthUserResponse, dependencies=[Depends(require_test_ui)])
def ui_me(
    request: Request,
    settings: MlServiceSettings = Depends(get_settings),
) -> AuthUserResponse:
    if not request_has_admin_session(request, settings):
        return AuthUserResponse(authenticated=False, username=None)
    return AuthUserResponse(authenticated=True, username=settings.admin_username)


@app.get("/health", response_model=HealthResponse)
def health(
    settings: MlServiceSettings = Depends(get_settings),
    store: RecommendationExportStore = Depends(get_store),
) -> HealthResponse:
    artifact_status = artifact_status_for_settings(settings)
    export_ready = store.ready("normal")
    generated_at = None
    recommendation_count = 0
    export_manifest: dict = {}
    manifest_path = settings.export_dir / "recommendation_export_manifest.json"
    if manifest_path.exists():
        try:
            import json
            export_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            export_manifest = {}
    if export_ready:
        try:
            df = store.load("normal")
            recommendation_count = len(df)
            generated_at = str(df["generated_at"].iloc[0]) if len(df) else None
        except Exception:
            export_ready = False

    status = "ok" if export_ready and artifact_status.get("status") == "OK" else "not_ready"
    return HealthResponse(
        status=status,
        model_version=str(artifact_status.get("model_version") or settings.model_version),
        generated_at=generated_at,
        export_ready=export_ready,
        artifact_status=artifact_status.get("status"),
        recommendation_count=recommendation_count,
        primary_ranking=str(artifact_status.get("primary_ranking", "Softmax Ranking")),
        masking_protocol=str(artifact_status.get("masking_protocol", "full_pre_target_history")),
        export_mode=str(export_manifest.get("export_mode") or ("demonstration_subset" if export_manifest.get("max_users") else "full_batch")),
        active_export_users=export_manifest.get("user_count"),
        active_export_top_k=export_manifest.get("top_k"),
    )


@app.get("/recommendations/export", response_model=ExportResponse)
def export_recommendations(
    request: Request,
    model_version: str = Query(default="latest"),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    mode: str = Query(default="normal"),
    settings: MlServiceSettings = Depends(get_settings),
    store: RecommendationExportStore = Depends(get_store),
):
    security_error = require_security(request, settings)
    if security_error is not None:
        return security_error

    request_id = request_id_from(request)
    resolved_limit = limit or settings.default_export_limit
    if resolved_limit < 1 or resolved_limit > settings.max_export_limit:
        return error_response(422, request_id, "INVALID_LIMIT", "limit must be between 1 and 1000.")

    if mode not in {"normal", "test"}:
        return error_response(400, request_id, "INVALID_REQUEST", "mode must be normal or test.")

    if not store.ready(mode):  # type: ignore[arg-type]
        return error_response(503, request_id, "EXPORT_NOT_READY", "Recommendation export is not ready.")

    try:
        page = store.page(
            limit=resolved_limit,
            cursor=cursor,
            model_version=model_version,
            mode=mode,  # type: ignore[arg-type]
        )
    except InvalidCursorError:
        return error_response(422, request_id, "INVALID_CURSOR", "Pagination cursor is invalid.")
    except Exception as exc:
        return error_response(500, request_id, "INTERNAL_ERROR", "Could not load recommendation export.", {"detail": str(exc)})

    if model_version != "latest" and not page.model_version:
        return error_response(422, request_id, "MODEL_VERSION_NOT_FOUND", "Requested model_version was not found.")

    return ExportResponse(
        request_id=request_id,
        model_version=page.model_version or settings.model_version,
        generated_at=page.generated_at or "",
        page=PageInfo(limit=page.limit, next_cursor=page.next_cursor, has_more=page.has_more),
        recommendations=page.rows,
    )


@app.get("/recommendations/user/{user_id}", response_model=UserResponse)
def user_recommendations(
    user_id: str,
    request: Request,
    model_version: str = Query(default="latest"),
    mode: str = Query(default="normal"),
    settings: MlServiceSettings = Depends(get_settings),
    store: RecommendationExportStore = Depends(get_store),
):
    security_error = require_security(request, settings)
    if security_error is not None:
        return security_error

    request_id = request_id_from(request)
    if mode not in {"normal", "test"}:
        return error_response(400, request_id, "INVALID_REQUEST", "mode must be normal or test.")

    if not store.ready(mode):  # type: ignore[arg-type]
        return error_response(503, request_id, "EXPORT_NOT_READY", "Recommendation export is not ready.")

    requested_user_id = str(user_id).strip()
    resolution, found_in_export = _resolve_export_or_source_user_id(
        requested_user_id,
        model_version=model_version,
        mode=mode,
        settings=settings,
        store=store,
    )
    if resolution["status"] == "ambiguous" or not found_in_export:
        return _user_lookup_error(
            request_id=request_id,
            requested_user_id=requested_user_id,
            resolution=resolution,
        )

    canonical_user_id = str(resolution["canonical_user_id"])
    try:
        rows, generated_at, resolved_version = store.user_rows(
            canonical_user_id,
            model_version=model_version,
            mode=mode,  # type: ignore[arg-type]
        )
    except Exception as exc:
        return error_response(500, request_id, "INTERNAL_ERROR", "Could not load user recommendations.", {"detail": str(exc)})

    if model_version != "latest" and not resolved_version:
        return error_response(422, request_id, "MODEL_VERSION_NOT_FOUND", "Requested model_version was not found.")

    if not rows:
        return _user_lookup_error(
            request_id=request_id,
            requested_user_id=requested_user_id,
            resolution={"status": "not_found", "canonical_user_id": None},
        )

    return UserResponse(
        request_id=request_id,
        user_id=canonical_user_id,
        requested_user_id=requested_user_id,
        canonical_user_id=canonical_user_id,
        match_type=str(resolution["status"]),
        model_version=resolved_version,
        generated_at=generated_at,
        recommendations=rows,
    )


@app.get(
    "/ui/api/health",
    response_model=HealthResponse,
    dependencies=[Depends(require_test_ui), Depends(require_admin_session)],
)
def ui_health(
    settings: MlServiceSettings = Depends(get_settings),
    store: RecommendationExportStore = Depends(get_store),
) -> HealthResponse:
    return health(settings=settings, store=store)


@app.get(
    "/ui/api/recommendations/export",
    response_model=ExportResponse,
    dependencies=[Depends(require_test_ui), Depends(require_admin_session)],
)
def ui_export_recommendations(
    model_version: str = Query(default="latest"),
    cursor: str | None = Query(default=None),
    limit: int | None = Query(default=None),
    mode: str = Query(default="test"),
    settings: MlServiceSettings = Depends(get_settings),
    store: RecommendationExportStore = Depends(get_store),
):
    request_id = str(uuid4())
    resolved_limit = limit or settings.default_export_limit
    if resolved_limit < 1 or resolved_limit > settings.max_export_limit:
        return error_response(422, request_id, "INVALID_LIMIT", "limit must be between 1 and 1000.")

    if mode not in {"normal", "test"}:
        return error_response(400, request_id, "INVALID_REQUEST", "mode must be normal or test.")

    if not store.ready(mode):  # type: ignore[arg-type]
        return error_response(503, request_id, "EXPORT_NOT_READY", "Recommendation export is not ready.")

    try:
        page = store.page(
            limit=resolved_limit,
            cursor=cursor,
            model_version=model_version,
            mode=mode,  # type: ignore[arg-type]
        )
    except InvalidCursorError:
        return error_response(422, request_id, "INVALID_CURSOR", "Pagination cursor is invalid.")
    except Exception as exc:
        return error_response(
            500,
            request_id,
            "INTERNAL_ERROR",
            "Could not load recommendation export.",
            {"detail": str(exc)},
        )

    if model_version != "latest" and not page.model_version:
        return error_response(422, request_id, "MODEL_VERSION_NOT_FOUND", "Requested model_version was not found.")

    return ExportResponse(
        request_id=request_id,
        model_version=page.model_version or settings.model_version,
        generated_at=page.generated_at or "",
        page=PageInfo(limit=page.limit, next_cursor=page.next_cursor, has_more=page.has_more),
        recommendations=page.rows,
    )


@app.get(
    "/ui/api/recommendations/user/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(require_test_ui), Depends(require_admin_session)],
)
def ui_user_recommendations(
    user_id: str,
    model_version: str = Query(default="latest"),
    mode: str = Query(default="test"),
    settings: MlServiceSettings = Depends(get_settings),
    store: RecommendationExportStore = Depends(get_store),
):
    request_id = str(uuid4())
    if mode not in {"normal", "test"}:
        return error_response(400, request_id, "INVALID_REQUEST", "mode must be normal or test.")

    requested_user_id = str(user_id).strip()

    # Keep using a prepared export when it exists. This path is fast and is
    # retained for batch review and backward compatibility.
    if store.ready(mode):  # type: ignore[arg-type]
        resolution, found_in_export = _resolve_export_or_source_user_id(
            requested_user_id,
            model_version=model_version,
            mode=mode,
            settings=settings,
            store=store,
        )
        if resolution["status"] == "ambiguous":
            return _user_lookup_error(
                request_id=request_id,
                requested_user_id=requested_user_id,
                resolution=resolution,
            )

        if found_in_export:
            canonical_user_id = str(resolution["canonical_user_id"])
            try:
                rows, generated_at, resolved_version = store.user_rows(
                    canonical_user_id,
                    model_version=model_version,
                    mode=mode,  # type: ignore[arg-type]
                )
            except Exception as exc:
                return error_response(
                    500,
                    request_id,
                    "INTERNAL_ERROR",
                    "Could not load user recommendations.",
                    {"detail": str(exc)},
                )

            if model_version != "latest" and not resolved_version:
                return error_response(
                    422,
                    request_id,
                    "MODEL_VERSION_NOT_FOUND",
                    "Requested model_version was not found.",
                )

            if not rows:
                return _user_lookup_error(
                    request_id=request_id,
                    requested_user_id=requested_user_id,
                    resolution={
                        "status": "not_found",
                        "canonical_user_id": None,
                    },
                )

            profile = None
            history = []
            attention = []
            actual_course = None
            learning_progress = None
            progress_items = []
            try:
                context = build_user_context(
                    data_dir=settings.data_dir,
                    artifact_dir=settings.artifact_dir,
                    user_id=canonical_user_id,
                    match_type=str(resolution["status"]),
                )
                profile = context.profile
                history = context.history
                actual_course = context.actual_course
                learning_progress = context.learning_progress
                progress_items = context.progress_items
                attention = get_ui_recommender().attention_for_user(
                    canonical_user_id,
                    context.inference_history,
                )
                _add_recommendation_reasons(rows, history, attention)
                _update_actual_course_status(actual_course, rows)
            except Exception:
                # Export inspection remains available even when optional
                # profile-enrichment source files are absent.
                pass

            return UserResponse(
                request_id=request_id,
                user_id=canonical_user_id,
                requested_user_id=requested_user_id,
                canonical_user_id=canonical_user_id,
                match_type=str(resolution["status"]),
                model_version=resolved_version,
                generated_at=generated_at,
                recommendations=rows,
                profile=profile,
                history=history,
                attention=attention,
                actual_course=actual_course,
                learning_progress=learning_progress,
                progress_items=progress_items,
                inference_source="active_export",
            )

        if resolution["canonical_user_id"] is None:
            return _user_lookup_error(
                request_id=request_id,
                requested_user_id=requested_user_id,
                resolution=resolution,
            )

    # If a prepared export does not exist yet, the dashboard performs one live
    # inference. The same fallback is used when an ID exists in source data but
    # is outside a deliberately limited demonstration export.
    resolution = resolve_user_id(
        requested_user_id,
        _source_user_ids(str(settings.data_dir.resolve())),
    )
    if resolution["status"] in {"ambiguous", "not_found"}:
        return _user_lookup_error(
            request_id=request_id,
            requested_user_id=requested_user_id,
            resolution=resolution,
        )

    canonical_user_id = str(resolution["canonical_user_id"])
    try:
        context = build_user_context(
            data_dir=settings.data_dir,
            artifact_dir=settings.artifact_dir,
            user_id=canonical_user_id,
            match_type=str(resolution["status"]),
        )
        recommender = get_ui_recommender()
        live_result = recommender.recommend(
            canonical_user_id,
            context.inference_history,
            top_n=10,
        )
        max_popularity = float(
            recommender.course_popularity["train_popularity_count"].max()
        )
        rows = []
        for item in live_result["recommendations"]:
            softmax_score = item.get("softmax_score")
            similarity_score = item.get("similarity_score_0_1")
            popularity_count = item.get("train_popularity_count")
            if softmax_score is not None:
                score = float(softmax_score)
            elif similarity_score is not None:
                score = float(similarity_score)
            elif popularity_count is not None and max_popularity > 0:
                score = float(popularity_count) / max_popularity
            else:
                score = 0.0

            rows.append(
                {
                    "canonical_course_id": str(item["course_id"]),
                    "rank": int(item["rank"]),
                    "score": round(score, 6),
                    "reason_code": live_result["metadata"].get(
                        "fallback_reason"
                    ),
                    "course_title": item.get("recommended_course"),
                    "competency": item.get("competency"),
                    "level": item.get("level"),
                    "certificate_status": item.get("certificate_status"),
                    "similarity_score": item.get("similarity_score_0_1"),
                    "similarity_score_percent": item.get(
                        "similarity_score_percent"
                    ),
                    "softmax_score": item.get("softmax_score"),
                    "softmax_score_percent": item.get(
                        "softmax_score_percent"
                    ),
                    "fallback_reason": live_result["metadata"].get(
                        "fallback_reason"
                    ),
                }
            )

        attention = recommender.attention_for_user(
            canonical_user_id,
            context.inference_history,
        )
        _add_recommendation_reasons(
            rows,
            context.history,
            attention,
        )
        _update_actual_course_status(context.actual_course, rows)
    except Exception as exc:
        return error_response(
            500,
            request_id,
            "LIVE_INFERENCE_FAILED",
            "Rekomendasi langsung tidak dapat dibuat.",
            {"detail": str(exc)},
        )

    return UserResponse(
        request_id=request_id,
        user_id=canonical_user_id,
        requested_user_id=requested_user_id,
        canonical_user_id=canonical_user_id,
        match_type=str(resolution["status"]),
        model_version=settings.model_version,
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(),
        recommendations=rows,
        profile=context.profile,
        history=context.history,
        attention=attention,
        actual_course=context.actual_course,
        learning_progress=context.learning_progress,
        progress_items=context.progress_items,
        inference_source="live_model",
    )


def _clean_table_records(frame: pd.DataFrame, max_rows: int = 50) -> list[dict]:
    records = []
    for row in frame.head(max_rows).to_dict(orient="records"):
        cleaned = {}
        for key, value in row.items():
            if pd.isna(value):
                cleaned[str(key)] = None
            elif hasattr(value, "item"):
                cleaned[str(key)] = value.item()
            else:
                cleaned[str(key)] = value
        records.append(cleaned)
    return records


def _read_artifact_table(settings: MlServiceSettings, name: str, max_rows: int = 50) -> list[dict]:
    path = settings.artifact_dir / "tables" / name
    if not path.exists():
        return []
    return _clean_table_records(pd.read_csv(path), max_rows=max_rows)


def _evaluation_generated_at(settings: MlServiceSettings) -> str | None:
    path = settings.export_dir / "recommendation_export_manifest.json"
    if not path.exists():
        return None
    try:
        import json

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload.get("generated_at")
    except Exception:
        return None


@app.get(
    "/ui/api/evaluation/summary",
    response_model=EvaluationResponse,
    dependencies=[Depends(require_test_ui), Depends(require_admin_session)],
)
def ui_evaluation_summary(
    settings: MlServiceSettings = Depends(get_settings),
) -> EvaluationResponse:
    final = _read_artifact_json(settings, "evaluation_final.json")
    topk_rows = _read_artifact_table(settings, "topk_performance_curve_df.csv", max_rows=100)
    coverage_rows = _read_artifact_table(settings, "coverage_summary_df.csv", max_rows=20)
    strict_rows = _normalize_strict_evaluation_rows(
        _read_artifact_table(settings, "strict_metrics_comparison_df.csv", max_rows=100)
    )
    similarity_rows = _read_artifact_table(settings, "similarity_metrics_df.csv", max_rows=100)
    softmax_rows = _read_artifact_table(settings, "softmax_metrics_df.csv", max_rows=100)

    overall_metrics = [
        {"label": label, "value": float(final[key]) * 100, "context": "Softmax Ranking · final temporal test"}
        for label, key in [("Hit@1", "hit_at_1"), ("Hit@5", "hit_at_5"), ("Hit@10", "hit_at_10"), ("MRR@10", "mrr_at_10"), ("NDCG@10", "ndcg_at_10"), ("Coverage@10", "coverage_at_10")]
        if key in final
    ]

    return EvaluationResponse(
        model_version=str(final.get("model_version", settings.model_version)),
        primary_ranking=str(final.get("ranking_method", "Softmax Ranking")),
        masking_protocol=str(final.get("masking_protocol", "unknown")),
        evaluation_samples=final.get("test_samples"),
        generated_at=_evaluation_generated_at(settings),
        overall_metrics=overall_metrics,
        metric_tables={
            "topk_performance": topk_rows,
            "coverage": coverage_rows,
            "strict_comparison": strict_rows,
            "similarity_metrics": similarity_rows,
            "softmax_metrics": softmax_rows,
            "popularity_baseline": _read_artifact_table(settings, "popularity_metrics_comparison_df.csv", max_rows=100),
        },
    )


def _normalize_strict_evaluation_rows(rows: list[dict]) -> list[dict]:
    """Expose the actual history protocol for default and strict rows.

    The strict comparison table reports the same metric values exported by the
    experiment; this only corrects its serving metadata for the UI/API.
    """
    normalized: list[dict] = []
    for source_row in rows:
        row = dict(source_row)
        setting = str(row.get("evaluation_setting", "")).strip().lower()
        if "strict" in setting and "train" in setting:
            row["masking_protocol"] = "strict_train_history"
            row["history_protocol"] = "strict_train_history"
        elif "default" in setting:
            row["masking_protocol"] = "full_pre_target_history"
            row["history_protocol"] = "full_pre_target_history"
        normalized.append(row)
    return normalized


def _read_artifact_json(settings: MlServiceSettings, name: str) -> dict:
    path = settings.artifact_dir / "config" / name
    if not path.exists():
        return {}
    try:
        import json

        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


@app.get(
    "/ui/api/research/summary",
    response_model=ResearchSummaryResponse,
    dependencies=[Depends(require_test_ui), Depends(require_admin_session)],
)
def ui_research_summary(
    settings: MlServiceSettings = Depends(get_settings),
) -> ResearchSummaryResponse:
    """Provide research-facing artifact tables without exposing filesystem paths."""
    experiment_config = _read_artifact_json(settings, "experiment_config.json")
    evaluation_final = _read_artifact_json(settings, "evaluation_final.json")
    artifact_check = artifact_status_for_settings(settings)

    model_card = {
        "model_version": experiment_config.get("model_version"),
        "configuration": experiment_config.get("final_model_config_id"),
        "architecture": "Encoder-Decoder LSTM with Temporal Attention",
        "primary_ranking": experiment_config.get("ranking_output_primary"),
        "alternative_ranking": "Cosine Similarity Ranking",
        "max_sequence_length": experiment_config.get("max_sequence_length"),
        "seen_course_masking": evaluation_final.get("masking_protocol"),
        "num_courses": experiment_config.get("num_courses_in_train_vocab"),
        "num_competencies": experiment_config.get("num_competencies_in_train_vocab"),
        "num_levels": experiment_config.get("num_levels_in_train_vocab"),
        "course_embedding_dim": experiment_config.get("course_embedding_dim"),
        "competency_embedding_dim": experiment_config.get("competency_embedding_dim"),
        "level_embedding_dim": experiment_config.get("level_embedding_dim"),
        "latent_dim": experiment_config.get("latent_dim"),
        "random_seed": experiment_config.get("random_seed_tensorflow"),
        "evaluation_protocol": experiment_config.get("evaluation_protocol"),
        "min_course_count_train": experiment_config.get("min_course_count_train"),
        "repeated_run_seeds": experiment_config.get("repeated_run_seeds"),
    }

    return ResearchSummaryResponse(
        model_version=str(evaluation_final.get("model_version", settings.model_version)),
        primary_ranking=str(evaluation_final.get("ranking_method", "Softmax Ranking")),
        masking_protocol=str(evaluation_final.get("masking_protocol", "unknown")),
        artifact_check=artifact_check,
        generated_at=_evaluation_generated_at(settings),
        data_quality={
            "data_split": _read_artifact_table(settings, "data_split_summary_df.csv", max_rows=20),
            "interaction_per_user": _read_artifact_table(settings, "interaction_per_user_summary_df.csv", max_rows=5),
            "noise_cleaning": _read_artifact_table(settings, "course_noise_summary_df.csv", max_rows=20),
            "course_popularity": _read_artifact_table(settings, "course_popularity_summary_df.csv", max_rows=5),
        },
        model_card=model_card,
        error_analysis={
            "summary": _read_artifact_table(settings, "error_analysis_summary_display.csv", max_rows=20),
            "error_types": _read_artifact_table(settings, "error_type_summary_display.csv", max_rows=30),
        },
    )
REFRESH_JOBS: dict[str, dict] = {}
REFRESH_JOBS_LOCK = Lock()


def _refresh_snapshot(job_id: str) -> RefreshJobResponse:
    with REFRESH_JOBS_LOCK:
        job = REFRESH_JOBS.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Refresh job not found.")
        return RefreshJobResponse(**{**job, "logs": list(job["logs"])})


def _append_job_log(job_id: str, message: str) -> None:
    stamped = f"{datetime.now(timezone.utc).astimezone().isoformat()} {message}"
    with REFRESH_JOBS_LOCK:
        if job_id in REFRESH_JOBS:
            REFRESH_JOBS[job_id]["logs"].append(stamped)


def _run_refresh_job(job_id: str, settings: MlServiceSettings, payload: RefreshStartRequest) -> None:
    try:
        _append_job_log(job_id, "Starting recommendation export refresh.")
        _append_job_log(job_id, f"Loading artifacts from {settings.artifact_dir}.")
        artifact_status = artifact_status_for_settings(settings)
        if artifact_status.get("critical"):
            raise RuntimeError(artifact_status.get("message", "Artifact check failed."))
        active_model_version = str(artifact_status.get("model_version") or settings.model_version)
        manifest = generate_recommendation_export(
            artifact_dir=settings.artifact_dir,
            data_dir=settings.data_dir,
            output_path=settings.export_path,
            fixture_path=settings.fixture_path,
            model_version=active_model_version,
            top_k=payload.top_k,
            max_users=payload.max_users,
            progress_callback=lambda message: _append_job_log(job_id, message),
        )
        try:
            get_store().clear_cache()
            get_artifact_status.cache_clear()
        except Exception as exc:
            _append_job_log(job_id, f"Cache refresh warning: {exc}")
        with REFRESH_JOBS_LOCK:
            REFRESH_JOBS[job_id].update(
                {
                    "status": "completed",
                    "finished_at": datetime.now(timezone.utc).astimezone().isoformat(),
                    "result": manifest,
                    "error": None,
                }
            )
        _append_job_log(job_id, "Recommendation export refresh completed.")
    except Exception as exc:
        with REFRESH_JOBS_LOCK:
            REFRESH_JOBS[job_id].update(
                {
                    "status": "failed",
                    "finished_at": datetime.now(timezone.utc).astimezone().isoformat(),
                    "error": str(exc),
                }
            )
        _append_job_log(job_id, f"Recommendation export refresh failed: {exc}")


@app.post(
    "/ui/api/refresh/start",
    response_model=RefreshJobResponse,
    dependencies=[Depends(require_test_ui), Depends(require_admin_session)],
)
def ui_refresh_start(
    payload: RefreshStartRequest,
    settings: MlServiceSettings = Depends(get_settings),
) -> RefreshJobResponse:
    if payload.mode not in {"normal", "test"}:
        raise HTTPException(status_code=400, detail="mode must be normal or test.")

    job_id = str(uuid4())
    now = datetime.now(timezone.utc).astimezone().isoformat()
    with REFRESH_JOBS_LOCK:
        REFRESH_JOBS[job_id] = {
            "job_id": job_id,
            "status": "running",
            "started_at": now,
            "finished_at": None,
            "top_k": payload.top_k,
            "max_users": payload.max_users,
            "logs": [f"{now} Refresh job queued."],
            "result": None,
            "error": None,
        }

    thread = Thread(target=_run_refresh_job, args=(job_id, settings, payload), daemon=True)
    thread.start()
    return _refresh_snapshot(job_id)


@app.get(
    "/ui/api/refresh/status/{job_id}",
    response_model=RefreshJobResponse,
    dependencies=[Depends(require_test_ui), Depends(require_admin_session)],
)
def ui_refresh_status(job_id: str) -> RefreshJobResponse:
    return _refresh_snapshot(job_id)
