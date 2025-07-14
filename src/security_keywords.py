"""
Security Keywords and Classifications for Foscam AI Analysis
Contains lookup tables for identifying security-relevant information
"""

# Keywords for activity classification
ACTIVITY_KEYWORDS = {
    "movement": ["walking", "running", "moving", "approaching", "leaving", "entering", "exiting"],
    "delivery": ["delivering", "dropping off", "picking up", "carrying", "package", "box"],
    "vehicles": ["driving", "parking", "backing up", "pulling in", "arriving", "departing"],
    "interaction": ["talking", "meeting", "greeting", "conversation", "handshake"],
    "suspicious": ["lurking", "hiding", "sneaking", "loitering", "prowling", "trespassing"],
    "maintenance": ["working", "repairing", "cleaning", "servicing", "installing"]
}

# Keywords for environment classification
ENVIRONMENT_KEYWORDS = {
    "time": ["morning", "afternoon", "evening", "night", "dawn", "dusk", "daylight", "dark"],
    "weather": ["sunny", "cloudy", "rainy", "foggy", "clear", "overcast", "storm"],
    "location": ["residential", "commercial", "parking", "driveway", "street", "yard", "dock", "marina"],
    "lighting": ["bright", "dim", "shadows", "illuminated", "dark", "lit up", "spotlight"]
}

# Alert type keywords for automatic detection
ALERT_KEYWORDS = {
    "person_detected": ["person", "people", "individual", "man", "woman", "child", "adult", "human"],
    "vehicle_detected": ["vehicle", "car", "truck", "van", "motorcycle", "bike", "automobile"],
    "package_detected": ["package", "delivery", "box", "bag", "container", "parcel"],
    "unusual_activity": ["suspicious", "unusual", "unexpected", "strange", "odd", "abnormal"],
    "night_time": ["night", "dark", "darkness", "evening", "late"]
}

# Vehicle identification keywords
VEHICLE_IDENTIFICATION = {
    "makes": ["ford", "chevrolet", "toyota", "honda", "nissan", "bmw", "mercedes", "audi", "hyundai", "kia"],
    "types": ["sedan", "suv", "truck", "van", "coupe", "hatchback", "convertible", "pickup"],
    "colors": ["white", "black", "gray", "silver", "red", "blue", "green", "yellow", "brown"],
    "commercial": ["delivery", "ups", "fedex", "amazon", "dhl", "usps", "utility", "service"],
    "features": ["license plate", "bumper", "hood", "door", "window", "tire", "rim", "headlight"]
}

# Person identification keywords
PERSON_IDENTIFICATION = {
    "clothing": ["shirt", "pants", "dress", "jacket", "coat", "hat", "cap", "uniform", "suit"],
    "colors": ["black", "white", "red", "blue", "green", "yellow", "brown", "gray", "pink"],
    "accessories": ["bag", "backpack", "hat", "glasses", "watch", "phone", "keys", "umbrella"],
    "build": ["tall", "short", "thin", "heavy", "medium", "large", "small"],
    "hair": ["blonde", "brown", "black", "gray", "red", "long", "short", "curly", "straight"]
}

# Company and logo keywords
COMPANY_KEYWORDS = {
    "delivery": ["ups", "fedex", "amazon", "dhl", "usps", "delivery", "express", "shipping"],
    "utilities": ["electric", "gas", "water", "cable", "internet", "phone", "utility"],
    "services": ["cleaning", "lawn", "pest", "security", "maintenance", "repair", "service"],
    "food": ["pizza", "restaurant", "food", "catering", "uber", "doordash", "grubhub"]
}

# Change detection keywords
CHANGE_KEYWORDS = {
    "appearance": ["appears", "emerges", "shows up", "comes into view", "arrives"],
    "disappearance": ["disappears", "vanishes", "leaves", "exits", "goes away"],
    "movement": ["moves", "shifts", "changes position", "relocates", "travels"],
    "activity": ["starts", "begins", "stops", "ends", "continues", "resumes"]
}

# Event type classifications
EVENT_TYPES = {
    "person_enters": ["person enters", "person appears", "person arrives", "person comes"],
    "person_exits": ["person exits", "person leaves", "person disappears", "person goes"],
    "vehicle_arrives": ["vehicle arrives", "car arrives", "truck arrives", "vehicle appears"],
    "vehicle_leaves": ["vehicle leaves", "car leaves", "truck leaves", "vehicle disappears"],
    "activity_starts": ["starts", "begins", "activity begins", "movement starts"],
    "activity_stops": ["stops", "ends", "activity ends", "movement stops"],
    "scene_change": ["different", "changed", "new scene", "scene changes"],
    "no_change": ["no change", "same", "similar", "unchanged"]
}

