#!/usr/bin/env python3
"""
GPU Performance Monitor for Camera Detection System

Monitors GPU memory usage, performance metrics, and system limits.
Provides logging and alerting for VRAM usage with BLIP-2 T5-XL.
"""

import torch
import psutil
import time
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from datetime import datetime
import threading
import queue

logger = logging.getLogger(__name__)

@dataclass
class GPUMetrics:
    """GPU performance metrics at a point in time."""
    timestamp: datetime
    gpu_name: str
    total_memory_gb: float
    allocated_memory_gb: float
    reserved_memory_gb: float
    free_memory_gb: float
    memory_utilization_pct: float
    gpu_utilization_pct: Optional[float]
    temperature_c: Optional[float]
    power_usage_w: Optional[float]

class GPUMonitor:
    """Monitors GPU performance and memory usage."""
    
    def __init__(self, warning_threshold_pct: float = 85.0, critical_threshold_pct: float = 95.0):
        """
        Initialize GPU monitor.
        
        Args:
            warning_threshold_pct: Warning threshold for memory usage (%)
            critical_threshold_pct: Critical threshold for memory usage (%)
        """
        self.warning_threshold = warning_threshold_pct
        self.critical_threshold = critical_threshold_pct
        self.monitoring = False
        self.metrics_history: List[GPUMetrics] = []
        self.monitor_thread: Optional[threading.Thread] = None
        self.metrics_queue = queue.Queue()
        
        # Check if CUDA is available
        if not torch.cuda.is_available():
            logger.warning("CUDA not available - GPU monitoring disabled")
            self.cuda_available = False
            return
        
        self.cuda_available = True
        self.device_count = torch.cuda.device_count()
        self.device_properties = torch.cuda.get_device_properties(0)
        
        logger.info(f"GPU Monitor initialized for: {self.device_properties.name}")
        logger.info(f"Total VRAM: {self.device_properties.total_memory / 1024**3:.1f}GB")
        logger.info(f"Warning threshold: {warning_threshold_pct}% ({self.device_properties.total_memory * warning_threshold_pct / 100 / 1024**3:.1f}GB)")
        logger.info(f"Critical threshold: {critical_threshold_pct}% ({self.device_properties.total_memory * critical_threshold_pct / 100 / 1024**3:.1f}GB)")

    def get_current_metrics(self) -> Optional[GPUMetrics]:
        """Get current GPU metrics."""
        if not self.cuda_available:
            return None
        
        try:
            # Basic CUDA metrics
            total_memory = self.device_properties.total_memory
            allocated_memory = torch.cuda.memory_allocated(0)
            reserved_memory = torch.cuda.memory_reserved(0)
            free_memory = total_memory - reserved_memory
            
            # Convert to GB
            total_gb = total_memory / 1024**3
            allocated_gb = allocated_memory / 1024**3
            reserved_gb = reserved_memory / 1024**3
            free_gb = free_memory / 1024**3
            
            memory_utilization = (reserved_memory / total_memory) * 100
            
            # Try to get additional metrics (may not be available on all systems)
            gpu_utilization = None
            temperature = None
            power_usage = None
            
            try:
                import nvidia_ml_py3 as nvml
                nvml.nvmlInit()
                handle = nvml.nvmlDeviceGetHandleByIndex(0)
                
                # GPU utilization
                utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
                gpu_utilization = utilization.gpu
                
                # Temperature
                temperature = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                
                # Power usage
                power_usage = nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert to watts
                
            except ImportError:
                logger.debug("nvidia-ml-py3 not available - limited GPU metrics")
            except Exception as e:
                logger.debug(f"Could not get extended GPU metrics: {e}")
            
            return GPUMetrics(
                timestamp=datetime.now(),
                gpu_name=self.device_properties.name,
                total_memory_gb=total_gb,
                allocated_memory_gb=allocated_gb,
                reserved_memory_gb=reserved_gb,
                free_memory_gb=free_gb,
                memory_utilization_pct=memory_utilization,
                gpu_utilization_pct=gpu_utilization,
                temperature_c=temperature,
                power_usage_w=power_usage
            )
            
        except Exception as e:
            logger.error(f"Error getting GPU metrics: {e}")
            return None

    def log_current_status(self, context: str = ""):
        """Log current GPU status with optional context."""
        metrics = self.get_current_metrics()
        if not metrics:
            return
        
        # Determine log level based on memory usage
        if metrics.memory_utilization_pct >= self.critical_threshold:
            log_level = logging.CRITICAL
            status = "CRITICAL"
        elif metrics.memory_utilization_pct >= self.warning_threshold:
            log_level = logging.WARNING
            status = "WARNING"
        else:
            log_level = logging.INFO
            status = "OK"
        
        context_str = f" ({context})" if context else ""
        
        # Basic memory info
        logger.log(log_level, 
            f"GPU Memory{context_str}: {metrics.reserved_memory_gb:.1f}GB used / "
            f"{metrics.total_memory_gb:.1f}GB total ({metrics.memory_utilization_pct:.1f}%) - {status}"
        )
        
        # Detailed breakdown
        logger.info(
            f"GPU Details{context_str}: Allocated: {metrics.allocated_memory_gb:.1f}GB, "
            f"Reserved: {metrics.reserved_memory_gb:.1f}GB, Free: {metrics.free_memory_gb:.1f}GB"
        )
        
        # Extended metrics if available
        if metrics.gpu_utilization_pct is not None:
            logger.info(f"GPU Utilization{context_str}: {metrics.gpu_utilization_pct}%")
        
        if metrics.temperature_c is not None:
            logger.info(f"GPU Temperature{context_str}: {metrics.temperature_c}°C")
        
        if metrics.power_usage_w is not None:
            logger.info(f"GPU Power Usage{context_str}: {metrics.power_usage_w:.1f}W")
        
        # Store metrics
        self.metrics_history.append(metrics)
        
        # Keep only last 1000 entries to prevent memory bloat
        if len(self.metrics_history) > 1000:
            self.metrics_history = self.metrics_history[-1000:]

    def check_memory_limits(self) -> Dict[str, bool]:
        """Check if we're approaching memory limits."""
        metrics = self.get_current_metrics()
        if not metrics:
            return {"warning": False, "critical": False, "available": False}
        
        return {
            "warning": metrics.memory_utilization_pct >= self.warning_threshold,
            "critical": metrics.memory_utilization_pct >= self.critical_threshold,
            "available": True
        }

    def suggest_optimizations(self) -> List[str]:
        """Suggest optimizations based on current memory usage."""
        metrics = self.get_current_metrics()
        if not metrics:
            return ["GPU monitoring not available"]
        
        suggestions = []
        
        if metrics.memory_utilization_pct >= self.critical_threshold:
            suggestions.extend([
                "CRITICAL: Reduce BATCH_SIZE to 1",
                "Consider switching to smaller model (blip2-opt-2.7b)",
                "Increase VIDEO_SAMPLE_RATE to process fewer frames",
                "Close other GPU applications",
                "Restart system to clear GPU memory fragmentation"
            ])
        elif metrics.memory_utilization_pct >= self.warning_threshold:
            suggestions.extend([
                "WARNING: Monitor memory usage closely",
                "Consider reducing BATCH_SIZE",
                "Increase VIDEO_SAMPLE_RATE for videos",
                "Clear GPU cache with torch.cuda.empty_cache()"
            ])
        else:
            suggestions.append("Memory usage looks healthy")
        
        return suggestions

    def start_monitoring(self, interval_seconds: float = 30.0):
        """Start continuous GPU monitoring in background thread."""
        if not self.cuda_available:
            logger.warning("Cannot start GPU monitoring - CUDA not available")
            return
        
        if self.monitoring:
            logger.warning("GPU monitoring already running")
            return
        
        self.monitoring = True
        
        def monitor_loop():
            logger.info(f"Started GPU monitoring (interval: {interval_seconds}s)")
            while self.monitoring:
                try:
                    self.log_current_status("Monitor")
                    
                    # Check for alerts
                    limits = self.check_memory_limits()
                    if limits["critical"]:
                        logger.critical("GPU memory usage is CRITICAL - system may crash!")
                        suggestions = self.suggest_optimizations()
                        for suggestion in suggestions[:3]:  # Show top 3 suggestions
                            logger.critical(f"SUGGESTION: {suggestion}")
                    elif limits["warning"]:
                        logger.warning("GPU memory usage approaching limits")
                    
                    time.sleep(interval_seconds)
                    
                except Exception as e:
                    logger.error(f"Error in GPU monitoring loop: {e}")
                    time.sleep(interval_seconds)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self):
        """Stop continuous GPU monitoring."""
        if self.monitoring:
            self.monitoring = False
            logger.info("Stopped GPU monitoring")

    def clear_cache_and_log(self, context: str = ""):
        """Clear GPU cache and log the effect."""
        if not self.cuda_available:
            return
        
        # Log before
        self.log_current_status(f"Before cache clear {context}".strip())
        
        # Clear cache
        torch.cuda.empty_cache()
        
        # Small delay to let the clear take effect
        time.sleep(1)
        
        # Log after
        self.log_current_status(f"After cache clear {context}".strip())

    def get_memory_summary(self) -> Dict[str, float]:
        """Get summary of memory usage."""
        metrics = self.get_current_metrics()
        if not metrics:
            return {}
        
        return {
            "total_gb": metrics.total_memory_gb,
            "used_gb": metrics.reserved_memory_gb,
            "free_gb": metrics.free_memory_gb,
            "utilization_pct": metrics.memory_utilization_pct,
            "allocated_gb": metrics.allocated_memory_gb
        }

# Global GPU monitor instance
gpu_monitor = GPUMonitor()

def log_gpu_status(context: str = ""):
    """Convenience function to log GPU status."""
    gpu_monitor.log_current_status(context)

def clear_gpu_cache(context: str = ""):
    """Convenience function to clear GPU cache and log."""
    gpu_monitor.clear_cache_and_log(context)

def check_gpu_limits() -> Dict[str, bool]:
    """Convenience function to check GPU limits."""
    return gpu_monitor.check_memory_limits()

def start_gpu_monitoring(interval: float = 30.0):
    """Convenience function to start GPU monitoring."""
    gpu_monitor.start_monitoring(interval)

def stop_gpu_monitoring():
    """Convenience function to stop GPU monitoring."""
    gpu_monitor.stop_monitoring() 