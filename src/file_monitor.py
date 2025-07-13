import asyncio
import logging
from pathlib import Path
from datetime import datetime
import time
from typing import Optional, List, Tuple

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from config import (
    FOSCAM_DIR, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS,
    MODEL_NAME, DEVICE, MAX_LENGTH, DATABASE_URL, VIDEO_SAMPLE_RATE,
    AI_ANALYSIS_LOG_LEVEL, CAMERA_LOCATIONS, FOSCAM_DEVICE_PATTERNS,
    FOSCAM_IMAGE_PATTERNS, FOSCAM_VIDEO_PATTERNS, FOSCAM_DATETIME_PATTERNS
)
from models import Base, Detection
from ai_model import VisionLanguageModel

# Import GPU monitoring
from gpu_monitor import start_gpu_monitoring, stop_gpu_monitoring, log_gpu_status, check_gpu_limits

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FoscamFileHandler(FileSystemEventHandler):
    """Handles new file uploads from foscam cameras."""
    
    def __init__(self, processor):
        self.processor = processor
        
    def on_created(self, event):
        if event.is_directory:
            return
            
        file_path = Path(event.src_path)
        
        # Check if it's a media file we care about
        if file_path.suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            # Check if it matches foscam naming patterns
            filename = file_path.name
            is_foscam_file = (
                any(filename.startswith(pattern) for pattern in FOSCAM_IMAGE_PATTERNS) or
                any(filename.startswith(pattern) for pattern in FOSCAM_VIDEO_PATTERNS)
            )
            
            if is_foscam_file:
                logger.info(f"New foscam file detected: {file_path}")
                
                # Extract camera info from path
                camera_name = self.processor.extract_camera_name_from_path(file_path)
                
                # Add to processing queue
                asyncio.create_task(self.processor.process_file(file_path, camera_name))
            else:
                logger.debug(f"Ignoring non-foscam file: {filename}")

