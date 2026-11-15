import hashlib
import json
import math

from app.services.library_repository import _connection, init_db


def validate_vectors(vectors, count):
    if not isinstance(vectors, list) or len(vectors) != count or not vectors:
        raise ValueError("Embedding count mismatch.")
    dimension = len(vectors[0])
    if not dimension or any(len(v) != dimension or not all(math.isfinite(float(x)) for x in v) or not any(v) for v in vectors):
        raise ValueError("Invalid embedding values or dimensions.")


async def cached_embed(provider, texts):
    """Content-addressed embeddings, isolated inside the signed-in user's database."""
    if not texts:
        return []
    key = getattr(provider, "cache_key", None)
    if not key:
        result = await provider.embed(texts)
        validate_vectors(result, len(texts))
        return result
    init_db()
    hashes = [hashlib.sha256((key + "\0" + text).encode()).hexdigest() for text in texts]
    with _connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS embeddings (key TEXT PRIMARY KEY, vector TEXT NOT NULL)")
        cached = {}
        for digest in set(hashes):
            row = db.execute("SELECT vector FROM embeddings WHERE key=?", (digest,)).fetchone()
            if row:
                cached[digest] = json.loads(row["vector"])
    missing = list(dict.fromkeys(digest for digest in hashes if digest not in cached))
    text_map = dict(zip(hashes, texts))
    if missing:
        generated = await provider.embed([text_map[digest] for digest in missing])
        validate_vectors(generated, len(missing))
        with _connection() as db:
            for digest, vector in zip(missing, generated):
                db.execute("INSERT OR REPLACE INTO embeddings VALUES (?, ?)", (digest, json.dumps(vector)))
                cached[digest] = vector
    result = [cached[digest] for digest in hashes]
    validate_vectors(result, len(texts))
    return result
