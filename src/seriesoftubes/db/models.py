"""Database models for seriesoftubes"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Base class for all database models"""

    pass


def generate_uuid() -> str:
    """Generate a new UUID"""
    return str(uuid.uuid4())


class User(Base):
    """User model"""

    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
        nullable=False,
    )
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for system user
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    workflows = relationship(
        "Workflow", back_populates="user", cascade="all, delete-orphan"
    )
    executions = relationship(
        "Execution", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(username='{self.username}', is_system={self.is_system})>"


class Workflow(Base):
    """Workflow model"""

    __tablename__ = "workflows"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
        nullable=False,
    )
    name = Column(String(255), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    package_path = Column(String(500), nullable=False)  # Path to extracted workflow
    yaml_content = Column(Text, nullable=False)  # Cached workflow.yaml content
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="workflows")
    executions = relationship(
        "Execution", back_populates="workflow", cascade="all, delete-orphan"
    )

    # Constraints
    __table_args__ = (
        UniqueConstraint(
            "name", "version", "user_id", name="uq_workflow_name_version_user"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Workflow(name='{self.name}', version='{self.version}', "
            f"user_id='{self.user_id}')>"
        )


class ExecutionStatus(enum.Enum):
    """Execution status enum"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Execution(Base):
    """Execution model"""

    __tablename__ = "executions"

    id = Column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
        nullable=False,
    )
    workflow_id = Column(
        UUID(as_uuid=False), ForeignKey("workflows.id"), nullable=False
    )
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    status = Column(
        Enum(ExecutionStatus, values_callable=lambda x: [e.value for e in x]),
        default=ExecutionStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    inputs = Column(JSON, nullable=False, default=dict)
    outputs = Column(JSON, nullable=True)
    errors = Column(JSON, nullable=True)
    started_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    workflow = relationship("Workflow", back_populates="executions")
    user = relationship("User", back_populates="executions")

    def __repr__(self) -> str:
        return (
            f"<Execution(id='{self.id}', workflow_id='{self.workflow_id}', "
            f"status='{self.status}')>"
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow.name if self.workflow else None,
            "user_id": self.user_id,
            "status": self.status
            if isinstance(self.status, str)
            else self.status.value
            if self.status
            else None,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }
