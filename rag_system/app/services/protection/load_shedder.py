"""
Load shedding service for graceful degradation under high load.

This module detects system stress and gracefully reduces quality to maintain availability.
"""

import logging
import time
import psutil
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LoadLevel(str, Enum):
    """System load levels."""
    
    NORMAL = "normal"  # Normal operation
    ELEVATED = "elevated"  # Slight degradation
    HIGH = "high"  # Moderate degradation
    CRITICAL = "critical"  # Maximum degradation


@dataclass
class DegradationConfig:
    """Configuration for degraded mode."""
    
    # Retrieval parameters
    top_k: int
    enable_mmr: bool
    
    # Generation parameters
    max_output_tokens: int
    temperature: float
    
    # Timeouts
    retrieval_timeout: float
    generation_timeout: float


@dataclass
class LoadMetrics:
    """Current system load metrics."""
    
    cpu_percent: float
    memory_percent: float
    load_level: LoadLevel
    degraded: bool
    degradation_config: Optional[DegradationConfig] = None


class LoadShedder:
    """
    Load shedding service for graceful degradation.
    
    Monitors system resources and adjusts parameters to maintain
    availability under high load conditions.
    
    Degradation strategy:
    1. NORMAL: Full quality
    2. ELEVATED: Reduce top_k slightly
    3. HIGH: Reduce top_k, skip MMR, reduce output tokens
    4. CRITICAL: Minimal retrieval, minimal generation
    """
    
    def __init__(
        self,
        cpu_threshold_elevated: float = 70.0,
        cpu_threshold_high: float = 85.0,
        cpu_threshold_critical: float = 95.0,
        memory_threshold_elevated: float = 75.0,
        memory_threshold_high: float = 90.0,
        memory_threshold_critical: float = 95.0,
    ):
        """
        Initialize load shedder.
        
        Args:
            cpu_threshold_elevated: CPU % for elevated load
            cpu_threshold_high: CPU % for high load
            cpu_threshold_critical: CPU % for critical load
            memory_threshold_elevated: Memory % for elevated load
            memory_threshold_high: Memory % for high load
            memory_threshold_critical: Memory % for critical load
        """
        self.cpu_threshold_elevated = cpu_threshold_elevated
        self.cpu_threshold_high = cpu_threshold_high
        self.cpu_threshold_critical = cpu_threshold_critical
        self.memory_threshold_elevated = memory_threshold_elevated
        self.memory_threshold_high = memory_threshold_high
        self.memory_threshold_critical = memory_threshold_critical
        
        # Track degradation history for hysteresis
        self.degradation_start_time: Optional[float] = None
        self.current_load_level = LoadLevel.NORMAL
        
        logger.info(
            "LoadShedder initialized",
            extra={
                "cpu_thresholds": {
                    "elevated": cpu_threshold_elevated,
                    "high": cpu_threshold_high,
                    "critical": cpu_threshold_critical,
                },
                "memory_thresholds": {
                    "elevated": memory_threshold_elevated,
                    "high": memory_threshold_high,
                    "critical": memory_threshold_critical,
                },
            },
        )
    
    def _get_system_metrics(self) -> tuple[float, float]:
        """
        Get current system metrics.
        
        Returns:
            Tuple of (cpu_percent, memory_percent)
        """
        try:
            # Get CPU percentage (1 second interval for accuracy)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Get memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            return cpu_percent, memory_percent
            
        except Exception as e:
            logger.error(
                f"Failed to get system metrics: {str(e)}",
                exc_info=True,
            )
            # Return normal values on error
            return 0.0, 0.0
    
    def _determine_load_level(
        self,
        cpu_percent: float,
        memory_percent: float,
    ) -> LoadLevel:
        """
        Determine current load level based on metrics.
        
        Args:
            cpu_percent: Current CPU usage percentage
            memory_percent: Current memory usage percentage
            
        Returns:
            LoadLevel indicating system stress
        """
        # Use the worse of CPU or memory metrics
        max_metric = max(cpu_percent, memory_percent)
        
        if max_metric >= self.cpu_threshold_critical or max_metric >= self.memory_threshold_critical:
            return LoadLevel.CRITICAL
        elif max_metric >= self.cpu_threshold_high or max_metric >= self.memory_threshold_high:
            return LoadLevel.HIGH
        elif max_metric >= self.cpu_threshold_elevated or max_metric >= self.memory_threshold_elevated:
            return LoadLevel.ELEVATED
        else:
            return LoadLevel.NORMAL
    
    def _get_degradation_config(
        self,
        load_level: LoadLevel,
        original_top_k: int = 5,
        original_max_tokens: int = 2048,
    ) -> DegradationConfig:
        """
        Get degradation configuration for load level.
        
        Args:
            load_level: Current load level
            original_top_k: Original top_k parameter
            original_max_tokens: Original max output tokens
            
        Returns:
            DegradationConfig with adjusted parameters
        """
        if load_level == LoadLevel.CRITICAL:
            return DegradationConfig(
                top_k=2,  # Minimal retrieval
                enable_mmr=False,  # Skip diversification
                max_output_tokens=512,  # Very short answers
                temperature=0.3,  # More deterministic
                retrieval_timeout=5.0,  # Short timeout
                generation_timeout=10.0,  # Short timeout
            )
        
        elif load_level == LoadLevel.HIGH:
            return DegradationConfig(
                top_k=max(3, original_top_k // 2),  # Half retrieval
                enable_mmr=False,  # Skip diversification
                max_output_tokens=1024,  # Shorter answers
                temperature=0.5,  # Slightly more deterministic
                retrieval_timeout=10.0,
                generation_timeout=20.0,
            )
        
        elif load_level == LoadLevel.ELEVATED:
            return DegradationConfig(
                top_k=max(4, int(original_top_k * 0.75)),  # 75% retrieval
                enable_mmr=True,  # Keep MMR
                max_output_tokens=int(original_max_tokens * 0.75),  # 75% tokens
                temperature=0.7,
                retrieval_timeout=15.0,
                generation_timeout=30.0,
            )
        
        else:  # NORMAL
            return DegradationConfig(
                top_k=original_top_k,
                enable_mmr=True,
                max_output_tokens=original_max_tokens,
                temperature=0.7,
                retrieval_timeout=30.0,
                generation_timeout=60.0,
            )
    
    def check_load(
        self,
        original_top_k: int = 5,
        original_max_tokens: int = 2048,
    ) -> LoadMetrics:
        """
        Check current system load and get degradation config.
        
        Args:
            original_top_k: Original top_k parameter
            original_max_tokens: Original max output tokens
            
        Returns:
            LoadMetrics with current load and degradation config
        """
        try:
            # Get system metrics
            cpu_percent, memory_percent = self._get_system_metrics()
            
            # Determine load level
            load_level = self._determine_load_level(cpu_percent, memory_percent)
            
            # Track degradation state changes
            if load_level != self.current_load_level:
                if load_level != LoadLevel.NORMAL:
                    if self.degradation_start_time is None:
                        self.degradation_start_time = time.time()
                    
                    logger.warning(
                        f"Load level changed: {self.current_load_level.value} -> {load_level.value}",
                        extra={
                            "previous_level": self.current_load_level.value,
                            "new_level": load_level.value,
                            "cpu_percent": cpu_percent,
                            "memory_percent": memory_percent,
                        },
                    )
                else:
                    if self.degradation_start_time:
                        duration = time.time() - self.degradation_start_time
                        logger.info(
                            f"System returned to normal load",
                            extra={
                                "degradation_duration": duration,
                                "cpu_percent": cpu_percent,
                                "memory_percent": memory_percent,
                            },
                        )
                        self.degradation_start_time = None
                
                self.current_load_level = load_level
            
            # Get degradation config
            degradation_config = self._get_degradation_config(
                load_level,
                original_top_k,
                original_max_tokens,
            )
            
            metrics = LoadMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                load_level=load_level,
                degraded=(load_level != LoadLevel.NORMAL),
                degradation_config=degradation_config,
            )
            
            if metrics.degraded:
                logger.info(
                    "System under load - degraded mode active",
                    extra={
                        "load_level": load_level.value,
                        "cpu_percent": cpu_percent,
                        "memory_percent": memory_percent,
                        "top_k": degradation_config.top_k,
                        "max_output_tokens": degradation_config.max_output_tokens,
                        "enable_mmr": degradation_config.enable_mmr,
                    },
                )
            
            return metrics
            
        except Exception as e:
            logger.error(
                f"Load check failed: {str(e)}",
                exc_info=True,
            )
            
            # Return normal metrics on error
            return LoadMetrics(
                cpu_percent=0.0,
                memory_percent=0.0,
                load_level=LoadLevel.NORMAL,
                degraded=False,
                degradation_config=self._get_degradation_config(LoadLevel.NORMAL),
            )
    
    def get_status(self) -> Dict:
        """
        Get current load shedder status.
        
        Returns:
            Dictionary with status information
        """
        cpu_percent, memory_percent = self._get_system_metrics()
        load_level = self._determine_load_level(cpu_percent, memory_percent)
        
        status = {
            "current_load_level": load_level.value,
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "degraded": load_level != LoadLevel.NORMAL,
            "degradation_duration": (
                time.time() - self.degradation_start_time
                if self.degradation_start_time
                else None
            ),
            "thresholds": {
                "cpu": {
                    "elevated": self.cpu_threshold_elevated,
                    "high": self.cpu_threshold_high,
                    "critical": self.cpu_threshold_critical,
                },
                "memory": {
                    "elevated": self.memory_threshold_elevated,
                    "high": self.memory_threshold_high,
                    "critical": self.memory_threshold_critical,
                },
            },
        }
        
        return status
