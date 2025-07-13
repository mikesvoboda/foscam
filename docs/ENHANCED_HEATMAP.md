# Enhanced Heatmap Functionality

This document describes the enhanced heatmap system for the Foscam Detection Dashboard, featuring 30-day focus, camera-specific visualization, and hourly activity views.

## 🔥 **Overview**

The enhanced heatmap provides two distinct views with camera-specific activity visualization:

- **📅 30-Day View**: Daily activity over the past 30 days (matching data retention)
- **⏰ 24-Hour View**: Hourly activity breakdown for detailed analysis

## 🎯 **Key Features**

### Camera-Specific Visualization
- **Different colors** for each camera location
- **Activity intensity** shown through color saturation
- **Interactive legends** showing camera mappings
- **Combined or separated** views

### Color Scheme
- **🔵 ami**: Blue (#3498db) - Front yard camera
- **🔴 beach**: Red (#e74c3c) - Beach front camera  
- **🟢 dock**: Green (#2ecc71) - Dock camera
- **🟣 default**: Purple (#9b59b6) - Unknown locations

### Smart Data Focus
- **30-day limit** matches image retention policy
- **Automatic cleanup** aligns with cron job schedule
- **Real-time updates** reflect current activity

## 📊 **Heatmap Views**

### Daily View (30 Days)
```
┌─────────────────────────────────────────┐
│ 🔥 Detection Activity    [📅 30 Days] │
│                          [📹 Show by Camera] │
├─────────────────────────────────────────┤
│ Mon Wed Fri                             │
│ ▢▢▢▢▢  <- Week 1                       │
│ ▢🔵▢🔴▢  <- Week 2 (camera colors)      │
│ ▢▢🟢▢▢  <- Week 3                       │
│ ▢▢▢▢▢  <- Week 4                       │
│ ▢▢▢                                     │
├─────────────────────────────────────────┤
│ Cameras: 🔵 ami  🔴 beach  🟢 dock      │
└─────────────────────────────────────────┘
```

### Hourly View (24 Hours)
```
┌─────────────────────────────────────────┐
│ 🔥 Detection Activity    [⏰ 24 Hours] │
├─────────────────────────────────────────┤
│ 00 01 02 03 04 05 06 07 08 09 10 11     │
│ ▢  ▢  ▢  ▢  ▢  🔵  🔵  🔴  ▢  ▢  ▢  ▢   │
│ 12 13 14 15 16 17 18 19 20 21 22 23     │
│ ▢  🟢  ▢  ▢  🔵  🔵  🔴  🔴  ▢  ▢  ▢  ▢   │
├─────────────────────────────────────────┤
│ Hours: 00    06    12    18    24       │
│ Cameras: 🔵 ami  🔴 beach  🟢 dock      │
└─────────────────────────────────────────┘
```

## 🔧 **API Endpoints**

### Enhanced Daily Heatmap
```http
GET /api/detections/heatmap?days=30&resolution=day&per_camera=true&camera_ids=1,2,3
```

**Parameters:**
- `days`: Number of days (default: 30)
- `resolution`: Time granularity (day, hour, week)
- `per_camera`: Enable camera breakdown (true/false)
- `camera_ids`: Filter specific cameras (comma-separated)

**Response:**
```json
{
  "heatmap_data": [...],
  "camera_data": {
    "1": {
      "info": {"name": "ami_camera", "location": "ami"},
      "activity": [{"timestamp": "...", "count": 5, "level": 3}]
    }
  },
  "camera_info": {...},
  "resolution": "day",
  "days": 30,
  "per_camera": true
}
```

### Hourly Activity Heatmap
```http
GET /api/detections/heatmap-hourly?hours=24&camera_ids=1,2,3
```

**Parameters:**
- `hours`: Number of hours (default: 24)
- `camera_ids`: Filter specific cameras (comma-separated)

**Response:**
```json
{
  "hourly_data": [...],
  "camera_data": {
    "1": {
      "info": {"name": "ami_camera", "location": "ami", "color": "#3498db"},
      "activity": [{"timestamp": "...", "count": 2, "intensity": 0.8, "level": 4}],
      "max_count": 5
    }
  },
  "camera_colors": {"ami": "#3498db", "beach": "#e74c3c", "dock": "#2ecc71"},
  "hours": 24
}
```

## 🎨 **Visual Elements**

### Activity Levels
- **Level 0**: No activity (light gray)
- **Level 1**: Low activity (25% intensity)
- **Level 2**: Medium activity (50% intensity)  
- **Level 3**: High activity (75% intensity)
- **Level 4**: Very high activity (100% intensity)

### Camera Colors
Each camera location has a distinct color that becomes more saturated with higher activity:

```css
/* Base colors */
.camera-ami { background-color: #3498db; }      /* Blue */
.camera-beach { background-color: #e74c3c; }    /* Red */
.camera-dock { background-color: #2ecc71; }     /* Green */

/* Intensity variations */
.level-1 { opacity: 0.3; }
.level-2 { opacity: 0.5; }
.level-3 { opacity: 0.75; }
.level-4 { opacity: 1.0; }
```

### Interactive Features
- **Click cells** to jump to specific time periods
- **Hover tooltips** show detailed breakdown
- **Camera filtering** updates in real-time
- **View switching** between daily/hourly modes

## 📱 **User Interface**

### Control Buttons
```
[📅 30 Days] [⏰ 24 Hours]  [📹 Show by Camera]
```

- **View Toggle**: Switch between daily and hourly views
- **Camera Breakdown**: Toggle combined vs. per-camera visualization
- **Camera Filter**: Use existing dropdown for specific cameras

### Statistics Display
```
🔥 Detection Activity
━━━━━━━━━━━━━━━━━━━━━
156 detections in the last 30 days
Busiest period: 12 detections Jul 7
```

- **Total activity** for the selected time period
- **Busiest period** with count and date/time
- **Auto-updating** based on current view and filters

## 🔄 **Data Flow**

### Daily View Process
1. **API Call**: Request 30-day data with camera breakdown
2. **Data Processing**: Aggregate detections by day and camera
3. **Color Assignment**: Apply camera-specific colors
4. **Intensity Calculation**: Normalize activity levels per camera
5. **Rendering**: Create calendar grid with colored squares

### Hourly View Process
1. **API Call**: Request 24-hour data with camera details
2. **Time Buckets**: Create hourly time slots
3. **Camera Analysis**: Determine dominant camera per hour
4. **Color Blending**: Apply camera colors with intensity
5. **Grid Creation**: Render 24-cell hourly grid

## 📈 **Activity Analysis**

### Camera Comparison
```
ami (Blue):   ████████░░ 80% activity
beach (Red):  ██████░░░░ 60% activity  
dock (Green): ███░░░░░░░ 30% activity
```

### Time Patterns
- **Morning Peak**: 6-8 AM (commute activity)
- **Midday Lull**: 10 AM - 2 PM (low activity)
- **Evening Peak**: 5-7 PM (return activity)
- **Night Quiet**: 10 PM - 5 AM (minimal activity)

### Data Insights
- **Busiest Camera**: Automatically highlighted
- **Activity Trends**: Visual patterns over time
- **Anomaly Detection**: Unusual activity spikes
- **Coverage Analysis**: Camera effectiveness comparison

## 🛠️ **Usage Examples**

### Basic Daily View
```javascript
// Switch to daily view
switchHeatmapView('daily');

// Enable camera breakdown
toggleCameraBreakdown();
```

### Filtered Hourly Analysis
```javascript
// Switch to hourly view
switchHeatmapView('hourly');

// Filter to specific cameras
applyCameraFilter(); // Uses selected cameras from dropdown
```

### Click Interactions
```javascript
// Daily square clicked - jump to that day
jumpToDay(selectedDate);

// Hourly cell clicked - jump to that hour
jumpToHour(selectedDateTime);
```

## 🔍 **Troubleshooting**

### Common Issues

1. **No camera colors showing**
   - Check if "Show by Camera" is enabled
   - Verify camera data exists for the time period
   - Ensure cameras have location assignments

2. **Empty heatmap**
   - Confirm detection data exists in the 30-day window
   - Check camera filters aren't excluding all data
   - Verify database has processed detections

3. **Slow loading**
   - Large datasets may take time to process
   - Consider shorter time ranges for testing
   - Check database performance

### Debug Commands
```bash
# Check 30-day data availability
curl "localhost:8000/api/detections/heatmap?days=30" | jq '.heatmap_data | length'

# Verify camera breakdown
curl "localhost:8000/api/detections/heatmap?days=30&per_camera=true" | jq '.camera_info'

# Test hourly data
curl "localhost:8000/api/detections/heatmap-hourly?hours=24" | jq '.camera_colors'
```

## 🚀 **Future Enhancements**

### Planned Features
1. **Multi-camera overlays** for complex activity patterns
2. **Animation support** for time-lapse views
3. **Custom time ranges** beyond 30 days / 24 hours
4. **Export functionality** for activity reports
5. **Alert integration** with heatmap highlighting

### Performance Optimizations
1. **Caching** for frequently accessed time periods
2. **Progressive loading** for large datasets
3. **Background updates** for real-time data
4. **Compression** for reduced bandwidth

---

*Last updated: July 13, 2025*  
*Compatible with: Foscam Detection Dashboard v2.0+* 