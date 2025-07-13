from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, selectinload
from datetime import datetime, timedelta
from pathlib import Path
import json

from config import DATABASE_URL, FOSCAM_DIR, HOST, PORT
from models import Base, Detection, Camera, AlertType, initialize_alert_types

app = FastAPI(title="Foscam Camera Detection Dashboard")

# Database setup
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Template setup
templates = Jinja2Templates(directory="templates")

# Create templates directory
Path("templates").mkdir(exist_ok=True)

# Static files (serve original files from foscam directory)
app.mount("/media", StaticFiles(directory=str(FOSCAM_DIR)), name="media")

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize alert types
    async with SessionLocal() as session:
        initialize_alert_types(session)
        await session.commit()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Main dashboard page with optimized queries."""
    async with SessionLocal() as session:
        # Get recent detections with camera information (only processed ones)
        result = await session.execute(
            select(Detection, Camera)
            .join(Camera)
            .where(Detection.processed == True)
            .order_by(desc(Detection.file_timestamp))
            .limit(50)
        )
        detection_rows = result.all()
        detections = [{"detection": det, "camera": cam} for det, cam in detection_rows]
        
        # Get statistics - total detections
        total_result = await session.execute(
            select(func.count(Detection.id)).where(Detection.processed == True)
        )
        total_detections = total_result.scalar()
        
        # Get active cameras count
        camera_result = await session.execute(
            select(func.count(Camera.id)).where(Camera.is_active == True)
        )
        active_cameras = camera_result.scalar()
        
        # Today's stats
        today = datetime.now().date()
        today_result = await session.execute(
            select(func.count(Detection.id)).where(
                Detection.processed == True,
                Detection.file_timestamp >= today
            )
        )
        today_detections = today_result.scalar()
        
        # Get recent alerts using optimized alert flags
        alert_result = await session.execute(
            select(Detection, Camera)
            .join(Camera)
            .where(
                Detection.processed == True,
                Detection.file_timestamp >= datetime.now() - timedelta(hours=1),
                Detection.alert_count > 0  # Fast alert filtering
            )
            .order_by(desc(Detection.file_timestamp))
        )
        
        alerts = [{"detection": det, "camera": cam} for det, cam in alert_result.all()]
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "detections": detections,
            "total_detections": total_detections,
            "active_cameras": active_cameras,
            "today_detections": today_detections,
            "alerts": alerts
        })

@app.get("/api/detections")
async def get_detections(
    limit: int = 50,
    offset: int = 0,
    camera_id: int = None,
    location: str = None,
    media_type: str = None,
    hours: int = 24,
    has_alerts: bool = None
):
    """Get detections with enhanced filtering using optimized schema."""
    async with SessionLocal() as session:
        # Build query with joins
        query = select(Detection, Camera).join(Camera).where(Detection.processed == True)
        
        # Time filter
        if hours > 0:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            query = query.where(Detection.file_timestamp >= cutoff_time)
        
        # Camera filters
        if camera_id:
            query = query.where(Detection.camera_id == camera_id)
        
        if location:
            query = query.where(Camera.location == location)
        
        # Media type filter
        if media_type:
            query = query.where(Detection.media_type == media_type)
        
        # Alert filter using fast alert flags
        if has_alerts is not None:
            if has_alerts:
                query = query.where(Detection.alert_count > 0)
            else:
                query = query.where(Detection.alert_count == 0)
        
        # Apply ordering, limit, and offset
        query = query.order_by(desc(Detection.file_timestamp)).limit(limit).offset(offset)
        
        result = await session.execute(query)
        detection_rows = result.all()
        
        # Enhanced detection data with optimized schema
        enhanced_detections = []
        for detection, camera in detection_rows:
            detection_data = {
                "id": detection.id,
                "filename": detection.filename,
                "filepath": detection.filepath,
                "media_type": detection.media_type,
                "description": detection.description,
                "confidence": detection.confidence,
                "camera_id": detection.camera_id,
                "camera_name": camera.full_name,
                "camera_location": camera.location,
                "camera_device": camera.device_name,
                "camera_type": camera.device_type,
                "motion_detection_type": detection.motion_detection_type,
                "timestamp": detection.timestamp.isoformat(),
                "file_timestamp": detection.file_timestamp.isoformat() if detection.file_timestamp else None,
                "width": detection.width,
                "height": detection.height,
                "frame_count": detection.frame_count,
                "duration": detection.duration,
                "processing_time": detection.processing_time,
                # Alert flags for fast frontend filtering
                "has_person": detection.has_person,
                "has_vehicle": detection.has_vehicle,
                "has_package": detection.has_package,
                "has_unusual_activity": detection.has_unusual_activity,
                "is_night_time": detection.is_night_time,
                "alert_count": detection.alert_count
            }
            
            # Parse structured analysis if available
            structured_analysis = detection.get_structured_analysis()
            if structured_analysis:
                detection_data["structured_analysis"] = structured_analysis
                detection_data["has_enhanced_analysis"] = True
            else:
                detection_data["structured_analysis"] = {"general": detection.description}
                detection_data["has_enhanced_analysis"] = False
                
            enhanced_detections.append(detection_data)
        
        return {
            "detections": enhanced_detections,
            "limit": limit,
            "offset": offset,
            "enhanced_analysis_available": True
        }

@app.get("/api/cameras")
async def get_cameras():
    """Get all cameras with statistics."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Camera).order_by(Camera.location, Camera.device_name)
        )
        cameras = result.scalars().all()
        
        camera_data = []
        for camera in cameras:
            camera_data.append({
                "id": camera.id,
                "location": camera.location,
                "device_name": camera.device_name,
                "device_type": camera.device_type,
                "full_name": camera.full_name,
                "is_active": camera.is_active,
                "total_detections": camera.total_detections,
                "total_alerts": camera.total_alerts,
                "last_seen": camera.last_seen.isoformat() if camera.last_seen else None,
                "created_at": camera.created_at.isoformat()
            })
        
        return {"cameras": camera_data}

