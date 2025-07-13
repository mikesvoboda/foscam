import torch
from transformers import Blip2Processor, Blip2ForConditionalGeneration
from PIL import Image
import cv2
import numpy as np
from typing import List, Tuple, Optional, Dict
import time
from pathlib import Path
import logging
import re

# Import GPU monitoring
from gpu_monitor import log_gpu_status, clear_gpu_cache, check_gpu_limits, gpu_monitor

logger = logging.getLogger(__name__)

class VisionLanguageModel:
    def __init__(self, model_name: str, device: str = "cuda", use_8bit: bool = True):
        """
        Initialize the vision-language model.
        
        Args:
            model_name: Hugging Face model name (e.g., "Salesforce/blip2-t5-xl")
            device: Device to run on ("cuda" or "cpu")
            use_8bit: Whether to use 8-bit quantization to save memory
        """
        self.device = device
        self.model_name = model_name
        self.use_8bit = use_8bit
        
        logger.info(f"Loading model: {model_name}")
        
        # Log initial GPU status
        log_gpu_status("Initial state")
        
        # Check GPU memory before loading large models
        if device == "cuda" and torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"GPU Memory: {gpu_memory:.1f}GB total")
            
            # Check if we have enough memory
            limits = check_gpu_limits()
            if limits["warning"]:
                logger.warning("GPU memory already in warning zone before model loading!")
                suggestions = gpu_monitor.suggest_optimizations()
                for suggestion in suggestions[:2]:
                    logger.warning(f"SUGGESTION: {suggestion}")
            
            if "t5-xl" in model_name.lower():
                if gpu_memory < 20:
                    logger.warning(f"T5-XL requires ~18-22GB VRAM. You have {gpu_memory:.1f}GB.")
                if gpu_memory < 16:
                    logger.error(f"Insufficient GPU memory for T5-XL. Consider using blip2-opt-2.7b instead.")
        
        # Clear cache before loading
        clear_gpu_cache("Before model loading")
        
        # Load processor
        logger.info("Loading processor...")
        self.processor = Blip2Processor.from_pretrained(model_name)
        log_gpu_status("After processor loading")
        
        # Load model with optional 8-bit quantization
        logger.info("Loading model...")
        loading_start_time = time.time()
        
        if use_8bit and device == "cuda":
            try:
                self.model = Blip2ForConditionalGeneration.from_pretrained(
                    model_name,
                    load_in_8bit=True,
                    device_map="auto",
                    torch_dtype=torch.float16  # Additional memory optimization
                )
                logger.info("Model loaded with 8-bit quantization")
            except Exception as e:
                logger.error(f"Failed to load with 8-bit quantization: {e}")
                logger.info("Falling back to FP16...")
                self.model = Blip2ForConditionalGeneration.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16
                )
                self.model.to(device)
        else:
            self.model = Blip2ForConditionalGeneration.from_pretrained(model_name)
            self.model.to(device)
        
        loading_time = time.time() - loading_start_time
        logger.info(f"Model loading took {loading_time:.1f} seconds")
        
        self.model.eval()
        
        # Clear cache after loading and log final status
        clear_gpu_cache("After model loading")
        log_gpu_status("Model loaded")
        
        # Check final memory state
        limits = check_gpu_limits()
        if limits["critical"]:
            logger.critical("GPU memory is CRITICAL after model loading!")
            suggestions = gpu_monitor.suggest_optimizations()
            for suggestion in suggestions[:3]:
                logger.critical(f"URGENT: {suggestion}")
        elif limits["warning"]:
            logger.warning("GPU memory in warning zone after model loading")
            suggestions = gpu_monitor.suggest_optimizations()
            for suggestion in suggestions[:2]:
                logger.warning(f"SUGGESTION: {suggestion}")
        
        logger.info("Model loaded successfully")

    def generate_detailed_description(self, image: Image.Image) -> Dict[str, str]:
        """
        Generate detailed analysis covering multiple aspects using enhanced T5-XL capabilities.
        
        Returns:
            Dictionary with detailed analysis for each aspect
        """
        try:
            # Prepare inputs once
            inputs = self.processor(image, return_tensors="pt").to(self.device)
            
            logger.debug("Generating detailed multi-aspect analysis...")
            
            # Define comprehensive analysis prompts for enhanced T5-XL analysis
            analysis_prompts = {
                "general": "Question: What is happening in this image? Describe the scene in detail. Answer:",
                "security": "Question: From a security perspective, what security-relevant elements, people, vehicles, or activities can you identify in this image? Answer:",
                "objects": "Question: What objects, items, and entities can you identify in this image? List them with their locations if possible. Answer:",
                "activities": "Question: What activities, movements, or behaviors are occurring in this image? Answer:",
                "environment": "Question: What is the environmental context? Describe the location, time of day, weather conditions, and setting. Answer:"
            }
            
            detailed_descriptions = {}
            
            # Generate each analysis aspect
            for aspect, prompt in analysis_prompts.items():
                logger.debug(f"  Analyzing {aspect} aspect...")
                description = self._generate_with_prompt(inputs, prompt, max_length=100)
                detailed_descriptions[aspect] = description
                logger.debug(f"  {aspect.upper()}: {description}")
            
            logger.debug("Multi-aspect analysis complete")
            return detailed_descriptions
            
        except Exception as e:
            logger.error(f"Error generating detailed description: {str(e)}")
            return {
                "general": "Error analyzing scene",
                "security": "Error analyzing security aspects",
                "objects": "Error identifying objects",
                "activities": "Error detecting activities",
                "environment": "Error analyzing environment"
            }

    def _generate_with_prompt(self, inputs: dict, prompt: str, max_length: int = 100) -> str:
        """Generate caption with a specific prompt."""
        try:
            # For BLIP-2, we can't directly use prompts, but we can influence generation
            # through generation parameters and post-process for more detailed output
            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_length=max_length,
                    min_length=20,  # Ensure minimum detail
                    num_beams=5,
                    repetition_penalty=1.2,
                    length_penalty=1.1,
                    early_stopping=True,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    no_repeat_ngram_size=3  # Avoid repetition
                )
            
            caption = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            return caption.strip()
            
        except Exception as e:
            logger.error(f"Error generating with prompt: {e}")
            return "Error generating description"

    def generate_caption(self, image: Image.Image, max_length: int = 150) -> Tuple[str, float]:
        """
        Generate a comprehensive caption combining multiple analysis types.
        
        Args:
            image: PIL Image
            max_length: Maximum length of generated caption
            
        Returns:
            Tuple of (comprehensive_caption, confidence_score)
        """
        try:
            start_time = time.time()
            
            # Generate detailed descriptions
            descriptions = self.generate_detailed_description(image)
            
            # Combine descriptions into comprehensive analysis
            comprehensive_caption = self._create_comprehensive_description(descriptions)
            
            # Calculate confidence based on description quality and detail
            confidence = self._calculate_confidence(comprehensive_caption, descriptions)
            
            processing_time = time.time() - start_time
            logger.debug(f"Comprehensive caption generation took {processing_time:.2f}s")
            
            return comprehensive_caption, confidence
            
        except Exception as e:
            logger.error(f"Error generating comprehensive caption: {str(e)}")
            return "Error generating comprehensive description", 0.0

    def _create_comprehensive_description(self, descriptions: Dict[str, str]) -> str:
        """Combine multiple descriptions into a comprehensive analysis."""
        try:
            # Start with general description as base
            general = descriptions.get("general", "")
            security = descriptions.get("security", "")
            objects = descriptions.get("objects", "")
            activities = descriptions.get("activities", "")
            environment = descriptions.get("environment", "")
            
            # Create structured description
            parts = []
            
            # Main scene
            if general:
                parts.append(f"SCENE: {general}")
            
            # Security analysis
            if security and "error" not in security.lower():
                security_relevant = self._extract_security_relevance(security)
                if security_relevant:
                    parts.append(f"SECURITY: {security_relevant}")
            
            # Object inventory
            if objects:
                object_summary = self._extract_object_counts(objects)
                if object_summary:
                    parts.append(f"OBJECTS: {object_summary}")
            
            # Activities
            if activities and "no activities" not in activities.lower():
                activity_summary = self._extract_activities(activities)
                if activity_summary:
                    parts.append(f"ACTIVITY: {activity_summary}")
            
            # Environment
            if environment:
                env_summary = self._extract_environment_info(environment)
                if env_summary:
                    parts.append(f"SETTING: {env_summary}")
            
            # Combine all parts
            comprehensive = " | ".join(parts)
            
            # Add alert tags for important detections
            alert_tags = self._generate_alert_tags(descriptions)
            if alert_tags:
                comprehensive += f" | ALERTS: {', '.join(alert_tags)}"
            
            return comprehensive if comprehensive else general
            
        except Exception as e:
            logger.error(f"Error creating comprehensive description: {e}")
            return descriptions.get("general", "Error creating description")

    def _extract_security_relevance(self, security_desc: str) -> str:
        """Extract security-relevant information."""
        security_keywords = [
            "person", "people", "individual", "man", "woman", "child",
            "vehicle", "car", "truck", "van", "motorcycle", "bike",
            "package", "delivery", "box", "bag", "briefcase",
            "suspicious", "unusual", "unexpected", "unauthorized"
        ]
        
        relevant_parts = []
        for keyword in security_keywords:
            if keyword in security_desc.lower():
                # Extract sentence containing the keyword
                sentences = security_desc.split('.')
                for sentence in sentences:
                    if keyword in sentence.lower():
                        relevant_parts.append(sentence.strip())
                        break
        
        return "; ".join(set(relevant_parts))

    def _extract_object_counts(self, objects_desc: str) -> str:
        """Extract object counts and types."""
        # Look for patterns like "2 people", "one car", "several packages"
        import re
        
        count_patterns = [
            r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(people|persons?|individuals?)',
            r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(cars?|vehicles?|trucks?|vans?)',
            r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(packages?|boxes?|bags?)',
            r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(dogs?|cats?|animals?)'
        ]
        
        findings = []
        for pattern in count_patterns:
            matches = re.findall(pattern, objects_desc.lower())
            for match in matches:
                findings.append(f"{match[0]} {match[1]}")
        
        return ", ".join(findings) if findings else objects_desc[:50]

    def _extract_activities(self, activities_desc: str) -> str:
        """Extract and categorize activities."""
        activity_keywords = {
            "movement": ["walking", "running", "moving", "approaching", "leaving"],
            "delivery": ["delivering", "dropping off", "picking up", "carrying"],
            "vehicles": ["driving", "parking", "backing up", "pulling in"],
            "interaction": ["talking", "meeting", "greeting", "conversation"]
        }
        
        detected_activities = []
        for category, keywords in activity_keywords.items():
            for keyword in keywords:
                if keyword in activities_desc.lower():
                    detected_activities.append(keyword)
                    break
        
        return ", ".join(detected_activities) if detected_activities else activities_desc[:50]

    def _extract_environment_info(self, environment_desc: str) -> str:
        """Extract key environment information."""
        env_keywords = {
            "time": ["morning", "afternoon", "evening", "night", "dawn", "dusk", "daylight", "dark"],
            "weather": ["sunny", "cloudy", "rainy", "foggy", "clear", "overcast"],
            "location": ["residential", "commercial", "parking", "driveway", "street", "yard"]
        }
        
        env_info = []
        for category, keywords in env_keywords.items():
            for keyword in keywords:
                if keyword in environment_desc.lower():
                    env_info.append(keyword)
                    break
        
        return ", ".join(env_info) if env_info else environment_desc[:50]

    def _generate_alert_tags(self, descriptions: Dict[str, str]) -> List[str]:
        """Generate alert tags for important detections."""
        alerts = []
        
        all_text = " ".join(descriptions.values()).lower()
        
        # Critical alerts
        if any(word in all_text for word in ["person", "people", "individual", "man", "woman"]):
            alerts.append("PERSON_DETECTED")
        
        if any(word in all_text for word in ["vehicle", "car", "truck", "van"]):
            alerts.append("VEHICLE_DETECTED")
        
        if any(word in all_text for word in ["package", "delivery", "box", "bag"]):
            alerts.append("PACKAGE_DETECTED")
        
        if any(word in all_text for word in ["suspicious", "unusual", "unexpected"]):
            alerts.append("UNUSUAL_ACTIVITY")
        
        if "night" in all_text or "dark" in all_text:
            alerts.append("NIGHT_TIME")
        
        return alerts

    def _calculate_confidence(self, caption: str, descriptions: Dict[str, str]) -> float:
        """Calculate confidence based on description quality and detail."""
        try:
            # Base confidence on length and detail
            base_confidence = min(1.0, len(caption.split()) / 50.0)
            
            # Bonus for multiple description types
            successful_descriptions = sum(1 for desc in descriptions.values() if desc and "error" not in desc.lower())
            description_bonus = (successful_descriptions - 1) * 0.1
            
            # Bonus for specific detections
            security_bonus = 0.1 if any(alert in caption for alert in ["PERSON_DETECTED", "VEHICLE_DETECTED"]) else 0
            
            final_confidence = min(1.0, base_confidence + description_bonus + security_bonus)
            return final_confidence
            
        except Exception:
            return 0.5  # Default confidence

    def process_image(self, image_path: Path) -> dict:
        """
        Process a single image file with enhanced detailed analysis.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Dictionary with comprehensive processing results
        """
        try:
            logger.info(f"Processing image: {image_path}")
            processing_start = time.time()
            
            # Check memory before processing
            limits = check_gpu_limits()
            if limits["critical"]:
                logger.warning("GPU memory critical before image processing - clearing cache")
                clear_gpu_cache("Before image processing")
            
            # Load and process image
            image = Image.open(image_path).convert('RGB')
            
            # Get image dimensions
            width, height = image.size
            
            # Generate comprehensive description using enhanced T5-XL capabilities
            comprehensive_description, confidence = self.generate_caption(image)
            
            # Also get the detailed breakdown for additional analysis
            detailed_descriptions = self.generate_detailed_description(image)
            
            # Extract camera name from path
            camera_name = self._extract_camera_name(image_path)
            
            processing_time = time.time() - processing_start
            
            result = {
                "success": True,
                "description": comprehensive_description,
                "confidence": confidence,
                "camera_name": camera_name,
                "width": width,
                "height": height,
                "processing_time": processing_time,
                # Additional detailed analysis
                "detailed_analysis": detailed_descriptions,
                "alert_summary": self._generate_alert_tags(detailed_descriptions)
            }
            
            logger.info(f"Image processed in {processing_time:.2f}s")
            logger.info(f"Comprehensive: {comprehensive_description}")
            
            # Log alerts if any
            if result["alert_summary"]:
                logger.info(f"ALERTS: {', '.join(result['alert_summary'])}")
            
            # Log GPU status after processing (periodically)
            if hasattr(self, '_last_gpu_log'):
                if time.time() - self._last_gpu_log > 60:  # Log every minute
                    log_gpu_status("Image processing")
                    self._last_gpu_log = time.time()
            else:
                self._last_gpu_log = time.time()
                log_gpu_status("First image processing")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "description": "Error processing image",
                "confidence": 0.0,
                "camera_name": self._extract_camera_name(image_path),
                "processing_time": 0.0,
                "detailed_analysis": {},
                "alert_summary": []
            }

    def process_video(self, video_path: Path, sample_rate: int = 30) -> dict:
        """
        Process a video file by sampling frames with enhanced analysis.
        
        Args:
            video_path: Path to video file
            sample_rate: Process every Nth frame
            
        Returns:
            Dictionary with comprehensive processing results
        """
        try:
            logger.info(f"Processing video: {video_path} (sample rate: {sample_rate})")
            processing_start = time.time()
            
            # Check memory before video processing
            limits = check_gpu_limits()
            if limits["warning"]:
                logger.warning("GPU memory warning before video processing")
                clear_gpu_cache("Before video processing")
            
            # Open video
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                raise ValueError(f"Could not open video: {video_path}")
            
            # Get video properties
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duration = total_frames / fps if fps > 0 else 0
            
            logger.info(f"Video: {total_frames} frames, {fps:.1f} fps, {width}x{height}, {duration:.1f}s")
            
            # Sample frames and generate enhanced descriptions
            frame_analyses = []
            frame_count = 0
            processed_frames = 0
            all_alerts = set()
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Sample frames based on sample_rate
                if frame_count % sample_rate == 0:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_image = Image.fromarray(frame_rgb)
                    
                    # Generate comprehensive description for this frame
                    comprehensive_desc, confidence = self.generate_caption(frame_image)
                    detailed_descs = self.generate_detailed_description(frame_image)
                    alerts = self._generate_alert_tags(detailed_descs)
                    
                    timestamp = frame_count / fps if fps > 0 else frame_count
                    frame_analysis = {
                        "timestamp": timestamp,
                        "frame_number": frame_count,
                        "comprehensive_description": comprehensive_desc,
                        "detailed_analysis": detailed_descs,
                        "confidence": confidence,
                        "alerts": alerts
                    }
                    
                    frame_analyses.append(frame_analysis)
                    all_alerts.update(alerts)
                    
                    processed_frames += 1
                    logger.debug(f"Frame {frame_count} ({timestamp:.1f}s): {comprehensive_desc}")
                    
                    # Check memory periodically during video processing
                    if processed_frames % 5 == 0:  # Check every 5 frames (more frequent for detailed analysis)
                        limits = check_gpu_limits()
                        if limits["critical"]:
                            logger.warning(f"GPU memory critical during video processing (frame {frame_count})")
                            clear_gpu_cache("During video processing")
                
                frame_count += 1
            
            cap.release()
            
            # Create comprehensive video summary
            video_summary = self._create_video_summary(frame_analyses)
            
            # Calculate overall confidence
            avg_confidence = sum(f["confidence"] for f in frame_analyses) / len(frame_analyses) if frame_analyses else 0.0
            
            # Extract camera name
            camera_name = self._extract_camera_name(video_path)
            
            processing_time = time.time() - processing_start
            
            result = {
                "success": True,
                "description": video_summary,
                "confidence": avg_confidence,
                "camera_name": camera_name,
                "width": width,
                "height": height,
                "duration": duration,
                "frame_count": total_frames,
                "processed_frames": processed_frames,
                "processing_time": processing_time,
                # Enhanced video analysis
                "frame_analyses": frame_analyses,
                "video_alerts": list(all_alerts),
                "activity_timeline": self._create_activity_timeline(frame_analyses)
            }
            
            logger.info(f"Video processed in {processing_time:.2f}s: {processed_frames} frames analyzed")
            logger.info(f"Summary: {video_summary}")
            
            # Log video-wide alerts
            if result["video_alerts"]:
                logger.info(f"VIDEO ALERTS: {', '.join(result['video_alerts'])}")
            
            # Log GPU status after video processing
            log_gpu_status("After video processing")
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "description": "Error processing video",
                "confidence": 0.0,
                "camera_name": self._extract_camera_name(video_path),
                "processing_time": 0.0,
                "frame_analyses": [],
                "video_alerts": [],
                "activity_timeline": []
            }

    def _create_video_summary(self, frame_analyses: List[dict]) -> str:
        """Create a comprehensive video summary from frame analyses."""
        if not frame_analyses:
            return "No content detected in video"
        
        try:
            # Extract key information across all frames
            all_alerts = set()
            key_activities = set()
            environments = set()
            
            for frame in frame_analyses:
                all_alerts.update(frame.get("alerts", []))
                
                # Extract activities from detailed analysis
                activities = frame.get("detailed_analysis", {}).get("activities", "")
                if activities:
                    activity_summary = self._extract_activities(activities)
                    if activity_summary:
                        key_activities.update(activity_summary.split(", "))
                
                # Extract environment info
                env = frame.get("detailed_analysis", {}).get("environment", "")
                if env:
                    env_summary = self._extract_environment_info(env)
                    if env_summary:
                        environments.update(env_summary.split(", "))
            
            # Create summary
            summary_parts = []
            
            # Duration and frame info
            duration = frame_analyses[-1]["timestamp"] if frame_analyses else 0
            summary_parts.append(f"VIDEO ANALYSIS ({duration:.1f}s, {len(frame_analyses)} key frames)")
            
            # Key activities throughout video
            if key_activities:
                summary_parts.append(f"ACTIVITIES: {', '.join(sorted(key_activities))}")
            
            # Environment
            if environments:
                summary_parts.append(f"ENVIRONMENT: {', '.join(sorted(environments))}")
            
            # Most detailed frame description
            most_detailed = max(frame_analyses, key=lambda x: len(x.get("comprehensive_description", "")))
            if most_detailed:
                main_scene = most_detailed["comprehensive_description"].split(" | ")[0]  # Get SCENE part
                summary_parts.append(f"MAIN SCENE: {main_scene.replace('SCENE: ', '')}")
            
            # Alerts throughout video
            if all_alerts:
                summary_parts.append(f"ALERTS: {', '.join(sorted(all_alerts))}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error creating video summary: {e}")
            return f"Video analysis completed ({len(frame_analyses)} frames processed)"

    def _create_activity_timeline(self, frame_analyses: List[dict]) -> List[dict]:
        """Create a timeline of significant activities in the video."""
        timeline = []
        
        try:
            for frame in frame_analyses:
                timestamp = frame.get("timestamp", 0)
                alerts = frame.get("alerts", [])
                activities = frame.get("detailed_analysis", {}).get("activities", "")
                
                # Create timeline entry for frames with significant activity
                if alerts or any(keyword in activities.lower() for keyword in ["walking", "driving", "delivering", "approaching"]):
                    timeline_entry = {
                        "timestamp": timestamp,
                        "time_formatted": f"{int(timestamp//60):02d}:{int(timestamp%60):02d}",
                        "alerts": alerts,
                        "activities": self._extract_activities(activities) if activities else "",
                        "description": frame.get("comprehensive_description", "").split(" | ")[0]  # Main scene only
                    }
                    timeline.append(timeline_entry)
            
            return timeline
            
        except Exception as e:
            logger.error(f"Error creating activity timeline: {e}")
            return []

    def _extract_camera_name(self, file_path: Path) -> str:
        """Extract camera name from foscam file path structure."""
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
                
                # Create readable camera name from location and device
                camera_name = f"{camera_location}_{device_name}"
                return camera_name
            
            # Fallback: try to extract meaningful name from path
            if len(path_parts) >= 3:
                # Use the last two meaningful directories
                return f"{path_parts[-3]}_{path_parts[-2]}"
            
            logger.warning(f"Could not extract camera name from path: {file_path}")
            return "unknown_camera"
            
        except Exception as e:
            logger.error(f"Error extracting camera name from {file_path}: {str(e)}")
            return "unknown_camera" 