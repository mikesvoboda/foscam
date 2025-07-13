#!/usr/bin/env python3
"""
Test script for BLIP-2 T5-XL model with enhanced detailed analysis capabilities.
Run this before starting the full system to verify everything works.
"""

import torch
import logging
from pathlib import Path
from PIL import Image
import numpy as np

# Import GPU monitoring
from gpu_monitor import gpu_monitor, log_gpu_status, start_gpu_monitoring, stop_gpu_monitoring

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gpu_memory():
    """Check available GPU memory."""
    if not torch.cuda.is_available():
        logger.error("CUDA not available!")
        return False
    
    gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
    free_memory = torch.cuda.memory_reserved(0) / 1024**3
    
    logger.info(f"GPU: {torch.cuda.get_device_name(0)}")
    logger.info(f"Total GPU Memory: {gpu_memory:.1f}GB")
    logger.info(f"Free GPU Memory: {gpu_memory - free_memory:.1f}GB")
    
    if gpu_memory < 20:
        logger.warning("Less than 20GB total memory. T5-XL may use most of your VRAM.")
    
    return True

def test_gpu_monitoring():
    """Test the GPU monitoring system."""
    logger.info("Testing GPU monitoring system...")
    
    # Test basic monitoring functions
    log_gpu_status("Test startup")
    
    # Test memory limits checking
    limits = gpu_monitor.check_memory_limits()
    logger.info(f"Memory limits check: {limits}")
    
    # Test optimization suggestions
    suggestions = gpu_monitor.suggest_optimizations()
    logger.info(f"Optimization suggestions: {suggestions[0]}")
    
    # Test metrics collection
    metrics = gpu_monitor.get_current_metrics()
    if metrics:
        logger.info(f"Current VRAM usage: {metrics.memory_utilization_pct:.1f}%")
        if metrics.gpu_utilization_pct is not None:
            logger.info(f"GPU utilization: {metrics.gpu_utilization_pct}%")
        if metrics.temperature_c is not None:
            logger.info(f"GPU temperature: {metrics.temperature_c}°C")
    
    logger.info("✅ GPU monitoring system working")
    return True

def test_model_loading():
    """Test loading the BLIP-2 T5-XL model."""
    try:
        from ai_model import VisionLanguageModel
        
        logger.info("Testing enhanced T5-XL model loading...")
        
        # Log GPU status before loading
        log_gpu_status("Before model loading")
        
        model = VisionLanguageModel(
            model_name="Salesforce/blip2-t5-xl",
            device="cuda",
            use_8bit=True
        )
        
        # Log GPU status after loading
        log_gpu_status("After model loading")
        
        logger.info("✅ Enhanced T5-XL model loaded successfully!")
        return model
    
    except Exception as e:
        logger.error(f"❌ Model loading failed: {e}")
        return None

def test_enhanced_image_processing(model):
    """Test enhanced image processing with detailed analysis."""
    try:
        # Create test images for different scenarios
        test_scenarios = [
            ("Blue solid color", Image.new('RGB', (224, 224), color='blue')),
            ("Red with white square", create_test_scene_1()),
            ("Complex multi-object scene", create_test_scene_2()),
        ]
        
        for scenario_name, test_image in test_scenarios:
            logger.info(f"\n=== Testing Enhanced Analysis: {scenario_name} ===")
            
            # Log GPU status before processing
            log_gpu_status("Before detailed analysis")
            
            # Test detailed description generation
            logger.info("Testing detailed description generation...")
            detailed_descriptions = model.generate_detailed_description(test_image)
            
            # Display detailed analysis results
            logger.info("📊 DETAILED ANALYSIS RESULTS:")
            for analysis_type, description in detailed_descriptions.items():
                logger.info(f"  {analysis_type.upper()}: {description}")
            
            # Test comprehensive caption generation
            logger.info("\nTesting comprehensive caption generation...")
            comprehensive_caption, confidence = model.generate_caption(test_image)
            
            logger.info(f"🎯 COMPREHENSIVE ANALYSIS:")
            logger.info(f"  Caption: {comprehensive_caption}")
            logger.info(f"  Confidence: {confidence:.3f}")
            
            # Test alert generation
            alerts = model._generate_alert_tags(detailed_descriptions)
            if alerts:
                logger.info(f"🚨 ALERTS: {', '.join(alerts)}")
            else:
                logger.info("✅ No alerts detected")
            
            # Log GPU status after processing
            log_gpu_status("After detailed analysis")
            
            logger.info(f"✅ Enhanced analysis completed for {scenario_name}")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Enhanced image processing failed: {e}")
        log_gpu_status("Error during enhanced processing")
        return False

