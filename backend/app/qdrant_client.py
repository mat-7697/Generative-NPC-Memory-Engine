"""Qdrant vector database client wrapper and collection initialization.

Collection Schema (`npc_memories`):
------------------------------------
Vector:
  - size: 384 (default, matches `all-MiniLM-L6-v2`)
  - distance: Cosine

Payload Fields & Indexes:
  - player_id (Integer): Identifier of the player involved; filtered on retrieve.
  - npc_id (Integer): Identifier of the NPC who holds or is related to this memory.
  - timestamp (Float): Unix timestamp of the memory event; used for decay/recency scoring.
  - importance (Float): Relative importance score (0.0 to 10.0); used in generative memory ranking.
  - session_id (Keyword): Optional game session identifier.
  - content (Text): The raw dialogue, observation, or reflection text.
  - memory_type (Keyword): Type of memory ('observation', 'dialogue', 'reflection', 'plan').
"""

import logging
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType
from app.config import get_settings

logger = logging.getLogger(__name__)

# Cached client instance
_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """Return a singleton or cached QdrantClient instance configured from settings."""
    global _client
    if _client is None:
        settings = get_settings()
        logger.info(
            "Connecting to Qdrant at %s:%s",
            settings.qdrant_host,
            settings.qdrant_port,
        )
        server_client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=2.0,
        )
        try:
            server_client.get_collections()
            _client = server_client
        except Exception as exc:
            # No Qdrant server running (e.g. no Docker) -> use embedded on-disk mode.
            from pathlib import Path

            local_path = Path(__file__).resolve().parent.parent / "qdrant_local_data"
            logger.warning(
                "Qdrant server unreachable (%s). Using embedded local Qdrant at %s",
                exc,
                local_path,
            )
            _client = QdrantClient(path=str(local_path))
    return _client


def init_qdrant() -> None:
    """Create the NPC memories collection and payload indexes if they do not already exist."""
    settings = get_settings()
    client = get_qdrant_client()
    collection_name = settings.qdrant_collection

    try:
        collections = client.get_collections().collections
        existing_names = {col.name for col in collections}

        if collection_name not in existing_names:
            logger.info(
                "Creating Qdrant collection '%s' (vector size: %d, distance: %s)...",
                collection_name,
                settings.embedding_dim,
                Distance.COSINE,
            )
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info("Collection '%s' created successfully.", collection_name)
        else:
            logger.info("Qdrant collection '%s' already exists.", collection_name)

        # Create payload indexes for fast filtering and scoring
        indexed_fields = [
            ("player_id", PayloadSchemaType.INTEGER),
            ("npc_id", PayloadSchemaType.INTEGER),
            ("timestamp", PayloadSchemaType.FLOAT),
            ("importance", PayloadSchemaType.FLOAT),
        ]

        for field_name, field_schema in indexed_fields:
            try:
                client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=field_schema,
                )
                logger.debug(
                    "Created payload index on '%s' (%s) in '%s'.",
                    field_name,
                    field_schema,
                    collection_name,
                )
            except Exception as e:
                # If index already exists or server returns notice, log and proceed
                logger.debug("Payload index creation notice for '%s': %s", field_name, e)

        logger.info("Qdrant initialization completed successfully.")

    except Exception as exc:
        logger.error("Failed to initialize Qdrant vector database: %s", exc)
        raise exc
