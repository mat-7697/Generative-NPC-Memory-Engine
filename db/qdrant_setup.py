#!/usr/bin/env python3
"""Standalone script to initialize or recreate the Qdrant collection for NPC memories.

Usage:
    python db/qdrant_setup.py [--recreate]
"""

import argparse
import os
import sys
from pathlib import Path

# Load environment variables from .env or backend/.env
try:
    from dotenv import load_dotenv

    root_dir = Path(__file__).resolve().parent.parent
    env_paths = [
        root_dir / ".env",
        root_dir / "backend" / ".env",
        Path(".env"),
    ]
    for p in env_paths:
        if p.exists():
            load_dotenv(p)
            break
except ImportError:
    pass

try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
    from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType
except ImportError:
    print(
        "Error: 'qdrant-client' is required to run this script.\n"
        "Please install requirements: pip install -r backend/requirements.txt"
    )
    sys.exit(1)


def setup_qdrant(recreate: bool = False):
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    collection_name = os.getenv("QDRANT_COLLECTION", "npc_memories")
    vector_dim = int(os.getenv("EMBEDDING_DIM", "384"))

    print(f"=== Qdrant Setup for NPC Memory Engine ===")
    print(f"Target: {host}:{port}")
    print(f"Collection: {collection_name}")
    print(f"Vector Dimensions: {vector_dim} (Distance: Cosine)")

    try:
        client = QdrantClient(host=host, port=port)
        collections = client.get_collections().collections
        existing_names = [col.name for col in collections]
    except Exception as e:
        print(f"\n[ERROR] Could not connect to Qdrant at {host}:{port}: {e}")
        print("Please ensure Qdrant is running via Docker: docker-compose up -d")
        sys.exit(1)

    if collection_name in existing_names:
        if recreate:
            print(f"Deleting existing collection '{collection_name}' as requested...")
            client.delete_collection(collection_name=collection_name)
        else:
            print(f"Collection '{collection_name}' already exists. Updating indexes...")

    if collection_name not in existing_names or recreate:
        print(f"Creating collection '{collection_name}'...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_dim,
                distance=Distance.COSINE,
            ),
        )
        print(f"[OK] Collection '{collection_name}' created.")

    # Create payload indexes
    indexes = [
        ("player_id", PayloadSchemaType.INTEGER),
        ("npc_id", PayloadSchemaType.INTEGER),
        ("timestamp", PayloadSchemaType.FLOAT),
        ("importance", PayloadSchemaType.FLOAT),
        ("session_id", PayloadSchemaType.KEYWORD),
    ]

    print("Creating payload indexes:")
    for field_name, schema_type in indexes:
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field_name,
                field_schema=schema_type,
            )
            print(f"  - {field_name} ({schema_type}) -> [OK]")
        except Exception as e:
            print(f"  - {field_name} ({schema_type}) -> Notice: {e}")

    # Verify status
    info = client.get_collection(collection_name=collection_name)
    print("\n=== Setup Complete ===")
    print(f"Status: {info.status}")
    print(f"Points Count: {getattr(info, 'points_count', getattr(info, 'vectors_count', 0)) or 0}")
    print("Qdrant is ready for Generative NPC Memory operations!\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Set up Qdrant collection and indexes for Generative NPC Memory Engine."
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Recreate the collection if it already exists (drops existing memories).",
    )
    args = parser.parse_args()
    setup_qdrant(recreate=args.recreate)
