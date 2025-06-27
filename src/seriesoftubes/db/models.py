"""Database models for seriesoftubes"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all database models"""

    pass


def generate_uuid() -> str:
    """Generate a new UUID"""
    return str(uuid.uuid4())


class User(Base):
    """User model"""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    password_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # Nullable for system user
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    workflows: Mapped[list["Workflow"]] = relationship(
        "Workflow", back_populates="user", cascade="all, delete-orphan"
    )
    executions: Mapped[list["Execution"]] = relationship(
        "Execution", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(username='{self.username}', is_system={self.is_system})>"


class Workflow(Base):
    """Workflow model"""

    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    name: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    package_path: Mapped[str] = mapped_column(String(500))  # Path to extracted workflow
    yaml_content: Mapped[str] = mapped_column(Text)  # Cached workflow.yaml content
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="workflows")
    executions: Mapped[list["Execution"]] = relationship(
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
    CANCELLED = "cancelled"


class Execution(Base):
    """Execution model"""

    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=generate_uuid,
    )
    workflow_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("workflows.id")
    )
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(
        Enum(ExecutionStatus, values_callable=lambda x: [e.value for e in x]),
        default=ExecutionStatus.PENDING.value,
        index=True,
    )
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    outputs: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    errors: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    progress: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="executions")
    user: Mapped["User"] = relationship("User", back_populates="executions")

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
            "status": (
                self.status
                if isinstance(self.status, str)
                else self.status.value if self.status else None
            ),
            "inputs": self.inputs,
            "outputs": self.outputs,
            "errors": self.errors,
            "progress": self.progress,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }
