"""
rag_index.py — ChromaDB + nomic-embed indexer.

Usage:
    python rag_index.py --docs docs/  [--reset]

Indexes all .md and .txt files from the given directory into ChromaDB.
"""

import argparse
import json
import os
import sys
from typing import Optional

import requests


_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(_BASE_DIR, "config.json")) as _f:
    _CFG = json.load(_f)

_LMS = _CFG["lmstudio"]
_BASE_URL = _LMS["base_url"]
_API_TOKEN = _LMS["api_token"]
_EMBED_MODEL = _LMS["embed_model"]
_RAG_PATH = os.path.join(_BASE_DIR, "rag_db")


def _lmstudio_headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = str(
        os.environ.get("LM_STUDIO_API_TOKEN")
        or os.environ.get("FIELD_MARSHAL_LMSTUDIO_API_TOKEN")
        or _API_TOKEN
        or ""
    ).strip()
    if token and "YOUR_LM_STUDIO" not in token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _embed(texts: list[str]) -> list[list[float]]:
    """Call LM Studio embedding endpoint."""
    url = f"{_BASE_URL}/v1/embeddings"
    headers = _lmstudio_headers()
    payload = {"model": _EMBED_MODEL, "input": texts}
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


def index_directory(
    docs_dir: str,
    collection_name: str = "field_marshal_docs",
    reset: bool = False,
):
    """Index all .md and .txt files in docs_dir."""
    try:
        import chromadb  # type: ignore
    except ImportError:
        print("chromadb not installed. Run: pip install chromadb")
        sys.exit(1)

    client = chromadb.PersistentClient(path=_RAG_PATH)

    if reset:
        try:
            client.delete_collection(collection_name)
            print(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass

    collection = client.get_or_create_collection(collection_name)

    doc_files = []
    for root, _, files in os.walk(docs_dir):
        for filename in files:
            if filename.lower().endswith((".md", ".txt")):
                doc_files.append(os.path.join(root, filename))

    if not doc_files:
        print(f"No .md or .txt files found in {docs_dir}")
        return

    total_chunks = 0
    for filepath in doc_files:
        print(f"Indexing: {filepath}")
        with open(filepath, encoding="utf-8", errors="replace") as f:
            text = f.read()

        chunks = _chunk_text(text)
        if not chunks:
            continue

        # Embed chunks in batches of 10
        batch_size = 10
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            try:
                embeddings = _embed(batch)
            except Exception as exc:
                print(f"  Embedding failed for chunk batch: {exc}")
                continue

            ids = [f"{os.path.basename(filepath)}_chunk_{i + j}" for j in range(len(batch))]
            collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=batch,
                metadatas=[{"source": filepath, "chunk": i + j} for j in range(len(batch))],
            )
            total_chunks += len(batch)

    print(f"Indexed {total_chunks} chunks from {len(doc_files)} files into '{collection_name}'")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index documents into ChromaDB for Field Marshal RAG")
    parser.add_argument("--docs", default="docs", help="Directory containing .md/.txt files to index")
    parser.add_argument("--reset", action="store_true", help="Delete existing collection before indexing")
    parser.add_argument("--collection", default="field_marshal_docs", help="ChromaDB collection name")
    args = parser.parse_args()

    docs_path = os.path.join(_BASE_DIR, args.docs)
    if not os.path.isdir(docs_path):
        print(f"docs directory not found: {docs_path}")
        sys.exit(1)

    index_directory(docs_path, collection_name=args.collection, reset=args.reset)
