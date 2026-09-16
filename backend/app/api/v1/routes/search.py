import json

from fastapi import APIRouter, HTTPException
from openai import OpenAIError

from app.database import get_db
from app.models import (
    BackfillResponse,
    VectorSearchQuery,
    VectorSearchResponse,
    VectorSearchResultItem,
)
from app.services.embeddings import (
    batch_get_embeddings,
    cosine_similarity,
    get_embedding,
)

router = APIRouter()


@router.post("/search", response_model=VectorSearchResponse)
async def search_logs(params: VectorSearchQuery):
    db = await get_db()
    try:
        query_vec = get_embedding(params.query)
    except OpenAIError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Semantic search is unavailable: {e}",
        ) from e

    rows = await db.get_all_embeddings()
    if not rows:
        raise HTTPException(status_code=404, detail="No embeddings found. Run backfill first.")

    scored = []
    for row in rows:
        try:
            emb = json.loads(row["embedding"])
        except (json.JSONDecodeError, TypeError):
            continue
        sim = cosine_similarity(query_vec, emb)

        svc = row.get("service")
        lvl = (row.get("level") or "").upper()
        if params.service and svc != params.service:
            continue
        if params.level and lvl != params.level.upper():
            continue

        scored.append((sim, row, svc, lvl))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[: params.limit]

    results = []
    for sim, row, svc, lvl in top:
        ts = row.get("timestamp")
        results.append(
            VectorSearchResultItem(
                id=row["id"],
                timestamp=ts,
                service=svc,
                level=lvl,
                message=row.get("message", ""),
                raw_log=row.get("raw_log", ""),
                similarity=round(sim, 4),
            )
        )

    return VectorSearchResponse(
        results=results,
        query=params.query,
        total=len(results),
    )


@router.post("/search/backfill", response_model=BackfillResponse)
async def backfill_embeddings():
    db = await get_db()
    logs = await db.get_logs_without_embeddings(limit=500)
    if not logs:
        return BackfillResponse(processed=0, failed=0, errors=[])

    texts = []
    id_map = []
    for log in logs:
        if log.get("raw_log"):
            texts.append(log["raw_log"])
        else:
            texts.append(log.get("message", ""))
        id_map.append(log["id"])

    errors = []
    processed = 0
    BATCH_SIZE = 20
    for i in range(0, len(texts), BATCH_SIZE):
        chunk_texts = texts[i : i + BATCH_SIZE]
        chunk_ids = id_map[i : i + BATCH_SIZE]
        try:
            embeddings = batch_get_embeddings(chunk_texts)
            for log_id, emb in zip(chunk_ids, embeddings):
                await db.update_embedding(log_id, emb)
                processed += 1
        except Exception as e:
            errors.append(f"batch {i // BATCH_SIZE}: {e}")
            for log_id in chunk_ids:
                await db.update_embedding(log_id, [])

    return BackfillResponse(
        processed=processed,
        failed=len(errors),
        errors=errors[:20],
    )