@app.get("/api/stats")
async def get_stats(hours: int = 24):
    """Get detection statistics with optimized queries."""
    async with SessionLocal() as session:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Total detections
        total_result = await session.execute(
            select(func.count(Detection.id)).where(
                Detection.processed == True,
                Detection.file_timestamp >= cutoff_time
            )
        )
        total_detections = total_result.scalar()
        
        # By camera location (optimized)
        location_result = await session.execute(
            select(Camera.location, func.count(Detection.id))
            .join(Detection)
            .where(
                Detection.processed == True,
                Detection.file_timestamp >= cutoff_time
            )
            .group_by(Camera.location)
        )
        
        location_stats = {row[0]: row[1] for row in location_result}
        
        # By media type
        media_result = await session.execute(
            select(Detection.media_type, func.count(Detection.id)).where(
                Detection.processed == True,
                Detection.file_timestamp >= cutoff_time
            ).group_by(Detection.media_type)
        )
        
        media_stats = {row[0]: row[1] for row in media_result}
        
        # Alert statistics using fast alert flags
        alert_stats = {}
        for alert_type in ["has_person", "has_vehicle", "has_package", "has_unusual_activity", "is_night_time"]:
            alert_result = await session.execute(
                select(func.count(Detection.id)).where(
                    Detection.processed == True,
                    Detection.file_timestamp >= cutoff_time,
                    getattr(Detection, alert_type) == True
                )
            )
            alert_stats[alert_type] = alert_result.scalar()
        
        return {
            "total_detections": total_detections,
            "location_stats": location_stats,
            "media_stats": media_stats,
            "alert_stats": alert_stats,
            "time_range_hours": hours
        }

@app.get("/api/alerts")
async def get_alerts(hours: int = 1, priority: int = None):
    """Get recent alerts using optimized alert filtering."""
    async with SessionLocal() as session:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Fast alert filtering using alert flags
        query = select(Detection, Camera).join(Camera).where(
            Detection.processed == True,
            Detection.file_timestamp >= cutoff_time,
            Detection.alert_count > 0  # Fast filtering for any alerts
        ).order_by(desc(Detection.file_timestamp))
        
        result = await session.execute(query)
        detection_rows = result.all()
        
        alerts = []
        for detection, camera in detection_rows:
            # Determine alert types from flags
            alert_types = []
            if detection.has_person:
                alert_types.append("PERSON_DETECTED")
            if detection.has_vehicle:
                alert_types.append("VEHICLE_DETECTED")
            if detection.has_package:
                alert_types.append("PACKAGE_DETECTED")
            if detection.has_unusual_activity:
                alert_types.append("UNUSUAL_ACTIVITY")
            if detection.is_night_time:
                alert_types.append("NIGHT_TIME")
            
            for alert_type in alert_types:
                alerts.append({
                    "id": detection.id,
                    "alert_type": alert_type,
                    "description": detection.description,
                    "camera_id": detection.camera_id,
                    "camera_name": camera.full_name,
                    "camera_location": camera.location,
                    "timestamp": detection.file_timestamp.isoformat(),
                    "confidence": detection.confidence,
                    "filepath": detection.filepath,
                    "enhanced_analysis": bool(detection.analysis_structured),
                    "structured_components": detection.get_structured_analysis()
                })
        
        return {"alerts": alerts, "enhanced_analysis_available": True}

