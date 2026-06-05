class RecommenderError(Exception):
    """Base exception for the recommendation module."""


class MissingUpstageApiKeyError(RecommenderError):
    """Raised when UPSTAGE_API_KEY is not configured."""


class MissingEmbeddingCacheError(RecommenderError):
    """Raised when a recommendation run has no usable embedding cache."""


class RecommendationInputError(RecommenderError):
    """Raised when a recommendation request is missing required input."""