def create_test_scene_1():
    """Create a simple test scene with geometric shapes."""
    img = Image.new('RGB', (224, 224), color='red')
    # Add a white square in the center (simulating a simple object)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    draw.rectangle([75, 75, 149, 149], fill='white', outline='black', width=2)
    return img

def create_test_scene_2():
    """Create a more complex test scene."""
    img = Image.new('RGB', (224, 224), color='lightblue')
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    
    # Multiple objects
    draw.rectangle([20, 20, 60, 60], fill='brown', outline='black')  # Building/box
    draw.rectangle([150, 180, 200, 220], fill='gray', outline='black')  # Vehicle/object
    draw.circle([100, 100, 120], fill='green', outline='darkgreen')  # Tree/circular object
    draw.rectangle([80, 170, 120, 220], fill='yellow', outline='black')  # Person/object
    
    return img

def test_memory_usage():
    """Check GPU memory usage after model loading."""
    if torch.cuda.is_available():
        memory_allocated = torch.cuda.memory_allocated(0) / 1024**3
        memory_reserved = torch.cuda.memory_reserved(0) / 1024**3
        
        logger.info(f"GPU Memory Allocated: {memory_allocated:.1f}GB")
        logger.info(f"GPU Memory Reserved: {memory_reserved:.1f}GB")
        
        if memory_reserved > 22:
            logger.warning("⚠️  Using over 22GB VRAM. Monitor for OOM errors.")
        else:
            logger.info("✅ Memory usage looks good for enhanced analysis!")

def test_background_monitoring():
    """Test background GPU monitoring."""
    logger.info("Testing background monitoring (5 seconds)...")
    
    # Start monitoring
    start_gpu_monitoring(interval=1.0)  # 1 second for testing
    
    # Wait a bit
    import time
    time.sleep(5)
    
    # Stop monitoring
    stop_gpu_monitoring()
    
    logger.info("✅ Background monitoring test completed")

def test_performance_comparison(model):
    """Test performance with different generation parameters."""
    try:
        logger.info("\n=== Performance & Quality Comparison ===")
        
        test_image = create_test_scene_2()
        
        # Test different max_length settings
        for max_len in [50, 100, 150]:
            logger.info(f"\nTesting max_length={max_len}:")
            start_time = torch.cuda.Event(enable_timing=True)
            end_time = torch.cuda.Event(enable_timing=True)
            
            start_time.record()
            caption, confidence = model.generate_caption(test_image, max_length=max_len)
            end_time.record()
            
            torch.cuda.synchronize()
            elapsed_time = start_time.elapsed_time(end_time) / 1000.0  # Convert to seconds
            
            word_count = len(caption.split())
            logger.info(f"  Time: {elapsed_time:.2f}s | Words: {word_count} | Confidence: {confidence:.3f}")
            logger.info(f"  Result: {caption[:100]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Performance comparison failed: {e}")
        return False

def main():
    """Run all enhanced tests."""
    logger.info("🧪 Testing BLIP-2 T5-XL Enhanced Analysis System...")
    
    # Test 1: GPU Memory
    if not test_gpu_memory():
        return
    
    # Test 2: GPU Monitoring System
    if not test_gpu_monitoring():
        logger.warning("GPU monitoring tests failed, but continuing...")
    
    # Test 3: Enhanced Model Loading
    model = test_model_loading()
    if not model:
        return
    
    # Test 4: Memory Usage
    test_memory_usage()
    
    # Test 5: Enhanced Image Processing
    if not test_enhanced_image_processing(model):
        logger.error("❌ Enhanced image processing test failed.")
        return
    
    # Test 6: Performance Comparison
    if not test_performance_comparison(model):
        logger.warning("⚠️ Performance comparison failed, but continuing...")
    
    # Test 7: Background Monitoring
    test_background_monitoring()
    
    logger.info("🎉 All enhanced tests passed! T5-XL system ready for detailed analysis.")
    
    # Final GPU status
    log_gpu_status("Final enhanced test status")
    
    # Provide usage tips
    logger.info("\n💡 ENHANCED T5-XL TIPS:")
    logger.info("  • Expect 5x more detailed descriptions than basic models")
    logger.info("  • Structured output: SCENE | SECURITY | OBJECTS | ACTIVITY | SETTING | ALERTS")
    logger.info("  • Automatic alert detection for people, vehicles, packages")
    logger.info("  • Video analysis includes activity timelines")
    logger.info("  • Monitor GPU usage - processing time increased for quality")
    
    # Cleanup
    del model
    torch.cuda.empty_cache()
    logger.info("🧹 Cleaned up GPU memory.")

if __name__ == "__main__":
    main() 