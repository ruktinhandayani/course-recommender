"""Regression checks for the final H2 artifact serving policy."""

import numpy as np
import pandas as pd

from course_recommender.batch_export import clean_id_series
from course_recommender.service import CourseRecommenderService, normalize_user_id_value


class _PredictionModel:
    output_shape = (None, 4)

    def predict(self, _inputs, verbose=0):
        # Course 2 is deliberately highest but must be removed as seen.
        return np.array([[0.0, 0.2, 0.99, 0.8]], dtype=float)

    def __call__(self, _inputs, training=False):
        return type("TensorLike", (), {"numpy": lambda _self: self.predict(_inputs)})()

    def get_layer(self, name):
        assert name == "course_prediction"
        return type("Head", (), {"get_weights": lambda _self: [np.ones((192, 4)), np.zeros(4)]})()


class _SimilarityModel:
    def predict(self, _inputs, verbose=0):
        return np.ones((1, 192), dtype=float)

    def __call__(self, _inputs, training=False):
        return type("TensorLike", (), {"numpy": lambda _self: self.predict(_inputs)})()


def test_full_history_masking_excludes_course_outside_sequence_window():
    service = CourseRecommenderService.__new__(CourseRecommenderService)
    service.catalog_check = {"critical": False, "status": "OK", "message": "", "issues": []}
    service.min_history_for_model_inference = 1
    service.num_courses = 4
    service.model = _PredictionModel()
    service.similarity_model = _SimilarityModel()
    service.course_catalog = pd.DataFrame([
        {"course_encoded": 1, "canonical_course_id": "old-course", "course_name": "Old", "kompetensi": "A", "level": "L1", "course_has_certificate_train": 0, "certificate_count_train": 0},
        {"course_encoded": 2, "canonical_course_id": "recent-course", "course_name": "Recent", "kompetensi": "A", "level": "L1", "course_has_certificate_train": 0, "certificate_count_train": 0},
        {"course_encoded": 3, "canonical_course_id": "new-course", "course_name": "New", "kompetensi": "B", "level": "L2", "course_has_certificate_train": 1, "certificate_count_train": 1},
    ])
    service.course_popularity = pd.DataFrame(columns=["course_encoded", "train_popularity_count"])
    service._prepare_user_input = lambda **_kwargs: ([np.zeros((1, 10))], {1, 2}, {"status": "ready_for_model", "known_history_count": 11, "unknown_history_count": 0, "total_history_count": 11})

    response = service.recommend("000123451", pd.DataFrame(), top_n=3)

    assert response["user_id"] == "000123451"
    assert [row["course_id"] for row in response["recommendations"]] == ["new-course"]
    assert response["recommendations"][0]["softmax_score"] == 0.8


def test_user_ids_remain_opaque_strings_with_leading_zeroes():
    assert normalize_user_id_value(" 000123451 ") == "000123451"
    assert clean_id_series(pd.Series(["000123451", "123451"])).tolist() == ["000123451", "123451"]
