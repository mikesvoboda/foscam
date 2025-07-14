"""
AI Analysis Prompts for Foscam Security System
Contains all prompts used for image and video analysis
"""

# Standard image analysis prompts
IMAGE_ANALYSIS_PROMPTS = {
    "general": "Question: What is happening in this image? Describe the scene in detail. Answer:",
    "security": "Question: From a security perspective, what security-relevant elements, people, vehicles, or activities can you identify in this image? Answer:",
    "identification": "Question: What specific identifying information can you extract from this image? Include vehicle details (make, model, color, license plates), person descriptions (clothing, physical features), company logos, text, signs, or any other distinguishing features. Answer:",
    "vehicles": "Question: If there are any vehicles in this image, describe them in detail including make, model, color, type, license plate numbers, company markings, logos, or any text visible on the vehicle. Answer:",
    "people": "Question: If there are people in this image, describe their clothing, physical appearance, what they are carrying, and any distinguishing features that could help identify them. Answer:",
    "objects": "Question: What objects, items, packages, signs, or text can you identify in this image? Include any readable text, logos, or markings. Answer:",
    "activities": "Question: What activities, movements, or behaviors are occurring in this image? Answer:",
    "environment": "Question: What is the environmental context? Describe the location, time of day, weather conditions, and setting. Answer:"
}

# Timeline-specific prompts for video analysis
TIMELINE_PROMPTS = {
    "first_frame": {
        "scene_summary": "Question: What is the initial scene at the beginning of this video? Describe the setting, main elements, and any people or objects present. Answer:",
        "timeline_description": "Question: This is the opening scene of a video. What is happening and what should we watch for? Answer:",
        "change_detection": "Question: What key elements are present in this initial scene that might change later? Answer:"
    },
    "subsequent_frame": {
        "scene_summary": "Question: What is currently happening in this scene? Focus on the main activity and any people or objects. Answer:",
        "timeline_description": "Question: Compared to the previous scene, what has changed or is different in this current scene? Focus only on new events or changes. Answer:",
        "change_detection": "Question: What specific changes, movements, or new events can you identify in this scene? Answer:"
    }
}

# Security-focused prompts for detailed identification
SECURITY_IDENTIFICATION_PROMPTS = {
    "license_plates": "Question: Are there any license plates visible in this image? If so, describe the text, numbers, state, or any other details you can see. Answer:",
    "vehicle_details": "Question: For any vehicles present, describe in detail: make, model, year (if identifiable), color, body type, any damage or distinctive features, company logos, decals, or text. Answer:",
    "person_identification": "Question: For any people present, describe: clothing colors and styles, physical build, hair color/style, accessories, what they are carrying, and any distinctive features. Answer:",
    "company_logos": "Question: Are there any company logos, business names, or commercial text visible on vehicles, uniforms, packages, or signs? Describe them in detail. Answer:",
    "readable_text": "Question: What text, numbers, or writing can you read in this image? Include signs, labels, license plates, vehicle text, or any other readable content. Answer:",
    "packages_deliveries": "Question: Are there any packages, boxes, or delivery items visible? Describe their size, color, shape, and any logos or text on them. Answer:",
    "distinctive_features": "Question: What are the most distinctive or unusual features in this image that would help identify this scene, person, or vehicle later? Answer:"
}

# Prompts for different alert types
ALERT_SPECIFIC_PROMPTS = {
    "person_detected": "Question: Focus on the person(s) in this image. Describe their appearance, clothing, what they are doing, and any identifying features. Answer:",
    "vehicle_detected": "Question: Focus on the vehicle(s) in this image. Describe make, model, color, license plate, and any company markings or distinctive features. Answer:",
    "package_detected": "Question: Focus on the package or delivery item. Describe its size, color, shape, any logos or text, and the delivery context. Answer:",
    "unusual_activity": "Question: What makes this activity unusual or suspicious? Describe the specific behaviors or elements that stand out. Answer:",
    "night_time": "Question: This is a nighttime scene. What can you identify despite the low light conditions? Focus on any visible details. Answer:"
}

# Context-aware prompts for different camera locations
LOCATION_SPECIFIC_PROMPTS = {
    "frontyard": "Question: This is a front yard security camera. Focus on visitors, deliveries, vehicles, and any activity near the entrance. Answer:",
    "backyard": "Question: This is a backyard security camera. Focus on any unusual activity, people, or access attempts in the private area. Answer:",
    "driveway": "Question: This is a driveway security camera. Focus on vehicles, their details, and any loading/unloading activity. Answer:",
    "dock": "Question: This is a dock security camera. Focus on boats, water activity, people on the dock, and any marine-related activity. Answer:",
    "kitchen": "Question: This is an indoor kitchen security camera. Focus on any people, activity, or unusual events in the home. Answer:",
    "general": "Question: Analyze this security camera footage for any notable activity, people, vehicles, or events. Answer:"
}

# Prompt templates for different time periods
TIME_BASED_PROMPTS = {
    "morning": "Question: This is morning footage. Focus on typical morning activities, deliveries, and commuting patterns. Answer:",
    "afternoon": "Question: This is afternoon footage. Focus on any mid-day activities, service visits, or unusual events. Answer:",
    "evening": "Question: This is evening footage. Focus on evening activities, arrivals, and any unusual late-day events. Answer:",
    "night": "Question: This is nighttime footage. Focus on any activity during sleeping hours, which may be more significant. Answer:"
}

def get_analysis_prompts(location: str = None, time_period: str = None, alert_type: str = None) -> dict:
    """
    Get contextual analysis prompts based on location, time, and alert type.
    
    Args:
        location: Camera location (frontyard, backyard, driveway, dock, kitchen)
        time_period: Time of day (morning, afternoon, evening, night)
        alert_type: Type of alert detected (person_detected, vehicle_detected, etc.)
        
    Returns:
        Dictionary of contextual prompts
    """
    prompts = IMAGE_ANALYSIS_PROMPTS.copy()
    
    # Add location-specific prompt if available
    if location and location in LOCATION_SPECIFIC_PROMPTS:
        prompts["location_context"] = LOCATION_SPECIFIC_PROMPTS[location]
    
    # Add time-based prompt if available
    if time_period and time_period in TIME_BASED_PROMPTS:
        prompts["time_context"] = TIME_BASED_PROMPTS[time_period]
    
    # Add alert-specific prompt if available
    if alert_type and alert_type in ALERT_SPECIFIC_PROMPTS:
        prompts["alert_context"] = ALERT_SPECIFIC_PROMPTS[alert_type]
    
    # Always add security identification prompts for detailed analysis
    prompts.update(SECURITY_IDENTIFICATION_PROMPTS)
    
    return prompts

def get_timeline_prompts(is_first_frame: bool, previous_scene: str = None) -> dict:
    """
    Get timeline-specific prompts for video analysis.
    
    Args:
        is_first_frame: Whether this is the first frame of the video
        previous_scene: Summary of previous scene for comparison
        
    Returns:
        Dictionary of timeline prompts
    """
    if is_first_frame:
        return TIMELINE_PROMPTS["first_frame"]
    else:
        prompts = TIMELINE_PROMPTS["subsequent_frame"].copy()
        if previous_scene:
            # Customize the timeline description prompt with previous scene context
            prompts["timeline_description"] = f"Question: Compared to the previous scene: '{previous_scene[:100]}...', what has changed or is different in this current scene? Focus only on new events or changes. Answer:"
        return prompts 