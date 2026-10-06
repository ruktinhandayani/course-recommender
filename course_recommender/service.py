"""Production inference boundary for the course recommender model.

This module intentionally contains no notebook display code and no backend
framework code. A backend service should load one CourseRecommenderService at
process startup, fetch a user's course history from storage, then call
recommend().
"""

from __future__ import annotations

import json
import math
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


RECOMMENDATION_COLUMNS = [
    "rank",
    "course_id",
    "recommended_course",
    "competency",
    "level",
    "certificate_status",
    "certificate_count_train",
    "similarity_score_0_1",
    "similarity_score_percent",
    "softmax_score",
    "softmax_score_percent",
    "train_popularity_count",
]


@dataclass(frozen=True)
class RecommenderArtifactPaths:
    artifact_dir: Path
    model_path: Path
    encoder_mappings_path: Path
    scaler_path: Path
    experiment_config_path: Path
    evaluation_path: Path
    manifest_path: Path
    course_catalog_path: Path
    course_popularity_path: Path

    @classmethod
    def from_dir(cls, artifact_dir: str | Path) -> "RecommenderArtifactPaths":
        base = Path(artifact_dir)
        return cls(
            artifact_dir=base,
            model_path=base / "model" / "cre-lstm-attention-h2-seed42-fullmask-v1.keras",
            encoder_mappings_path=base / "config" / "encoder_mappings.pkl",
            scaler_path=base / "config" / "certificate_count_scaler.pkl",
            experiment_config_path=base / "config" / "experiment_config.json",
            evaluation_path=base / "config" / "evaluation_final.json",
            manifest_path=base / "artifact_manifest.csv",
            course_catalog_path=base / "tables" / "course_catalog.csv",
            course_popularity_path=base / "tables" / "course_popularity_train_df.csv",
        )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_pickle(path: Path) -> Any:
    with path.open("rb") as file:
        return pickle.load(file)


def normalize_user_id_value(value: Any) -> str:
    """Treat identifiers as opaque strings; never coerce or repair IDs."""
    return str(value).strip()


def _finite_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