# Security relevance levels
SECURITY_RELEVANCE = {
    "high": ["unknown person", "suspicious activity", "forced entry", "breaking", "damage"],
    "medium": ["delivery", "visitor", "service person", "maintenance", "package"],
    "low": ["routine activity", "normal behavior", "expected visitor", "regular pattern"]
}

def extract_security_relevance(security_desc: str) -> str:
    """Extract security-relevant information from security description."""
    security_lower = security_desc.lower()
    
    # Check for high-priority security items
    high_priority = ["person", "individual", "vehicle", "suspicious", "unusual", "unauthorized"]
    medium_priority = ["delivery", "package", "visitor", "service"]
    
    relevant_items = []
    for item in high_priority:
        if item in security_lower:
            relevant_items.append(item)
    
    for item in medium_priority:
        if item in security_lower and item not in relevant_items:
            relevant_items.append(item)
    
    return ", ".join(relevant_items) if relevant_items else security_desc[:50]

def extract_object_counts(objects_desc: str) -> str:
    """Extract object counts and types."""
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

def extract_activities(activities_desc: str) -> str:
    """Extract and categorize activities."""
    detected_activities = []
    for category, keywords in ACTIVITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in activities_desc.lower():
                detected_activities.append(keyword)
                break
    
    return ", ".join(detected_activities) if detected_activities else activities_desc[:50]

def extract_environment_info(environment_desc: str) -> str:
    """Extract key environment information."""
    env_info = []
    for category, keywords in ENVIRONMENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword in environment_desc.lower():
                env_info.append(keyword)
                break
    
    return ", ".join(env_info) if env_info else environment_desc[:50]

def generate_alert_tags(descriptions: dict) -> list:
    """Generate alert tags for important detections."""
    alerts = []
    
    all_text = " ".join(descriptions.values()).lower()
    
    # Check each alert type
    for alert_type, keywords in ALERT_KEYWORDS.items():
        if any(keyword in all_text for keyword in keywords):
            alerts.append(alert_type.upper())
    
    return alerts

def extract_changes(change_description: str) -> list:
    """Extract specific changes from change detection description."""
    changes = []
    
    words = change_description.lower().split()
    for i, word in enumerate(words):
        # Check all change keyword categories
        for category, keywords in CHANGE_KEYWORDS.items():
            if word in keywords:
                # Get context around the change keyword
                context_start = max(0, i-2)
                context_end = min(len(words), i+3)
                context = " ".join(words[context_start:context_end])
                changes.append(context)
                break
    
    return changes[:3]  # Limit to 3 most significant changes

def classify_event_type(timeline_description: str) -> str:
    """Classify the type of event based on timeline description."""
    description_lower = timeline_description.lower()
    
    for event_type, keywords in EVENT_TYPES.items():
        if any(keyword in description_lower for keyword in keywords):
            return event_type
    
    return "general_activity"

def extract_vehicle_details(vehicle_desc: str) -> dict:
    """Extract detailed vehicle information."""
    details = {
        "make": None,
        "type": None,
        "color": None,
        "commercial": None,
        "features": []
    }
    
    desc_lower = vehicle_desc.lower()
    
    # Check for vehicle makes
    for make in VEHICLE_IDENTIFICATION["makes"]:
        if make in desc_lower:
            details["make"] = make
            break
    
    # Check for vehicle types
    for vtype in VEHICLE_IDENTIFICATION["types"]:
        if vtype in desc_lower:
            details["type"] = vtype
            break
    
    # Check for colors
    for color in VEHICLE_IDENTIFICATION["colors"]:
        if color in desc_lower:
            details["color"] = color
            break
    
    # Check for commercial indicators
    for commercial in VEHICLE_IDENTIFICATION["commercial"]:
        if commercial in desc_lower:
            details["commercial"] = commercial
            break
    
    # Extract features
    for feature in VEHICLE_IDENTIFICATION["features"]:
        if feature in desc_lower:
            details["features"].append(feature)
    
    return details

def extract_person_details(person_desc: str) -> dict:
    """Extract detailed person information."""
    details = {
        "clothing": [],
        "colors": [],
        "accessories": [],
        "build": None,
        "hair": None
    }
    
    desc_lower = person_desc.lower()
    
    # Extract clothing
    for clothing in PERSON_IDENTIFICATION["clothing"]:
        if clothing in desc_lower:
            details["clothing"].append(clothing)
    
    # Extract colors
    for color in PERSON_IDENTIFICATION["colors"]:
        if color in desc_lower:
            details["colors"].append(color)
    
    # Extract accessories
    for accessory in PERSON_IDENTIFICATION["accessories"]:
        if accessory in desc_lower:
            details["accessories"].append(accessory)
    
    # Extract build
    for build in PERSON_IDENTIFICATION["build"]:
        if build in desc_lower:
            details["build"] = build
            break
    
    # Extract hair
    for hair in PERSON_IDENTIFICATION["hair"]:
        if hair in desc_lower:
            details["hair"] = hair
            break
    
    return details 