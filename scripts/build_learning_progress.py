"""Build website-only learning progress tables from the original LMS files.

This script does not retrain or change the recommendation model. It prepares
supporting information for the dashboard: completion status, score summary,
and certificate count per employee.
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd


STATUS_PRIORITY = {
    "Unenroll": 1,
    "Enroll": 2,
    "On Going": 3,
    "Completed": 4,
}


def normalize_identifier(value: object) -> str:
    text = re.sub(r"\.0$", "", str(value).strip())
    return text.lstrip("0") or "0"


def normalize_course_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii").lower().strip()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def clean_identifier_series(series: pd.Series) -> pd.Series:
    return (
        series.astype("string")
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
    )


def build_progress_tables(
    *,
    users_path: Path,
    courses_path: Path,
    alias_path: Path,
    status_path: Path,
    scores_path: Path,
    certificates_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    users = pd.read_csv(users_path, dtype={"user_id": "string"})
    courses = pd.read_csv(
        courses_path,
        dtype={"canonical_course_id": "string"},
    )
    aliases = pd.read_csv(
        alias_path,
        dtype={
            "legacy_course_id": "string",
            "canonical_course_id": "string",
        },
    )
    status = pd.read_excel(status_path, dtype="string")
    scores = pd.read_excel(scores_path, dtype="string")
    certificates = pd.read_excel(certificates_path, dtype="string")

    users["user_id"] = clean_identifier_series(users["user_id"])
    courses["canonical_course_id"] = clean_identifier_series(
        courses["canonical_course_id"]
    )
    aliases["legacy_course_id"] = clean_identifier_series(
        aliases["legacy_course_id"]
    )
    aliases["canonical_course_id"] = clean_identifier_series(
        aliases["canonical_course_id"]
    )

    user_lookup = {
        normalize_identifier(user_id): str(user_id)
        for user_id in users["user_id"].dropna()
    }
    alias_lookup = dict(
        zip(
            aliases["legacy_course_id"].astype(str),
            aliases["canonical_course_id"].astype(str),
        )
    )
    course_lookup = (
        courses.drop_duplicates("canonical_course_id")
        .set_index("canonical_course_id")["course_name"]
        .astype(str)
        .to_dict()
    )

    status = status.rename(
        columns={
            "employee_id": "source_user_id",
            "coursesId": "source_course_id",
            "course": "source_course_name",
            "description": "learning_status",
        }
    )
    status["user_id"] = status["source_user_id"].map(
        lambda value: user_lookup.get(normalize_identifier(value))
    )
    status["source_course_id"] = clean_identifier_series(
        status["source_course_id"]
    )
    status["canonical_course_id"] = status["source_course_id"].map(
        lambda value: alias_lookup.get(str(value), str(value))
    )
    status["course_name"] = status["canonical_course_id"].map(course_lookup)
    status["course_name"] = status["course_name"].fillna(
        status["source_course_name"]
    )
    status["course_name_key"] = status["course_name"].map(
        normalize_course_name
    )
    status["_priority"] = (
        status["learning_status"].map(STATUS_PRIORITY).fillna(0)
    )
    status = status.dropna(subset=["user_id", "canonical_course_id"])
    status = (
        status.sort_values("_priority")
        .drop_duplicates(["user_id", "canonical_course_id"], keep="last")
        .reset_index(drop=True)
    )

    scores = scores.rename(
        columns={
            "idNumber": "source_user_id",
            "courseName": "source_course_name",
        }
    )
    scores["user_id"] = scores["source_user_id"].map(
        lambda value: user_lookup.get(normalize_identifier(value))
    )
    scores["course_name_key"] = scores["source_course_name"].map(
        normalize_course_name
    )
    scores["score"] = pd.to_numeric(scores["score"], errors="coerce")
    scores = scores.dropna(subset=["user_id", "score"])

    score_by_course = (
        scores.groupby(["user_id", "course_name_key"], as_index=False)
        .agg(score=("score", "mean"))
    )
    score_by_user = (
        scores.groupby("user_id", as_index=False)
        .agg(
            average_score=("score", "mean"),
            score_count=("score", "size"),
        )
    )

    certificates = certificates.rename(
        columns={
            "personnel_number": "source_user_id",
            "course_name": "source_course_name",
        }
    )
    certificates["user_id"] = certificates["source_user_id"].map(
        lambda value: user_lookup.get(normalize_identifier(value))
    )
    certificates["course_name_key"] = certificates["source_course_name"].map(
        normalize_course_name
    )
    certificates = certificates.dropna(
        subset=["user_id", "course_name_key"]
    )
    certificate_by_course = (
        certificates[
            ["user_id", "course_name_key"]
        ].drop_duplicates()
    )
    certificate_by_course["has_certificate"] = True
    certificate_by_user = (
        certificate_by_course.groupby("user_id", as_index=False)
        .agg(certificate_count=("course_name_key", "size"))
    )

    detail = status.merge(
        score_by_course,
        on=["user_id", "course_name_key"],
        how="left",
    ).merge(
        certificate_by_course,
        on=["user_id", "course_name_key"],
        how="left",
    )
    detail["has_certificate"] = detail["has_certificate"].eq(True)
    detail = detail[
        [
            "user_id",
            "canonical_course_id",
            "course_name",
            "learning_status",
            "score",
            "has_certificate",
        ]
    ].sort_values(
        ["user_id", "learning_status", "course_name"],
        kind="stable",
    )

    counts = (
        status.assign(value=1)
        .pivot_table(
            index="user_id",
            columns="learning_status",
            values="value",
            aggfunc="sum",
            fill_value=0,
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for source_name, target_name in {
        "Completed": "completed_count",
        "On Going": "ongoing_count",
        "Enroll": "enrolled_count",
        "Unenroll": "unenrolled_count",
    }.items():
        if source_name not in counts:
            counts[source_name] = 0
        counts = counts.rename(columns={source_name: target_name})

    count_columns = [
        "completed_count",
        "ongoing_count",
        "enrolled_count",
        "unenrolled_count",
    ]
    counts["tracked_course_count"] = counts[count_columns].sum(axis=1)
    active_denominator = (
        counts["completed_count"]
        + counts["ongoing_count"]
        + counts["enrolled_count"]
    )
    counts["completion_rate_percent"] = (
        counts["completed_count"]
        .div(active_denominator.where(active_denominator > 0))
        .mul(100)
    )
    counts["status_available"] = True

    summary = users[["user_id"]].drop_duplicates().merge(
        counts,
        on="user_id",
        how="left",
    ).merge(
        score_by_user,
        on="user_id",
        how="left",
    ).merge(
        certificate_by_user,
        on="user_id",
        how="left",
    )
    summary["status_available"] = summary["status_available"].eq(True)
    for column in count_columns + [
        "tracked_course_count",
        "score_count",
        "certificate_count",
    ]:
        summary[column] = (
            pd.to_numeric(summary[column], errors="coerce")
            .fillna(0)
            .astype(int)
        )
    summary["average_score"] = pd.to_numeric(
        summary["average_score"],
        errors="coerce",
    ).round(2)
    summary["completion_rate_percent"] = pd.to_numeric(
        summary["completion_rate_percent"],
        errors="coerce",
    ).round(2)

    summary = summary[
        [
            "user_id",
            "status_available",
            "tracked_course_count",
            "completed_count",
            "ongoing_count",
            "enrolled_count",
            "unenrolled_count",
            "completion_rate_percent",
            "average_score",
            "score_count",
            "certificate_count",
        ]
    ].sort_values("user_id")

    return summary.reset_index(drop=True), detail.reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare website-only employee learning progress tables."
    )
    parser.add_argument("--users", type=Path, required=True)
    parser.add_argument("--courses", type=Path, required=True)
    parser.add_argument("--aliases", type=Path, required=True)
    parser.add_argument("--status", type=Path, required=True)
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--certificates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary, detail = build_progress_tables(
        users_path=args.users,
        courses_path=args.courses,
        alias_path=args.aliases,
        status_path=args.status,
        scores_path=args.scores,
        certificates_path=args.certificates,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "learning_progress_summary.csv"
    detail_path = args.output_dir / "learning_progress_detail.csv"
    summary.to_csv(summary_path, index=False)
    detail.to_csv(detail_path, index=False)
    print(f"Wrote {len(summary):,} employee summaries to {summary_path}")
    print(f"Wrote {len(detail):,} progress rows to {detail_path}")


if __name__ == "__main__":
    main()