class FoscamMediaProcessor:
    """Processes media files using the vision-language model."""
    
    def __init__(self):
        self.model = None
        
        # Database setup
        engine = create_async_engine(DATABASE_URL, echo=False)
        self.SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def initialize(self):
        """Initialize the AI model and database."""
        logger.info("Initializing Foscam Media Processor...")
        
        # Initialize database
        async with create_async_engine(DATABASE_URL, echo=False).begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Check GPU status
        logger.info("Checking GPU status...")
        limits = check_gpu_limits()
        if limits["critical"]:
            logger.error("GPU memory critical - clearing cache before model loading")
            from gpu_monitor import clear_gpu_cache
            clear_gpu_cache("Initial cleanup")
        
        # Load AI model
        logger.info(f"Loading AI model: {MODEL_NAME}")
        self.model = VisionLanguageModel(MODEL_NAME, DEVICE)
        
        logger.info("✅ Foscam Media Processor initialized successfully")

    def extract_camera_name_from_path(self, file_path: Path) -> str:
        """Extract camera name from foscam file path."""
        try:
            # Expected path structure: foscam/camera_location/device_name/snap_or_record/filename
            path_parts = file_path.parts
            
            # Find the foscam directory index
            foscam_index = None
            for i, part in enumerate(path_parts):
                if part == "foscam":
                    foscam_index = i
                    break
            
            if foscam_index is not None and foscam_index + 2 < len(path_parts):
                camera_location = path_parts[foscam_index + 1]
                device_name = path_parts[foscam_index + 2]
                
                # Create readable camera name
                camera_name = f"{camera_location}_{device_name}"
                return camera_name
            
            logger.warning(f"Could not extract camera name from path: {file_path}")
            return "unknown_camera"
            
        except Exception as e:
            logger.error(f"Error extracting camera name from {file_path}: {str(e)}")
            return "unknown_camera"

    def parse_file_timestamp(self, filename: str) -> Optional[datetime]:
        """Parse timestamp from foscam filename."""
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

    async def _is_file_processed(self, file_path: Path) -> bool:
        """Check if file has already been processed."""
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(Detection).where(Detection.filepath == str(file_path))
            )
            return result.scalar_one_or_none() is not None

    async def process_file(self, file_path: Path, camera_name: str = None):
        """Process a single media file."""
        try:
            # Wait a bit to ensure file is fully written
            await asyncio.sleep(2)
            
            # Check if file still exists
            if not file_path.exists():
                logger.warning(f"File no longer exists: {file_path}")
                return
            
            # Extract camera name if not provided
            if not camera_name:
                camera_name = self.extract_camera_name_from_path(file_path)
            
            # Check if file has already been processed
            if await self._is_file_processed(file_path):
                logger.info(f"File already processed, skipping: {file_path}")
                return
            
            # Parse file timestamp
            file_timestamp = self.parse_file_timestamp(file_path.name)
            if not file_timestamp:
                file_stat = file_path.stat()
                file_timestamp = datetime.fromtimestamp(file_stat.st_mtime)
            
            # Determine media type
            suffix = file_path.suffix.lower()
            if suffix in IMAGE_EXTENSIONS:
                media_type = "image"
                result = self.model.process_image(file_path)
            elif suffix in VIDEO_EXTENSIONS:
                media_type = "video"
                result = self.model.process_video(file_path, VIDEO_SAMPLE_RATE)
            else:
                logger.warning(f"Unknown file type: {file_path}")
                return
            
            if result["success"]:
                # Save to database
                await self._save_detection(
                    file_path=file_path,
                    media_type=media_type,
                    result=result,
                    file_timestamp=file_timestamp,
                    camera_name=camera_name
                )
                
                # Enhanced logging for AI analysis results
                self._log_analysis_results(file_path, media_type, result, camera_name)
                
            else:
                logger.error(f"Failed to process {file_path}: {result.get('error', 'Unknown error')}")
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {str(e)}")

    def _log_analysis_results(self, file_path: Path, media_type: str, result: dict, camera_name: str):
        """Log comprehensive AI analysis results to the log file."""
        # Always log basic completion info
        logger.info(f"AI Analysis Complete: {file_path.name} ({media_type}) - {camera_name}")
        
        # Check logging level configuration
        log_level = AI_ANALYSIS_LOG_LEVEL.upper()
        
        if log_level == "WARNING":
            # Only log alerts and errors
            alerts = result.get('alert_summary', []) if media_type == "image" else result.get('video_alerts', [])
            if alerts:
                logger.warning(f"SECURITY ALERTS detected in {file_path.name} ({camera_name}):")
                for alert in alerts:
                    logger.warning(f"  🚨 {alert}")
            return
        
        # INFO and DEBUG levels get detailed logging
        logger.info("="*80)
        logger.info(f"AI ANALYSIS COMPLETE: {file_path.name}")
        logger.info(f"Media Type: {media_type.upper()}")
        logger.info(f"Camera: {camera_name}")
        logger.info(f"Processing Time: {result.get('processing_time', 0):.2f}s")
        logger.info(f"Confidence: {result.get('confidence', 0):.1%}")
        
        # Log dimensions and file info
        if media_type == "image":
            logger.info(f"Dimensions: {result.get('width', 0)}x{result.get('height', 0)}")
        else:  # video
            logger.info(f"Dimensions: {result.get('width', 0)}x{result.get('height', 0)}")
            logger.info(f"Duration: {result.get('duration', 0):.1f}s")
            logger.info(f"Frames: {result.get('processed_frames', 0)}/{result.get('frame_count', 0)} analyzed")
        
        logger.info("-" * 40)
        
        # Log comprehensive description
        logger.info("COMPREHENSIVE DESCRIPTION:")
        logger.info(f"  {result.get('description', 'No description available')}")
        
        # Log detailed analysis breakdown (INFO and DEBUG)
        detailed_analysis = result.get('detailed_analysis', {})
        if detailed_analysis:
            logger.info("-" * 40)
            logger.info("DETAILED ANALYSIS BREAKDOWN:")
            
            if 'general' in detailed_analysis:
                logger.info(f"  GENERAL SCENE: {detailed_analysis['general']}")
            
            if 'security' in detailed_analysis:
                logger.info(f"  SECURITY ANALYSIS: {detailed_analysis['security']}")
            
            if 'objects' in detailed_analysis:
                logger.info(f"  OBJECT INVENTORY: {detailed_analysis['objects']}")
            
            if 'activities' in detailed_analysis:
                logger.info(f"  ACTIVITY DETECTION: {detailed_analysis['activities']}")
            
            if 'environment' in detailed_analysis:
                logger.info(f"  ENVIRONMENTAL CONTEXT: {detailed_analysis['environment']}")
        
        # Log alerts
        alerts = result.get('alert_summary', []) if media_type == "image" else result.get('video_alerts', [])
        if alerts:
            logger.info("-" * 40)
            logger.info("SECURITY ALERTS:")
            for alert in alerts:
                logger.info(f"  🚨 {alert}")
        else:
            logger.info("-" * 40)
            logger.info("SECURITY ALERTS: None detected")
        
        # Additional logging for videos
        if media_type == "video":
            if log_level == "DEBUG":
                self._log_video_analysis_debug(result)
            else:  # INFO level
                self._log_video_analysis_info(result)
        
        logger.info("="*80)

    def _log_video_analysis_info(self, result: dict):
        """Log video analysis results at INFO level (summary only)."""
        # Log activity timeline
        activity_timeline = result.get('activity_timeline', [])
        if activity_timeline:
            logger.info("-" * 40)
            logger.info("ACTIVITY TIMELINE:")
            for activity in activity_timeline:
                start_time = activity.get('start_time', 0)
                end_time = activity.get('end_time', 0)
                description = activity.get('description', 'Unknown activity')
                logger.info(f"  {start_time:.1f}s - {end_time:.1f}s: {description}")
        
        # Log summary statistics only
        frame_analyses = result.get('frame_analyses', [])
        if frame_analyses:
            logger.info("-" * 40)
            logger.info("FRAME ANALYSIS SUMMARY:")
            
            total_frames = len(frame_analyses)
            frames_with_alerts = sum(1 for f in frame_analyses if f.get('alerts', []))
            avg_confidence = sum(f.get('confidence', 0) for f in frame_analyses) / total_frames if total_frames > 0 else 0
            
            logger.info(f"  Total frames analyzed: {total_frames}")
            logger.info(f"  Frames with alerts: {frames_with_alerts}")
            logger.info(f"  Average confidence: {avg_confidence:.1%}")
            
            # Log only frames with alerts
            for i, frame in enumerate(frame_analyses):
                if frame.get('alerts', []):
                    timestamp = frame.get('timestamp', 0)
                    description = frame.get('comprehensive_description', 'No description')
                    frame_alerts = frame.get('alerts', [])
                    logger.info(f"  Alert Frame {frame.get('frame_number', i)} ({timestamp:.1f}s): {description} [ALERTS: {', '.join(frame_alerts)}]")

    def _log_video_analysis_debug(self, result: dict):
        """Log video analysis results at DEBUG level (detailed)."""
        # Log activity timeline
        activity_timeline = result.get('activity_timeline', [])
        if activity_timeline:
            logger.info("-" * 40)
            logger.info("ACTIVITY TIMELINE:")
            for activity in activity_timeline:
                start_time = activity.get('start_time', 0)
                end_time = activity.get('end_time', 0)
                description = activity.get('description', 'Unknown activity')
                logger.info(f"  {start_time:.1f}s - {end_time:.1f}s: {description}")
        
        # Log detailed frame-by-frame analysis
        frame_analyses = result.get('frame_analyses', [])
        if frame_analyses:
            logger.info("-" * 40)
            logger.info("FRAME ANALYSIS DETAILS:")
            
            # Log every 10th frame or significant frames with alerts
            for i, frame in enumerate(frame_analyses):
                if i % 10 == 0 or frame.get('alerts', []):
                    timestamp = frame.get('timestamp', 0)
                    description = frame.get('comprehensive_description', 'No description')
                    frame_alerts = frame.get('alerts', [])
                    
                    log_msg = f"  Frame {frame.get('frame_number', i)} ({timestamp:.1f}s): {description}"
                    if frame_alerts:
                        log_msg += f" [ALERTS: {', '.join(frame_alerts)}]"
                    
                    logger.info(log_msg)
            
            # Summary statistics
            total_frames = len(frame_analyses)
            frames_with_alerts = sum(1 for f in frame_analyses if f.get('alerts', []))
            avg_confidence = sum(f.get('confidence', 0) for f in frame_analyses) / total_frames if total_frames > 0 else 0
            
            logger.info(f"  Summary: {total_frames} frames analyzed, {frames_with_alerts} with alerts, avg confidence: {avg_confidence:.1%}")

    def _log_video_analysis(self, result: dict):
        """Log additional video-specific analysis results."""
        # This method is now replaced by _log_video_analysis_info and _log_video_analysis_debug
        # Kept for backward compatibility
        self._log_video_analysis_info(result)

    async def _save_detection(self, file_path: Path, media_type: str, result: dict, 
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
            await initialize_alert_types(session)
            await session.commit()
            
            camera = await get_or_create_camera(session, location, device_name)
            await session.commit()
            
            # Extract alert information
            alerts = result.get('alert_summary', []) if media_type == "image" else result.get('video_alerts', [])
            alert_flags = get_alert_flags_from_alerts(alerts)
            
            # Extract motion detection type
            motion_type = extract_motion_detection_type(file_path.name)
            
            detection = Detection(
                filename=file_path.name,
                filepath=str(file_path),  # Keep original path
                media_type=media_type,
                camera_id=camera.id,
                motion_detection_type=motion_type,
                processed=True,  # Mark as processed
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

class FoscamFileMonitor:
    """Main file monitoring service for foscam cameras."""
    
    def __init__(self):
        self.processor = FoscamMediaProcessor()
        self.observers = []

    def discover_monitor_directories(self) -> List[Path]:
        """Discover all directories that should be monitored for new files."""
        monitor_dirs = []
        
        if not FOSCAM_DIR.exists():
            logger.error(f"Foscam directory not found: {FOSCAM_DIR}")
            return monitor_dirs
        
        # Scan each camera location
        for location in CAMERA_LOCATIONS:
            location_path = FOSCAM_DIR / location
            
            if not location_path.exists():
                logger.warning(f"Camera location not found: {location_path}")
                continue
            
            # Look for device directories
            for device_dir in location_path.iterdir():
                if device_dir.is_dir():
                    device_name = device_dir.name
                    is_known_device = any(
                        device_name.startswith(pattern) 
                        for pattern in FOSCAM_DEVICE_PATTERNS
                    )
                    
                    if is_known_device:
                        # Add snap and record directories
                        snap_dir = device_dir / "snap"
                        record_dir = device_dir / "record"
                        
                        if snap_dir.exists():
                            monitor_dirs.append(snap_dir)
                        
                        if record_dir.exists():
                            monitor_dirs.append(record_dir)
        
        logger.info(f"Will monitor {len(monitor_dirs)} directories for new files")
        return monitor_dirs

    async def start(self):
        """Start monitoring foscam directories."""
        logger.info("🎥 Starting Foscam File Monitor...")
        
        # Start GPU monitoring
        start_gpu_monitoring()
        
        # Initialize processor
        await self.processor.initialize()
        
        # Discover directories to monitor
        monitor_dirs = self.discover_monitor_directories()
        
        if not monitor_dirs:
            logger.error("No directories to monitor found!")
            return
        
        # Set up file system monitoring
        event_handler = FoscamFileHandler(self.processor)
        
        # Create observers for each directory
        for monitor_dir in monitor_dirs:
            observer = Observer()
            observer.schedule(event_handler, str(monitor_dir), recursive=False)
            observer.start()
            self.observers.append(observer)
            logger.info(f"👁️  Monitoring: {monitor_dir}")
        
        logger.info("✅ Foscam File Monitor started successfully")
        
        # Process any existing unprocessed files
        await self._process_existing_files()
        
        # Keep the monitor running
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutting down file monitor...")
            await self.stop()

    async def _process_existing_files(self):
        """Process any existing files that haven't been processed yet."""
        logger.info("🔍 Scanning for existing unprocessed files...")
        
        # This is a simplified version - for full processing use foscam_crawler.py
        monitor_dirs = self.discover_monitor_directories()
        
        for monitor_dir in monitor_dirs:
            for file_path in monitor_dir.iterdir():
                if file_path.is_file():
                    suffix = file_path.suffix.lower()
                    if suffix in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
                        # Check if it matches foscam patterns
                        filename = file_path.name
                        is_foscam_file = (
                            any(filename.startswith(pattern) for pattern in FOSCAM_IMAGE_PATTERNS) or
                            any(filename.startswith(pattern) for pattern in FOSCAM_VIDEO_PATTERNS)
                        )
                        
                        if is_foscam_file:
                            camera_name = self.processor.extract_camera_name_from_path(file_path)
                            await self.processor.process_file(file_path, camera_name)
        
        logger.info("✅ Existing file scan complete")

    async def stop(self):
        """Stop the file monitor."""
        logger.info("Stopping foscam file monitor...")
        
        # Stop all observers
        for observer in self.observers:
            observer.stop()
            observer.join()
        
        # Stop GPU monitoring
        stop_gpu_monitoring()
        
        logger.info("✅ Foscam file monitor stopped")

async def main():
    """Main entry point for file monitor."""
    monitor = FoscamFileMonitor()
    await monitor.start()

if __name__ == "__main__":
    asyncio.run(main()) 