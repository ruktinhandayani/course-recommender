"""CRE API response and error helpers."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class PageInfo(BaseModel):
    limit: int
    next_cursor: str | None = None
    has_more: bool


class ExportRecommendation(BaseModel):
    user_id: str
    canonical_course_id: str
    rank: int = Field(ge=1)
    score: float
    reason_code: str | None = None
    course_title: str | None = None
    competency: str | None = None
    level: str | None = None
    certificate_status: str | None = None
    similarity_score: float | None = None
    similarity_score_percent: float | None = None
    softmax_score: float | None = None
    softmax_score_percent: float | None = None
    fallback_reason: str | None = None


class ExportResponse(BaseModel):
    request_id: str
    model_version: str
    generated_at: str
    page: PageInfo
    recommendations: list[ExportRecommendation]


class UserRecommendation(BaseModel):
    canonical_course_id: str
    rank: int = Field(ge=1)
    score: float
    reason_code: str | None = None
    course_title: str | None = None
    competency: str | None = None
    level: str | None = None
    certificate_status: str | None = None
    similarity_score: float | None = None
    similarity_score_percent: float | None = None
    softmax_score: float | None = None
    softmax_score_percent: float | None = None
    fallback_reason: str | None = None
    recommendation_reason: str | None = None


class EmployeeProfile(BaseModel):
    employee_name: str
    user_id: str
    source_system: str
    history_count: int
    id_match_type: str


class CourseHistoryItem(BaseModel):
    event_timestamp: str | None = None
    course_id: str
    course_name: str
    competency: str
    level: str
    certificate_status: str


class AttentionItem(BaseModel):
    input_position: int
    course_id: str
    course_name: str
    attention_weight: float


class ActualCourseCheck(BaseModel):
    course_id: str
    course_name: str
    rank: int | None = None
    status: str


class LearningProgressSummary(BaseModel):
    status_available: bool
    tracked_course_count: int
    completed_count: int
    ongoing_count: int
    enrolled_count: int
    unenrolled_count: int
    completion_rate_percent: float | None = None
    average_score: float | None = None
    score_count: int
    certificate_count: int
    note: str


class LearningProgressItem(BaseModel):
    course_id: str
    course_name: str
    learning_status: str
    score: float | None = None
    has_certificate: bool


class UserResponse(BaseModel):
    request_id: str
    user_id: str
    requested_user_id: str
    canonical_user_id: str
    match_type: str
    model_version: str
    generated_at: str
    recommendations: list[UserRecommendation]
    profile: EmployeeProfile | None = None
    history: list[CourseHistoryItem] = Field(default_factory=list)
    attention: list[AttentionItem] = Field(default_factory=list)
    actual_course: ActualCourseCheck | None = None
    learning_progress: LearningProgressSummary | None = None
    progress_items: list[LearningProgressItem] = Field(default_factory=list)
    inference_source: str = "active_export"


class HealthResponse(BaseModel):
    status: str
    model_version: str
    generated_at: str | None
    export_ready: bool
    artifact_status: str | None = None
    recommendation_count: int = 0
    primary_ranking: str = "Softmax Ranking"
    masking_protocol: str = "full_pre_target_history"
    export_mode: str | None = None
    active_export_users: int | None = None
    active_export_top_k: int | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthUserResponse(BaseModel):
    authenticated: bool
    username: str | None = None


class EvaluationResponse(BaseModel):
    model_version: str
    primary_ranking: str
    masking_protocol: str
    evaluation_samples: int | None = None
    generated_at: str | None = None
    overall_metrics: list[dict[str, Any]]
    metric_tables: dict[str, list[dict[str, Any]]]


class ResearchSummaryResponse(BaseModel):
    """Artifact-backed information shown in the research dashboard."""

    model_version: str
    primary_ranking: str
    masking_protocol: str
    artifact_check: dict[str, Any]
    generated_at: str | None = None
    data_quality: dict[str, list[dict[str, Any]]]
    model_card: dict[str, Any]
    error_analysis: dict[str, list[dict[str, Any]]]


class RefreshStartRequest(BaseModel):
    top_k: int = Field(default=20, ge=1, le=100)
    max_users: int | None = Field(default=None, ge=1)
    mode: str = "normal"


class RefreshJobResponse(BaseModel):
    job_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    top_k: int
    max_users: int | None = None
    logs: list[str]
    result: dict[str, Any] | None = None
    error: str | None = None


def error_response(
    status_code: int,
    request_id: str | None,
    code: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "request_id": request_id or "",
        "error": {
            "code": code,
            "message": message,
        },
    }
    if extra:
        payload["error"].update(extra)
    return JSONResponse(status_code=status_code, content=payload)
