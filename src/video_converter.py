#!/usr/bin/env python3
"""
Video Conversion Service for Foscam Detection System
Converts H.265/HEVC videos to browser-friendly H.264/MP4 format
Generates video thumbnails for preview display
"""
import os
import subprocess
import hashlib
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import time

logger = logging.getLogger(__name__)

class VideoConverter:
    def __init__(self, converted_dir: str = "converted_videos", thumbnail_dir: str = "video_thumbnails"):
        self.converted_dir = Path(converted_dir)
        self.converted_dir.mkdir(exist_ok=True)
        
        self.thumbnail_dir = Path(thumbnail_dir)
        self.thumbnail_dir.mkdir(exist_ok=True)
        
        # Find ffmpeg executable
        self.ffmpeg_path = self._find_ffmpeg()
        
        # Conversion settings optimized for web playback
        self.ffmpeg_params = [
            '-c:v', 'libx264',          # H.264 codec (universal browser support)
            '-preset', 'fast',          # Fast encoding for quicker conversion
            '-crf', '23',               # Good quality/size balance
            '-maxrate', '2M',           # Max bitrate for mobile compatibility
            '-bufsize', '4M',           # Buffer size
            '-vf', 'scale=1280:720',    # Scale down to 720p for better streaming
            '-c:a', 'aac',              # AAC audio codec
            '-b:a', '128k',             # Audio bitrate
            '-movflags', '+faststart',  # Enable progressive download
            '-f', 'mp4'                 # MP4 container format
        ]
        
        # Fallback params for compatibility
        self.ffmpeg_params_simple = [
            '-c:v', 'libx264',          # H.264 codec
            '-preset', 'fast',          # Fast encoding
            '-crf', '28',               # Higher CRF for smaller files
            '-vf', 'scale=1280:720',    # Scale to 720p
            '-f', 'mp4'                 # MP4 container
        ]
        
        # Thumbnail generation params - Higher quality for large display
        self.thumbnail_params = [
            '-vf', 'thumbnail,scale=1400:1050',    # Extract thumbnail and scale to full display size
            '-frames:v', '1',                      # Extract only 1 frame
            '-f', 'image2',                        # Output as image
            '-q:v', '1'                           # Highest quality JPEG (1-31, lower is better)
        ]
    
    def _find_ffmpeg(self) -> str:
        """Find ffmpeg executable in common locations."""
        possible_paths = [
            '/usr/bin/ffmpeg',
            '/usr/local/bin/ffmpeg',
            '/opt/homebrew/bin/ffmpeg',  # macOS Homebrew
            'ffmpeg'  # Hope it's in PATH
        ]
        
        for path in possible_paths:
            if Path(path).exists() or path == 'ffmpeg':
                logger.info(f"Using ffmpeg at: {path}")
                return path
        
        logger.error("ffmpeg not found in any common locations")
        return 'ffmpeg'  # Fallback to PATH search
    
    def get_video_hash(self, video_path: Path) -> str:
        """Generate a unique hash for the video based on path and modification time."""
        stat = video_path.stat()
        content = f"{video_path}_{stat.st_size}_{stat.st_mtime}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def get_converted_path(self, original_path: Path) -> Path:
        """Get the path where converted video should be stored."""
        video_hash = self.get_video_hash(original_path)
        return self.converted_dir / f"{video_hash}.mp4"
    
    def get_thumbnail_path(self, original_path: Path) -> Path:
        """Get the path where video thumbnail should be stored."""
        video_hash = self.get_video_hash(original_path)
        return self.thumbnail_dir / f"{video_hash}.jpg"
    
    def is_already_converted(self, original_path: Path) -> bool:
        """Check if video has already been converted."""
        return self.get_converted_path(original_path).exists()
    
    def has_thumbnail(self, original_path: Path) -> bool:
        """Check if video thumbnail already exists."""
        return self.get_thumbnail_path(original_path).exists()

    async def generate_thumbnail(self, original_path: Path) -> Dict[str, Any]:
        """Generate a thumbnail image from video."""
        if not self.check_ffmpeg_available():
            return {
                'success': False,
                'error': 'ffmpeg not available',
                'thumbnail_path': None
            }
        
        original_path = Path(original_path)
        if not original_path.exists():
            return {
                'success': False,
                'error': f'Video file not found: {original_path}',
                'thumbnail_path': None
            }
        
        thumbnail_path = self.get_thumbnail_path(original_path)
        
        # Check if thumbnail already exists
        if thumbnail_path.exists():
            logger.info(f"Thumbnail already exists: {thumbnail_path}")
            return {
                'success': True,
                'message': 'Thumbnail already exists',
                'thumbnail_path': thumbnail_path
            }
        
        try:
            logger.info(f"Generating thumbnail for: {original_path}")
            
            # Build ffmpeg command
            cmd = [
                self.ffmpeg_path,
                '-i', str(original_path),
                '-ss', '00:00:05',  # Seek to 5 seconds into video
                *self.thumbnail_params,
                '-y',  # Overwrite if exists
                str(thumbnail_path)
            ]
            
            # Run ffmpeg
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and thumbnail_path.exists():
                logger.info(f"Thumbnail generated successfully: {thumbnail_path}")
                return {
                    'success': True,
                    'message': 'Thumbnail generated successfully',
                    'thumbnail_path': thumbnail_path
                }
            else:
                error_msg = stderr.decode() if stderr else 'Unknown error'
                logger.error(f"Thumbnail generation failed: {error_msg}")
                return {
                    'success': False,
                    'error': f'Thumbnail generation failed: {error_msg}',
                    'thumbnail_path': None
                }
                
        except Exception as e:
            logger.error(f"Exception during thumbnail generation: {e}")
            return {
                'success': False,
                'error': f'Exception: {str(e)}',
                'thumbnail_path': None
            }
    
    def check_ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available."""
        try:
            result = subprocess.run([self.ffmpeg_path, '-version'], 
                                  capture_output=True, timeout=5)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False
    
    async def _try_conversion(self, original_path: Path, converted_path: Path, params: list, mode: str) -> bool:
        """Try converting with specific parameters."""
        try:
            # Build ffmpeg command
            cmd = [
                self.ffmpeg_path,
                '-i', str(original_path),    # Input file
                '-y',                        # Overwrite output file
                *params,                     # Conversion parameters
                str(converted_path)          # Output file
            ]
            
            logger.info(f"Attempting {mode} conversion: {' '.join(cmd)}")
            
            # Run conversion
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                logger.info(f"{mode.capitalize()} conversion successful")
                return True
            else:
                error_msg = stderr.decode() if stderr else "Unknown ffmpeg error"
                logger.error(f"{mode.capitalize()} conversion failed: {error_msg}")
                
                # Clean up failed conversion
                if converted_path.exists():
                    converted_path.unlink()
                
                return False
                
        except Exception as e:
            logger.error(f"{mode.capitalize()} conversion exception: {str(e)}")
            
            # Clean up failed conversion
            if converted_path.exists():
                converted_path.unlink()
            
            return False
    
    async def convert_video(self, original_path: Path) -> Dict[str, Any]:
        """Convert a video to browser-friendly format."""
        try:
            if not original_path.exists():
                return {"success": False, "error": "Original video file not found"}
            
            # Check if ffmpeg is available
            if not self.check_ffmpeg_available():
                return {"success": False, "error": f"ffmpeg not found at {self.ffmpeg_path}. Please install ffmpeg: sudo apt install ffmpeg"}
            
            converted_path = self.get_converted_path(original_path)
            
            # Check if already converted
            if self.is_already_converted(original_path):
                logger.info(f"Video already converted: {converted_path}")
                return {
                    "success": True,
                    "converted_path": converted_path,
                    "cached": True,
                    "file_size": converted_path.stat().st_size
                }
            
            logger.info(f"Converting video: {original_path} -> {converted_path}")
            start_time = time.time()
            
            # Try conversion with optimized parameters first
            success = await self._try_conversion(original_path, converted_path, self.ffmpeg_params, "optimized")
            
            # If that fails, try with simple parameters
            if not success:
                logger.warning("Optimized conversion failed, trying simple parameters")
                success = await self._try_conversion(original_path, converted_path, self.ffmpeg_params_simple, "simple")
            
            if success:
                conversion_time = time.time() - start_time
                file_size = converted_path.stat().st_size
                
                logger.info(f"Video conversion successful: {conversion_time:.2f}s, {file_size} bytes")
                
                return {
                    "success": True,
                    "converted_path": converted_path,
                    "cached": False,
                    "conversion_time": conversion_time,
                    "file_size": file_size,
                    "original_size": original_path.stat().st_size
                }
            else:
                return {
                    "success": False,
                    "error": "Both optimized and simple conversion attempts failed. Check logs for details."
                }
                
        except Exception as e:
            logger.error(f"Video conversion exception: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_video_info(self, video_path: Path) -> Dict[str, Any]:
        """Get information about a video file."""
        try:
            if not video_path.exists():
                return {"success": False, "error": "Video file not found"}
            
            stat = video_path.stat()
            return {
                "success": True,
                "file_size": stat.st_size,
                "modified_time": stat.st_mtime,
                "format": "MP4 (H.264/AAC)" if video_path.suffix.lower() == '.mp4' else "Original format"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def cleanup_old_conversions(self, max_age_days: int = 7):
        """Clean up converted videos older than specified days."""
        try:
            current_time = time.time()
            max_age_seconds = max_age_days * 24 * 60 * 60
            
            cleaned_count = 0
            for converted_file in self.converted_dir.glob("*.mp4"):
                if current_time - converted_file.stat().st_mtime > max_age_seconds:
                    converted_file.unlink()
                    cleaned_count += 1
                    logger.info(f"Cleaned up old converted video: {converted_file}")
            
            logger.info(f"Cleanup complete: removed {cleaned_count} old converted videos")
            return {"success": True, "cleaned_count": cleaned_count}
            
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
            return {"success": False, "error": str(e)}

# Global converter instance
video_converter = VideoConverter() 