#!/usr/bin/env python3
"""
GPU Monitoring Module for Foscam Detection Dashboard

Collects GPU metrics similar to Green with Envy, storing 5 minutes of data.
Supports both NVIDIA and AMD GPUs.
"""

import time
import json
import subprocess
import threading
from datetime import datetime, timedelta
from collections import deque
from typing import Dict, List, Optional, Any
import asyncio
from pathlib import Path

# Try to import GPU libraries, fallback gracefully
try:
    import pynvml
    NVIDIA_AVAILABLE = True
except ImportError:
    NVIDIA_AVAILABLE = False

try:
    import pyamdgpuinfo
    AMD_AVAILABLE = True
except ImportError:
    AMD_AVAILABLE = False

class GPUMetrics:
    """Container for GPU metrics at a specific timestamp"""
    def __init__(self, timestamp: datetime):
        self.timestamp = timestamp
        self.gpu_utilization = 0.0  # %
        self.memory_used = 0  # MB
        self.memory_total = 0  # MB
        self.memory_utilization = 0.0  # %
        self.temperature = 0.0  # °C
        self.power_usage = 0.0  # W
        self.power_limit = 0.0  # W
        self.fan_speed = 0.0  # %
        self.core_clock = 0  # MHz
        self.memory_clock = 0  # MHz
        self.gpu_name = "Unknown GPU"
        self.driver_version = "Unknown"
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'gpu_utilization': self.gpu_utilization,
            'memory_used': self.memory_used,
            'memory_total': self.memory_total,
            'memory_utilization': self.memory_utilization,
            'temperature': self.temperature,
            'power_usage': self.power_usage,
            'power_limit': self.power_limit,
            'fan_speed': self.fan_speed,
            'core_clock': self.core_clock,
            'memory_clock': self.memory_clock,
            'gpu_name': self.gpu_name,
            'driver_version': self.driver_version
        }

