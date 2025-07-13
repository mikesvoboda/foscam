#!/usr/bin/env python3
"""
Test script to demonstrate AI analysis logging functionality
"""
import logging
import sys
import os
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai_model import VisionLanguageModel
from config import MODEL_NAME, DEVICE, AI_ANALYSIS_LOG_LEVEL

# Configure logging to show in console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('ai_analysis_test.log')
    ]
)

logger = logging.getLogger(__name__)

def test_logging_levels():
    """Test different logging levels for AI analysis."""
    
    # Test image path (create a simple test image if needed)
    test_image_path = Path("test_image.jpg")
    
    if not test_image_path.exists():
        print(f"Test image not found at {test_image_path}")
        print("Please place a test image named 'test_image.jpg' in the current directory")
        return
    
    print(f"Testing AI Analysis Logging with level: {AI_ANALYSIS_LOG_LEVEL}")
    print("=" * 60)
    
    # Initialize the model
    logger.info("Initializing VisionLanguageModel...")
    model = VisionLanguageModel(MODEL_NAME, DEVICE)
    
    # Process test image
    logger.info("Processing test image...")
    result = model.process_image(test_image_path)
    
    print("\n" + "=" * 60)
    print("LOGGING LEVELS EXPLANATION:")
    print("=" * 60)
    print("WARNING: Only logs alerts and errors (minimal output)")
    print("INFO:    Logs comprehensive analysis results (default)")
    print("DEBUG:   Logs all analysis steps and detailed breakdowns")
    print("\nTo change log level, edit AI_ANALYSIS_LOG_LEVEL in config.py")
    
    # Show results summary
    if result["success"]:
        print(f"\n✅ Analysis completed successfully!")
        print(f"   Confidence: {result['confidence']:.1%}")
        print(f"   Processing time: {result['processing_time']:.2f}s")
        if result.get('alert_summary'):
            print(f"   Alerts: {', '.join(result['alert_summary'])}")
        else:
            print("   No alerts detected")
    else:
        print(f"\n❌ Analysis failed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    test_logging_levels() 