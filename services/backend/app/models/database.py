"""SQLAlchemy 2.0 database engine, session, and 6-table core schema.
Supports PostgreSQL 16 with JSONB and SQLite fallback for local unit tests.
"""
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.types import JSON, TypeDecorator

# Detect database URL from environment or default to local sqlite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./supplychain.db")

# Cross-platform JSON type: uses JSONB on postgres, standard JSON on sqlite
class CrossPlatformJSON(TypeDecorator):
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


Base = declarative_base()


# ---------------------------------------------------------------------------
# Table 1: components_inventory
# ---------------------------------------------------------------------------
class ComponentInventory(Base):
    __tablename__ = "components_inventory"

    component_id = Column(String(50), primary_key=True)
    name = Column(String(255), nullable=False)
    unit = Column(String(20), nullable=False, default="units")
    on_hand_qty = Column(Float, nullable=False, default=0.0)
    reserved_qty = Column(Float, nullable=False, default=0.0)
    safety_stock = Column(Float, nullable=False, default=0.0)
    target_stock = Column(Float, nullable=False, default=0.0)
    daily_burn_rate = Column(Float, nullable=False, default=1.0)
    downtime_cost_per_day = Column(Float, nullable=False, default=10000.0)
    budget_limit = Column(Float, nullable=False, default=100000.0)
    criticality = Column(String(20), nullable=False, default="HIGH")  # CRITICAL, HIGH, MEDIUM, LOW
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    suppliers = relationship("SupplierCatalog", back_populates="component")


# ---------------------------------------------------------------------------
# Table 2: suppliers_catalog
# ---------------------------------------------------------------------------
class SupplierCatalog(Base):
    __tablename__ = "suppliers_catalog"

    supplier_id = Column(String(50), primary_key=True)
    component_id = Column(String(50), ForeignKey("components_inventory.component_id"), primary_key=True)
    supplier_name = Column(String(255), nullable=False)
    unit_price = Column(Float, nullable=False)
    shipping_cost = Column(Float, nullable=False, default=0.0)
    lead_time_days = Column(Integer, nullable=False)
    capacity = Column(Float, nullable=False, default=1000.0)
    moq = Column(Float, nullable=False, default=1.0)
    reliability_score = Column(Float, nullable=False, default=0.95)
    is_active = Column(Boolean, nullable=False, default=True)
    technical_compliant = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    component = relationship("ComponentInventory", back_populates="suppliers")


# ---------------------------------------------------------------------------
# Table 3: blackboard_entries
# ---------------------------------------------------------------------------
class BlackboardEntry(Base):
    __tablename__ = "blackboard_entries"

    entry_id = Column(String(100), primary_key=True, default=lambda: f"bb-{uuid.uuid4().hex[:12]}")
    workflow_id = Column(String(100), nullable=False, index=True)
    artifact_type = Column(String(50), nullable=False)  # ShortageAlert, RFQAndQuotesList, RiskDecision, InvoiceAuditResult
    step_name = Column(String(100), nullable=False)
    producer_agent = Column(String(100), nullable=False)
    framework = Column(String(20), nullable=False)  # ADK, CrewAI, SYSTEM
    payload = Column(CrossPlatformJSON, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    trace_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_bb_wf_type_ver", "workflow_id", "artifact_type", "version"),
    )


# ---------------------------------------------------------------------------
# Table 4: procurement_workflows
# ---------------------------------------------------------------------------
class ProcurementWorkflow(Base):
    __tablename__ = "procurement_workflows"

    workflow_id = Column(String(100), primary_key=True)
    component_id = Column(String(50), ForeignKey("components_inventory.component_id"), nullable=False)
    required_qty = Column(Float, nullable=False)
    buffer_days = Column(Integer, nullable=False)
    status = Column(String(50), nullable=False, default="RUNNING")
    selected_supplier_id = Column(String(50), nullable=True)
    estimated_total_cost = Column(Float, nullable=True)
    approval_required = Column(Boolean, nullable=False, default=False)
    approval_status = Column(String(50), nullable=True)  # PENDING, APPROVED, REJECTED
    approval_actor = Column(String(100), nullable=True)
    approval_timestamp = Column(DateTime, nullable=True)
    escalation_reason = Column(Text, nullable=True)
    final_report_md = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Table 5: orders_and_invoices
# ---------------------------------------------------------------------------
class OrderAndInvoice(Base):
    __tablename__ = "orders_and_invoices"

    po_id = Column(String(100), primary_key=True)
    workflow_id = Column(String(100), ForeignKey("procurement_workflows.workflow_id"), nullable=False)
    supplier_id = Column(String(50), nullable=False)
    po_qty = Column(Float, nullable=False)
    po_unit = Column(String(20), nullable=False, default="units")
    po_unit_price = Column(Float, nullable=False)
    goods_receipt_ref = Column(String(100), nullable=True)
    received_qty = Column(Float, nullable=True)
    received_unit = Column(String(20), nullable=True)
    invoice_ref = Column(String(100), nullable=True)
    invoiced_qty = Column(Float, nullable=True)
    invoiced_unit = Column(String(20), nullable=True)
    invoiced_unit_price = Column(Float, nullable=True)
    invoice_notes = Column(Text, nullable=True)
    match_status = Column(String(50), nullable=False, default="UNMATCHED")  # MATCHED, DISCREPANCY, UNMATCHED
    discrepancies_jsonb = Column(CrossPlatformJSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Table 6: benchmark_runs
# ---------------------------------------------------------------------------
class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    run_id = Column(String(100), primary_key=True, default=lambda: f"run-{uuid.uuid4().hex[:12]}")
    architecture = Column(String(50), nullable=False)  # BASELINE_A, SEQUENTIAL, PURE_BLACKBOARD, HYBRID
    prompt_style = Column(String(50), nullable=False)  # STANDARD, FEW_SHOT, REACT
    persona = Column(String(50), nullable=False)  # COST_FOCUSED, RISK_CONSCIOUS, NEUTRAL
    scenario_id = Column(String(50), nullable=False)
    seed = Column(Integer, nullable=False, default=42)
    predicted_cost_inr = Column(Float, nullable=False, default=0.0)
    realized_procurement_cost_inr = Column(Float, nullable=False, default=0.0)
    downtime_cost_inr = Column(Float, nullable=False, default=0.0)
    total_realized_cost_inr = Column(Float, nullable=False, default=0.0)
    machine_latency_ms = Column(Float, nullable=False, default=0.0)
    approval_wait_ms = Column(Float, nullable=False, default=0.0)
    tokens_used = Column(Integer, nullable=False, default=0)
    llm_cost_inr = Column(Float, nullable=False, default=0.0)
    outcome = Column(String(50), nullable=False)
    guardrail_blocks = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_engine(db_url: Optional[str] = None):
    url = db_url or DATABASE_URL
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def init_db(engine=None):
    eng = engine or get_engine()
    Base.metadata.create_all(bind=eng)
    return eng


def get_session(engine=None):
    eng = engine or get_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    return SessionLocal()
