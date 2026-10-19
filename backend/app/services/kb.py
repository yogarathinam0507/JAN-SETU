"""Knowledge base: ingestion, chunking, versioning and retrieval with citations.

Retrieval uses a local BM25 lexical index (reliable offline fallback). A vector store (Qdrant/FAISS) +
embedding provider can be plugged in behind `search()`; it is listed as 'planned' on /integrations.
"""
import io
import math
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import iso, utcnow
from ..models import KnowledgeChunk, KnowledgeDocument

RETRIEVAL_MODE = "bm25-lexical (local, offline)"
STOPWORDS = {"the", "and", "for", "are", "with", "that", "this", "from", "what", "how", "can", "who", "which",
             "is", "a", "an", "of", "to", "in", "on", "my", "i", "do", "be", "it", "or", "by", "as", "at", "me", "about"}


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"\w+", (text or "").lower()) if t not in STOPWORDS and len(t) > 1]


def chunk_text(text: str, max_chars: int = 700) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    chunks, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                chunks.append(buf)
            while len(p) > max_chars:
                cut = p.rfind(". ", 0, max_chars)
                cut = cut + 1 if cut > 200 else max_chars
                chunks.append(p[:cut].strip())
                p = p[cut:].strip()
            buf = p
    if buf:
        chunks.append(buf)
    return chunks


def extract_text(filename: str, content_type: str, data: bytes) -> tuple[str, str]:
    """Returns (text, status). PDF text extraction is local; image OCR needs a configured provider."""
    name = filename.lower()
    if content_type == "application/pdf" or name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages)
            return text, "extracted:pypdf" if text.strip() else "no_text_layer:ocr_provider_required"
        except Exception as exc:  # noqa: BLE001 - report extraction failure honestly
            return "", f"failed:{type(exc).__name__}"
    if content_type.startswith("text/") or name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace"), "extracted:text"
    if content_type.startswith("image/"):
        return "", "ocr_not_configured"
    return "", "unsupported_type"


def index_document(db: Session, doc: KnowledgeDocument) -> int:
    db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == doc.id).delete()
    chunks = chunk_text(doc.body)
    for i, c in enumerate(chunks):
        db.add(KnowledgeChunk(document_id=doc.id, idx=i, text=c))
    doc.indexed_at = utcnow()
    return len(chunks)


def add_version(db: Session, *, tenant_id: str, doc_key: str, title: str, body: str, actor_id: str | None,
                **meta) -> KnowledgeDocument:
    prev = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == tenant_id,
                                                      KnowledgeDocument.doc_key == doc_key)
                      .order_by(KnowledgeDocument.version.desc())).scalars().first()
    version = (prev.version + 1) if prev else 1
    if prev:
        for old in db.execute(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == tenant_id,
                                                              KnowledgeDocument.doc_key == doc_key,
                                                              KnowledgeDocument.status == "active")).scalars():
            old.status = "superseded"
    doc = KnowledgeDocument(tenant_id=tenant_id, doc_key=doc_key, title=title, body=body, version=version,
                            created_by=actor_id, **meta)
    db.add(doc)
    db.flush()
    index_document(db, doc)
    return doc


def search(db: Session, tenant_id: str, query: str, k: int = 4, min_score: float = 1.2,
           department_code: str | None = None) -> list[dict]:
    q_terms = tokenize(query)
    if not q_terms:
        return []
    stmt = (select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.tenant_id == tenant_id, KnowledgeDocument.status == "active"))
    if department_code:
        stmt = stmt.where(KnowledgeDocument.department_code == department_code)
    rows = db.execute(stmt).all()
    if not rows:
        return []
    docs_tokens = [tokenize(ch.text + " " + d.title) for ch, d in rows]
    n = len(rows)
    avgdl = sum(len(t) for t in docs_tokens) / n or 1
    df = Counter()
    for toks in docs_tokens:
        df.update(set(toks))
    k1, b = 1.4, 0.75
    scored = []
    for (ch, d), toks in zip(rows, docs_tokens):
        tf = Counter(toks)
        score = 0.0
        for t in set(q_terms):
            if t not in tf:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(toks) / avgdl))
        if score >= min_score:
            scored.append((score, ch, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [{
        "score": round(s, 2), "text": ch.text, "chunk_index": ch.idx, "document_id": d.id, "title": d.title,
        "version": d.version, "source_url": d.source_url, "source_filename": d.source_filename,
        "published_date": d.published_date, "indexed_at": iso(d.indexed_at), "verified": d.verified,
        "is_sample": d.is_sample, "language": d.language, "department_code": d.department_code,
        "label": "Verified official source" if d.verified else "SAMPLE - needs official verification",
    } for s, ch, d in scored[:k]]