class CourseRecommenderService:
    """Framework-agnostic inference service for backend integration."""

    def __init__(self, artifact_dir: str | Path = "course_recommender_artifacts_final"):
        self.paths = RecommenderArtifactPaths.from_dir(artifact_dir)
        self._validate_required_files()

        self.experiment_config = load_json(self.paths.experiment_config_path)
        self.evaluation_final = load_json(self.paths.evaluation_path)
        self.encoder_mappings = load_pickle(self.paths.encoder_mappings_path)
        self.scaler = load_pickle(self.paths.scaler_path)

        self.unknown_token = self.encoder_mappings.get("unknown_token", "__UNKNOWN__")
        self.course_to_idx = {
            str(key): int(value)
            for key, value in self.encoder_mappings["course_to_idx"].items()
        }
        self.competency_to_idx = {
            str(key): int(value)
            for key, value in self.encoder_mappings["competency_to_idx"].items()
        }
        self.level_to_idx = {
            str(key): int(value)
            for key, value in self.encoder_mappings["level_to_idx"].items()
        }

        self.max_sequence_length = int(self.experiment_config["max_sequence_length"])
        self.min_history_for_model_inference = 2
        self.num_courses = len(self.course_to_idx) + 1

        self.course_catalog = self._load_course_catalog(self.paths.course_catalog_path)
        self.course_popularity = self._load_course_popularity(self.paths.course_popularity_path)
        self.model = self._load_model()
        self.similarity_model = self._build_similarity_model()
        self.attention_model = self._build_attention_model()
        self.catalog_check = self.validate_catalog_consistency()

    def _validate_required_files(self) -> None:
        missing = [
            str(path)
            for path in [
                self.paths.model_path,
                self.paths.encoder_mappings_path,
                self.paths.scaler_path,
                self.paths.experiment_config_path,
                self.paths.evaluation_path,
                self.paths.manifest_path,
                self.paths.course_catalog_path,
                self.paths.course_popularity_path,
            ]
            if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(
                "Missing recommender artifact files: " + ", ".join(missing)
            )

    def _load_model(self):
        from tensorflow.keras.models import load_model

        from .attention import TemporalAttention

        # The final Keras archive registers this layer as CRE>TemporalAttention.
        # Keep the plain-name alias for older notebook exports as well.
        custom_objects = {
            "TemporalAttention": TemporalAttention,
            "CRE>TemporalAttention": TemporalAttention,
        }
        model = load_model(
            self.paths.model_path,
            custom_objects=custom_objects,
            compile=False,
        )
        return model

    def _build_similarity_model(self):
        """Expose the final model state used by its classifier for a secondary cosine score."""
        from tensorflow.keras import Model
        return Model(self.model.inputs, self.model.get_layer("attention_enhanced_state").output)

    def _build_attention_model(self):
        """Expose the temporal attention weights for an employee history."""
        from tensorflow.keras import Model

        attention_output = self.model.get_layer("temporal_attention").output
        return Model(self.model.inputs, attention_output[1])

    def _load_course_catalog(self, path: Path) -> pd.DataFrame:
        catalog = pd.read_csv(path)
        required_columns = {
            "course_encoded",
            "canonical_course_id",
            "course_name",
            "kompetensi",
            "level",
            "course_has_certificate_train",
            "certificate_count_train",
        }
        missing = required_columns - set(catalog.columns)
        if missing:
            raise ValueError(f"course_catalog.csv is missing columns: {sorted(missing)}")

        catalog = catalog.copy()
        catalog["course_encoded"] = pd.to_numeric(
            catalog["course_encoded"], errors="coerce"
        ).astype("Int64")
        catalog = catalog.dropna(subset=["course_encoded"]).copy()
        catalog["course_encoded"] = catalog["course_encoded"].astype(int)
        return catalog.drop_duplicates("course_encoded").reset_index(drop=True)

    def _load_course_popularity(self, path: Path) -> pd.DataFrame:
        popularity = pd.read_csv(path)
        # The final notebook exports the count as train_interaction_count.
        # Normalize it at the loader boundary for the serving contract.
        if "train_interaction_count" in popularity.columns and "train_popularity_count" not in popularity.columns:
            popularity = popularity.rename(columns={"train_interaction_count": "train_popularity_count"})
        required_columns = {"course_encoded", "train_popularity_count"}
        missing = required_columns - set(popularity.columns)
        if missing:
            raise ValueError(
                f"course_popularity_train.csv is missing columns: {sorted(missing)}"
            )
        popularity = popularity.copy()
        popularity["course_encoded"] = pd.to_numeric(
            popularity["course_encoded"], errors="coerce"
        ).astype("Int64")
        popularity["train_popularity_count"] = pd.to_numeric(
            popularity["train_popularity_count"], errors="coerce"
        ).fillna(0).astype(int)
        popularity = popularity.dropna(subset=["course_encoded"]).copy()
        popularity["course_encoded"] = popularity["course_encoded"].astype(int)
        return popularity.sort_values(
            ["train_popularity_count", "course_encoded"], ascending=[False, True]
        ).reset_index(drop=True)

    def validate_catalog_consistency(self) -> dict[str, Any]:
        issues: list[str] = []
        critical_issues: list[str] = []
        checks = {
            "model_file_found": self.paths.model_path.exists(),
            "manifest_found": self.paths.manifest_path.exists(),
            "course_mapping_found": self.paths.encoder_mappings_path.exists(),
            "competency_mapping_found": self.paths.encoder_mappings_path.exists(),
            "level_mapping_found": self.paths.encoder_mappings_path.exists(),
            "scaler_found": self.paths.scaler_path.exists(),
            "course_catalog_found": self.paths.course_catalog_path.exists(),
            "evaluation_metrics_found": self.paths.evaluation_path.exists(),
            "recommendation_export_found": (self.paths.artifact_dir / "export" / "recommendations.csv").exists(),
        }

        try:
            model_output_dim = int(self.model.output_shape[-1])
            if model_output_dim != self.num_courses:
                critical_issues.append(
                    f"Model output dimension {model_output_dim} != num_courses {self.num_courses}."
                )
        except Exception as exc:
            critical_issues.append(f"Cannot inspect model output dimension: {exc}")

        expected_version = "cre-lstm-attention-h2-seed42-fullmask-v1"
        config_version = str(self.experiment_config.get("model_version", ""))
        evaluation_version = str(self.evaluation_final.get("model_version", ""))
        if config_version != expected_version or evaluation_version != expected_version:
            critical_issues.append("ARTIFACT VERSION MISMATCH: model configuration and evaluation must match the final model version.")
        checks["model_version_match"] = config_version == expected_version and evaluation_version == expected_version
        if self.evaluation_final.get("masking_protocol") != "full_pre_target_history":
            critical_issues.append("ARTIFACT VERSION MISMATCH: evaluation masking protocol is not full_pre_target_history.")

        catalog_encoded = set(self.course_catalog["course_encoded"].astype(int).tolist())
        expected_encoded = set(range(1, self.num_courses))
        invalid = sorted(course_id for course_id in catalog_encoded if course_id <= 0 or course_id >= self.num_courses)
        missing = sorted(expected_encoded - catalog_encoded)

        if invalid:
            critical_issues.append(
                f"{len(invalid)} course_catalog IDs are outside encoder range."
            )
        if missing:
            issues.append(f"{len(missing)} encoder course IDs are missing from catalog.")

        all_issues = critical_issues + issues
        if critical_issues:
            status = "CRITICAL"
            message = "ARTIFACT VERSION MISMATCH"
        elif issues:
            status = "WARNING"
            message = "Non-critical artifact mismatch detected."
        else:
            status = "OK"
            message = "Artifacts are consistent."

        return {
            "status": status,
            "message": message,
            "issues": all_issues,
            "critical": bool(critical_issues),
            "model_version": config_version,
            "primary_ranking": "Softmax Ranking",
            "masking_protocol": self.evaluation_final.get("masking_protocol"),
            "checks": checks,
        }

    def recommend(
        self,
        user_id: Any,
        user_history_df: pd.DataFrame | None,
        top_n: int = 10,
    ) -> dict[str, Any]:
        """Return JSON-serializable recommendations and audit metadata."""
        user_id_normalized = normalize_user_id_value(user_id)
        top_n = max(1, int(top_n))

        model_input, taken_courses, audit = self._prepare_user_input(
            user_id=user_id_normalized,
            user_history_df=user_history_df,
        )

        catalog_check = self.catalog_check
        if catalog_check.get("critical", False):
            rows = self._build_popularity_fallback(top_n, taken_courses)
            return self._response(
                user_id_normalized,
                rows,
                audit,
                catalog_check,
                "catalog_model_mismatch",
            )

        if audit["status"] in {"not_found", "invalid_source_df"}:
            rows = self._build_popularity_fallback(top_n, set())
            return self._response(
                user_id_normalized,
                rows,
                audit,
                catalog_check,
                "user_history_not_found",
            )

        if audit["status"] == "all_history_unknown_to_encoder":
            rows = self._build_popularity_fallback(top_n, set())
            return self._response(
                user_id_normalized,
                rows,
                audit,
                catalog_check,
                "all_history_unknown_to_encoder",
            )

        if audit["known_history_count"] < self.min_history_for_model_inference:
            rows = self._build_popularity_fallback(top_n, taken_courses)
            return self._response(
                user_id_normalized,
                rows,
                audit,
                catalog_check,
                "history_too_short",
            )

        try:
            # Calling the Keras model directly avoids the substantial per-user
            # predict() adapter overhead during full batch export. It uses the
            # same trained graph and produces the same Softmax output.
            softmax_score = self.model(model_input, training=False).numpy()[0].copy()
            # The final archive contains one deployable Keras model.  The
            # secondary score is cosine similarity between its attention state
            # and the columns of its trained softmax classifier head.
            user_vector = self.similarity_model(model_input, training=False).numpy()[0]
            classifier_vectors = self.model.get_layer("course_prediction").get_weights()[0].T
            similarity_score = self._calculate_similarity(user_vector[None, :], classifier_vectors)[0].copy()
        except Exception as exc:
            rows = self._build_popularity_fallback(top_n, taken_courses)
            audit["inference_error"] = str(exc)
            return self._response(
                user_id_normalized,
                rows,
                audit,
                catalog_check,
                "model_inference_failed",
            )

        for taken in taken_courses:
            if 0 <= taken < len(similarity_score):
                similarity_score[taken] = -np.inf
            if 0 <= taken < len(softmax_score):
                softmax_score[taken] = -np.inf

        similarity_score[0] = -np.inf
        softmax_score[0] = -np.inf

        catalog_by_encoded = self.course_catalog.set_index("course_encoded")
        rows = []
        # Softmax is the research-approved primary ordering. Similarity is
        # retained strictly as a secondary, displayed score.
        for course_encoded in np.argsort(softmax_score)[::-1]:
            course_encoded = int(course_encoded)
            if course_encoded == 0 or not np.isfinite(softmax_score[course_encoded]):
                continue
            if course_encoded not in catalog_by_encoded.index:
                continue

            catalog_row = catalog_by_encoded.loc[course_encoded]
            rows.append(
                self._format_recommendation_row(
                    rank=len(rows) + 1,
                    catalog_row=catalog_row,
                    similarity_score=float(similarity_score[course_encoded]),
                    softmax_score=float(softmax_score[course_encoded]),
                    train_popularity_count=None,
                )
            )
            if len(rows) >= top_n:
                break

        if not rows:
            rows = self._build_popularity_fallback(top_n, taken_courses)
            return self._response(
                user_id_normalized,
                rows,
                audit,
                catalog_check,
                "empty_model_recommendation",
            )

        reason = "model_recommendation"
        if audit["unknown_history_count"] > 0:
            reason = "model_recommendation_unknown_history_ignored"

        return self._response(user_id_normalized, rows, audit, catalog_check, reason)

    def recommend_dataframe(
        self,
        user_id: Any,
        user_history_df: pd.DataFrame | None,
        top_n: int = 10,
    ) -> pd.DataFrame:
        """Convenience wrapper for notebooks and batch jobs."""
        response = self.recommend(user_id, user_history_df, top_n)
        rows = response["recommendations"]
        frame = pd.DataFrame(rows)
        for key, value in response["metadata"].items():
            frame[key] = value
        return frame

    def attention_for_user(
        self,
        user_id: Any,
        user_history_df: pd.DataFrame | None,
    ) -> list[dict[str, Any]]:
        """Return the history positions and attention weights read by the model."""
        normalized_user_id = normalize_user_id_value(user_id)
        model_input, _, audit = self._prepare_user_input(
            normalized_user_id,
            user_history_df,
        )
        if model_input is None or audit.get("known_history_count", 0) == 0:
            return []

        attention_values = self.attention_model(
            model_input,
            training=False,
        ).numpy()[0]
        encoded_sequence = model_input[0][0]
        catalog_lookup = self.course_catalog.set_index("course_encoded")
        rows = []
        for input_position, (course_encoded, weight) in enumerate(
            zip(encoded_sequence, attention_values),
            start=1,
        ):
            course_encoded = int(course_encoded)
            if course_encoded == 0 or course_encoded not in catalog_lookup.index:
                continue
            catalog_row = catalog_lookup.loc[course_encoded]
            rows.append(
                {
                    "input_position": input_position,
                    "course_id": str(catalog_row["canonical_course_id"]),
                    "course_name": str(catalog_row["course_name"]),
                    "attention_weight": round(float(weight), 4),
                }
            )
        return sorted(
            rows,
            key=lambda item: item["attention_weight"],
            reverse=True,
        )

    def _prepare_user_input(
        self,
        user_id: str,
        user_history_df: pd.DataFrame | None,
    ) -> tuple[list[np.ndarray] | None, set[int], dict[str, Any]]:
        audit = {
            "total_history_count": 0,
            "known_history_count": 0,
            "unknown_history_count": 0,
            "status": "not_found",
        }

        if user_history_df is None or not isinstance(user_history_df, pd.DataFrame):
            audit["status"] = "invalid_source_df"
            return None, set(), audit
        if user_history_df.empty:
            return None, set(), audit

        history = user_history_df.copy()
        if "user_id" in history.columns:
            user_mask = history["user_id"].map(normalize_user_id_value) == user_id
            history = history[user_mask].copy()

        if history.empty:
            return None, set(), audit

        history = self._sort_history_for_inference(history)
        audit["total_history_count"] = int(len(history))
        audit["status"] = "found"

        if "course_encoded" not in history.columns:
            if "canonical_course_id" not in history.columns:
                audit["status"] = "missing_course_identifier"
                return None, set(), audit
            history["canonical_course_id"] = history["canonical_course_id"].astype(str)
            history["course_encoded"] = history["canonical_course_id"].map(self.course_to_idx)
        else:
            history["course_encoded"] = pd.to_numeric(history["course_encoded"], errors="coerce")

        history = self._attach_catalog_features(history)
        history = self._encode_side_features(history)
        history["certificate_count_scaled"] = self._scale_certificate_count(
            history["certificate_count_train"]
        )

        known_mask = (
            history["course_encoded"].notna()
            & history["competency_encoded"].notna()
            & history["level_encoded"].notna()
            & history["course_encoded"].astype(float).between(1, self.num_courses - 1)
        )
        known = history[known_mask].copy()
        audit["known_history_count"] = int(len(known))
        audit["unknown_history_count"] = int(len(history) - len(known))

        if known.empty:
            audit["status"] = "all_history_unknown_to_encoder"
            return None, set(), audit

        known["course_encoded"] = known["course_encoded"].astype(int)
        known["competency_encoded"] = known["competency_encoded"].astype(int)
        known["level_encoded"] = known["level_encoded"].astype(int)

        # The sequence is capped at ten, while taken_courses deliberately
        # remains the whole pre-prediction history for candidate masking.
        full_seen_courses = set(known["course_encoded"].astype(int).tolist())
        recent_known = known.tail(self.max_sequence_length)
        course_seq = recent_known["course_encoded"].tolist()
        competency_seq = recent_known["competency_encoded"].tolist()
        level_seq = recent_known["level_encoded"].tolist()
        course_cert_seq = recent_known["course_has_certificate_train"].astype(float).tolist()
        cert_count_seq = recent_known["certificate_count_scaled"].astype(float).tolist()

        model_input = [
            self._pad_sequence(course_seq, dtype=np.int64),
            self._pad_sequence(competency_seq, dtype=np.int64),
            self._pad_sequence(level_seq, dtype=np.int64),
            np.expand_dims(self._pad_sequence(course_cert_seq, dtype=np.float32), axis=-1),
            np.expand_dims(self._pad_sequence(cert_count_seq, dtype=np.float32), axis=-1),
        ]

        audit["status"] = "ready_for_model"
        return model_input, full_seen_courses, audit

    def _attach_catalog_features(self, history: pd.DataFrame) -> pd.DataFrame:
        history = history.copy()
        history["course_encoded"] = pd.to_numeric(
            history["course_encoded"], errors="coerce"
        ).astype("Int64")

        lookup_columns = [
            "course_encoded",
            "kompetensi",
            "level",
            "certificate_count_train",
            "course_has_certificate_train",
        ]
        lookup = self.course_catalog[lookup_columns].drop_duplicates("course_encoded")
        overlap_columns = [
            column
            for column in lookup_columns
            if column != "course_encoded" and column in history.columns
        ]
        merged = history.drop(columns=overlap_columns, errors="ignore").merge(
            lookup,
            on="course_encoded",
            how="left",
        )
        merged["certificate_count_train"] = pd.to_numeric(
            merged.get("certificate_count_train", 0), errors="coerce"
        ).fillna(0)
        merged["course_has_certificate_train"] = pd.to_numeric(
            merged.get("course_has_certificate_train", 0), errors="coerce"
        ).fillna(0).astype(int)
        return merged

    def _encode_side_features(self, history: pd.DataFrame) -> pd.DataFrame:
        history = history.copy()
        if "kompetensi" not in history.columns:
            history["kompetensi"] = self.unknown_token
        if "level" not in history.columns:
            history["level"] = self.unknown_token

        history["kompetensi"] = history["kompetensi"].fillna(self.unknown_token).astype(str)
        history["level"] = history["level"].fillna(self.unknown_token).astype(str)

        history["competency_clean"] = history["kompetensi"].where(
            history["kompetensi"].isin(set(self.competency_to_idx)),
            self.unknown_token,
        )
        history["level_clean"] = history["level"].where(
            history["level"].isin(set(self.level_to_idx)),
            self.unknown_token,
        )
        history["competency_encoded"] = history["competency_clean"].map(
            self.competency_to_idx
        )
        history["level_encoded"] = history["level_clean"].map(self.level_to_idx)
        return history

    def _scale_certificate_count(self, series: pd.Series) -> pd.Series:
        values = pd.to_numeric(series, errors="coerce").fillna(0).astype(float)
        # The scaler was fitted by the notebook with this feature name.
        # Keeping the name here avoids a misleading scikit-learn warning and
        # documents which numeric input is being transformed.
        scaler_input = pd.DataFrame(
            {"certificate_count_train": values.to_numpy()},
            index=values.index,
        )
        transformed = self.scaler.transform(scaler_input).reshape(-1)
        return pd.Series(transformed, index=values.index)

    def _build_popularity_fallback(
        self,
        top_n: int,
        exclude_encoded: set[int] | None = None,
    ) -> list[dict[str, Any]]:
        exclude = {0}
        if exclude_encoded:
            exclude.update(int(value) for value in exclude_encoded if pd.notna(value))

        catalog_by_encoded = self.course_catalog.set_index("course_encoded")
        rows = []
        for _, popularity_row in self.course_popularity.iterrows():
            course_encoded = int(popularity_row["course_encoded"])
            if course_encoded in exclude or course_encoded not in catalog_by_encoded.index:
                continue
            rows.append(
                self._format_recommendation_row(
                    rank=len(rows) + 1,
                    catalog_row=catalog_by_encoded.loc[course_encoded],
                    similarity_score=None,
                    softmax_score=None,
                    train_popularity_count=int(popularity_row["train_popularity_count"]),
                )
            )
            if len(rows) >= top_n:
                break
        return rows

    def _format_recommendation_row(
        self,
        rank: int,
        catalog_row: pd.Series,
        similarity_score: float | None,
        softmax_score: float | None,
        train_popularity_count: int | None,
    ) -> dict[str, Any]:
        has_certificate = int(catalog_row["course_has_certificate_train"])
        similarity = _finite_float(similarity_score)
        softmax = _finite_float(softmax_score)

        return {
            "rank": int(rank),
            "course_id": str(catalog_row["canonical_course_id"]),
            "recommended_course": str(catalog_row["course_name"]),
            "competency": str(catalog_row["kompetensi"]),
            "level": str(catalog_row["level"]),
            "certificate_status": "certified" if has_certificate == 1 else "not_certified",
            "certificate_count_train": int(catalog_row["certificate_count_train"]),
            "similarity_score_0_1": round(similarity, 4) if similarity is not None else None,
            "similarity_score_percent": round(similarity * 100, 2) if similarity is not None else None,
            "softmax_score": round(softmax, 6) if softmax is not None else None,
            "softmax_score_percent": round(softmax * 100, 4) if softmax is not None else None,
            "train_popularity_count": train_popularity_count,
        }

    def _response(
        self,
        user_id: str,
        recommendations: list[dict[str, Any]],
        audit: dict[str, Any],
        catalog_check: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "recommendations": recommendations,
            "metadata": {
                "fallback_reason": reason,
                "known_history_count": int(audit.get("known_history_count", 0)),
                "unknown_history_count": int(audit.get("unknown_history_count", 0)),
                "total_history_count": int(audit.get("total_history_count", 0)),
                "history_status": audit.get("status", "unknown"),
                "catalog_check_status": catalog_check.get("status", "UNKNOWN"),
                "catalog_check_message": catalog_check.get("message", ""),
                "catalog_check_issues": catalog_check.get("issues", []),
                "inference_error": audit.get("inference_error"),
            },
        }

    def _pad_sequence(self, values: list[Any], dtype: Any) -> np.ndarray:
        output = np.zeros((1, self.max_sequence_length), dtype=dtype)
        if not values:
            return output
        tail = np.asarray(values[-self.max_sequence_length :], dtype=dtype)
        output[0, -len(tail) :] = tail
        return output

    def _sort_history_for_inference(self, history: pd.DataFrame) -> pd.DataFrame:
        sort_columns = [
            column
            for column in ["sort_timestamp", "sort_interaction_id", "sort_row_order"]
            if column in history.columns
        ]
        if sort_columns:
            return history.sort_values(sort_columns).reset_index(drop=True)
        if "first_event_timestamp" in history.columns:
            return history.sort_values("first_event_timestamp").reset_index(drop=True)
        return history.reset_index(drop=True)

    @staticmethod
    def _normalize_vector(matrix: np.ndarray) -> np.ndarray:
        norm = np.linalg.norm(matrix, axis=1, keepdims=True)
        norm = np.where(norm == 0, 1e-8, norm)
        return matrix / norm

    @classmethod
    def _calculate_similarity(
        cls,
        user_vectors: np.ndarray,
        course_vectors: np.ndarray,
    ) -> np.ndarray:
        user_norm = cls._normalize_vector(user_vectors)
        course_norm = cls._normalize_vector(course_vectors)
        cosine = np.dot(user_norm, course_norm.T)
        similarity = (cosine + 1) / 2
        similarity[:, 0] = -np.inf
        return similarity


def load_recommender(
    artifact_dir: str | Path = "course_recommender_artifacts_final",
) -> CourseRecommenderService:
    return CourseRecommenderService(artifact_dir=artifact_dir)