class GPUMonitor:
    """GPU monitoring service that tracks metrics for 5 minutes"""
    
    def __init__(self, update_interval: float = 1.0):
        self.update_interval = update_interval
        self.metrics_history = deque(maxlen=300)  # 5 minutes at 1 second intervals
        self.is_running = False
        self.monitor_thread = None
        self.gpu_type = None
        self.gpu_count = 0
        self.gpu_handles = []
        
        # Initialize GPU libraries
        self._initialize_gpu_libraries()
    
    def _initialize_gpu_libraries(self):
        """Initialize available GPU libraries"""
        # Try NVIDIA first
        if NVIDIA_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self.gpu_count = pynvml.nvmlDeviceGetCount()
                self.gpu_type = "NVIDIA"
                
                # Get GPU handles
                for i in range(self.gpu_count):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    self.gpu_handles.append(handle)
                    
                print(f"Initialized NVIDIA GPU monitoring: {self.gpu_count} GPU(s)")
                return
            except Exception as e:
                print(f"Failed to initialize NVIDIA GPU monitoring: {e}")
        
        # Try AMD
        if AMD_AVAILABLE:
            try:
                # AMD GPU initialization would go here
                self.gpu_type = "AMD"
                print("AMD GPU monitoring not fully implemented yet")
                return
            except Exception as e:
                print(f"Failed to initialize AMD GPU monitoring: {e}")
        
        # Fallback to system commands
        self.gpu_type = "SYSTEM"
        print("Using system command fallback for GPU monitoring")
    
    def _get_nvidia_metrics(self) -> Optional[GPUMetrics]:
        """Get metrics from NVIDIA GPU"""
        if not self.gpu_handles:
            return None
            
        try:
            # For now, just monitor the first GPU
            handle = self.gpu_handles[0]
            metrics = GPUMetrics(datetime.now())
            
            # GPU Name
            gpu_name = pynvml.nvmlDeviceGetName(handle)
            metrics.gpu_name = gpu_name.decode('utf-8') if isinstance(gpu_name, bytes) else gpu_name
            
            # Driver Version
            try:
                driver_version = pynvml.nvmlSystemGetDriverVersion()
                metrics.driver_version = driver_version.decode('utf-8') if isinstance(driver_version, bytes) else driver_version
            except:
                metrics.driver_version = "Unknown"
            
            # GPU Utilization
            try:
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                metrics.gpu_utilization = utilization.gpu
                metrics.memory_utilization = utilization.memory
            except:
                pass
            
            # Memory Info
            try:
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                metrics.memory_used = mem_info.used // (1024 * 1024)  # Convert to MB
                metrics.memory_total = mem_info.total // (1024 * 1024)  # Convert to MB
                if metrics.memory_total > 0:
                    metrics.memory_utilization = (metrics.memory_used / metrics.memory_total) * 100
            except:
                pass
            
            # Temperature
            try:
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                metrics.temperature = temp
            except:
                pass
            
            # Power Usage
            try:
                power = pynvml.nvmlDeviceGetPowerUsage(handle)
                metrics.power_usage = power / 1000.0  # Convert to W
            except:
                pass
            
            # Power Limit
            try:
                power_limit = pynvml.nvmlDeviceGetPowerManagementLimitConstraints(handle)
                metrics.power_limit = power_limit[1] / 1000.0  # Max power limit in W
            except:
                pass
            
            # Fan Speed
            try:
                fan_speed = pynvml.nvmlDeviceGetFanSpeed(handle)
                metrics.fan_speed = fan_speed
            except:
                pass
            
            # Clock speeds
            try:
                core_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_GRAPHICS)
                metrics.core_clock = core_clock
                
                mem_clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_MEM)
                metrics.memory_clock = mem_clock
            except:
                pass
            
            return metrics
            
        except Exception as e:
            print(f"Error getting NVIDIA metrics: {e}")
            return None
    
    def _get_system_metrics(self) -> Optional[GPUMetrics]:
        """Get metrics using system commands as fallback"""
        try:
            metrics = GPUMetrics(datetime.now())
            
            # Try nvidia-smi for NVIDIA
            try:
                result = subprocess.run([
                    'nvidia-smi', 
                    '--query-gpu=name,driver_version,temperature.gpu,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,power.limit,fan.speed,clocks.gr,clocks.mem',
                    '--format=csv,noheader,nounits'
                ], capture_output=True, text=True, timeout=5)
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if lines:
                        data = lines[0].split(', ')
                        if len(data) >= 12:
                            metrics.gpu_name = data[0]
                            metrics.driver_version = data[1]
                            metrics.temperature = float(data[2]) if data[2] != '[N/A]' else 0.0
                            metrics.gpu_utilization = float(data[3]) if data[3] != '[N/A]' else 0.0
                            metrics.memory_utilization = float(data[4]) if data[4] != '[N/A]' else 0.0
                            metrics.memory_used = int(data[5]) if data[5] != '[N/A]' else 0
                            metrics.memory_total = int(data[6]) if data[6] != '[N/A]' else 0
                            metrics.power_usage = float(data[7]) if data[7] != '[N/A]' else 0.0
                            metrics.power_limit = float(data[8]) if data[8] != '[N/A]' else 0.0
                            metrics.fan_speed = float(data[9]) if data[9] != '[N/A]' else 0.0
                            metrics.core_clock = int(data[10]) if data[10] != '[N/A]' else 0
                            metrics.memory_clock = int(data[11]) if data[11] != '[N/A]' else 0
                            
                            return metrics
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            # Try radeontop for AMD
            try:
                result = subprocess.run(['radeontop', '-d', '-', '-l', '1'], 
                                     capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    # Parse radeontop output
                    # This is a simplified parser - you'd need to implement full parsing
                    metrics.gpu_name = "AMD GPU"
                    return metrics
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                pass
            
            return metrics
            
        except Exception as e:
            print(f"Error getting system metrics: {e}")
            return None
    
    def get_current_metrics(self) -> Optional[GPUMetrics]:
        """Get current GPU metrics"""
        if self.gpu_type == "NVIDIA" and NVIDIA_AVAILABLE:
            return self._get_nvidia_metrics()
        else:
            return self._get_system_metrics()
    
    def start_monitoring(self):
        """Start the GPU monitoring thread"""
        if self.is_running:
            return
            
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print("GPU monitoring started")
    
    def stop_monitoring(self):
        """Stop the GPU monitoring thread"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("GPU monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                metrics = self.get_current_metrics()
                if metrics:
                    self.metrics_history.append(metrics)
                    
                    # Clean old metrics (keep only last 5 minutes)
                    cutoff_time = datetime.now() - timedelta(minutes=5)
                    while (self.metrics_history and 
                           self.metrics_history[0].timestamp < cutoff_time):
                        self.metrics_history.popleft()
                
                time.sleep(self.update_interval)
                
            except Exception as e:
                print(f"Error in monitoring loop: {e}")
                time.sleep(self.update_interval)
    
    def get_metrics_history(self, minutes: int = 5) -> List[Dict[str, Any]]:
        """Get metrics history for the last N minutes"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            metrics.to_dict() 
            for metrics in self.metrics_history 
            if metrics.timestamp >= cutoff_time
        ]
    
    def get_latest_metrics(self) -> Optional[Dict[str, Any]]:
        """Get the latest metrics"""
        if self.metrics_history:
            return self.metrics_history[-1].to_dict()
        return None
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the current monitoring period"""
        if not self.metrics_history:
            return {}
        
        recent_metrics = list(self.metrics_history)
        
        # Calculate averages and peaks
        gpu_utils = [m.gpu_utilization for m in recent_metrics]
        temps = [m.temperature for m in recent_metrics]
        powers = [m.power_usage for m in recent_metrics]
        mem_utils = [m.memory_utilization for m in recent_metrics]
        
        return {
            'gpu_utilization': {
                'current': recent_metrics[-1].gpu_utilization if recent_metrics else 0,
                'average': sum(gpu_utils) / len(gpu_utils) if gpu_utils else 0,
                'peak': max(gpu_utils) if gpu_utils else 0
            },
            'temperature': {
                'current': recent_metrics[-1].temperature if recent_metrics else 0,
                'average': sum(temps) / len(temps) if temps else 0,
                'peak': max(temps) if temps else 0
            },
            'power_usage': {
                'current': recent_metrics[-1].power_usage if recent_metrics else 0,
                'average': sum(powers) / len(powers) if powers else 0,
                'peak': max(powers) if powers else 0
            },
            'memory_utilization': {
                'current': recent_metrics[-1].memory_utilization if recent_metrics else 0,
                'average': sum(mem_utils) / len(mem_utils) if mem_utils else 0,
                'peak': max(mem_utils) if mem_utils else 0
            },
            'gpu_name': recent_metrics[-1].gpu_name if recent_metrics else "Unknown",
            'driver_version': recent_metrics[-1].driver_version if recent_metrics else "Unknown",
            'monitoring_duration': len(recent_metrics),
            'last_updated': recent_metrics[-1].timestamp.isoformat() if recent_metrics else None
        }

# Global GPU monitor instance
gpu_monitor = GPUMonitor()

def initialize_gpu_monitoring():
    """Initialize and start GPU monitoring"""
    gpu_monitor.start_monitoring()

def shutdown_gpu_monitoring():
    """Shutdown GPU monitoring"""
    gpu_monitor.stop_monitoring()

# Auto-start monitoring when module is imported
if __name__ != "__main__":
    initialize_gpu_monitoring() 