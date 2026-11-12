"""Embedding service with sentence-transformers and deterministic mock fallback."""

import hashlib
import logging
import math
import random
from typing import List, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)

# Singleton model reference
_model = None
_model_initialized = False


def _get_model():
    """Lazily load the SentenceTransformer model singleton or flag fallback."""
    global _model, _model_initialized
    if _model_initialized:
        return _model

    settings = get_settings()
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model '%s'...", settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model '%s' loaded successfully.", settings.embedding_model)
    except Exception as exc:
        logger.warning(
            "SentenceTransformer failed to load ('%s'): %s. Using deterministic mock embeddings.",
            settings.embedding_model,
            exc,
        )
        _model = None

    _model_initialized = True
    return _model


def _mock_embed(text: str, dim: int) -> List[float]:
    """Generate a deterministic normalized unit vector based on input text hash.

    Ensures identical texts yield identical vectors with unit length,
    matching cosine distance metric expectations in vector databases.
    """
    clean_text = text.strip().lower()
    seed_bytes = hashlib.sha256(clean_text.encode("utf-8")).digest()
    rng = random.Random(seed_bytes)

    # Sample pseudo-random gaussian values
    raw_vec = [rng.gauss(0.0, 1.0) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw_vec))
    if norm == 0.0:
        return [0.0] * dim

    return [x / norm for x in raw_vec]


def embed_text(text: str) -> List[float]:
    """Generate a dense vector embedding for a single string.

    Args:
        text: Input string to embed.

    Returns:
        A list of floats representing the embedding vector.
    """
    settings = get_settings()
    model = _get_model()

    if model is not None:
        try:
            vector = model.encode(text, convert_to_numpy=True)
            return vector.tolist()
        except Exception as e:
            logger.error("Error generating embedding with model: %s. Falling back to mock.", e)

    return _mock_embed(text, settings.embedding_dim)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """Generate dense vector embeddings for a list of strings in batch.

    Args:
        texts: List of input strings to embed.

    Returns:
        A list of embedding vectors.
    """
    if not texts:
        return []

    settings = get_settings()
    model = _get_model()

    if model is not None:
        try:
            vectors = model.encode(texts, convert_to_numpy=True)
            return [vec.tolist() for vec in vectors]
        except Exception as e:
            logger.error("Error generating batch embeddings with model: %s. Falling back to mock.", e)

    return [_mock_embed(t, settings.embedding_dim) for t in texts]
