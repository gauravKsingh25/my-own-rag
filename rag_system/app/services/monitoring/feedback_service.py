"""
Feedback service for collecting and managing user feedback.

This module handles storage and retrieval of user feedback on chat interactions.
"""

import logging
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.db.models import ChatFeedback, ChatInteraction

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing chat feedback."""
    
    async def submit_feedback(
        self,
        db: AsyncSession,
        interaction_id: UUID,
        rating: int,
        comment: Optional[str] = None,
    ) -> Optional[ChatFeedback]:
        """
        Submit feedback for a chat interaction.
        
        Args:
            db: Database session
            interaction_id: ID of the chat interaction
            rating: Rating from 1-5
            comment: Optional feedback comment
            
        Returns:
            Created feedback record or None if failed
        """
        try:
            # Validate rating
            if not 1 <= rating <= 5:
                logger.error(f"Invalid rating: {rating}. Must be between 1 and 5")
                return None
            
            # Check if interaction exists
            stmt = select(ChatInteraction).where(ChatInteraction.id == interaction_id)
            result = await db.execute(stmt)
            interaction = result.scalar_one_or_none()
            
            if not interaction:
                logger.error(f"Interaction {interaction_id} not found")
                return None
            
            # Check if feedback already exists
            existing_stmt = select(ChatFeedback).where(
                ChatFeedback.interaction_id == interaction_id
            )
            existing_result = await db.execute(existing_stmt)
            existing_feedback = existing_result.scalar_one_or_none()
            
            if existing_feedback:
                # Update existing feedback
                existing_feedback.rating = rating
                existing_feedback.comment = comment
                existing_feedback.created_at = datetime.utcnow()
                feedback = existing_feedback
                logger.info(f"Updated existing feedback for interaction {interaction_id}")
            else:
                # Create new feedback
                feedback = ChatFeedback(
                    interaction_id=interaction_id,
                    rating=rating,
                    comment=comment,
                )
                db.add(feedback)
                logger.info(f"Created new feedback for interaction {interaction_id}")
            
            await db.commit()
            await db.refresh(feedback)
            
            logger.info(
                "Feedback submitted",
                extra={
                    "feedback_id": str(feedback.id),
                    "interaction_id": str(interaction_id),
                    "rating": rating,
                    "has_comment": comment is not None,
                },
            )
            
            return feedback
            
        except Exception as e:
            logger.error(f"Error submitting feedback: {str(e)}", exc_info=True)
            await db.rollback()
            return None
    
    async def get_feedback(
        self,
        db: AsyncSession,
        feedback_id: UUID,
    ) -> Optional[ChatFeedback]:
        """
        Get feedback by ID.
        
        Args:
            db: Database session
            feedback_id: Feedback identifier
            
        Returns:
            Feedback record or None if not found
        """
        try:
            stmt = select(ChatFeedback).where(ChatFeedback.id == feedback_id)
            result = await db.execute(stmt)
            feedback = result.scalar_one_or_none()
            
            if feedback:
                logger.debug(f"Retrieved feedback {feedback_id}")
            else:
                logger.warning(f"Feedback {feedback_id} not found")
            
            return feedback
            
        except Exception as e:
            logger.error(f"Error getting feedback: {str(e)}", exc_info=True)
            return None
    
    async def get_interaction_feedback(
        self,
        db: AsyncSession,
        interaction_id: UUID,
    ) -> Optional[ChatFeedback]:
        """
        Get feedback for a specific interaction.
        
        Args:
            db: Database session
            interaction_id: Chat interaction identifier
            
        Returns:
            Feedback record or None if not found
        """
        try:
            stmt = select(ChatFeedback).where(
                ChatFeedback.interaction_id == interaction_id
            )
            result = await db.execute(stmt)
            feedback = result.scalar_one_or_none()
            
            if feedback:
                logger.debug(f"Retrieved feedback for interaction {interaction_id}")
            else:
                logger.debug(f"No feedback found for interaction {interaction_id}")
            
            return feedback
            
        except Exception as e:
            logger.error(f"Error getting interaction feedback: {str(e)}", exc_info=True)
            return None
    
    async def get_user_feedbacks(
        self,
        db: AsyncSession,
        user_id: str,
        limit: int = 50,
    ) -> List[ChatFeedback]:
        """
        Get all feedbacks from a user.
        
        Args:
            db: Database session
            user_id: User identifier
            limit: Maximum number of feedbacks to return
            
        Returns:
            List of feedback records
        """
        try:
            stmt = (
                select(ChatFeedback)
                .join(ChatInteraction, ChatFeedback.interaction_id == ChatInteraction.id)
                .where(ChatInteraction.user_id == user_id)
                .order_by(ChatFeedback.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            feedbacks = result.scalars().all()
            
            logger.debug(f"Retrieved {len(feedbacks)} feedbacks for user {user_id}")
            
            return list(feedbacks)
            
        except Exception as e:
            logger.error(f"Error getting user feedbacks: {str(e)}", exc_info=True)
            return []
    
    async def get_average_rating(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> Optional[float]:
        """
        Get average rating over a time period.
        
        Args:
            db: Database session
            hours: Number of hours to look back
            
        Returns:
            Average rating or None if no feedbacks
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            stmt = select(func.avg(ChatFeedback.rating)).where(
                ChatFeedback.created_at >= cutoff_time
            )
            result = await db.execute(stmt)
            avg_rating = result.scalar()
            
            if avg_rating is not None:
                logger.info(
                    f"Average rating over {hours}h: {avg_rating:.2f}",
                    extra={
                        "hours": hours,
                        "average_rating": float(avg_rating),
                    },
                )
            
            return float(avg_rating) if avg_rating is not None else None
            
        except Exception as e:
            logger.error(f"Error getting average rating: {str(e)}", exc_info=True)
            return None
    
    async def get_rating_distribution(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> dict[int, int]:
        """
        Get distribution of ratings over a time period.
        
        Args:
            db: Database session
            hours: Number of hours to look back
            
        Returns:
            Dictionary mapping rating (1-5) to count
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            stmt = (
                select(ChatFeedback.rating, func.count(ChatFeedback.id))
                .where(ChatFeedback.created_at >= cutoff_time)
                .group_by(ChatFeedback.rating)
            )
            result = await db.execute(stmt)
            
            # Initialize all ratings to 0
            distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            
            # Update with actual counts
            for rating, count in result:
                distribution[rating] = count
            
            logger.info(
                f"Rating distribution over {hours}h",
                extra={
                    "hours": hours,
                    "distribution": distribution,
                },
            )
            
            return distribution
            
        except Exception as e:
            logger.error(f"Error getting rating distribution: {str(e)}", exc_info=True)
            return {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    
    async def get_low_rated_interactions(
        self,
        db: AsyncSession,
        threshold: int = 2,
        limit: int = 20,
    ) -> List[tuple[ChatInteraction, ChatFeedback]]:
        """
        Get interactions with low ratings for analysis.
        
        Args:
            db: Database session
            threshold: Maximum rating to include (inclusive)
            limit: Maximum number of results
            
        Returns:
            List of (interaction, feedback) tuples
        """
        try:
            stmt = (
                select(ChatInteraction, ChatFeedback)
                .join(ChatFeedback, ChatInteraction.id == ChatFeedback.interaction_id)
                .where(ChatFeedback.rating <= threshold)
                .order_by(ChatFeedback.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            pairs = result.all()
            
            logger.info(
                f"Retrieved {len(pairs)} low-rated interactions",
                extra={
                    "threshold": threshold,
                    "count": len(pairs),
                },
            )
            
            return pairs
            
        except Exception as e:
            logger.error(f"Error getting low-rated interactions: {str(e)}", exc_info=True)
            return []
    
    async def get_feedback_rate(
        self,
        db: AsyncSession,
        hours: int = 24,
    ) -> Optional[float]:
        """
        Get percentage of interactions that received feedback.
        
        Args:
            db: Database session
            hours: Number of hours to look back
            
        Returns:
            Feedback rate (0-1) or None if no interactions
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            # Count total interactions
            interactions_stmt = select(func.count(ChatInteraction.id)).where(
                ChatInteraction.created_at >= cutoff_time
            )
            interactions_result = await db.execute(interactions_stmt)
            total_interactions = interactions_result.scalar()
            
            if not total_interactions:
                return None
            
            # Count feedbacks
            feedbacks_stmt = (
                select(func.count(ChatFeedback.id))
                .join(ChatInteraction, ChatFeedback.interaction_id == ChatInteraction.id)
                .where(ChatInteraction.created_at >= cutoff_time)
            )
            feedbacks_result = await db.execute(feedbacks_stmt)
            total_feedbacks = feedbacks_result.scalar()
            
            feedback_rate = total_feedbacks / total_interactions
            
            logger.info(
                f"Feedback rate over {hours}h: {feedback_rate:.2%}",
                extra={
                    "hours": hours,
                    "total_interactions": total_interactions,
                    "total_feedbacks": total_feedbacks,
                    "feedback_rate": feedback_rate,
                },
            )
            
            return feedback_rate
            
        except Exception as e:
            logger.error(f"Error getting feedback rate: {str(e)}", exc_info=True)
            return None
