from __future__ import annotations
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Text,
    JSON,
    Boolean,
    Index,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Source(Base):
    __tablename__ = "sources"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    url = Column(String(1024), nullable=False)
    jurisdiction = Column(String(128), nullable=True)  # e.g., "US", "TX", "CA"
    type = Column(String(16), nullable=False, default="rss")  # "rss" | "html"
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,  # keep this auto-updated
        nullable=False,
    )

    documents = relationship("Document", back_populates="source", cascade="all,delete")

    __table_args__ = (
        Index("ix_sources_jurisdiction", "jurisdiction"),
        Index("ix_sources_active", "active"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    source_id = Column(
        Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(1024), nullable=False)
    url = Column(String(2048), nullable=False, unique=True)
    published_at = Column(DateTime, nullable=True)
    text = Column(Text, nullable=True)

    # Python attribute name is `meta`; DB column remains "metadata"
    meta = Column("metadata", JSON, nullable=True)

    jurisdiction = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # ---- Change tracking fields (added by migration 001_change_tracking.py) ----
    # Note: in SQLite these map fine even if the column was created as TEXT.
    current_hash = Column(String(64), nullable=True)
    first_seen_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_changed_at = Column(DateTime, nullable=True)

    source = relationship("Source", back_populates="documents")
    versions = relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentVersion.version_no",
    )

    __table_args__ = (
        Index("ix_documents_published_at", "published_at"),
        Index("ix_documents_jurisdiction", "jurisdiction"),
        Index("ix_documents_title_gin", "title"),
        # Helpful when creating a fresh DB from models (existing DB needs migration)
        Index("ix_documents_jur_last_changed", "jurisdiction", "last_changed_at"),
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True)
    doc_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_no = Column(Integer, nullable=False)
    content_hash = Column(String(64), nullable=False)
    title = Column(Text)
    snapshot = Column(Text)  # optional excerpt or full extracted text
    change_type = Column(String(16), nullable=False)  # ADDED | UPDATED | REMOVED
    fetched_at = Column(DateTime, server_default=func.current_timestamp())

    document = relationship("Document", back_populates="versions")

    __table_args__ = (
        Index("ix_doc_versions_doc_id_fetched", "doc_id", "fetched_at"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)  # optional for MVP
    keyword = Column(String(255), nullable=False)
    jurisdiction = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    active = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_alerts_keyword", "keyword"),
        Index("ix_alerts_jurisdiction", "jurisdiction"),
        Index("ix_alerts_active", "active"),
    )
