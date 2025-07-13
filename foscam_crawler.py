#!/usr/bin/env python3
"""
Foscam Directory Crawler - Process existing foscam camera data
"""
import asyncio
import logging
from pathlib import Path
from datetime import datetime
import time
from typing import List, Optional, Tuple
import re

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from config import (
    FOSCAM_DIR, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, DATABASE_URL,
    CAMERA_LOCATIONS, FOSCAM_DEVICE_PATTERNS, FOSCAM_IMAGE_PATTERNS,
    FOSCAM_VIDEO_PATTERNS, FOSCAM_DATETIME_PATTERNS, MODEL_NAME, DEVICE,
    VIDEO_SAMPLE_RATE, AI_ANALYSIS_LOG_LEVEL
)
from models import Base, Detection
from ai_model import VisionLanguageModel

# Import GPU monitoring
from gpu_monitor import start_gpu_monitoring, stop_gpu_monitoring, log_gpu_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FoscamCrawler:
    """Crawls and processes existing foscam camera data."""
    
    def __init__(self):
        self.model = None
        self.processed_count = 0
        self.skipped_count = 0
        self.error_count = 0
        
        # Database setup
        engine = create_async_engine(DATABASE_URL, echo=False)
        self.SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
    async def initialize(self):
        """Initialize the AI model and database."""
        logger.info("Initializing Foscam Crawler...")
        
        # Start GPU monitoring
        await start_gpu_monitoring()
        
        # Initialize database
        async with create_async_engine(DATABASE_URL, echo=False).begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Initialize AI model
        logger.info("Loading AI model...")
        self.model = VisionLanguageModel(MODEL_NAME, DEVICE)
        logger.info("✅ Foscam Crawler initialized successfully")
        
    async def discover_camera_structure(self) -> List[Tuple[str, str, Path]]:
        """
        Discover all camera directories and their structure.
        
        Returns:
            List of tuples: (camera_location, device_id, device_path)
        """
        discovered_cameras = []
        
        if not FOSCAM_DIR.exists():
            logger.error(f"Foscam directory not found: {FOSCAM_DIR}")
            return discovered_cameras
        
        logger.info(f"Scanning foscam directory: {FOSCAM_DIR}")
        
        # Scan each camera location
        for location in CAMERA_LOCATIONS:
            location_path = FOSCAM_DIR / location
            
            if not location_path.exists():
                logger.warning(f"Camera location not found: {location_path}")
                continue
                
            logger.info(f"Scanning location: {location}")
            
            # Look for device directories
            for device_dir in location_path.iterdir():
                if device_dir.is_dir():
                    # Check if it matches known device patterns
                    device_name = device_dir.name
                    is_known_device = any(
                        device_name.startswith(pattern) 
                        for pattern in FOSCAM_DEVICE_PATTERNS
                    )
                    
                    if is_known_device:
                        discovered_cameras.append((location, device_name, device_dir))
                        logger.info(f"  Found device: {device_name}")
                    else:
                        logger.warning(f"  Unknown device pattern: {device_name}")
        
        logger.info(f"Discovered {len(discovered_cameras)} camera devices")
        return discovered_cameras
    
    async def get_media_files(self, device_path: Path) -> List[Tuple[Path, str]]:
        """
        Get all media files from a device directory.
        
        Args:
            device_path: Path to device directory
            
        Returns:
            List of tuples: (file_path, media_type)
        """
        media_files = []
        
        # Check snap directory for images
        snap_dir = device_path / "snap"
        if snap_dir.exists():
            for file_path in snap_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in IMAGE_EXTENSIONS:
                    # Check if it matches foscam image patterns
                    filename = file_path.name
                    if any(filename.startswith(pattern) for pattern in FOSCAM_IMAGE_PATTERNS):
                        media_files.append((file_path, "image"))
        
        # Check record directory for videos
        record_dir = device_path / "record"
        if record_dir.exists():
            for file_path in record_dir.iterdir():
                if file_path.is_file() and file_path.suffix.lower() in VIDEO_EXTENSIONS:
                    # Check if it matches foscam video patterns
                    filename = file_path.name
                    if any(filename.startswith(pattern) for pattern in FOSCAM_VIDEO_PATTERNS):
                        media_files.append((file_path, "video"))
        
        return media_files
    
    def extract_camera_info(self, camera_location: str, device_name: str) -> str:
        """Extract camera name from location and device info."""
        # Create a readable camera name
        camera_name = f"{camera_location}_{device_name}"
        return camera_name
    
    def parse_file_timestamp(self, filename: str) -> Optional[datetime]:
        """Parse timestamp from foscam filename."""
        # Extract timestamp portion from filename
        # Examples: MDAlarm_20250712-213837.jpg, MDalarm_20250712_213837.mkv
        
        for pattern in FOSCAM_IMAGE_PATTERNS + FOSCAM_VIDEO_PATTERNS:
            if filename.startswith(pattern):
                timestamp_part = filename[len(pattern):].split('.')[0]
                
                # Try different datetime patterns
                for dt_pattern in FOSCAM_DATETIME_PATTERNS:
                    try:
                        return datetime.strptime(timestamp_part, dt_pattern)
                    except ValueError:
                        continue
        
        logger.warning(f"Could not parse timestamp from filename: {filename}")
        return None
    
    async def is_file_already_processed(self, file_path: Path) -> bool:
        """Check if file has already been processed."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(Detection).where(Detection.filepath == str(file_path))
            )
            return result.scalar_one_or_none() is not None
    
    async def process_file(self, file_path: Path, media_type: str, camera_name: str) -> bool:
        """
        Process a single media file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if already processed
            if await self.is_file_already_processed(file_path):
                logger.debug(f"File already processed: {file_path.name}")
                return True
            
            # Parse file timestamp
            file_timestamp = self.parse_file_timestamp(file_path.name)
            if not file_timestamp:
                file_timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
            
            # Process with AI model
            if media_type == "image":
                result = self.model.process_image(file_path)
            else:  # video
                result = self.model.process_video(file_path, VIDEO_SAMPLE_RATE)
            
            if result["success"]:
                # Save to database
                await self.save_detection(
                    file_path=file_path,
                    media_type=media_type,
                    result=result,
                    file_timestamp=file_timestamp,
                    camera_name=camera_name
                )
                
                # Log analysis results (respecting log level)
                self.log_analysis_results(file_path, media_type, result, camera_name)
                
                return True
            else:
                logger.error(f"AI processing failed for {file_path}: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")
            return False
    
    def log_analysis_results(self, file_path: Path, media_type: str, result: dict, camera_name: str):
        """Log analysis results based on configured level."""
        log_level = AI_ANALYSIS_LOG_LEVEL.upper()
        
        if log_level == "WARNING":
            # Only log alerts
            alerts = result.get('alert_summary', []) if media_type == "image" else result.get('video_alerts', [])
            if alerts:
                logger.warning(f"ALERTS in {file_path.name} ({camera_name}): {', '.join(alerts)}")
        else:
            # INFO and DEBUG levels
            logger.info(f"✅ Processed {file_path.name} ({camera_name}) - {result.get('confidence', 0):.1%} confidence")
            
            if log_level == "DEBUG":
                logger.debug(f"   Description: {result.get('description', 'No description')}")
                alerts = result.get('alert_summary', []) if media_type == "image" else result.get('video_alerts', [])
                if alerts:
                    logger.debug(f"   Alerts: {', '.join(alerts)}")
    
    async def save_detection(self, file_path: Path, media_type: str, result: dict, 
                           file_timestamp: datetime, camera_name: str):
        """Save detection results to database using optimized schema."""
        async with self.SessionLocal() as session:
            # Parse camera info from camera_name
            if "_" in camera_name:
                parts = camera_name.split("_", 1)
                location = parts[0]
                device_name = parts[1] if len(parts) > 1 else parts[0]
            else:
                location = "unknown"
                device_name = camera_name
            
            # Get or create camera
            from models import get_or_create_camera, get_alert_flags_from_alerts, extract_motion_detection_type, initialize_alert_types
            
            # Initialize alert types on first run
            initialize_alert_types(session)
            await session.commit()
            
            camera = get_or_create_camera(session, location, device_name)
            await session.commit()
            
            # Extract alert information
            alerts = result.get('alert_summary', []) if media_type == "image" else result.get('video_alerts', [])
            alert_flags = get_alert_flags_from_alerts(alerts)
            
            # Extract motion detection type
            motion_type = extract_motion_detection_type(file_path.name)
            
            detection = Detection(
                filename=file_path.name,
                filepath=str(file_path),
                media_type=media_type,
                camera_id=camera.id,
                motion_detection_type=motion_type,
                processed=True,
                description=result["description"],
                confidence=result["confidence"],
                processing_time=time.time(),
                file_timestamp=file_timestamp,
                width=result.get("width", 0),
                height=result.get("height", 0),
                frame_count=result.get("frame_count"),
                duration=result.get("duration"),
                # Alert flags for fast filtering
                **alert_flags
            )
            
            # Store structured analysis if available
            detailed_analysis = result.get('detailed_analysis', {})
            if detailed_analysis:
                detection.set_structured_analysis(detailed_analysis)
            
            session.add(detection)
            
            # Update camera statistics
            camera.total_detections += 1
            camera.total_alerts += alert_flags['alert_count']
            camera.last_seen = datetime.utcnow()
            
            await session.commit()
            
            # Log the save operation
            logger.debug(f"Saved detection: {file_path.name} -> Camera ID {camera.id}, Alerts: {alert_flags['alert_count']}")
    
    async def crawl_and_process(self, limit: Optional[int] = None) -> dict:
        """
        Main crawling and processing function.
        
        Args:
            limit: Maximum number of files to process (for testing)
            
        Returns:
            Dictionary with processing statistics
        """
        logger.info("🔍 Starting Foscam directory crawl...")
        start_time = time.time()
        
        # Discover camera structure
        cameras = await self.discover_camera_structure()
        
        if not cameras:
            logger.error("No cameras found in foscam directory")
            return {"error": "No cameras found"}
        
        # Process each camera
        total_files = 0
        
        for camera_location, device_name, device_path in cameras:
            camera_name = self.extract_camera_info(camera_location, device_name)
            logger.info(f"📷 Processing camera: {camera_name}")
            
            # Get all media files for this camera
            media_files = await self.get_media_files(device_path)
            logger.info(f"   Found {len(media_files)} media files")
            
            # Process each file
            for file_path, media_type in media_files:
                if limit and total_files >= limit:
                    logger.info(f"Reached processing limit: {limit}")
                    break
                
                logger.debug(f"Processing: {file_path.name}")
                
                success = await self.process_file(file_path, media_type, camera_name)
                
                if success:
                    self.processed_count += 1
                else:
                    self.error_count += 1
                
                total_files += 1
                
                # Progress update every 10 files
                if total_files % 10 == 0:
                    logger.info(f"Progress: {total_files} files processed ({self.processed_count} successful, {self.error_count} errors)")
            
            if limit and total_files >= limit:
                break
        
        processing_time = time.time() - start_time
        
        # Final statistics
        stats = {
            "total_files": total_files,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "cameras_found": len(cameras),
            "processing_time": processing_time
        }
        
        logger.info("📊 Crawling Complete!")
        logger.info(f"   Total files: {total_files}")
        logger.info(f"   Successfully processed: {self.processed_count}")
        logger.info(f"   Errors: {self.error_count}")
        logger.info(f"   Cameras: {len(cameras)}")
        logger.info(f"   Processing time: {processing_time:.1f}s")
        
        return stats
    
    async def cleanup(self):
        """Cleanup resources."""
        await stop_gpu_monitoring()
        logger.info("Crawler cleanup complete")

async def main():
    """Main entry point for crawler."""
    crawler = FoscamCrawler()
    
    try:
        await crawler.initialize()
        
        # For testing, limit to 50 files
        # Remove limit=50 to process all files
        stats = await crawler.crawl_and_process(limit=50)
        
        if "error" not in stats:
            logger.info("✅ Crawling completed successfully")
        else:
            logger.error(f"❌ Crawling failed: {stats['error']}")
            
    except Exception as e:
        logger.error(f"❌ Crawler error: {str(e)}")
    finally:
        await crawler.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 