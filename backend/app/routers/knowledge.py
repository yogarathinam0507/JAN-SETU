import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db, iso, utcnow
from ..models import Category, Department, KnowledgeChunk, KnowledgeDocument, Scheme, User
from ..security import require
from ..services import audit, kb
from ..services.uploads import read_validated

router = APIRouter(prefix="/api/knowledge", tags=["knowledge base"])
writer = require("kb:write")


def doc_out(db: Session, d: KnowledgeDocument) -> dict:
    n = db.query(KnowledgeChunk).filter(KnowledgeChunk.document_id == d.id).count()
    return {"id": d.id, "doc_key": d.doc_key, "title": d.title, "version": d.version, "status": d.status,
            "department_code": d.department_code, "language": d.language, "source_url": d.source_url,
            "source_filename": d.source_filename, "published_date": d.published_date, "verified": d.verified,
            "is_sample": d.is_sample, "chunks": n, "created_at": iso(d.created_at), "indexed_at": iso(d.indexed_at),
            "label": "Verified official source" if d.verified else "SAMPLE - needs official verification"}


@router.get("/documents")
def list_docs(user: User = Depends(require("kb:read")), db: Session = Depends(get_db), include_history: bool = False):
    q = select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == user.tenant_id)
    if not include_history:
        q = q.where(KnowledgeDocument.status != "superseded")
    return [doc_out(db, d) for d in db.execute(q.order_by(KnowledgeDocument.title, KnowledgeDocument.version.desc())).scalars()]


@router.get("/documents/{doc_id}")
def get_doc(doc_id: str, user: User = Depends(require("kb:read")), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d or d.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Document not found."})
    versions = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == user.tenant_id,
                                                          KnowledgeDocument.doc_key == d.doc_key)
                          .order_by(KnowledgeDocument.version.desc())).scalars().all()
    return doc_out(db, d) | {"body": d.body, "versions": [{"id": v.id, "version": v.version, "status": v.status,
                                                           "created_at": iso(v.created_at)} for v in versions]}


class DocIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=20, max_length=200000)
    doc_key: str | None = Field(None, max_length=120)
    department_code: str = Field("", max_length=40)
    language: str = Field("en", max_length=10)
    source_url: str = Field("", max_length=500, pattern=r"^$|^https://")
    published_date: str = Field("", max_length=20)
    verified: bool = False


def _key(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:100]


