"""Normalized data model. Every tenant-owned table carries tenant_id and is always filtered by it."""
import secrets
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, utcnow


def new_id() -> str:
    return str(uuid.uuid4())


def public_code(prefix: str) -> str:
    """Non-guessable public identifier, e.g. GRV-7KQ2-M9XD."""
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    raw = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{prefix}-{raw[:4]}-{raw[4:]}"


class Tenant(Base):
    __tablename__ = "tenants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(100))
    default_language: Mapped[str] = mapped_column(String(10))
    languages: Mapped[list] = mapped_column(JSON, default=list)
    branding: Mapped[dict] = mapped_column(JSON, default=dict)
    emergency_contacts: Mapped[list] = mapped_column(JSON, default=list)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Role(Base):
    __tablename__ = "roles"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")


class RolePermission(Base):
    __tablename__ = "role_permissions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code"))
    permission: Mapped[str] = mapped_column(String(80))
    __table_args__ = (UniqueConstraint("role_code", "permission"),)


class Language(Base):
    __tablename__ = "languages"
    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name: Mapped[str] = mapped_column(String(60))
    native_name: Mapped[str] = mapped_column(String(60))
    script: Mapped[str] = mapped_column(String(40))
    direction: Mapped[str] = mapped_column(String(3), default="ltr")
    eighth_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    classical: Mapped[bool] = mapped_column(Boolean, default=False)
    planned_tier: Mapped[str] = mapped_column(String(30))  # voice_text | text_translation | content_assisted
    current_support: Mapped[str] = mapped_column(String(40))  # what is actually implemented & tested now
    speech_code: Mapped[str] = mapped_column(String(10), default="")
    ui_strings: Mapped[bool] = mapped_column(Boolean, default=False)
    triage_keywords: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str] = mapped_column(Text, default="")


class Jurisdiction(Base):
    __tablename__ = "jurisdictions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))  # zone | ward
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True)
    polygon: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [[lat,lng],...]
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    is_demo_boundary: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    names: Mapped[dict] = mapped_column(JSON, default=dict)
    parent_body: Mapped[str] = mapped_column(String(200), default="")
    contact: Mapped[dict] = mapped_column(JSON, default=dict)
    working_hours: Mapped[str] = mapped_column(String(100), default="")
    name_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"))
    code: Mapped[str] = mapped_column(String(40))  # shared family code across tenants
    names: Mapped[dict] = mapped_column(JSON, default=dict)
    family: Mapped[str] = mapped_column(String(80))
    default_priority: Mapped[str] = mapped_column(String(20))
    requires_photo_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)


class SlaPolicy(Base):
    __tablename__ = "sla_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    priority: Mapped[str] = mapped_column(String(20))
    first_response_hours: Mapped[float] = mapped_column(Float)
    resolve_hours: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(Text, default="")
    __table_args__ = (UniqueConstraint("tenant_id", "priority"),)


class EscalationRule(Base):
    __tablename__ = "escalation_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    level: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(40))
    sla_fraction: Mapped[float] = mapped_column(Float)  # escalate when elapsed >= fraction * SLA
    description: Mapped[str] = mapped_column(Text, default="")


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    designation: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(ForeignKey("roles.code"))
    password_hash: Mapped[str] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    jurisdiction_id: Mapped[str | None] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True)
    vendor_id: Mapped[str | None] = mapped_column(ForeignKey("vendors.id"), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    phone_hash: Mapped[str] = mapped_column(String(128), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[str] = mapped_column(String(30))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class MasterIncident(Base):
    __tablename__ = "master_incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, default=lambda: public_code("MST"))
    category_id: Mapped[str] = mapped_column(ForeignKey("categories.id"))
    jurisdiction_id: Mapped[str | None] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Grievance(Base):
    __tablename__ = "grievances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, default=lambda: public_code("GRV"))
    citizen_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(20), default="web")  # web|voice|chat|whatsapp|email|assistant
    input_mode: Mapped[str] = mapped_column(String(20), default="text")  # text|voice
    original_text: Mapped[str] = mapped_column(Text)
    transcript_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(10), default="en")
    summary: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True, index=True)
    joint_department_ids: Mapped[list] = mapped_column(JSON, default=list)
    jurisdiction_id: Mapped[str | None] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True)
    location_text: Mapped[str] = mapped_column(String(300), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="submitted", index=True)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    triage_id: Mapped[str | None] = mapped_column(ForeignKey("triage_records.id"), nullable=True)
    sla_policy_id: Mapped[str | None] = mapped_column(ForeignKey("sla_policies.id"), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_response_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    assigned_officer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    master_incident_id: Mapped[str | None] = mapped_column(ForeignKey("master_incidents.id"), nullable=True)
    contact_name: Mapped[str] = mapped_column(String(200), default="")
    contact_phone: Mapped[str] = mapped_column(String(20), default="")
    consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    emergency: Mapped[bool] = mapped_column(Boolean, default=False)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    citizen_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    citizen_feedback: Mapped[str] = mapped_column(Text, default="")
    resolution_note: Mapped[str] = mapped_column(Text, default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    __table_args__ = (Index("ix_grv_tenant_status_dept", "tenant_id", "status", "department_id"),)


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grievance_id: Mapped[str] = mapped_column(ForeignKey("grievances.id"), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(40), default="system")
    event_type: Mapped[str] = mapped_column(String(40))
    from_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str] = mapped_column(Text, default="")
    public: Mapped[bool] = mapped_column(Boolean, default=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_role: Mapped[str] = mapped_column(String(40), default="system")
    action: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(64))
    before: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), default="")


