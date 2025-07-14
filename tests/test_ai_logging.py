#!/usr/bin/env python3
"""
Test script for AI Analysis Logging System
Demonstrates how prompts and responses are logged
"""

import sys
from pathlib import Path

# Add parent directory to path so we can import from src
sys.path.append(str(Path(__file__).parent.parent))

from src.logging_config import setup_ai_analysis_logger
import time

# Initialize AI logger
ai_logger = setup_ai_analysis_logger("DEBUG")

def test_ai_logging():
    """Test the AI logging system with sample prompts and responses."""
    
    # Simulate an image analysis session
    ai_logger.info("="*60)
    ai_logger.info("STARTING IMAGE PROCESSING SESSION")
    ai_logger.info("IMAGE_PATH: /home/msvoboda/foscam/test_image.jpg")
    ai_logger.info("IMAGE_NAME: test_image.jpg")
    ai_logger.info("CAMERA_NAME: frontyard_camera")
    ai_logger.info("IMAGE_DIMENSIONS: 1280x720")
    
    # Simulate individual prompts and responses
    test_prompts = [
        {
            "aspect": "general",
            "prompt": "Question: What is happening in this image? Describe the scene in detail. Answer:",
            "response": "A person in blue jacket walking toward the front door carrying a package"
        },
        {
            "aspect": "vehicles", 
            "prompt": "Question: If there are any vehicles in this image, describe them in detail including make, model, color, type, license plate numbers, company markings, logos, or any text visible on the vehicle. Answer:",
            "response": "White Ford Transit delivery van parked in driveway with Amazon logo on side panel"
        },
        {
            "aspect": "identification",
            "prompt": "Question: What specific identifying information can you extract from this image? Include vehicle details, person descriptions, company logos, text, signs, or any other distinguishing features. Answer:",
            "response": "Person: Adult wearing blue jacket, dark pants, carrying brown package. Vehicle: White Ford Transit with license plate ABC-1234, Amazon Prime logo visible"
        }
    ]
    
    for prompt_data in test_prompts:
        ai_logger.info(f"ANALYZING_ASPECT: {prompt_data['aspect']}")
        ai_logger.info(f"PROMPT_SENT: {prompt_data['prompt']}")
        
        # Simulate processing time
        time.sleep(0.1)
        
        ai_logger.info(f"RESPONSE_RECEIVED: {prompt_data['response']}")
        ai_logger.debug(f"PROMPT_TIMING: 0.856s")
        ai_logger.debug(f"RESPONSE_LENGTH: {len(prompt_data['response'])} characters")
    
    # Simulate final results
    ai_logger.info("COMPREHENSIVE_DESCRIPTION: Amazon delivery person in blue jacket approaching front door with package, white Ford Transit van in driveway")
    ai_logger.info("CONFIDENCE_SCORE: 0.87")
    ai_logger.info("ALERT_SUMMARY: ['PERSON_DETECTED', 'VEHICLE_DETECTED', 'PACKAGE_DETECTED']")
    ai_logger.info("PROCESSING_TIME: 2.543s")
    ai_logger.info("IMAGE PROCESSING SESSION COMPLETED SUCCESSFULLY")
    ai_logger.info("="*60)
    
    print("AI logging test completed! Check logs/ai_analysis.log and logs/ai_analysis_prompts.log")

if __name__ == "__main__":
    test_ai_logging() 