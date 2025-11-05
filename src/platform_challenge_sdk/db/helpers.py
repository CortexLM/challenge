"""SQLAlchemy database helpers for challenge SDK."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import (
    ChallengeMetrics,
    ChallengeSubmission,
    MinerPerformance,
    WeightRecommendation,
)
from .sqlalchemy_manager import get_db_manager


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session from the global manager."""
    manager = get_db_manager()
    async with manager.get_session() as session:
        yield session


class ChallengeSubmissionHelper:
    """Helper class for ChallengeSubmission operations."""

    @staticmethod
    async def create(
        validator_hotkey: str,
        miner_hotkey: str,
        block_height: int,
        challenge_name: str,
        challenge_version: str,
        input_data: dict,
    ) -> ChallengeSubmission:
        """Create a new challenge submission."""
        async with get_db_session() as session:
            submission = ChallengeSubmission(
                validator_hotkey=validator_hotkey,
                miner_hotkey=miner_hotkey,
                block_height=block_height,
                challenge_name=challenge_name,
                challenge_version=challenge_version,
                input_data=input_data,
                status="pending",
            )
            session.add(submission)
            await session.commit()
            await session.refresh(submission)
            return submission

    @staticmethod
    async def get_by_id(submission_id: int) -> ChallengeSubmission | None:
        """Get a submission by ID."""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChallengeSubmission).where(ChallengeSubmission.id == submission_id)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def update_result(
        submission_id: int,
        output_data: dict,
        score: float,
        weight: float,
        status: str = "completed",
    ) -> ChallengeSubmission | None:
        """Update submission with results."""
        async with get_db_session() as session:
            result = await session.execute(
                update(ChallengeSubmission)
                .where(ChallengeSubmission.id == submission_id)
                .values(
                    output_data=output_data,
                    score=score,
                    weight=weight,
                    status=status,
                    completed_at=func.now(),
                )
                .returning(ChallengeSubmission)
            )
            await session.commit()
            return result.scalar_one_or_none()

    @staticmethod
    async def get_pending_submissions(limit: int = 10) -> list[ChallengeSubmission]:
        """Get pending submissions."""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChallengeSubmission)
                .where(ChallengeSubmission.status == "pending")
                .order_by(ChallengeSubmission.created_at)
                .limit(limit)
            )
            return list(result.scalars().all())


class MinerPerformanceHelper:
    """Helper class for MinerPerformance operations."""

    @staticmethod
    async def update_performance(
        miner_hotkey: str,
        epoch: int,
        submission_count: int = 1,
        success: bool = True,
        score: float | None = None,
        weight: float | None = None,
    ) -> MinerPerformance:
        """Update or create miner performance record."""
        async with get_db_session() as session:
            # Try to get existing record
            result = await session.execute(
                select(MinerPerformance).where(
                    MinerPerformance.miner_hotkey == miner_hotkey,
                    MinerPerformance.epoch == epoch,
                )
            )
            performance = result.scalar_one_or_none()

            if performance:
                # Update existing
                performance.total_submissions += submission_count
                if success:
                    performance.successful_submissions += submission_count
                else:
                    performance.failed_submissions += submission_count

                # Update scores
                if score is not None:
                    if performance.average_score is None:
                        performance.average_score = score
                    else:
                        # Calculate new average
                        total = performance.successful_submissions
                        performance.average_score = (
                            performance.average_score * (total - submission_count) + score
                        ) / total

                if weight is not None:
                    performance.total_weight = (performance.total_weight or 0) + weight
            else:
                # Create new
                performance = MinerPerformance(
                    miner_hotkey=miner_hotkey,
                    epoch=epoch,
                    total_submissions=submission_count,
                    successful_submissions=submission_count if success else 0,
                    failed_submissions=submission_count if not success else 0,
                    average_score=score,
                    total_weight=weight,
                )
                session.add(performance)

            await session.commit()
            await session.refresh(performance)
            return performance

    @staticmethod
    async def get_epoch_performance(epoch: int) -> list[MinerPerformance]:
        """Get all miner performance records for an epoch."""
        async with get_db_session() as session:
            result = await session.execute(
                select(MinerPerformance)
                .where(MinerPerformance.epoch == epoch)
                .order_by(MinerPerformance.total_weight.desc())
            )
            return list(result.scalars().all())


class WeightRecommendationHelper:
    """Helper class for WeightRecommendation operations."""

    @staticmethod
    async def create_recommendation(
        epoch: int,
        block_height: int,
        weights: dict[str, float],
    ) -> WeightRecommendation:
        """Create a new weight recommendation."""
        async with get_db_session() as session:
            # Count active miners (those with non-zero weights)
            active_miners = sum(1 for w in weights.values() if w > 0)

            recommendation = WeightRecommendation(
                epoch=epoch,
                block_height=block_height,
                weights=weights,
                total_miners=len(weights),
                active_miners=active_miners,
                submitted=False,
            )
            session.add(recommendation)
            await session.commit()
            await session.refresh(recommendation)
            return recommendation

    @staticmethod
    async def get_latest_recommendation() -> WeightRecommendation | None:
        """Get the latest weight recommendation."""
        async with get_db_session() as session:
            result = await session.execute(
                select(WeightRecommendation)
                .order_by(WeightRecommendation.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    @staticmethod
    async def mark_submitted(recommendation_id: int) -> WeightRecommendation | None:
        """Mark a recommendation as submitted."""
        async with get_db_session() as session:
            result = await session.execute(
                update(WeightRecommendation)
                .where(WeightRecommendation.id == recommendation_id)
                .values(submitted=True, submitted_at=func.now())
                .returning(WeightRecommendation)
            )
            await session.commit()
            return result.scalar_one_or_none()


class ChallengeMetricsHelper:
    """Helper class for ChallengeMetrics operations."""

    @staticmethod
    async def record_metric(
        metric_name: str,
        metric_type: str,
        value: float,
        labels: dict[str, str] | None = None,
        window_minutes: int = 60,
    ) -> ChallengeMetrics:
        """Record a metric value."""
        from datetime import datetime, timedelta

        async with get_db_session() as session:
            now = datetime.utcnow()
            window_start = now - timedelta(minutes=window_minutes)

            metric = ChallengeMetrics(
                metric_name=metric_name,
                metric_type=metric_type,
                value=value,
                labels=labels or {},
                window_start=window_start,
                window_end=now,
            )
            session.add(metric)
            await session.commit()
            await session.refresh(metric)
            return metric

    @staticmethod
    async def get_recent_metrics(
        metric_name: str,
        hours: int = 24,
        limit: int = 100,
    ) -> list[ChallengeMetrics]:
        """Get recent metrics by name."""
        from datetime import datetime, timedelta

        async with get_db_session() as session:
            since = datetime.utcnow() - timedelta(hours=hours)
            result = await session.execute(
                select(ChallengeMetrics)
                .where(
                    ChallengeMetrics.metric_name == metric_name,
                    ChallengeMetrics.created_at >= since,
                )
                .order_by(ChallengeMetrics.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
