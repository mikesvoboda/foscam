# AI Prompts and Security Keywords Guide

## Overview

The AI analysis system has been refactored into modular components for better maintainability and customization. This guide explains how to use and modify the new system.

## File Structure

```
src/
├── ai_prompts.py           # All AI analysis prompts
├── security_keywords.py    # Security classification keywords
└── ai_model.py            # Main AI processing (imports from above)
```

## AI Prompts (ai_prompts.py)

### Standard Analysis Prompts

The system includes comprehensive prompts for security analysis:

- **`general`**: Basic scene description
- **`security`**: Security-focused analysis  
- **`identification`**: Detailed identifying information extraction
- **`vehicles`**: Vehicle-specific details (make, model, license plates)
- **`people`**: Person descriptions (clothing, appearance, features)
- **`objects`**: Object identification and text reading
- **`activities`**: Activity and behavior analysis
- **`environment`**: Environmental context

### Security Identification Prompts

Special prompts for security incidents:

- **`license_plates`**: License plate extraction
- **`vehicle_details`**: Complete vehicle descriptions
- **`person_identification`**: Detailed person descriptions
- **`company_logos`**: Company and logo identification
- **`readable_text`**: Text and sign reading
- **`packages_deliveries`**: Package and delivery analysis
- **`distinctive_features`**: Unique identifying features

### Contextual Prompts

The system can provide contextual prompts based on:

- **Location**: frontyard, backyard, driveway, dock, kitchen
- **Time**: morning, afternoon, evening, night  
- **Alert Type**: person_detected, vehicle_detected, package_detected

### Usage Examples

```python
from ai_prompts import get_analysis_prompts, get_timeline_prompts

# Basic analysis prompts
prompts = get_analysis_prompts()

# Contextual prompts for front yard, evening, person detection
prompts = get_analysis_prompts(
    location="frontyard", 
    time_period="evening", 
    alert_type="person_detected"
)

# Timeline prompts for video analysis
timeline_prompts = get_timeline_prompts(is_first_frame=True)
```

## Security Keywords (security_keywords.py)

### Keyword Categories

- **`ACTIVITY_KEYWORDS`**: Movement, delivery, vehicle, interaction, suspicious activities
- **`ENVIRONMENT_KEYWORDS`**: Time, weather, location, lighting conditions
- **`ALERT_KEYWORDS`**: Person, vehicle, package, unusual activity detection
- **`VEHICLE_IDENTIFICATION`**: Makes, types, colors, commercial indicators
- **`PERSON_IDENTIFICATION`**: Clothing, colors, accessories, physical features
- **`COMPANY_KEYWORDS`**: Delivery, utilities, services, food companies

### Extraction Functions

```python
from security_keywords import (
    extract_vehicle_details, 
    extract_person_details,
    extract_security_relevance
)

# Extract vehicle information
vehicle_info = extract_vehicle_details("white Ford delivery truck")
# Returns: {"make": "ford", "type": "truck", "color": "white", "commercial": "delivery"}

# Extract person information  
person_info = extract_person_details("man in blue shirt carrying backpack")
# Returns: {"clothing": ["shirt"], "colors": ["blue"], "accessories": ["backpack"]}
```

## Security Enhancement Features

### 1. Comprehensive Vehicle Analysis

The system now extracts:
- **Make/Model**: Ford, Toyota, Chevrolet, etc.
- **Type**: Sedan, SUV, truck, van, etc.
- **Color**: Specific color identification
- **Commercial**: Delivery, utility, service indicators
- **License Plates**: Text and state identification
- **Company Markings**: Logos, text, decals

### 2. Detailed Person Identification

For security incidents, the system captures:
- **Clothing**: Colors, styles, types
- **Physical Features**: Build, hair, distinctive characteristics
- **Accessories**: Bags, hats, glasses, carried items
- **Behavior**: Activities and movements

### 3. Context-Aware Analysis

The system adjusts prompts based on:
- **Camera Location**: Different prompts for front yard vs. driveway
- **Time of Day**: Night analysis focuses on unusual activity
- **Alert Type**: Specialized prompts for different alert types

## Customization Guide

### Adding New Prompts

1. **Edit `ai_prompts.py`**:
```python
# Add to IMAGE_ANALYSIS_PROMPTS
"new_category": "Question: Your custom prompt here. Answer:"

# Add to SECURITY_IDENTIFICATION_PROMPTS  
"custom_security": "Question: Security-specific prompt. Answer:"
```

2. **Update `get_analysis_prompts()`** to include new categories

### Adding New Keywords

1. **Edit `security_keywords.py`**:
```python
# Add to existing categories
VEHICLE_IDENTIFICATION["new_category"] = ["keyword1", "keyword2"]

# Or create new categories
NEW_CATEGORY_KEYWORDS = {
    "subcategory1": ["keyword1", "keyword2"],
    "subcategory2": ["keyword3", "keyword4"]
}
```

2. **Create extraction functions** for new categories

### Modifying Timeline Analysis

1. **Edit timeline prompts in `ai_prompts.py`**:
```python
TIMELINE_PROMPTS = {
    "first_frame": {
        "custom_analysis": "Question: Custom first frame prompt. Answer:"
    },
    "subsequent_frame": {
        "custom_analysis": "Question: Custom change detection prompt. Answer:"
    }
}
```

## Best Practices

### 1. Prompt Writing

- **Be Specific**: Ask for exact details needed
- **Use Examples**: Include examples of desired output
- **Focus on Security**: Emphasize identifying information
- **Avoid Ambiguity**: Use clear, direct language

### 2. Keyword Management

- **Keep Updated**: Add new company names, vehicle models
- **Be Comprehensive**: Include variations and synonyms
- **Test Regularly**: Verify keywords work with real data

### 3. Security Focus

- **Identifying Information**: Prioritize license plates, faces, unique features
- **Context Matters**: Different locations need different analysis
- **Documentation**: Good for incident reports and investigations

## Testing Changes

```bash
# Test imports
python -c "from src.ai_prompts import get_analysis_prompts; print('OK')"

# Test keyword extraction
python -c "from src.security_keywords import extract_vehicle_details; print('OK')"

# Restart system to apply changes
bash restart-webui.sh
```

## Future Enhancements

1. **Dynamic Prompts**: Context-aware prompt generation
2. **Learning System**: Prompts that improve based on results
3. **Custom Alerts**: User-defined security categories
4. **Integration**: Connection with external security databases

This modular system makes it easy to enhance and customize the AI analysis for specific security needs while maintaining clean, maintainable code. 