@router.post("/documents", status_code=201)
def create_doc(body: DocIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    d = kb.add_version(db, tenant_id=user.tenant_id, doc_key=body.doc_key or _key(body.title), title=body.title,
                       body=body.body, actor_id=user.id, department_code=body.department_code, language=body.language,
                       source_url=body.source_url, published_date=body.published_date, verified=body.verified,
                       is_sample=not body.verified)
    audit.record(db, actor=user, action="kb.add_version", entity_type="kb_document", entity_id=d.id,
                 after={"title": d.title, "version": d.version, "verified": d.verified})
    db.commit()
    return doc_out(db, d)


@router.post("/documents/upload", status_code=201)
async def upload_doc(file: UploadFile = File(...), title: str = Form(...), doc_key: str = Form(""),
                     department_code: str = Form(""), language: str = Form("en"), source_url: str = Form(""),
                     published_date: str = Form(""), verified: bool = Form(False),
                     user: User = Depends(writer), db: Session = Depends(get_db)):
    if source_url and not source_url.startswith("https://"):
        raise HTTPException(422, detail={"code": "invalid_url", "message": "Source URL must start with https://"})
    data, ctype = await read_validated(file, {"application/pdf", "text/plain"})
    text, status = kb.extract_text(file.filename or "", ctype, data)
    if not text.strip():
        raise HTTPException(422, detail={"code": "no_text", "message": f"No text could be extracted ({status})."})
    d = kb.add_version(db, tenant_id=user.tenant_id, doc_key=doc_key or _key(title), title=title[:300], body=text,
                       actor_id=user.id, department_code=department_code[:40], language=language[:10],
                       source_url=source_url[:500], source_filename=(file.filename or "")[:255],
                       published_date=published_date[:20], verified=verified, is_sample=not verified)
    audit.record(db, actor=user, action="kb.upload", entity_type="kb_document", entity_id=d.id,
                 after={"title": d.title, "version": d.version, "extraction": status})
    db.commit()
    return doc_out(db, d) | {"extraction_status": status}


class StatusIn(BaseModel):
    status: str = Field(pattern="^(active|inactive)$")
    reason: str = Field(min_length=3, max_length=300)


@router.post("/documents/{doc_id}/status")
def set_status(doc_id: str, body: StatusIn, user: User = Depends(writer), db: Session = Depends(get_db)):
    d = db.get(KnowledgeDocument, doc_id)
    if not d or d.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Document not found."})
    before = d.status
    d.status = body.status
    audit.record(db, actor=user, action="kb.status", entity_type="kb_document", entity_id=d.id,
                 before={"status": before}, after={"status": d.status}, reason=body.reason)
    db.commit()
    return doc_out(db, d)


@router.post("/reindex")
def reindex(user: User = Depends(writer), db: Session = Depends(get_db)):
    n_docs = n_chunks = 0
    for d in db.execute(select(KnowledgeDocument).where(KnowledgeDocument.tenant_id == user.tenant_id,
                                                        KnowledgeDocument.status == "active")).scalars():
        n_chunks += kb.index_document(db, d)
        n_docs += 1
    audit.record(db, actor=user, action="kb.reindex", entity_type="kb", entity_id=user.tenant_id,
                 after={"documents": n_docs, "chunks": n_chunks})
    db.commit()
    return {"documents": n_docs, "chunks": n_chunks, "retrieval_mode": kb.RETRIEVAL_MODE}


@router.get("/search")
def search(q: str, user: User = Depends(require("kb:read")), db: Session = Depends(get_db)):
    return {"retrieval_mode": kb.RETRIEVAL_MODE, "results": kb.search(db, user.tenant_id, q, k=6, min_score=0.5)}


class SchemeUpdateIn(BaseModel):
    summary: str | None = Field(None, max_length=4000)
    benefits: str | None = Field(None, max_length=4000)
    documents: list[str] | None = None
    steps: list[str] | None = None
    official_url: str | None = Field(None, max_length=500, pattern=r"^$|^https://")
    source_note: str | None = Field(None, max_length=2000)
    verified: bool | None = None
    names: dict[str, str] | None = None


@router.put("/schemes/{code}")
def update_scheme(code: str, body: SchemeUpdateIn, user: User = Depends(require("schemes:write")), db: Session = Depends(get_db)):
    s = db.execute(select(Scheme).where(Scheme.tenant_id == user.tenant_id, Scheme.code == code)).scalar_one_or_none()
    if not s:
        raise HTTPException(404, detail={"code": "not_found", "message": "Scheme not found."})
    changes = body.model_dump(exclude_none=True)
    if changes.get("verified") and not (changes.get("official_url") or s.official_url):
        raise HTTPException(422, detail={"code": "source_required", "message": "Add the official source URL before marking verified."})
    before = {k: getattr(s, k) for k in changes}
    for k, v in changes.items():
        setattr(s, k, v)
    s.version += 1
    s.updated_at = utcnow()
    audit.record(db, actor=user, action="scheme.update", entity_type="scheme", entity_id=s.code, before=before,
                 after=changes | {"version": s.version})
    db.commit()
    return {"code": s.code, "version": s.version, "verified": s.verified}


class TranslationIn(BaseModel):
    entity: str = Field(pattern="^(category|department)$")
    entity_id: str
    language: str = Field(min_length=2, max_length=10)
    name: str = Field(min_length=1, max_length=200)


@router.put("/translations")
def set_translation(body: TranslationIn, user: User = Depends(require("translations:write")), db: Session = Depends(get_db)):
    model = Category if body.entity == "category" else Department
    obj = db.get(model, body.entity_id)
    if not obj or obj.tenant_id != user.tenant_id:
        raise HTTPException(404, detail={"code": "not_found", "message": "Not found."})
    before = dict(obj.names)
    obj.names = {**obj.names, body.language: body.name}
    audit.record(db, actor=user, action="translation.set", entity_type=body.entity, entity_id=obj.id, before=before,
                 after=obj.names)
    db.commit()
    return {"id": obj.id, "names": obj.names}
