"""
Metrics collection service for monitoring RAG system performance.

This module provides metrics collection and aggregation for the RAG pipeline.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models import ChatInteraction, ChatFeedback

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """Latency breakdown for a chat request."""
    
    total_ms: float
    retrieval_ms: Optional[float] = None
    prompt_building_ms: Optional[float] = None
    generation_ms: Optional[float] = None
    validation_ms: Optional[float] = None
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "total_ms": self.total_ms,
            "retrieval_ms": self.retrieval_ms,
            "prompt_building_ms": self.prompt_building_ms,
            "generation_ms": self.generation_ms,
            "validation_ms": self.validation_ms,
        }


@dataclass
class TokenMetrics:
    """Token usage metrics."""
    
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class QualityMetrics:
    """Quality metrics for generated answers."""
    
    confidence_score: float
    citations_count: int
    has_hallucinations: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "confidence_score": self.confidence_score,
            "citations_count": self.citations_count,
            "has_hallucinations": self.has_hallucinations,
        }


@dataclass
class InteractionMetrics:
    """Complete metrics for a chat interaction."""
    
    interaction_id: str
    user_id: str
    query: str
    latency: LatencyMetrics
    tokens: TokenMetrics
    quality: QualityMetrics
    cost: float
    model_name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "interaction_id": self.interaction_id,
            "user_id": self.user_id,
            "query": self.query,
            "latency": self.latency.to_dict(),
            "tokens": self.tokens.to_dict(),
            "quality": self.quality.to_dict(),
            "cost": self.cost,
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
        }


class MetricsCollector:
    """Service for collecting and aggregating system metrics."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.current_metrics: List[InteractionMetrics] = []
    
    def record_interaction(self, metrics: InteractionMetrics) -> None:
        """
        Record metrics for a chat interaction.
        
        Args:
            metrics: Interaction metrics to record
        """
        self.current_metrics.append(metrics)
        
        logger.info(
            "Interaction metrics recorded",
            extra={
                "interaction_id": metrics.interaction_id,
                "user_id": metrics.user_id,
                "total_latency_ms": metrics.latency.total_ms,
                "total_tokens": metrics.tokens.total_tokens,
                "confidence_score": metrics.quality.confidence_score,
                "cost": metrics.cost,
            },
        )
    
    async def get_user_statistics(
        self,
        db: AsyncSession,
        user_id: str,
        hours: int = 24,
    ) -> Dict:
        """
        Get user-specific statistics.
        
        Args:
            db: Database session
            user_id: User identifier
            hours: Number of hours to look back
            
        Returns:
            Dictionary with user statistics
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Query interactions
            stmt = select(ChatInteraction).where(
                ChatInteraction.user_id == user_id,
                ChatInteraction.created_at >= cutoff_time,
            )
            result = await db.execute(stmt)
            interactions = result.scalars().all()
            
            if not interactions:
                return {
                    "user_id": user_id,
                    "period_hours": hours,
                    "total_requests": 0,
                }
            
            # Calculate statistics
            total_requests = len(interactions)
            total_cost = sum(i.cost_estimate or 0 for i in interactions)
            avg_latency = sum(i.latency_ms for i in interactions) / total_requests
            avg_confidence = sum(i.confidence_score for i in interactions) / total_requests
            total_tokens = sum(i.total_tokens or 0 for i in interactions)
            
            stats = {
                "user_id": user_id,
                "period_hours": hours,
                "total_requests": total_requests,
                "total_cost": total_cost,
                "average_latency_ms": avg_latency,
                "average_confidence": avg_confidence,
                "total_tokens": total_tokens,
            }
            
            logger.info(f"User statistics calculated for {user_id}", extra=stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting user statistics: {str(e)}", exc_info=True)
            return {}
    
    async def get_system_statistics(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> Dict:
        """
        Get system-wide statistics.
        
        Args:
            db: Database session
            hours: Number of hours to look back
            
        Returns:
            Dictionary with system statistics
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Query interactions
            stmt = select(ChatInteraction).where(
                ChatInteraction.created_at >= cutoff_time,
            )
            result = await db.execute(stmt)
            interactions = result.scalars().all()
            
            if not interactions:
                return {
                    "period_hours": hours,
                    "total_requests": 0,
                }
            
            # Calculate statistics
            total_requests = len(interactions)
            total_cost = sum(i.cost_estimate or 0 for i in interactions)
            avg_latency = sum(i.latency_ms for i in interactions) / total_requests
            avg_confidence = sum(i.confidence_score for i in interactions) / total_requests
            total_tokens = sum(i.total_tokens or 0 for i in interactions)
            
            # Get unique users
            unique_users = len(set(i.user_id for i in interactions))
            
            # Get feedback statistics
            feedback_stmt = select(ChatFeedback).join(
                ChatInteraction,
                ChatFeedback.interaction_id == ChatInteraction.id,
            ).where(
                ChatInteraction.created_at >= cutoff_time,
            )
            feedback_result = await db.execute(feedback_stmt)
            feedbacks = feedback_result.scalars().all()
            
            feedback_stats = {}
            if feedbacks:
                avg_rating = sum(f.rating for f in feedbacks) / len(feedbacks)
                feedback_stats = {
                    "total_feedbacks": len(feedbacks),
                    "average_rating": avg_rating,
                    "feedback_rate": len(feedbacks) / total_requests,
                }
            
            stats = {
                "period_hours": hours,
                "total_requests": total_requests,
                "unique_users": unique_users,
                "total_cost": total_cost,
                "average_latency_ms": avg_latency,
                "average_confidence": avg_confidence,
                "total_tokens": total_tokens,
                **feedback_stats,
            }
            
            logger.info("System statistics calculated", extra=stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting system statistics: {str(e)}", exc_info=True)
            return {}
    
    async def get_confidence_distribution(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> Dict[str, int]:
        """
        Get distribution of confidence scores.
        
        Args:
            db: Database session
            hours: Number of hours to look back
            
        Returns:
            Dictionary with confidence score distribution
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Query interactions
            stmt = select(ChatInteraction.confidence_score).where(
                ChatInteraction.created_at >= cutoff_time,
            )
            result = await db.execute(stmt)
            scores = result.scalars().all()
            
            if not scores:
                return {}
            
            # Bucket scores (0-0.5, 0.5-0.7, 0.7-0.85, 0.85-1.0)
            distribution = {
                "very_low (0.0-0.5)": sum(1 for s in scores if 0 <= s < 0.5),
                "low (0.5-0.7)": sum(1 for s in scores if 0.5 <= s < 0.7),
                "medium (0.7-0.85)": sum(1 for s in scores if 0.7 <= s < 0.85),
                "high (0.85-1.0)": sum(1 for s in scores if 0.85 <= s <= 1.0),
            }
            
            logger.info("Confidence distribution calculated", extra=distribution)
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error getting confidence distribution: {str(e)}", exc_info=True)
            return {}
    
    async def get_latency_percentiles(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> Dict[str, float]:
        """
        Get latency percentiles.
        
        Args:
            db: Database session
            hours: Number of hours to look back
            
        Returns:
            Dictionary with latency percentiles
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Query latencies
            stmt = select(ChatInteraction.latency_ms).where(
                ChatInteraction.created_at >= cutoff_time,
            )
            result = await db.execute(stmt)
            latencies = sorted(result.scalars().all())
            
            if not latencies:
                return {}
            
            # Calculate percentiles
            def percentile(data: List[float], p: float) -> float:
                k = (len(data) - 1) * p
                f = int(k)
                c = f + 1
                if c >= len(data):
                    return data[-1]
                return data[f] + (k - f) * (data[c] - data[f])
            
            percentiles = {
                "p50": percentile(latencies, 0.50),
                "p75": percentile(latencies, 0.75),
                "p90": percentile(latencies, 0.90),
                "p95": percentile(latencies, 0.95),
                "p99": percentile(latencies, 0.99),
                "min": latencies[0],
                "max": latencies[-1],
            }
            
            logger.info("Latency percentiles calculated", extra=percentiles)
            
            return percentiles
            
        except Exception as e:
            logger.error(f"Error getting latency percentiles: {str(e)}", exc_info=True)
            return {}


class PerformanceMonitor:
    """Context manager for monitoring performance of operations."""
    
    def __init__(self, operation_name: str):
        """
        Initialize performance monitor.
        
        Args:
            operation_name: Name of the operation being monitored
        """
        self.operation_name = operation_name
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
    
    def __enter__(self):
        """Start monitoring."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop monitoring and log duration."""
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        if exc_type is None:
            logger.info(
                f"{self.operation_name} completed",
                extra={
                    "operation": self.operation_name,
                    "duration_ms": duration_ms,
                },
            )
        else:
            logger.error(
                f"{self.operation_name} failed",
                extra={
                    "operation": self.operation_name,
                    "duration_ms": duration_ms,
                    "error": str(exc_val),
                },
            )
    
    def get_duration_ms(self) -> Optional[float]:
        """Get duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None
