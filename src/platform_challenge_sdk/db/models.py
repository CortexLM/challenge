"""SQLAlchemy ORM models for challenges."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import Mapped, mapped_column

from ..orm import readable_table
from .sqlalchemy_manager import get_db_manager

# Get the Base from the manager
Base = None


def get_base():
    """Get the declarative base from the database manager."""
    global Base
    if Base is None:
        Base = get_db_manager().Base
    return Base


class BaseModel(AsyncAttrs):
    """Base model with common fields."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


@readable_table(
    readable_columns=[
        "id",
        "validator_hotkey",
        "miner_hotkey",
        "block_height",
        "challenge_name",
        "challenge_version",
        "score",
        "weight",
        "status",
        "created_at",
        "started_at",
        "completed_at",
    ],
    allow_aggregations=True,
    max_rows=10000,
)
class ChallengeSubmission(BaseModel):
    """Model for challenge submissions."""

    __tablename__ = "challenge_submissions"

    # Submission metadata
    validator_hotkey: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    miner_hotkey: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    block_height: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Challenge data
    challenge_name: Mapped[str] = mapped_column(String(255), nullable=False)
    challenge_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # Submission content
    input_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    output_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Scoring
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )  # pending, processing, completed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Processing times
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


@readable_table(
    readable_columns=[
        "id",
        "miner_hotkey",
        "epoch",
        "total_submissions",
        "successful_submissions",
        "failed_submissions",
        "average_score",
        "total_weight",
        "created_at",
        "updated_at",
    ],
    allow_aggregations=True,
    max_rows=5000,
)
class MinerPerformance(BaseModel):
    """Model for tracking miner performance over time."""

    __tablename__ = "miner_performance"

    miner_hotkey: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    epoch: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Performance metrics
    total_submissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_submissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_submissions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Scores
    average_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_weight: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Additional metrics
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


@readable_table(
    readable_columns=[
        "id",
        "metric_name",
        "metric_type",
        "value",
        "window_start",
        "window_end",
        "created_at",
    ],
    allow_aggregations=True,
    max_rows=5000,
)
class ChallengeMetrics(BaseModel):
    """Model for challenge-wide metrics."""

    __tablename__ = "challenge_metrics"

    metric_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    metric_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # counter, gauge, histogram

    # Metric values
    value: Mapped[float] = mapped_column(Float, nullable=False)
    labels: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)

    # Time window
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


@readable_table(
    readable_columns=[
        "id",
        "epoch",
        "block_height",
        "total_miners",
        "active_miners",
        "submitted",
        "created_at",
        "submitted_at",
    ],
    allow_aggregations=False,
    max_rows=1000,
)
class WeightRecommendation(BaseModel):
    """Model for storing weight recommendations."""

    __tablename__ = "weight_recommendations"

    epoch: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    block_height: Mapped[int] = mapped_column(Integer, nullable=False)

    # Weight data
    weights: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)  # {hotkey: weight}

    # Metadata
    total_miners: Mapped[int] = mapped_column(Integer, nullable=False)
    active_miners: Mapped[int] = mapped_column(Integer, nullable=False)

    # Status
    submitted: Mapped[bool] = mapped_column(Integer, nullable=False, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# Helper function to create all models
def init_models():
    """Initialize all models with the correct base."""
    base = get_base()

    # Update all model classes to use the correct base
    for model_class in [
        ChallengeSubmission,
        MinerPerformance,
        ChallengeMetrics,
        WeightRecommendation,
    ]:
        # Dynamically set the base class
        model_class.__bases__ = (BaseModel, base)

    return base
