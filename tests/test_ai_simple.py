#!/usr/bin/env python3
"""
Simple AI Model Test Script
Tests the new AI prompts and logging system with recent sample files
"""

import sys
import asyncio
import logging
from pathlib import Path
import glob
import time
import os

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ai_analysis():
    """Test AI analysis with recent sample files."""
    print("🧠 Testing AI Analysis with Enhanced Prompts and Logging (Recent Files)")
    print("=" * 60)
    
    # Find some sample files
    foscam_dir = Path("foscam")
    if not foscam_dir.exists():
        print("❌ Foscam directory not found")
        return
    
    # Look for image files
    image_files = []
    for pattern in ['*.jpg', '*.jpeg']:
        image_files.extend(glob.glob(f'foscam/**/{pattern}', recursive=True))
    
    # Look for video files
    video_files = []
    for pattern in ['*.mkv', '*.mp4']:
        video_files.extend(glob.glob(f'foscam/**/{pattern}', recursive=True))
    
    # Sort by modification time (newest first)
    image_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    video_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    
    # Take most recent 5 images and 2 videos
    recent_images = image_files[:5]
    recent_videos = video_files[:2]
    
    print(f"📸 Found {len(recent_images)} recent images to process")
    print(f"🎬 Found {len(recent_videos)} recent videos to process")
    
    if not recent_images and not recent_videos:
        print("❌ No recent files found to process")
        return
    
    try:
        # Import and initialize the AI model
        from src.ai_model import VisionLanguageModel
        
        print("🤖 Initializing AI model...")
        model = VisionLanguageModel("Salesforce/blip2-flan-t5-xl", "cuda")
        print("✅ AI model initialized successfully")
        
        total_files = len(recent_images) + len(recent_videos)
        processed_files = 0
        
        # Process recent images
        for image_path in recent_images:
            print(f"\n📸 Processing image: {Path(image_path).name}")
            
            try:
                start_time = time.time()
                result = model.process_image(Path(image_path))
                processing_time = time.time() - start_time
                
                if result["success"]:
                    print(f"✅ Image processed successfully in {processing_time:.2f}s")
                    print(f"   Confidence: {result['confidence']:.1%}")
                    print(f"   Description: {result['description'][:100]}...")
                    
                    # Log alerts if present
                    alerts = result.get('alert_summary', [])
                    if alerts:
                        print(f"   🚨 Alerts: {', '.join(alerts)}")
                    
                    processed_files += 1
                else:
                    print(f"❌ Failed to process image: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ Error processing image: {e}")
        
        # Process recent videos
        for video_path in recent_videos:
            print(f"\n🎬 Processing video: {Path(video_path).name}")
            
            try:
                start_time = time.time()
                result = await model.process_video(Path(video_path), sample_rate=60)  # Lower sample rate for testing
                processing_time = time.time() - start_time
                
                if result["success"]:
                    print(f"✅ Video processed successfully in {processing_time:.2f}s")
                    print(f"   Confidence: {result['confidence']:.1%}")
                    print(f"   Description: {result['description'][:100]}...")
                    print(f"   Duration: {result.get('duration', 0):.1f}s")
                    print(f"   Frames: {result.get('processed_frames', 0)}/{result.get('frame_count', 0)}")
                    
                    # Log alerts if present
                    alerts = result.get('video_alerts', [])
                    if alerts:
                        print(f"   🚨 Video Alerts: {', '.join(alerts)}")
                    
                    # Log thumbnail generation
                    thumbnail_path = result.get('thumbnail_path')
                    if thumbnail_path:
                        print(f"   🖼️  Thumbnail: {thumbnail_path}")
                    
                    processed_files += 1
                else:
                    print(f"❌ Failed to process video: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"❌ Error processing video: {e}")
        
        print(f"\n📊 Processing Complete!")
        print(f"   Total files processed: {processed_files}/{total_files}")
        print(f"   Success rate: {processed_files/total_files*100:.1f}%")
        
    except Exception as e:
        print(f"❌ Error initializing AI model: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai_analysis()) 