class TriageRecord(Base):
    __tablename__ = "triage_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    input_text: Mapped[str] = mapped_column(Text)
    input_language: Mapped[str] = mapped_column(String(10))
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(60))
    model_version: Mapped[str] = mapped_column(String(60))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    rules_applied: Mapped[list] = mapped_column(JSON, default=list)
    valid: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str] = mapped_column(Text, default="")
    human_override: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DuplicateLink(Base):
    __tablename__ = "duplicate_links"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grievance_id: Mapped[str] = mapped_column(ForeignKey("grievances.id"), index=True)
    master_incident_id: Mapped[str] = mapped_column(ForeignKey("master_incidents.id"), index=True)
    rule: Mapped[str] = mapped_column(String(200))
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(String(40), default="system")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    grievance_id: Mapped[str | None] = mapped_column(ForeignKey("grievances.id"), nullable=True, index=True)
    work_order_id: Mapped[str | None] = mapped_column(ForeignKey("work_orders.id"), nullable=True)
    officer_file_id: Mapped[str | None] = mapped_column(ForeignKey("officer_files.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))  # evidence | before | after | document
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    storage_name: Mapped[str] = mapped_column(String(100))
    sha256: Mapped[str] = mapped_column(String(64))
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    extraction_status: Mapped[str] = mapped_column(String(60), default="not_applicable")
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Interaction(Base):
    __tablename__ = "interactions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, default=lambda: public_code("INT"))
    channel: Mapped[str] = mapped_column(String(20))  # voice|web_chat|email|whatsapp|callback_request
    caller_name: Mapped[str] = mapped_column(String(200), default="")
    caller_phone: Mapped[str] = mapped_column(String(20), default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|active|wrap_up|closed
    priority: Mapped[str] = mapped_column(String(20), default="Medium")
    agent_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    queued_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    transcript: Mapped[list] = mapped_column(JSON, default=list)
    summary: Mapped[str] = mapped_column(Text, default="")
    action_items: Mapped[list] = mapped_column(JSON, default=list)
    sentiment: Mapped[str] = mapped_column(String(20), default="")
    disposition: Mapped[str] = mapped_column(String(40), default="")
    callback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    grievance_id: Mapped[str | None] = mapped_column(ForeignKey("grievances.id"), nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    qa_review: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    handoff_history: Mapped[list] = mapped_column(JSON, default=list)
    transcript_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    doc_key: Mapped[str] = mapped_column(String(120))  # stable key shared by all versions
    title: Mapped[str] = mapped_column(String(300))
    department_code: Mapped[str] = mapped_column(String(40), default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    source_url: Mapped[str] = mapped_column(String(500), default="")
    source_filename: Mapped[str] = mapped_column(String(255), default="")
    published_date: Mapped[str] = mapped_column(String(20), default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|inactive|superseded
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=True)
    body: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)


class Scheme(Base):
    __tablename__ = "schemes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    names: Mapped[dict] = mapped_column(JSON, default=dict)
    service_category: Mapped[str] = mapped_column(String(60))
    department: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)
    benefits: Mapped[str] = mapped_column(Text, default="")
    documents: Mapped[list] = mapped_column(JSON, default=list)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    questions: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[list] = mapped_column(JSON, default=list)
    official_url: Mapped[str] = mapped_column(String(500), default="")
    source_note: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (UniqueConstraint("tenant_id", "code"),)


class Vendor(Base):
    __tablename__ = "vendors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    is_sample: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkOrder(Base):
    __tablename__ = "work_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, default=lambda: public_code("WO"))
    grievance_id: Mapped[str] = mapped_column(ForeignKey("grievances.id"))
    vendor_id: Mapped[str] = mapped_column(ForeignKey("vendors.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    boq: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="issued")  # issued|in_progress|completed|verified|rejected
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    vendor_note: Mapped[str] = mapped_column(Text, default="")


class OfficerFile(Base):
    __tablename__ = "officer_files"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    public_id: Mapped[str] = mapped_column(String(30), unique=True, default=lambda: public_code("FILE"))
    subject: Mapped[str] = mapped_column(String(300))
    department_id: Mapped[str] = mapped_column(ForeignKey("departments.id"))
    current_holder_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="open")  # open|in_review|returned|closed
    grievance_id: Mapped[str | None] = mapped_column(ForeignKey("grievances.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="Medium")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class FileMovement(Base):
    __tablename__ = "file_movements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    file_id: Mapped[str] = mapped_column(ForeignKey("officer_files.id"), index=True)
    from_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    to_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    from_department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    to_department_id: Mapped[str | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocumentTemplate(Base):
    __tablename__ = "document_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    department_code: Mapped[str] = mapped_column(String(40), default="")
    doc_type: Mapped[str] = mapped_column(String(40))  # response_letter | notice | endorsement
    language: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)


class Draft(Base):
    __tablename__ = "drafts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    grievance_id: Mapped[str | None] = mapped_column(ForeignKey("grievances.id"), nullable=True)
    officer_file_id: Mapped[str | None] = mapped_column(ForeignKey("officer_files.id"), nullable=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("document_templates.id"), nullable=True)
    language: Mapped[str] = mapped_column(String(10))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="draft")  # draft | ready_for_manual_dispatch
    version: Mapped[int] = mapped_column(Integer, default=1)
    generator: Mapped[str] = mapped_column(String(60), default="template")
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class MonitoredService(Base):
    __tablename__ = "monitored_services"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    endpoint: Mapped[str] = mapped_column(String(500), default="")
    owner_team: Mapped[str] = mapped_column(String(200), default="")
    environment: Mapped[str] = mapped_column(String(40), default="demo")
    criticality: Mapped[str] = mapped_column(String(20), default="medium")
    expected_status: Mapped[int] = mapped_column(Integer, default=200)
    latency_threshold_ms: Mapped[int] = mapped_column(Integer, default=1500)
    slo_target: Mapped[float] = mapped_column(Float, default=99.5)
    check_mode: Mapped[str] = mapped_column(String(20))  # in_process | http | simulated | planned
    authorized: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class HealthCheck(Base):
    __tablename__ = "health_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("monitored_services.id"), index=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    ok: Mapped[bool] = mapped_column(Boolean)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("monitored_services.id"))
    public_id: Mapped[str] = mapped_column(String(30), unique=True, default=lambda: public_code("INC"))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|acknowledged|resolved
    severity: Mapped[str] = mapped_column(String(20), default="major")
    trigger: Mapped[str] = mapped_column(String(200), default="")
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    hypotheses: Mapped[list] = mapped_column(JSON, default=list)
    confirmed_root_cause: Mapped[str] = mapped_column(Text, default="")
    confirmed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    service_id: Mapped[str] = mapped_column(ForeignKey("monitored_services.id"))
    incident_id: Mapped[str | None] = mapped_column(ForeignKey("incidents.id"), nullable=True)
    rule: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    simulated: Mapped[bool] = mapped_column(Boolean, default=False)


class AiEvaluation(Base):
    __tablename__ = "ai_evaluations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(36), index=True)
    dataset: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(60))
    language: Mapped[str] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    expected_category: Mapped[str] = mapped_column(String(40))
    predicted_category: Mapped[str] = mapped_column(String(40))
    expected_priority: Mapped[str] = mapped_column(String(20))
    predicted_priority: Mapped[str] = mapped_column(String(20))
    category_correct: Mapped[bool] = mapped_column(Boolean)
    priority_correct: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IntegrationConfig(Base):
    __tablename__ = "integration_configs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str | None] = mapped_column(ForeignKey("tenants.id"), nullable=True)
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(60))
    state: Mapped[str] = mapped_column(String(40))  # connected_tested|configured_unverified|simulated|planned
    adapter: Mapped[str] = mapped_column(String(200), default="")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class DataRequest(Base):
    __tablename__ = "data_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))  # export | deletion
    status: Mapped[str] = mapped_column(String(30), default="received")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AssistantEvent(Base):
    """Usage log for the benefit navigator / assistant (no message content stored)."""
    __tablename__ = "assistant_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # chat | eligibility_check | human_referral | grievance_from_assistant
    language: Mapped[str] = mapped_column(String(10), default="en")
    outcome: Mapped[str] = mapped_column(String(60), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FieldLocation(Base):
    """Latest live position shared by a field user (officer / nodal / contractor). One row per user."""
    __tablename__ = "field_locations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    status_note: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
