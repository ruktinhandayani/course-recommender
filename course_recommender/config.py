"""Configuration for the CRE Pre-MVP ML service."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MlServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CRE_ML_",
        env_file=".env",
        extra="ignore",
    )

    # This directory is an isolated snapshot of one experimental run.  Do not
    # point it at the legacy directory, which contains incompatible artifacts.
    artifact_dir: Path = Path("course_recommender_artifacts_final")
    data_dir: Path = Path("data")
    export_dir: Path = Path("course_recommender_artifacts_final/export")
    export_file: str = "recommendations.csv"
    fixture_file: str = "recommendations_fixture.csv"

    model_version: str = "cre-lstm-attention-h2-seed42-fullmask-v1"
    generated_at: str | None = None
    default_export_limit: int = 1000
    max_export_limit: int = 1000
    default_top_k: int = 20

    api_key: str = Field(default="")
    hmac_secret: str = Field(default="")
    timestamp_tolerance_seconds: int = 60
    require_auth: bool = True
    enable_test_ui: bool = False
    test_ui_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    admin_username: str = "admin"
    admin_password: str = ""
    admin_password_hash: str | None = None
    session_secret: str = ""
    session_cookie_name: str = "cre_ml_admin_session"
    session_max_age_seconds: int = 8 * 60 * 60
    session_cookie_secure: bool = False

    @property
    def export_path(self) -> Path:
        return self.export_dir / self.export_file

    @property
    def fixture_path(self) -> Path:
        return self.export_dir / self.fixture_file

    @property
    def test_ui_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.test_ui_origins.split(",") if origin.strip()]
