"""Backend-ready course recommender inference package."""

from .service import CourseRecommenderService, load_recommender

__all__ = ["CourseRecommenderService", "load_recommender"]