@app.get("/api/enhanced-analysis/{detection_id}")
async def get_enhanced_analysis(detection_id: int):
    """Get detailed enhanced analysis for a specific detection."""
    async with SessionLocal() as session:
        result = await session.execute(
            select(Detection, Camera)
            .join(Camera)
            .where(Detection.id == detection_id)
        )
        row = result.first()
        
        if not row:
            return {"error": "Detection not found"}
        
        detection, camera = row
        
        # Parse enhanced analysis
        structured_analysis = detection.get_structured_analysis()
        
        return {
            "id": detection.id,
            "filename": detection.filename,
            "media_type": detection.media_type,
            "camera_name": camera.full_name,
            "camera_location": camera.location,
            "camera_device": camera.device_name,
            "timestamp": detection.file_timestamp.isoformat(),
            "confidence": detection.confidence,
            "raw_description": detection.description,
            "structured_analysis": structured_analysis,
            "alert_flags": {
                "has_person": detection.has_person,
                "has_vehicle": detection.has_vehicle,
                "has_package": detection.has_package,
                "has_unusual_activity": detection.has_unusual_activity,
                "is_night_time": detection.is_night_time,
                "alert_count": detection.alert_count
            },
            "has_enhanced_analysis": bool(detection.analysis_structured),
            "processing_info": {
                "processing_time": detection.processing_time,
                "frame_count": detection.frame_count,
                "duration": detection.duration,
                "dimensions": f"{detection.width}x{detection.height}" if detection.width and detection.height else None,
                "motion_detection_type": detection.motion_detection_type
            }
        }

# Create dashboard template
dashboard_html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Camera Detection Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
            color: #333;
        }
        
        .header {
            background-color: #2c3e50;
            color: white;
            padding: 1rem 2rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 2rem;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        
        .stat-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .stat-card h3 {
            color: #7f8c8d;
            font-size: 0.875rem;
            font-weight: 500;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }
        
        .stat-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #2c3e50;
        }
        
        .detections-table {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .table-header {
            background-color: #34495e;
            color: white;
            padding: 1rem 1.5rem;
            font-weight: 600;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            padding: 1rem;
            text-align: left;
            border-bottom: 1px solid #ecf0f1;
        }
        
        th {
            background-color: #ecf0f1;
            font-weight: 600;
            color: #2c3e50;
        }
        
        tr:hover {
            background-color: #f8f9fa;
        }
        
        .description {
            max-width: 400px;
            line-height: 1.4;
        }
        
        .confidence {
            font-weight: 600;
            color: #27ae60;
        }
        
        .camera-name {
            background-color: #3498db;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            display: inline-block;
        }
        
        .media-type {
            background-color: #9b59b6;
            color: white;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.875rem;
            display: inline-block;
        }
        
        .timestamp {
            color: #7f8c8d;
            font-size: 0.875rem;
        }
        
        .alert-banner {
            background-color: #e74c3c;
            color: white;
            padding: 1rem 2rem;
            margin-bottom: 2rem;
            border-radius: 8px;
            display: none;
        }
        
        .alert-banner.active {
            display: block;
        }
        
        .refresh-btn {
            background-color: #27ae60;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 500;
            margin-bottom: 1rem;
        }
        
        .refresh-btn:hover {
            background-color: #229954;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎥 Camera Detection Dashboard</h1>
    </div>
    
    <div class="container">
        <div id="alertBanner" class="alert-banner">
            <strong>⚠️ Alert:</strong> <span id="alertText"></span>
        </div>
        
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Detections</h3>
                <div class="value">{{ total_detections }}</div>
            </div>
            <div class="stat-card">
                <h3>Active Cameras</h3>
                <div class="value">{{ active_cameras }}</div>
            </div>
            <div class="stat-card">
                <h3>Last 24 Hours</h3>
                <div class="value" id="last24hours">{{ detections|length }}</div>
            </div>
        </div>
        
        <div class="detections-table">
            <div class="table-header">
                Recent Detections
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Camera</th>
                        <th>Type</th>
                        <th>Description</th>
                        <th>Confidence</th>
                    </tr>
                </thead>
                <tbody>
                    {% for detection in detections %}
                    <tr>
                        <td class="timestamp">{{ detection.detection.file_timestamp.strftime('%Y-%m-%d %H:%M:%S') }}</td>
                        <td><span class="camera-name">{{ detection.camera.full_name }}</span></td>
                        <td><span class="media-type">{{ detection.detection.media_type }}</span></td>
                        <td class="description">{{ detection.detection.description }}</td>
                        <td class="confidence">{{ "%.1f" | format(detection.detection.confidence * 100) }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        // Check for alerts
        async function checkAlerts() {
            try {
                const response = await fetch('/api/alerts?hours=1');
                const data = await response.json();
                
                if (data.alerts.length > 0) {
                    const alertBanner = document.getElementById('alertBanner');
                    const alertText = document.getElementById('alertText');
                    
                    const latestAlert = data.alerts[0];
                    alertText.textContent = `${latestAlert.description} (${latestAlert.camera_name})`;
                    alertBanner.classList.add('active');
                }
            } catch (error) {
                console.error('Error checking alerts:', error);
            }
        }
        
        // Check alerts on page load
        checkAlerts();
        
        // Auto-refresh every 30 seconds
        setInterval(() => {
            location.reload();
        }, 30000);
    </script>
</body>
</html>'''

# Save the template
with open("templates/dashboard.html", "w") as f:
    f.write(dashboard_html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT) 