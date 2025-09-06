from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean, Index
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
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    documents = relationship("Document", back_populates="source")

    __table_args__ = (
        Index("ix_sources_jurisdiction", "jurisdiction"),
        Index("ix_sources_active", "active"),
    )

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(1024), nullable=False)
    url = Column(String(2048), nullable=False, unique=True)
    published_at = Column(DateTime, nullable=True)
    text = Column(Text, nullable=True)

    # Python attribute name is `meta`; DB column remains "metadata"
    meta = Column("metadata", JSON, nullable=True)

    jurisdiction = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    source = relationship("Source", back_populates="documents")

    __table_args__ = (
        Index("ix_documents_published_at", "published_at"),
        Index("ix_documents_jurisdiction", "jurisdiction"),
        Index("ix_documents_title_gin", "title"),
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
