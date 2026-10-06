"""Stable recommendation export storage and cursor pagination."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd


EXPORT_COLUMNS = [
    "user_id",
    "canonical_course_id",
    "rank",
    "score",
    "reason_code",
    "model_version",
    "generated_at",
]

OPTIONAL_EXPORT_COLUMNS = [
    "course_title",
    "competency",
    "level",
    "certificate_status",
    "similarity_score",
    "similarity_score_percent",
    "softmax_score",
    "softmax_score_percent",
    "fallback_reason",
]


class ExportStoreError(Exception):
    pass


class InvalidCursorError(ExportStoreError):
    pass


@dataclass(frozen=True)
class ExportPage:
    rows: list[dict]
    limit: int
    next_cursor: str | None
    has_more: bool
    total_rows: int
    model_version: str
    generated_at: str


def encode_cursor(offset: int) -> str:
    payload = json.dumps({"offset": int(offset)}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
        offset = int(payload["offset"])
    except Exception as exc:
        raise InvalidCursorError("Cursor is invalid.") from exc
    if offset < 0:
        raise InvalidCursorError("Cursor is invalid.")
    return offset


class RecommendationExportStore:
    def __init__(
        self,
        export_path: str | Path,
        fixture_path: str | Path | None = None,
        course_catalog_path: str | Path | None = None,
    ) -> None:
        self.export_path = Path(export_path)
        self.fixture_path = Path(fixture_path) if fixture_path is not None else None
        self.course_catalog_path = Path(course_catalog_path) if course_catalog_path is not None else None
        self._normal_df: pd.DataFrame | None = None
        self._fixture_df: pd.DataFrame | None = None
        self._catalog_df: pd.DataFrame | None = None

    def ready(self, mode: Literal["normal", "test"] = "normal") -> bool:
        return self._path_for_mode(mode).exists()

    def load(self, mode: Literal["normal", "test"] = "normal") -> pd.DataFrame:
        if mode == "test":
            if self._fixture_df is None:
                self._fixture_df = self._enrich_with_catalog(self._read_csv(self._path_for_mode(mode)))
            return self._fixture_df.copy()

        if self._normal_df is None:
            self._normal_df = self._enrich_with_catalog(self._read_csv(self._path_for_mode(mode)))
        return self._normal_df.copy()

    def page(
        self,
        *,
        limit: int,
        cursor: str | None,
        model_version: str,
        mode: Literal["normal", "test"] = "normal",
    ) -> ExportPage:
        df = self.load(mode)
        if model_version != "latest":
            df = df[df["model_version"].astype(str) == model_version].copy()

        if df.empty:
            generated_at = ""
            resolved_version = model_version if model_version != "latest" else ""
        else:
            generated_at = str(df["generated_at"].iloc[0])
            resolved_version = str(df["model_version"].iloc[0])

        offset = decode_cursor(cursor)
        if offset > len(df):
            raise InvalidCursorError("Cursor offset is outside the export.")

        end = min(offset + limit, len(df))
        page_df = df.iloc[offset:end].copy()
        has_more = end < len(df)
        next_cursor = encode_cursor(end) if has_more else None

        rows = []
        for row in page_df.to_dict(orient="records"):
            rows.append(self._format_export_row(row, include_user=True))

        return ExportPage(
            rows=rows,
            limit=limit,
            next_cursor=next_cursor,
            has_more=has_more,
            total_rows=len(df),
            model_version=resolved_version,
            generated_at=generated_at,
        )

    def user_rows(
        self,
        user_id: str,
        *,
        model_version: str,
        mode: Literal["normal", "test"] = "normal",
    ) -> tuple[list[dict], str, str]:
        df = self.load(mode)
        df = df[df["user_id"].astype(str) == str(user_id)].copy()
        if model_version != "latest":
            df = df[df["model_version"].astype(str) == model_version].copy()
        if df.empty:
            return [], "", model_version if model_version != "latest" else ""

        df = df.sort_values(["rank", "canonical_course_id"]).reset_index(drop=True)
        generated_at = str(df["generated_at"].iloc[0])
        resolved_version = str(df["model_version"].iloc[0])
        rows = [self._format_export_row(row, include_user=False) for row in df.to_dict(orient="records")]
        return rows, generated_at, resolved_version

    def available_user_ids(
        self,
        *,
        model_version: str,
        mode: Literal["normal", "test"] = "normal",
    ) -> list[str]:
        """Return canonical export IDs without modifying their stored form."""
        df = self.load(mode)
        if model_version != "latest":
            df = df[df["model_version"].astype(str) == model_version].copy()
        return [str(user_id).strip() for user_id in df["user_id"].dropna().astype(str).unique()]

    def count(self, mode: Literal["normal", "test"] = "normal") -> int:
        if not self.ready(mode):
            return 0
        return len(self.load(mode))

    def clear_cache(self) -> None:
        self._normal_df = None
        self._fixture_df = None
        self._catalog_df = None

    def _path_for_mode(self, mode: Literal["normal", "test"]) -> Path:
        if mode == "test":
            if self.fixture_path is None:
                raise FileNotFoundError("Fixture export path is not configured.")
            return self.fixture_path
        return self.export_path

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"Recommendation export is not ready: {path}")
        df = pd.read_csv(path, dtype={"user_id": str, "canonical_course_id": str, "model_version": str})
        missing = set(EXPORT_COLUMNS) - set(df.columns)
        if missing:
            raise ValueError(f"Recommendation export missing columns: {sorted(missing)}")
        present_optional = [column for column in OPTIONAL_EXPORT_COLUMNS if column in df.columns]
        df = df[EXPORT_COLUMNS + present_optional].copy()
        df["rank"] = pd.to_numeric(df["rank"], errors="raise").astype(int)
        df["score"] = pd.to_numeric(df["score"], errors="raise").astype(float)
        df = df.sort_values(["user_id", "rank", "canonical_course_id"]).reset_index(drop=True)
        return df

    def _load_catalog(self) -> pd.DataFrame | None:
        if self.course_catalog_path is None or not self.course_catalog_path.exists():
            return None
        if self._catalog_df is not None:
            return self._catalog_df

        catalog = pd.read_csv(self.course_catalog_path, dtype={"canonical_course_id": str})
        required = {"canonical_course_id", "course_name", "kompetensi", "level", "course_has_certificate_train"}
        if not required.issubset(set(catalog.columns)):
            return None
        catalog = catalog.copy()
        catalog["canonical_course_id"] = catalog["canonical_course_id"].astype(str)
        catalog["certificate_status"] = pd.to_numeric(
            catalog["course_has_certificate_train"], errors="coerce"
        ).fillna(0).astype(int).map(lambda value: "certified" if value == 1 else "not_certified")
        self._catalog_df = catalog[
            ["canonical_course_id", "course_name", "kompetensi", "level", "certificate_status"]
        ].rename(
            columns={
                "course_name": "course_title",
                "kompetensi": "competency",
            }
        ).drop_duplicates("canonical_course_id")
        return self._catalog_df

    def _enrich_with_catalog(self, df: pd.DataFrame) -> pd.DataFrame:
        output = df.copy()
        for column in OPTIONAL_EXPORT_COLUMNS:
            if column not in output.columns:
                output[column] = None

        catalog = self._load_catalog()
        if catalog is None:
            return output

        merge_columns = ["course_title", "competency", "level", "certificate_status"]
        output = output.drop(columns=merge_columns, errors="ignore").merge(
            catalog,
            on="canonical_course_id",
            how="left",
        )
        for column in OPTIONAL_EXPORT_COLUMNS:
            if column not in output.columns:
                output[column] = None
        return output

    @staticmethod
    def _optional_value(row: dict, key: str):
        value = row.get(key)
        return None if pd.isna(value) else value

    @classmethod
    def _format_export_row(cls, row: dict, *, include_user: bool) -> dict:
        output = {
            "canonical_course_id": str(row["canonical_course_id"]),
            "rank": int(row["rank"]),
            "score": float(row["score"]),
            "reason_code": None if pd.isna(row.get("reason_code")) else str(row.get("reason_code")),
            "course_title": None if pd.isna(row.get("course_title")) else str(row.get("course_title")),
            "competency": None if pd.isna(row.get("competency")) else str(row.get("competency")),
            "level": None if pd.isna(row.get("level")) else str(row.get("level")),
            "certificate_status": None if pd.isna(row.get("certificate_status")) else str(row.get("certificate_status")),
            "similarity_score": cls._optional_value(row, "similarity_score"),
            "similarity_score_percent": cls._optional_value(row, "similarity_score_percent"),
            "softmax_score": cls._optional_value(row, "softmax_score"),
            "softmax_score_percent": cls._optional_value(row, "softmax_score_percent"),
            "fallback_reason": None if pd.isna(row.get("fallback_reason")) else str(row.get("fallback_reason")),
        }
        if include_user:
            output["user_id"] = str(row["user_id"])
        return output
