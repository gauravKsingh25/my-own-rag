"""
Quota management service for tracking daily usage limits.

This module tracks token usage and costs per user to enforce daily quotas.
"""

import logging
from typing import Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models import ChatInteraction
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class QuotaStatus:
    """Current quota status for a user."""
    
    tokens_used: int
    tokens_limit: int
    tokens_remaining: int
    cost_used: float
    cost_limit: float
    cost_remaining: float
    quota_exceeded: bool
    reset_time: datetime


class QuotaManager:
    """
    Manage daily quota limits for users.
    
    Tracks token usage and costs from ChatInteraction records.
    Enforces configurable daily limits to prevent abuse.
    """
    
    def __init__(
        self,
        daily_token_limit: Optional[int] = None,
        daily_cost_limit: Optional[float] = None,
    ):
        """
        Initialize quota manager.
        
        Args:
            daily_token_limit: Maximum tokens per user per day
            daily_cost_limit: Maximum cost (USD) per user per day
        """
        self.daily_token_limit = daily_token_limit or getattr(
            settings, 'DAILY_TOKEN_LIMIT', 1_000_000
        )
        self.daily_cost_limit = daily_cost_limit or getattr(
            settings, 'DAILY_COST_LIMIT', 10.0
        )
        
        logger.info(
            "QuotaManager initialized",
            extra={
                "daily_token_limit": self.daily_token_limit,
                "daily_cost_limit": self.daily_cost_limit,
            },
        )
    
    def _get_reset_time(self) -> datetime:
        """
        Get quota reset time (midnight UTC).
        
        Returns:
            Datetime of next quota reset
        """
        now = datetime.utcnow()
        tomorrow = now + timedelta(days=1)
        reset_time = datetime(
            tomorrow.year,
            tomorrow.month,
            tomorrow.day,
            0, 0, 0
        )
        return reset_time
    
    async def check_quota(
        self,
        db: AsyncSession,
        user_id: str,
    ) -> QuotaStatus:
        """
        Check current quota status for a user.
        
        Queries ChatInteraction records from today to calculate:
        - Total tokens used
        - Total cost incurred
        - Remaining quota
        
        Args:
            db: Database session
            user_id: User identifier
            
        Returns:
            QuotaStatus with current usage and limits
        """
        try:
            # Get start of today (UTC)
            now = datetime.utcnow()
            start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)
            
            # Query today's usage
            stmt = select(
                func.coalesce(func.sum(ChatInteraction.total_tokens), 0).label('total_tokens'),
                func.coalesce(func.sum(ChatInteraction.cost_estimate), 0.0).label('total_cost'),
            ).where(
                ChatInteraction.user_id == user_id,
                ChatInteraction.created_at >= start_of_day,
            )
            
            result = await db.execute(stmt)
            row = result.first()
            
            tokens_used = int(row.total_tokens) if row else 0
            cost_used = float(row.total_cost) if row else 0.0
            
            # Calculate remaining quota
            tokens_remaining = max(0, self.daily_token_limit - tokens_used)
            cost_remaining = max(0.0, self.daily_cost_limit - cost_used)
            
            # Check if quota exceeded
            quota_exceeded = (
                tokens_used >= self.daily_token_limit or
                cost_used >= self.daily_cost_limit
            )
            
            reset_time = self._get_reset_time()
            
            status = QuotaStatus(
                tokens_used=tokens_used,
                tokens_limit=self.daily_token_limit,
                tokens_remaining=tokens_remaining,
                cost_used=cost_used,
                cost_limit=self.daily_cost_limit,
                cost_remaining=cost_remaining,
                quota_exceeded=quota_exceeded,
                reset_time=reset_time,
            )
            
            if quota_exceeded:
                logger.warning(
                    f"Daily quota exceeded for user {user_id}",
                    extra={
                        "user_id": user_id,
                        "tokens_used": tokens_used,
                        "tokens_limit": self.daily_token_limit,
                        "cost_used": cost_used,
                        "cost_limit": self.daily_cost_limit,
                        "reset_time": reset_time.isoformat(),
                    },
                )
            else:
                logger.debug(
                    f"Quota check passed",
                    extra={
                        "user_id": user_id,
                        "tokens_remaining": tokens_remaining,
                        "cost_remaining": cost_remaining,
                    },
                )
            
            return status
            
        except Exception as e:
            logger.error(
                f"Quota check failed: {str(e)}",
                extra={
                    "user_id": user_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            
            # Fail open - allow request if quota check fails
            reset_time = self._get_reset_time()
            return QuotaStatus(
                tokens_used=0,
                tokens_limit=self.daily_token_limit,
                tokens_remaining=self.daily_token_limit,
                cost_used=0.0,
                cost_limit=self.daily_cost_limit,
                cost_remaining=self.daily_cost_limit,
                quota_exceeded=False,
                reset_time=reset_time,
            )
    
    async def get_usage_stats(
        self,
        db: AsyncSession,
        user_id: str,
        days: int = 7,
    ) -> Dict:
        """
        Get usage statistics for a user over multiple days.
        
        Args:
            db: Database session
            user_id: User identifier
            days: Number of days to look back
            
        Returns:
            Dictionary with daily usage breakdown
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(days=days)
            
            stmt = select(
                func.date(ChatInteraction.created_at).label('date'),
                func.count(ChatInteraction.id).label('request_count'),
                func.sum(ChatInteraction.total_tokens).label('total_tokens'),
                func.sum(ChatInteraction.cost_estimate).label('total_cost'),
            ).where(
                ChatInteraction.user_id == user_id,
                ChatInteraction.created_at >= cutoff_time,
            ).group_by(
                func.date(ChatInteraction.created_at)
            ).order_by(
                func.date(ChatInteraction.created_at).desc()
            )
            
            result = await db.execute(stmt)
            rows = result.all()
            
            daily_usage = []
            for row in rows:
                daily_usage.append({
                    "date": row.date.isoformat(),
                    "request_count": row.request_count,
                    "total_tokens": int(row.total_tokens or 0),
                    "total_cost": float(row.total_cost or 0.0),
                    "tokens_limit": self.daily_token_limit,
                    "cost_limit": self.daily_cost_limit,
                })
            
            stats = {
                "user_id": user_id,
                "days": days,
                "daily_usage": daily_usage,
                "current_limits": {
                    "daily_token_limit": self.daily_token_limit,
                    "daily_cost_limit": self.daily_cost_limit,
                },
            }
            
            logger.info(
                f"Usage stats retrieved for user {user_id}",
                extra={
                    "user_id": user_id,
                    "days": days,
                    "records": len(daily_usage),
                },
            )
            
            return stats
            
        except Exception as e:
            logger.error(
                f"Failed to get usage stats: {str(e)}",
                extra={
                    "user_id": user_id,
                    "days": days,
                },
                exc_info=True,
            )
            return {}
    
    async def get_top_users(
        self,
        db: AsyncSession,
        limit: int = 10,
        hours: int = 24,
    ) -> list:
        """
        Get top users by token usage or cost.
        
        Args:
            db: Database session
            limit: Number of top users to return
            hours: Time window in hours
            
        Returns:
            List of top users with usage stats
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            stmt = select(
                ChatInteraction.user_id,
                func.count(ChatInteraction.id).label('request_count'),
                func.sum(ChatInteraction.total_tokens).label('total_tokens'),
                func.sum(ChatInteraction.cost_estimate).label('total_cost'),
            ).where(
                ChatInteraction.created_at >= cutoff_time,
            ).group_by(
                ChatInteraction.user_id
            ).order_by(
                func.sum(ChatInteraction.total_tokens).desc()
            ).limit(limit)
            
            result = await db.execute(stmt)
            rows = result.all()
            
            top_users = []
            for row in rows:
                top_users.append({
                    "user_id": row.user_id,
                    "request_count": row.request_count,
                    "total_tokens": int(row.total_tokens or 0),
                    "total_cost": float(row.total_cost or 0.0),
                })
            
            logger.info(
                f"Top users retrieved",
                extra={
                    "limit": limit,
                    "hours": hours,
                    "count": len(top_users),
                },
            )
            
            return top_users
            
        except Exception as e:
            logger.error(
                f"Failed to get top users: {str(e)}",
                extra={"limit": limit, "hours": hours},
                exc_info=True,
            )
            return []
    
    def estimate_request_cost(
        self,
        estimated_tokens: int,
        estimated_cost: float,
    ) -> bool:
        """
        Estimate if a request would exceed quota.
        
        Args:
            estimated_tokens: Estimated tokens for request
            estimated_cost: Estimated cost for request
            
        Returns:
            True if request is within quota estimates
        """
        # Conservative estimate - assume 50% of daily limit per request is too much
        tokens_ok = estimated_tokens < (self.daily_token_limit * 0.5)
        cost_ok = estimated_cost < (self.daily_cost_limit * 0.5)
        
        return tokens_ok and cost_ok
