"""Build the employee profile and pre-prediction course history for the UI."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd


@dataclass
class UserContext:
    profile: dict[str, Any]
    history: list[dict[str, Any]]
    inference_history: pd.DataFrame
    actual_course: dict[str, Any] | None
    learning_progress: dict[str, Any]
    progress_items: list[dict[str, Any]]


def _clean_id(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)


def _safe_list(value: Any) -> list[int]:
    if isinstance(value, list):
        return [int(item) for item in value]
    if pd.isna(value):
        return []
    try:
        parsed = ast.literal_eval(str(value))
    except (SyntaxError, ValueError):
        return []
    return [int(item) for item in parsed] if isinstance(parsed, list) else []


@lru_cache(maxsize=4)
def _load_context_tables(data_dir_text: str, artifact_dir_text: str) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir_text)
    artifact_dir = Path(artifact_dir_text)

    users = pd.read_csv(
        data_dir / "users.csv",
        dtype={"user_id": "string"},
    )
    interactions = pd.read_csv(
        data_dir / "interactions.csv",
        dtype={
            "user_id": "string",
            "course_id": "string",
            "interaction_id": "string",
        },
    )
    courses = pd.read_csv(
        data_dir / "courses.csv",
        dtype={"canonical_course_id": "string"},
    )
    alias_map = pd.read_csv(
        data_dir / "course_alias_map.csv",
        dtype={
            "legacy_course_id": "string",
            "canonical_course_id": "string",
        },
    )
    catalog = pd.read_csv(
        artifact_dir / "tables" / "course_catalog.csv",
        dtype={"canonical_course_id": "string"},
    )
    test_metadata = pd.read_csv(
        artifact_dir / "tables" / "test_metadata.csv",
        dtype={"user_id": "string"},
    )
    progress_summary_path = data_dir / "learning_progress_summary.csv"
    progress_detail_path = data_dir / "learning_progress_detail.csv"
    progress_summary = (
        pd.read_csv(
            progress_summary_path,
            dtype={"user_id": "string"},
        )
        if progress_summary_path.exists()
        else pd.DataFrame(columns=["user_id"])
    )
    progress_detail = (
        pd.read_csv(
            progress_detail_path,
            dtype={
                "user_id": "string",
                "canonical_course_id": "string",
            },
        )
        if progress_detail_path.exists()
        else pd.DataFrame(columns=["user_id", "canonical_course_id"])
    )

    for frame in (
        users,
        interactions,
        courses,
        alias_map,
        catalog,
        test_metadata,
        progress_summary,
        progress_detail,
    ):
        frame.columns = frame.columns.astype(str).str.strip().str.lower()

    users["user_id"] = _clean_id(users["user_id"])
    interactions["user_id"] = _clean_id(interactions["user_id"])
    interactions["course_id"] = _clean_id(interactions["course_id"])
    courses["canonical_course_id"] = _clean_id(courses["canonical_course_id"])
    alias_map["legacy_course_id"] = _clean_id(alias_map["legacy_course_id"])
    alias_map["canonical_course_id"] = _clean_id(alias_map["canonical_course_id"])
    catalog["canonical_course_id"] = _clean_id(catalog["canonical_course_id"])
    test_metadata["user_id"] = _clean_id(test_metadata["user_id"])
    if "user_id" in progress_summary:
        progress_summary["user_id"] = _clean_id(progress_summary["user_id"])
    if "user_id" in progress_detail:
        progress_detail["user_id"] = _clean_id(progress_detail["user_id"])
    if "canonical_course_id" in progress_detail:
        progress_detail["canonical_course_id"] = _clean_id(
            progress_detail["canonical_course_id"]
        )

    history = interactions.merge(
        alias_map.rename(
            columns={"canonical_course_id": "mapped_canonical_course_id"}
        ),
        left_on="course_id",
        right_on="legacy_course_id",
        how="left",
    )
    history["canonical_course_id"] = (
        history["mapped_canonical_course_id"].fillna(history["course_id"])
    )
    history["canonical_course_id"] = _clean_id(history["canonical_course_id"])
    history["sort_timestamp"] = pd.to_datetime(
        history.get("event_timestamp"),
        errors="coerce",
    )
    history["sort_row_order"] = range(len(history))

    course_columns = [
        "canonical_course_id",
        "course_name",
        "description",
        "kompetensi",
        "level",
    ]
    history = history.merge(
        courses[course_columns].drop_duplicates("canonical_course_id"),
        on="canonical_course_id",
        how="left",
    )

    catalog_columns = [
        "course_encoded",
        "canonical_course_id",
        "course_name",
        "kompetensi",
        "level",
        "course_has_certificate_train",
        "certificate_count_train",
    ]
    catalog = catalog[catalog_columns].copy()
    catalog["course_encoded"] = pd.to_numeric(
        catalog["course_encoded"],
        errors="coerce",
    ).astype("Int64")

    return {
        "users": users,
        "history": history,
        "catalog": catalog,
        "test_metadata": test_metadata,
        "progress_summary": progress_summary,
        "progress_detail": progress_detail,
    }


def build_user_context(
    *,
    data_dir: str | Path,
    artifact_dir: str | Path,
    user_id: str,
    match_type: str,
) -> UserContext:
    tables = _load_context_tables(
        str(Path(data_dir).resolve()),
        str(Path(artifact_dir).resolve()),
    )
    users = tables["users"]
    all_history = tables["history"]
    catalog = tables["catalog"]
    test_metadata = tables["test_metadata"]
    progress_summary = tables["progress_summary"]
    progress_detail = tables["progress_detail"]

    user_row = users[users["user_id"] == user_id].head(1)
    employee_name = "Nama tidak tersedia"
    source_system = "Tidak tersedia"
    if not user_row.empty:
        employee_name = str(
            user_row.iloc[0].get("full_name") or "Nama tidak tersedia"
        )
        source_system = str(
            user_row.iloc[0].get("source_system") or "Tidak tersedia"
        )

    current = all_history[all_history["user_id"] == user_id].copy()
    current = current.sort_values(
        ["sort_timestamp", "interaction_id", "sort_row_order"],
        na_position="last",
    )
    current = current.drop_duplicates("canonical_course_id", keep="first")

    metadata_row = test_metadata[test_metadata["user_id"] == user_id].head(1)
    actual_course = None

    if not metadata_row.empty:
        metadata = metadata_row.iloc[0]
        history_encoded = _safe_list(metadata.get("history_encoded_full"))
        encoded_to_id = (
            catalog.dropna(subset=["course_encoded"])
            .set_index("course_encoded")["canonical_course_id"]
            .astype(str)
            .to_dict()
        )
        ordered_course_ids = [
            str(encoded_to_id[encoded])
            for encoded in history_encoded
            if encoded in encoded_to_id
        ]
        order_lookup = {
            course_id: position
            for position, course_id in enumerate(ordered_course_ids)
        }
        current = current[
            current["canonical_course_id"].isin(ordered_course_ids)
        ].copy()
        current["_expected_order"] = current["canonical_course_id"].map(order_lookup)
        current = current.sort_values("_expected_order").drop(
            columns="_expected_order"
        )

        ground_truth_encoded = pd.to_numeric(
            metadata.get("ground_truth_encoded"),
            errors="coerce",
        )
        ground_truth_id = None
        if pd.notna(ground_truth_encoded):
            ground_truth_id = encoded_to_id.get(int(ground_truth_encoded))
        actual_course = {
            "course_id": str(ground_truth_id or ""),
            "course_name": str(
                metadata.get("ground_truth_course") or "Tidak tersedia"
            ),
            "rank": None,
            "status": "Belum dibandingkan dengan hasil rekomendasi.",
        }
    else:
        known_course_ids = set(catalog["canonical_course_id"].astype(str))
        current = current[
            current["canonical_course_id"].isin(known_course_ids)
        ].copy()

    catalog_lookup = catalog.set_index("canonical_course_id")
    history_rows = []
    for _, row in current.iterrows():
        course_id = str(row["canonical_course_id"])
        catalog_row = (
            catalog_lookup.loc[course_id]
            if course_id in catalog_lookup.index
            else None
        )
        course_name = row.get("course_name")
        competency = row.get("kompetensi")
        level = row.get("level")
        certificate_flag = 0
        if catalog_row is not None:
            course_name = catalog_row.get("course_name", course_name)
            competency = catalog_row.get("kompetensi", competency)
            level = catalog_row.get("level", level)
            parsed_certificate = pd.to_numeric(
                catalog_row.get("course_has_certificate_train", 0),
                errors="coerce",
            )
            certificate_flag = (
                int(parsed_certificate) if pd.notna(parsed_certificate) else 0
            )

        timestamp = row.get("sort_timestamp")
        history_rows.append(
            {
                "event_timestamp": (
                    timestamp.isoformat()
                    if pd.notna(timestamp)
                    else None
                ),
                "course_id": course_id,
                "course_name": str(course_name or "Nama course tidak tersedia"),
                "competency": str(competency or "Tidak tersedia"),
                "level": str(level or "Tidak tersedia"),
                "certificate_status": (
                    "Bersertifikat"
                    if certificate_flag == 1
                    else "Tidak Bersertifikat"
                ),
            }
        )

    inference_columns = [
        "user_id",
        "canonical_course_id",
        "sort_timestamp",
        "interaction_id",
        "sort_row_order",
    ]
    inference_history = current[
        [column for column in inference_columns if column in current.columns]
    ].copy()

    employee_progress = progress_summary[
        progress_summary["user_id"] == user_id
    ].head(1)
    status_available = False
    learning_progress = {
        "status_available": False,
        "tracked_course_count": 0,
        "completed_count": 0,
        "ongoing_count": 0,
        "enrolled_count": 0,
        "unenrolled_count": 0,
        "completion_rate_percent": None,
        "average_score": None,
        "score_count": 0,
        "certificate_count": 0,
        "note": (
            "Data status penyelesaian belum tersedia untuk pegawai ini. "
            "Riwayat course tetap dapat digunakan oleh model."
        ),
    }
    if not employee_progress.empty:
        row = employee_progress.iloc[0]
        raw_status = row.get("status_available", False)
        status_available = (
            bool(raw_status)
            if isinstance(raw_status, bool)
            else str(raw_status).strip().lower() == "true"
        )

        def optional_float(value: Any) -> float | None:
            parsed = pd.to_numeric(value, errors="coerce")
            return round(float(parsed), 2) if pd.notna(parsed) else None

        def safe_int(value: Any) -> int:
            parsed = pd.to_numeric(value, errors="coerce")
            return int(parsed) if pd.notna(parsed) else 0

        learning_progress = {
            "status_available": status_available,
            "tracked_course_count": safe_int(
                row.get("tracked_course_count")
            ),
            "completed_count": safe_int(row.get("completed_count")),
            "ongoing_count": safe_int(row.get("ongoing_count")),
            "enrolled_count": safe_int(row.get("enrolled_count")),
            "unenrolled_count": safe_int(row.get("unenrolled_count")),
            "completion_rate_percent": optional_float(
                row.get("completion_rate_percent")
            ),
            "average_score": optional_float(row.get("average_score")),
            "score_count": safe_int(row.get("score_count")),
            "certificate_count": safe_int(row.get("certificate_count")),
            "note": (
                "Progres ini hanya informasi pendukung dan tidak mengubah "
                "urutan rekomendasi model."
                if status_available
                else (
                    "Data status penyelesaian belum tersedia untuk pegawai "
                    "ini. Riwayat course tetap dapat digunakan oleh model."
                )
            ),
        }

    progress_items = []
    current_progress = progress_detail[
        progress_detail["user_id"] == user_id
    ].copy()
    status_order = {
        "On Going": 1,
        "Enroll": 2,
        "Completed": 3,
        "Unenroll": 4,
    }
    if not current_progress.empty:
        current_progress["_status_order"] = (
            current_progress["learning_status"].map(status_order).fillna(5)
        )
        current_progress = current_progress.sort_values(
            ["_status_order", "course_name"],
            kind="stable",
        )
        for _, row in current_progress.iterrows():
            score = pd.to_numeric(row.get("score"), errors="coerce")
            raw_certificate = row.get("has_certificate", False)
            has_certificate = (
                bool(raw_certificate)
                if isinstance(raw_certificate, bool)
                else str(raw_certificate).strip().lower() == "true"
            )
            progress_items.append(
                {
                    "course_id": str(row["canonical_course_id"]),
                    "course_name": str(
                        row.get("course_name")
                        or "Nama course tidak tersedia"
                    ),
                    "learning_status": str(
                        row.get("learning_status")
                        or "Tidak tersedia"
                    ),
                    "score": (
                        round(float(score), 2)
                        if pd.notna(score)
                        else None
                    ),
                    "has_certificate": has_certificate,
                }
            )

    return UserContext(
        profile={
            "employee_name": employee_name,
            "user_id": user_id,
            "source_system": source_system,
            "history_count": len(history_rows),
            "id_match_type": match_type,
        },
        history=history_rows,
        inference_history=inference_history,
        actual_course=actual_course,
        learning_progress=learning_progress,
        progress_items=progress_items,
    )
