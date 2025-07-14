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
from src.gpu_monitor import gpu_monitor

# Import modular lookup tables and prompts
from src.ai_prompts import get_analysis_prompts, get_timeline_prompts, IMAGE_ANALYSIS_PROMPTS
from src.security_keywords import (
    extract_security_relevance, extract_object_counts, extract_activities,
    extract_environment_info, generate_alert_tags, extract_changes,
    classify_event_type, extract_vehicle_details, extract_person_details
)

# Import AI analysis logging
from src.logging_config import setup_ai_analysis_logger

# Import video converter for thumbnail generation
from src.video_converter import VideoConverter

logger = logging.getLogger(__name__)

# Initialize AI analysis logger
ai_logger = setup_ai_analysis_logger("DEBUG")

# Initialize video converter
video_converter = VideoConverter()

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
        ai_logger.info("Checking initial GPU status")
        
        # Check GPU memory before loading large models
        if device == "cuda" and torch.cuda.is_available():
            gpu_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
            logger.info(f"GPU Memory: {gpu_memory:.1f}GB total")
            
            # Check if we have enough memory
            current_metrics = gpu_monitor.get_current_metrics()
            if current_metrics and current_metrics.memory_utilization > 80:
                logger.warning("GPU memory already at high utilization before model loading!")
            
            if "t5-xl" in model_name.lower():
                if gpu_memory < 20:
                    logger.warning(f"T5-XL requires ~18-22GB VRAM. You have {gpu_memory:.1f}GB.")
                if gpu_memory < 16:
                    logger.error(f"Insufficient GPU memory for T5-XL. Consider using blip2-opt-2.7b instead.")
        
        # Clear cache before loading
        # clear_gpu_cache("Before model loading") # This line is removed as per the edit hint
        
        # Load processor
        logger.info("Loading processor...")
        self.processor = Blip2Processor.from_pretrained(model_name)
        # log_gpu_status("After processor loading") # This line is removed as per the edit hint
        
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
        # clear_gpu_cache("After model loading") # This line is removed as per the edit hint
        # log_gpu_status("Model loaded") # This line is removed as per the edit hint
        
        # Check final memory state
        # limits = check_gpu_limits() # This line is removed as per the edit hint
        # if limits["critical"]: # This line is removed as per the edit hint
        #     logger.critical("GPU memory is CRITICAL after model loading!") # This line is removed as per the edit hint
        #     suggestions = gpu_monitor.suggest_optimizations() # This line is removed as per the edit hint
        #     for suggestion in suggestions[:3]: # This line is removed as per the edit hint
        #         logger.critical(f"URGENT: {suggestion}") # This line is removed as per the edit hint
        # elif limits["warning"]: # This line is removed as per the edit hint
        #     logger.warning("GPU memory in warning zone after model loading") # This line is removed as per the edit hint
        #     suggestions = gpu_monitor.suggest_optimizations() # This line is removed as per the edit hint
        #     for suggestion in suggestions[:2]: # This line is removed as per the edit hint
        #         logger.warning(f"SUGGESTION: {suggestion}") # This line is removed as per the edit hint
        
        logger.info("Model loaded successfully")

    def generate_detailed_description(self, image: Image.Image) -> Dict[str, str]:
        """
        Generate detailed descriptions for multiple aspects of an image.
        
        Args:
            image: PIL Image
            
        Returns:
            Dictionary with aspect-specific descriptions
        """
        analysis_start_time = time.time()
        ai_logger.info("=== STARTING DETAILED IMAGE ANALYSIS ===")
        
        try:
            # Prepare inputs once
            inputs = self.processor(image, return_tensors="pt").to(self.device)
            
            logger.debug("Generating detailed multi-aspect analysis...")
            
            # Get contextual prompts based on analysis requirements
            # TODO: Extract camera location and time from context for better prompts
            analysis_prompts = get_analysis_prompts()
            
            ai_logger.info(f"ANALYSIS_PROMPTS_COUNT: {len(analysis_prompts)}")
            ai_logger.debug(f"ANALYSIS_ASPECTS: {list(analysis_prompts.keys())}")
            
            detailed_descriptions = {}
            
            # Generate each analysis aspect
            for aspect, prompt in analysis_prompts.items():
                logger.debug(f"  Analyzing {aspect} aspect...")
                ai_logger.info(f"ANALYZING_ASPECT: {aspect}")
                
                description = self._generate_with_prompt(inputs, prompt)
                detailed_descriptions[aspect] = description
                
                ai_logger.debug(f"ASPECT_RESULT: {aspect} -> {description[:100]}...")
                logger.debug(f"  {aspect.upper()}: {description}")
            
            analysis_duration = time.time() - analysis_start_time
            ai_logger.info(f"=== DETAILED ANALYSIS COMPLETE === (duration: {analysis_duration:.3f}s)")
            ai_logger.info(f"ANALYSIS_SUMMARY: {len(detailed_descriptions)} aspects analyzed")
            
            logger.debug("Multi-aspect analysis complete")
            return detailed_descriptions
            
        except Exception as e:
            analysis_duration = time.time() - analysis_start_time
            ai_logger.error(f"ANALYSIS_ERROR: {str(e)} (duration: {analysis_duration:.3f}s)")
            logger.error(f"Error generating detailed description: {str(e)}")
            return {
                "general": "Error analyzing scene",
                "security": "Error analyzing security aspects",
                "objects": "Error identifying objects",
                "activities": "Error detecting activities",
                "environment": "Error analyzing environment"
            }

    def _generate_with_prompt(self, inputs: dict, prompt: str, max_length: int = 512) -> str:
        """Generate caption with a specific prompt."""
        prompt_start_time = time.time()
        
        # Log the prompt being sent
        ai_logger.info(f"PROMPT_SENT: {prompt}")
        ai_logger.debug(f"PROMPT_CONFIG: max_length={max_length}")
        
        try:
            # For BLIP-2, we can't directly use prompts, but we can influence generation
            # through generation parameters and post-process for more detailed output
            with torch.no_grad():
                generated_ids = self.model.generate(
                    **inputs,
                    max_length=max_length,
                    min_length=30,  # Ensure minimum detail for security analysis
                    num_beams=5,
                    repetition_penalty=1.2,
                    length_penalty=1.1,
                    early_stopping=True,  # Let model stop naturally when done
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    no_repeat_ngram_size=3  # Avoid repetition
                )
            
            caption = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            response = caption.strip()
            
            # Calculate timing and log response
            prompt_duration = time.time() - prompt_start_time
            ai_logger.info(f"RESPONSE_RECEIVED: {response}")
            ai_logger.debug(f"PROMPT_TIMING: {prompt_duration:.3f}s")
            ai_logger.debug(f"RESPONSE_LENGTH: {len(response)} characters")
            
            return response
            
        except Exception as e:
            prompt_duration = time.time() - prompt_start_time
            ai_logger.error(f"PROMPT_ERROR: {str(e)} (duration: {prompt_duration:.3f}s)")
            ai_logger.error(f"FAILED_PROMPT: {prompt}")
            return "Error generating description"

    def generate_caption(self, image: Image.Image, max_length: int = 400) -> Tuple[str, float]:
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
                security_relevant = extract_security_relevance(security)
                if security_relevant:
                    parts.append(f"SECURITY: {security_relevant}")
            
            # Object inventory
            if objects:
                object_summary = extract_object_counts(objects)
                if object_summary:
                    parts.append(f"OBJECTS: {object_summary}")
            
            # Activities
            if activities and "no activities" not in activities.lower():
                activity_summary = extract_activities(activities)
                if activity_summary:
                    parts.append(f"ACTIVITY: {activity_summary}")
            
            # Environment
            if environment:
                env_summary = extract_environment_info(environment)
                if env_summary:
                    parts.append(f"SETTING: {env_summary}")
            
            # Combine all parts
            comprehensive = " | ".join(parts)
            
            # Add alert tags for important detections
            alert_tags = generate_alert_tags(descriptions)
            if alert_tags:
                comprehensive += f" | ALERTS: {', '.join(alert_tags)}"
            
            return comprehensive if comprehensive else general
            
        except Exception as e:
            logger.error(f"Error creating comprehensive description: {e}")
            return descriptions.get("general", "Error creating description")

    def _extract_security_relevance(self, security_desc: str) -> str:
        """Extract security-relevant information from security description."""
        return extract_security_relevance(security_desc)

    def _extract_object_counts(self, objects_desc: str) -> str:
        """Extract object counts and types."""
        return extract_object_counts(objects_desc)

    def _extract_activities(self, activities_desc: str) -> str:
        """Extract and categorize activities."""
        return extract_activities(activities_desc)

    def _extract_environment_info(self, environment_desc: str) -> str:
        """Extract key environment information."""
        return extract_environment_info(environment_desc)

    def _generate_alert_tags(self, descriptions: Dict[str, str]) -> List[str]:
        """Generate alert tags for important detections."""
        return generate_alert_tags(descriptions)

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
        session_start_time = time.time()
        ai_logger.info("="*60)
        ai_logger.info(f"STARTING IMAGE PROCESSING SESSION")
        ai_logger.info(f"IMAGE_PATH: {image_path}")
        ai_logger.info(f"IMAGE_NAME: {image_path.name}")
        
        try:
            logger.info(f"Processing image: {image_path}")
            processing_start = time.time()
            
            # Check memory before processing
            # limits = check_gpu_limits() # This line is removed as per the edit hint
            # if limits["critical"]: # This line is removed as per the edit hint
            #     logger.warning("GPU memory critical before image processing - clearing cache") # This line is removed as per the edit hint
            #     clear_gpu_cache("Before image processing") # This line is removed as per the edit hint
            
            # Load and process image
            image = Image.open(image_path).convert('RGB')
            
            # Get image dimensions
            width, height = image.size
            ai_logger.info(f"IMAGE_DIMENSIONS: {width}x{height}")
            
            # Generate comprehensive description using enhanced T5-XL capabilities
            comprehensive_description, confidence = self.generate_caption(image)
            
            # Also get the detailed breakdown for additional analysis
            detailed_descriptions = self.generate_detailed_description(image)
            
            # Extract camera name from path
            camera_name = self._extract_camera_name(image_path)
            ai_logger.info(f"CAMERA_NAME: {camera_name}")
            
            processing_time = time.time() - processing_start
            session_duration = time.time() - session_start_time
            
            # Log final results
            ai_logger.info(f"COMPREHENSIVE_DESCRIPTION: {comprehensive_description}")
            ai_logger.info(f"CONFIDENCE_SCORE: {confidence}")
            ai_logger.info(f"PROCESSING_TIME: {processing_time:.3f}s")
            ai_logger.info(f"SESSION_DURATION: {session_duration:.3f}s")
            
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
            
            ai_logger.info(f"ALERT_SUMMARY: {result['alert_summary']}")
            ai_logger.info("IMAGE PROCESSING SESSION COMPLETED SUCCESSFULLY")
            ai_logger.info("="*60)
            
            return result
            
        except Exception as e:
            session_duration = time.time() - session_start_time
            ai_logger.error(f"IMAGE_PROCESSING_ERROR: {str(e)}")
            ai_logger.error(f"FAILED_IMAGE_PATH: {image_path}")
            ai_logger.error(f"ERROR_SESSION_DURATION: {session_duration:.3f}s")
            ai_logger.info("="*60)
            
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

    async def process_video(self, video_path: Path, sample_rate: int = 30) -> dict:
        """
        Process a video file by sampling frames with enhanced timeline analysis.
        
        Args:
            video_path: Path to video file
            sample_rate: Process every Nth frame
            
        Returns:
            Dictionary with comprehensive processing results
        """
        try:
            logger.info(f"Processing video: {video_path} (sample rate: {sample_rate})")
            processing_start = time.time()
            
            # Log video processing session start
            ai_logger.info("="*60)
            ai_logger.info(f"STARTING VIDEO PROCESSING SESSION")
            ai_logger.info(f"VIDEO_PATH: {video_path}")
            ai_logger.info(f"VIDEO_NAME: {video_path.name}")
            ai_logger.info(f"SAMPLE_RATE: {sample_rate}")
            
            # Check memory before video processing
            # limits = check_gpu_limits() # This line is removed as per the edit hint
            # if limits["warning"]: # This line is removed as per the edit hint
            #     logger.warning("GPU memory warning before video processing") # This line is removed as per the edit hint
            #     clear_gpu_cache("Before video processing") # This line is removed as per the edit hint
            
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
            
            # Enhanced timeline-based analysis
            timeline_events = []
            frame_count = 0
            processed_frames = 0
            all_alerts = set()
            previous_scene_summary = ""
            significant_changes = []
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Sample frames based on sample_rate
                if frame_count % sample_rate == 0:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame_image = Image.fromarray(frame_rgb)
                    
                    timestamp = frame_count / fps if fps > 0 else frame_count
                    
                    # Generate timeline-aware analysis
                    timeline_analysis = self._generate_timeline_analysis(
                        frame_image, 
                        timestamp, 
                        previous_scene_summary,
                        processed_frames == 0  # First frame
                    )
                    
                    # Check for significant changes
                    if self._is_significant_change(timeline_analysis, previous_scene_summary):
                        timeline_event = {
                            "timestamp": timestamp,
                            "time_formatted": f"{int(timestamp//60):02d}:{int(timestamp%60):02d}",
                            "frame_number": frame_count,
                            "event_type": timeline_analysis.get("event_type", "scene_change"),
                            "description": timeline_analysis.get("timeline_description", ""),
                            "changes": timeline_analysis.get("changes", []),
                            "alerts": timeline_analysis.get("alerts", []),
                            "confidence": timeline_analysis.get("confidence", 0.0)
                        }
                        
                        timeline_events.append(timeline_event)
                        all_alerts.update(timeline_analysis.get("alerts", []))
                        significant_changes.append(timeline_analysis.get("changes", []))
                        
                        logger.debug(f"Timeline event at {timeline_event['time_formatted']}: {timeline_event['description']}")
                        
                        # Update previous scene for next comparison
                        previous_scene_summary = timeline_analysis.get("scene_summary", "")
                    
                    processed_frames += 1
                    
                    # Check memory periodically during video processing
                    if processed_frames % 5 == 0:
                        current_metrics = gpu_monitor.get_current_metrics()
                        if current_metrics and current_metrics.memory_utilization > 90:
                            logger.warning(f"GPU memory high during video processing (frame {frame_count})")
                
                frame_count += 1
            
            cap.release()
            
            # Create enhanced timeline summary
            timeline_summary = self._create_timeline_summary(timeline_events, duration)
            
            # Calculate overall confidence
            avg_confidence = sum(event["confidence"] for event in timeline_events) / len(timeline_events) if timeline_events else 0.0
            
            # Extract camera name
            camera_name = self._extract_camera_name(video_path)
            
            # Generate thumbnail for video
            thumbnail_result = await video_converter.generate_thumbnail(video_path)
            thumbnail_path = None
            if thumbnail_result["success"]:
                thumbnail_path = str(thumbnail_result["thumbnail_path"])
                logger.info(f"Video thumbnail generated: {thumbnail_path}")
            else:
                logger.warning(f"Failed to generate thumbnail for {video_path}: {thumbnail_result.get('error', 'Unknown error')}")
            
            processing_time = time.time() - processing_start
            
            result = {
                "success": True,
                "description": timeline_summary,
                "confidence": avg_confidence,
                "camera_name": camera_name,
                "width": width,
                "height": height,
                "duration": duration,
                "frame_count": total_frames,
                "processed_frames": processed_frames,
                "processing_time": processing_time,
                # Enhanced timeline-based analysis
                "timeline_events": timeline_events,
                "video_alerts": list(all_alerts),
                "significant_changes": significant_changes,
                "timeline_summary": timeline_summary,
                # Thumbnail path for video previews
                "thumbnail_path": thumbnail_path
            }
            
            logger.info(f"Video processed in {processing_time:.2f}s: {len(timeline_events)} timeline events identified")
            logger.info(f"Timeline Summary: {timeline_summary}")
            
            # Log video-wide alerts
            if result["video_alerts"]:
                logger.info(f"VIDEO ALERTS: {', '.join(result['video_alerts'])}")
            
            # Log GPU status after video processing
            # log_gpu_status("After video processing") # This line is removed as per the edit hint
            
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
                "timeline_events": [],
                "video_alerts": [],
                "significant_changes": [],
                "timeline_summary": "",
                "thumbnail_path": None
            }

    def _generate_timeline_analysis(self, image: Image.Image, timestamp: float, previous_scene: str, is_first_frame: bool) -> dict:
        """
        Generate timeline-aware analysis focusing on changes and events.
        
        Args:
            image: Current frame image
            timestamp: Current timestamp in seconds
            previous_scene: Summary of previous scene for comparison
            is_first_frame: Whether this is the first frame
            
        Returns:
            Dictionary with timeline analysis
        """
        timeline_start_time = time.time()
        ai_logger.info(f"--- TIMELINE FRAME ANALYSIS ---")
        ai_logger.info(f"FRAME_TIMESTAMP: {timestamp:.1f}s")
        ai_logger.info(f"IS_FIRST_FRAME: {is_first_frame}")
        ai_logger.debug(f"PREVIOUS_SCENE: {previous_scene[:100] if previous_scene else 'None'}...")
        
        try:
            # Prepare inputs
            inputs = self.processor(image, return_tensors="pt").to(self.device)
            
            # Generate timeline-specific prompts
            timeline_prompts = get_timeline_prompts(is_first_frame, previous_scene)
            ai_logger.info(f"TIMELINE_PROMPTS_COUNT: {len(timeline_prompts)}")
            ai_logger.debug(f"TIMELINE_ASPECTS: {list(timeline_prompts.keys())}")
            
            # Generate responses for each prompt
            analysis_results = {}
            for aspect, prompt in timeline_prompts.items():
                logger.debug(f"  Analyzing {aspect} aspect...")
                ai_logger.info(f"TIMELINE_ANALYZING: {aspect}")
                
                response = self._generate_with_prompt(inputs, prompt, max_length=256)
                analysis_results[aspect] = response
                
                ai_logger.debug(f"TIMELINE_RESULT: {aspect} -> {response[:50]}...")
            
            # Extract timeline-specific information
            timeline_analysis = {
                "scene_summary": analysis_results.get("scene_summary", ""),
                "timeline_description": analysis_results.get("timeline_description", ""),
                "changes": extract_changes(analysis_results.get("change_detection", "")),
                "event_type": classify_event_type(analysis_results.get("timeline_description", "")),
                "alerts": generate_alert_tags(analysis_results),
                "confidence": self._calculate_timeline_confidence(analysis_results),
                "timestamp": timestamp
            }
            
            timeline_duration = time.time() - timeline_start_time
            ai_logger.info(f"TIMELINE_EVENT_TYPE: {timeline_analysis['event_type']}")
            ai_logger.info(f"TIMELINE_CHANGES: {timeline_analysis['changes']}")
            ai_logger.info(f"TIMELINE_ALERTS: {timeline_analysis['alerts']}")
            ai_logger.info(f"TIMELINE_CONFIDENCE: {timeline_analysis['confidence']}")
            ai_logger.info(f"TIMELINE_DURATION: {timeline_duration:.3f}s")
            ai_logger.info("--- TIMELINE FRAME COMPLETE ---")
            
            return timeline_analysis
            
        except Exception as e:
            timeline_duration = time.time() - timeline_start_time
            ai_logger.error(f"TIMELINE_ERROR: {str(e)} (timestamp: {timestamp:.1f}s, duration: {timeline_duration:.3f}s)")
            logger.error(f"Error generating timeline analysis: {e}")
            return {
                "scene_summary": "Error analyzing scene",
                "timeline_description": "Error detecting changes",
                "changes": [],
                "event_type": "unknown",
                "alerts": [],
                "confidence": 0.0,
                "timestamp": timestamp
            }

    def _is_significant_change(self, current_analysis: dict, previous_scene: str) -> bool:
        """
        Determine if the current analysis represents a significant change worth recording.
        
        Args:
            current_analysis: Current timeline analysis
            previous_scene: Previous scene summary
            
        Returns:
            True if this represents a significant change
        """
        # Always include first frame
        if not previous_scene:
            return True
        
        # Check for alerts (always significant)
        if current_analysis.get("alerts"):
            return True
        
        # Check for explicit changes
        changes = current_analysis.get("changes", [])
        if changes:
            return True
        
        # Check for event type changes
        event_type = current_analysis.get("event_type", "")
        if event_type in ["person_enters", "person_exits", "vehicle_arrives", "vehicle_leaves", "activity_starts", "activity_stops"]:
            return True
        
        # Check for confidence in timeline description
        confidence = current_analysis.get("confidence", 0.0)
        if confidence > 0.7:
            return True
        
        return False

    def _extract_changes(self, change_description: str) -> List[str]:
        """Extract specific changes from change detection description."""
        return extract_changes(change_description)

    def _classify_event_type(self, timeline_description: str) -> str:
        """Classify the type of event based on timeline description."""
        return classify_event_type(timeline_description)

    def _calculate_timeline_confidence(self, analysis_results: dict) -> float:
        """Calculate confidence for timeline analysis."""
        # Base confidence from description quality
        timeline_desc = analysis_results.get("timeline_description", "")
        change_desc = analysis_results.get("change_detection", "")
        
        # Higher confidence for specific change descriptions
        if any(keyword in timeline_desc.lower() for keyword in ["enters", "exits", "arrives", "leaves", "starts", "stops"]):
            return 0.8
        
        # Medium confidence for general changes
        if any(keyword in timeline_desc.lower() for keyword in ["different", "changed", "new", "appears"]):
            return 0.6
        
        # Lower confidence for vague descriptions
        if len(timeline_desc) < 20:
            return 0.3
        
        return 0.5

    def _create_timeline_summary(self, timeline_events: List[dict], duration: float) -> str:
        """Create a human-readable timeline summary."""
        if not timeline_events:
            return f"Video analysis complete ({duration:.1f}s) - No significant events detected"
        
        try:
            # Extract key information
            all_alerts = set()
            event_types = set()
            
            for event in timeline_events:
                all_alerts.update(event.get("alerts", []))
                event_types.add(event.get("event_type", ""))
            
            # Create timeline header
            summary_parts = []
            summary_parts.append(f"TIMELINE ANALYSIS ({duration:.1f}s, {len(timeline_events)} events)")
            
            # Add timeline events with timestamps
            timeline_entries = []
            for event in timeline_events:
                time_str = event.get("time_formatted", "00:00")
                description = event.get("description", "")
                
                # Clean up description
                if description and not description.startswith("Error"):
                    # Remove redundant prefixes
                    description = description.replace("Compared to the previous scene:", "").strip()
                    if description:
                        timeline_entries.append(f"{time_str}: {description}")
            
            if timeline_entries:
                summary_parts.append(f"EVENTS: {' | '.join(timeline_entries)}")
            
            # Add summary of event types
            if event_types:
                event_summary = [et.replace("_", " ").title() for et in event_types if et != "general_activity"]
                if event_summary:
                    summary_parts.append(f"EVENT TYPES: {', '.join(event_summary)}")
            
            # Add alerts
            if all_alerts:
                summary_parts.append(f"ALERTS: {', '.join(sorted(all_alerts))}")
            
            return " | ".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error creating timeline summary: {e}")
            return f"Timeline analysis completed ({duration:.1f}s, {len(timeline_events)} events processed)"

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