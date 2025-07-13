# Camera Filtering Feature

The Foscam Web UI now includes comprehensive camera filtering capabilities, allowing users to view data from specific cameras or combinations of cameras.

## 🎥 **Camera Filter UI**

### Location
The camera filter controls are located below the Time Navigation section in the web dashboard.

### Components
- **Multi-select dropdown**: Choose one or more cameras from the list
- **Apply Filter button**: Apply the selected camera filter  
- **Clear Filter button**: Reset to show all cameras
- **Selected cameras display**: Shows which cameras are currently filtered
- **Camera tags**: Individual camera badges with remove buttons

## 📊 **What Gets Filtered**

When camera filters are applied, the following sections update automatically:

1. **Detection List**: Shows only detections from selected cameras
2. **Activity Heatmap**: Updates to show activity patterns for selected cameras only
3. **Statistics**: Recalculates based on filtered camera data
4. **Pagination**: Adjusts to the filtered dataset

## 🔧 **How to Use**

### Basic Filtering
1. **Select Cameras**: 
   - Click in the "Select Cameras" dropdown
   - Choose one or more cameras (hold Ctrl/Cmd for multiple)
   - Cameras are displayed as: `Full Camera Name (Location)`

2. **Apply Filter**:
   - Click "Apply Filter" button
   - The dashboard immediately updates to show only data from selected cameras

3. **View Selected**:
   - Selected cameras appear as blue tags below the dropdown
   - Each tag shows the camera name with an "×" to remove individual cameras

### Clearing Filters
- **Clear All**: Click "Clear Filter" button to return to showing all cameras
- **Remove Individual**: Click the "×" on any camera tag to remove just that camera

## 🔌 **API Endpoints**

The following API endpoints now support camera filtering via the `camera_ids` parameter:

### `/api/detections/time-range`
```
GET /api/detections/time-range?start_time=2025-07-10T00:00:00&end_time=2025-07-13T23:59:59&camera_ids=1,2,3
```

### `/api/detections/heatmap`
```
GET /api/detections/heatmap?days=30&resolution=day&camera_ids=1,2
```

### Camera IDs Parameter
- **Format**: Comma-separated list of camera IDs
- **Example**: `camera_ids=1,2,3`
- **Optional**: If omitted, returns data from all cameras

## 📋 **Available Cameras**

Current cameras in the system:

| ID | Camera Name | Location |
|----|-------------|----------|
| 1  | ami_frontyard_left_FoscamCamera_00626EFE8B21 | ami |
| 2  | beach_front_left_FoscamCamera_00626EFE546D | beach |
| 3  | dock_left_FoscamCamera_00626EFE89A8 | dock |

*Note: Camera list is dynamically loaded from `/api/cameras` endpoint*

## 💡 **Use Cases**

### Security Monitoring
- **Perimeter Cameras**: Filter to show only outdoor cameras (dock, beach)
- **Entry Points**: Focus on specific entrance cameras
- **High-Activity Areas**: Monitor cameras with frequent detections

### Troubleshooting
- **Camera Performance**: Check activity for specific cameras
- **Detection Quality**: Compare detection rates between cameras
- **Coverage Analysis**: Verify camera coverage patterns

### Data Analysis
- **Location-Based**: Analyze patterns by location (ami vs beach vs dock)
- **Time Patterns**: Compare activity between different camera locations
- **Alert Analysis**: Focus on cameras with high alert rates

## 🎯 **Technical Details**

### Frontend Implementation
- **Multi-select dropdown**: HTML `<select multiple>` element
- **Real-time filtering**: Updates all dashboard components automatically
- **State management**: Maintains selected cameras across page interactions
- **Visual feedback**: Camera tags with remove functionality

### Backend Implementation
- **SQL Filtering**: Uses `WHERE Camera.id IN (...)` for efficient filtering
- **API Consistency**: All relevant endpoints support `camera_ids` parameter
- **Error Handling**: Gracefully handles invalid camera IDs

### Performance
- **Optimized Queries**: Joins with Camera table only when filtering is needed
- **Caching**: Camera list is cached in frontend for fast dropdown population
- **Responsive UI**: Filter changes update immediately without page reload

## 🔄 **Future Enhancements**

- **Location Grouping**: Filter by camera location (ami, beach, dock)
- **Camera Type Filtering**: Filter by device type or model
- **Saved Filters**: Save and recall commonly used camera combinations
- **Quick Filters**: One-click filters for common scenarios (outdoor, indoor, etc.)
- **Bulk Actions**: Apply settings to multiple cameras at once

## 🚀 **Getting Started**

1. **Access the Dashboard**: Navigate to http://localhost:8000
2. **Load Cameras**: Camera list loads automatically on page load
3. **Try Filtering**: Select one or more cameras and click "Apply Filter"
4. **Observe Changes**: Watch how the detection list and heatmap update
5. **Experiment**: Try different camera combinations to see various patterns

The camera filtering feature provides powerful flexibility for monitoring specific areas or analyzing patterns from particular camera perspectives while maintaining the full functionality of the Foscam detection dashboard. 