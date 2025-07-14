#!/usr/bin/env python3
"""
Flexible script to process Foscam camera files for AI analysis.
Can process any number of images and videos specified via command line arguments.
"""

import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime
import time
import random
import sys

# Add parent directory to path so we can import from src
sys.path.append(str(Path(__file__).parent.parent))

# Import our components
from src.ai_model import VisionLanguageModel
from src.models import get_or_create_camera, get_alert_flags_from_alerts, Base
from src.file_monitor import FoscamMediaProcessor
from sqlalchemy.ext.asyncio import create_async_engine
import src.config as config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileProcessor:
    def __init__(self, num_images=5, num_videos=5):
        self.processor = FoscamMediaProcessor()
        self.num_images = num_images
        self.num_videos = num_videos
        self.total_files = num_images + num_videos
        self.processed_count = 0
        self.image_count = 0
        self.video_count = 0
        self.start_time = None
        
    async def initialize(self):
        """Initialize the processor and database."""
        logger.info("🚀 Initializing file processor...")
        
        # Initialize database
        async with create_async_engine(config.DATABASE_URL, echo=False).begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        await self.processor.initialize()
        logger.info("✅ Initialization complete!")
        
    def discover_files(self):
        """Discover image and video files from the foscam directory."""
        logger.info("🔍 Discovering files in foscam directory...")
        
        foscam_path = Path("foscam")
        if not foscam_path.exists():
            raise FileNotFoundError("foscam directory not found")
        
        # Find all image and video files
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv'}
        
        all_images = []
        all_videos = []
        
        # Recursively find files
        for file_path in foscam_path.rglob("*"):
            if file_path.is_file():
                suffix = file_path.suffix.lower()
                if suffix in image_extensions:
                    all_images.append(str(file_path))
                elif suffix in video_extensions:
                    all_videos.append(str(file_path))
        
        logger.info(f"📊 Discovery results:")
        logger.info(f"  📸 Total images found: {len(all_images)}")
        logger.info(f"  🎬 Total videos found: {len(all_videos)}")
        
        # Randomly select the requested number of files
        selected_images = random.sample(all_images, min(self.num_images, len(all_images)))
        selected_videos = random.sample(all_videos, min(self.num_videos, len(all_videos)))
        
        logger.info(f"📋 Selected for processing:")
        logger.info(f"  📸 Images: {len(selected_images)}")
        logger.info(f"  🎬 Videos: {len(selected_videos)}")
        
        return selected_images, selected_videos
    
    async def process_files(self):
        """Process the selected files."""
        self.start_time = time.time()
        
        # Discover files
        image_files, video_files = self.discover_files()
        
        logger.info(f"📋 Processing plan:")
        logger.info(f"  📸 Images: {len(image_files)}")
        logger.info(f"  🎬 Videos: {len(video_files)}")
        logger.info(f"  📊 Total: {len(image_files) + len(video_files)} files")
        logger.info("")
        
        # Process images
        if image_files:
            logger.info("📸 Processing images...")
            for i, file_path in enumerate(image_files, 1):
                try:
                    await self.process_single_file(file_path, "image", i, len(image_files))
                    self.image_count += 1
                except Exception as e:
                    logger.error(f"Error processing image {file_path}: {e}")
        
        # Process videos  
        if video_files:
            logger.info("")
            logger.info("🎬 Processing videos...")
            for i, file_path in enumerate(video_files, 1):
                try:
                    await self.process_single_file(file_path, "video", i, len(video_files))
                    self.video_count += 1
                except Exception as e:
                    logger.error(f"Error processing video {file_path}: {e}")
                
    async def process_single_file(self, file_path: str, media_type: str, current: int, total: int):
        """Process a single file."""
        path = Path(file_path)
        
        # Extract camera name
        camera_name = self.processor.extract_camera_name_from_path(path)
        
        # Show progress
        elapsed = time.time() - self.start_time
        avg_time = elapsed / (self.processed_count + 1) if self.processed_count > 0 else 0
        eta = avg_time * (self.total_files - self.processed_count - 1) if avg_time > 0 else 0
        
        logger.info(f"  [{current}/{total}] {media_type.upper()}: {path.name}")
        logger.info(f"    📷 Camera: {camera_name}")
        logger.info(f"    ⏱️  Progress: {self.processed_count + 1}/{self.total_files} | ETA: {eta/60:.1f}m")
        
        # Process the file
        await self.processor.process_file(path, camera_name)
        self.processed_count += 1
        
        logger.info(f"    ✅ Complete! ({self.processed_count}/{self.total_files} total)")
        logger.info("")

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process Foscam camera files for AI analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Process 5 images and 5 videos (default)
  %(prog)s -i 10 -v 10        # Process 10 images and 10 videos
  %(prog)s --images 20        # Process 20 images only
  %(prog)s --videos 15        # Process 15 videos only
  %(prog)s -i 0 -v 5          # Process 5 videos only
        """
    )
    
    parser.add_argument(
        '-i', '--images', 
        type=int, 
        default=5, 
        help='Number of images to process (default: 5)'
    )
    
    parser.add_argument(
        '-v', '--videos', 
        type=int, 
        default=5, 
        help='Number of videos to process (default: 5)'
    )
    
    parser.add_argument(
        '--no-random', 
        action='store_true',
        help='Process files in order instead of randomly selecting'
    )
    
    return parser.parse_args()

async def main():
    """Main execution function."""
    args = parse_arguments()
    
    # Validate arguments
    if args.images < 0 or args.videos < 0:
        logger.error("❌ Number of images and videos must be non-negative")
        return
        
    if args.images == 0 and args.videos == 0:
        logger.error("❌ Must specify at least one image or video to process")
        return
    
    processor = FileProcessor(num_images=args.images, num_videos=args.videos)
    
    try:
        # Initialize
        await processor.initialize()
        
        # Process files
        await processor.process_files()
        
        # Final report
        elapsed = time.time() - processor.start_time
        logger.info("🎉 PROCESSING COMPLETE!")
        logger.info(f"📊 Final Statistics:")
        logger.info(f"  📸 Images processed: {processor.image_count}")
        logger.info(f"  🎬 Videos processed: {processor.video_count}")
        logger.info(f"  📋 Total files: {processor.processed_count}")
        logger.info(f"  ⏱️  Total time: {elapsed/60:.1f} minutes")
        if processor.processed_count > 0:
            logger.info(f"  🚀 Average time per file: {elapsed/processor.processed_count:.1f} seconds")
        logger.info("")
        logger.info("🌐 Ready to check web application!")
        logger.info("Visit: http://localhost:8000")
        
    except Exception as e:
        logger.error(f"❌ Processing failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 