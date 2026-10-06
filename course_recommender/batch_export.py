"""Batch recommendation generation for CRE Pre-MVP export sync."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from .config import MlServiceSettings
from .export_store import EXPORT_COLUMNS, OPTIONAL_EXPORT_COLUMNS
from .service import load_recommender, normalize_user_id_value


def clean_id_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip()


def load_user_history(data_dir: str | Path) -> tuple[pd.DataFrame, list[str]]:
    data_dir = Path(data_dir)
    # Read identifiers as text at the source so leading zeroes are preserved.
    interactions = pd.read_csv(data_dir / "interactions.csv", dtype={"user_id": str, "course_id": str})
    users = pd.read_csv(data_dir / "users.csv", dtype={"user_id": str})
    alias_map = pd.read_csv(data_dir / "course_alias_map.csv", dtype={"legacy_course_id": str, "canonical_course_id": str})

    interactions.columns = interactions.columns.astype(str).str.strip().str.lower()
    users.columns = users.columns.astype(str).str.strip().str.lower()
    alias_map.columns = alias_map.columns.astype(str).str.strip().str.lower()

    required_interactions = {"user_id", "course_id"}
    required_users = {"user_id"}
    required_alias = {"legacy_course_id", "canonical_course_id"}

    for name, df, required in [
        ("interactions.csv", interactions, required_interactions),
        ("users.csv", users, required_users),
        ("course_alias_map.csv", alias_map, required_alias),
    ]:
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"{name} missing required columns: {sorted(missing)}")

    interactions["user_id"] = clean_id_series(interactions["user_id"])
    interactions["course_id"] = clean_id_series(interactions["course_id"])
    users["user_id"] = clean_id_series(users["user_id"])
    alias_map["legacy_course_id"] = clean_id_series(alias_map["legacy_course_id"])
    alias_map["canonical_course_id"] = clean_id_series(alias_map["canonical_course_id"])

    history = interactions.merge(
        alias_map.rename(columns={"canonical_course_id": "mapped_canonical_course_id"}),
        left_on="course_id",
        right_on="legacy_course_id",
        how="left",
    )
    history["canonical_course_id"] = history["mapped_canonical_course_id"].fillna(history["course_id"])
    history["canonical_course_id"] = clean_id_series(history["canonical_course_id"])
    history["sort_row_order"] = range(len(history))

    if "event_timestamp" in history.columns:
        history["sort_timestamp"] = pd.to_datetime(history["event_timestamp"], errors="coerce")

    output_columns = ["user_id", "canonical_course_id", "sort_row_order"]
    if "sort_timestamp" in history.columns:
        output_columns.append("sort_timestamp")

    history = history[output_columns].dropna(subset=["user_id", "canonical_course_id"])
    user_ids = sorted(users["user_id"].dropna().map(normalize_user_id_value).unique().tolist())
    return history, user_ids


def recommendation_score(row: dict, max_popularity: float) -> float:
    """Export score follows the primary Softmax ordering."""
    softmax = row.get("softmax_score")
    if softmax is not None and pd.notna(softmax):
        return round(float(softmax), 6)
    similarity = row.get("similarity_score_0_1")
    if similarity is not None and pd.notna(similarity):
        return round(float(similarity), 6)

    popularity = row.get("train_popularity_count")
    if popularity is not None and pd.notna(popularity) and max_popularity > 0:
        return round(float(popularity) / max_popularity, 6)

    return 0.0


def generate_recommendation_export(
    *,
    artifact_dir: str | Path,
    data_dir: str | Path,
    output_path: str | Path,
    fixture_path: str | Path,
    model_version: str,
    top_k: int,
    generated_at: str | None = None,
    max_users: int | None = None,
    progress_callback=None,
) -> dict:
    generated_at = generated_at or datetime.now(timezone.utc).astimezone().isoformat()
    output_path = Path(output_path)
    fixture_path = Path(fixture_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    recommender = load_recommender(artifact_dir)
    history, user_ids = load_user_history(data_dir)
    if max_users is not None:
        user_ids = user_ids[:max_users]

    history_by_user = {
        str(user_id): user_history.copy()
        for user_id, user_history in history.groupby("user_id", sort=False)
    }
    empty_history = history.head(0).copy()
    max_popularity = float(recommender.course_popularity["train_popularity_count"].max())
    rows = []

    for idx, user_id in enumerate(user_ids, start=1):
        user_history = history_by_user.get(str(user_id), empty_history)
        response = recommender.recommend(user_id, user_history, top_n=top_k)
        for rec in response["recommendations"]:
            rows.append(
                {
                    "user_id": str(user_id),
                    "canonical_course_id": str(rec["course_id"]),
                    "rank": int(rec["rank"]),
                    "score": recommendation_score(rec, max_popularity),
                    "reason_code": response["metadata"].get("fallback_reason") or "model_inference",
                    "course_title": rec.get("recommended_course"),
                    "competency": rec.get("competency"),
                    "level": rec.get("level"),
                    "certificate_status": rec.get("certificate_status"),
                    "similarity_score": rec.get("similarity_score_0_1"),
                    "similarity_score_percent": rec.get("similarity_score_percent"),
                    "softmax_score": rec.get("softmax_score"),
                    "softmax_score_percent": rec.get("softmax_score_percent"),
                    "fallback_reason": response["metadata"].get("fallback_reason"),
                    "model_version": model_version,
                    "generated_at": generated_at,
                }
            )
        if idx % 250 == 0:
            message = f"Generated recommendations for {idx}/{len(user_ids)} users"
            if progress_callback is not None:
                progress_callback(message)
            else:
                print(message)

    output_columns = EXPORT_COLUMNS + OPTIONAL_EXPORT_COLUMNS
    export_df = pd.DataFrame(rows, columns=output_columns)
    export_df = export_df.sort_values(["user_id", "rank", "canonical_course_id"]).reset_index(drop=True)
    export_df.to_csv(output_path, index=False)

    fixture_df = build_fixture_export(export_df, model_version, generated_at)
    fixture_df.to_csv(fixture_path, index=False)

    # Re-evaluate only after both CSV files have been committed.  The initial
    # artifact check happens while loading the model, before an export exists.
    # Recording that stale result would incorrectly mark a successful export as
    # missing in recommendation_export_manifest.json.
    catalog_check = recommender.validate_catalog_consistency()
    catalog_check.setdefault("checks", {})["recommendation_export_found"] = (
        output_path.exists() and fixture_path.exists()
    )

    manifest = {
        "export_mode": "demonstration_subset" if max_users is not None else "full_batch",
        "max_users": max_users,
        "model_version": model_version,
        "generated_at": generated_at,
        "user_count": int(len(user_ids)),
        "recommendation_count": int(len(export_df)),
        "top_k": int(top_k),
        "output_path": str(output_path),
        "fixture_path": str(fixture_path),
        "catalog_check": catalog_check,
        "primary_ranking": "Softmax Ranking",
        "masking_protocol": "full_pre_target_history",
    }
    manifest_path = output_path.parent / "recommendation_export_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(manifest, file, indent=2, ensure_ascii=False)

    return manifest


def build_fixture_export(export_df: pd.DataFrame, model_version: str, generated_at: str) -> pd.DataFrame:
    if export_df.empty:
        return pd.DataFrame(columns=EXPORT_COLUMNS)

    fixture = export_df.head(12).copy()
    first_user = str(fixture["user_id"].iloc[0])
    first_course = str(fixture["canonical_course_id"].iloc[0])

    fixture_rows = [
        {
            "user_id": first_user,
            "canonical_course_id": "UNMAPPED_PRE_MVP_COURSE",
            "rank": 98,
            "score": 0.01,
            "reason_code": None,
            "model_version": model_version,
            "generated_at": generated_at,
        },
        {
            "user_id": first_user,
            "canonical_course_id": first_course,
            "rank": 99,
            "score": 0.01,
            "reason_code": None,
            "model_version": model_version,
            "generated_at": generated_at,
        },
    ]
    return pd.concat([fixture, pd.DataFrame(fixture_rows)], ignore_index=True)[export_df_columns(export_df)]


def export_df_columns(export_df: pd.DataFrame) -> list[str]:
    return [column for column in EXPORT_COLUMNS + OPTIONAL_EXPORT_COLUMNS if column in export_df.columns]


def parse_args() -> argparse.Namespace:
    settings = MlServiceSettings()
    parser = argparse.ArgumentParser(description="Generate CRE recommendation export CSV.")
    parser.add_argument("--artifact-dir", default=str(settings.artifact_dir))
    parser.add_argument("--data-dir", default=str(settings.data_dir))
    parser.add_argument("--output", default=str(settings.export_path))
    parser.add_argument("--fixture-output", default=str(settings.fixture_path))
    parser.add_argument("--model-version", default=settings.model_version)
    parser.add_argument("--top-k", type=int, default=settings.default_top_k)
    parser.add_argument("--max-users", type=int, default=None)
    parser.add_argument("--generated-at", default=settings.generated_at)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = generate_recommendation_export(
        artifact_dir=args.artifact_dir,
        data_dir=args.data_dir,
        output_path=args.output,
        fixture_path=args.fixture_output,
        model_version=args.model_version,
        top_k=args.top_k,
        generated_at=args.generated_at,
        max_users=args.max_users,
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
