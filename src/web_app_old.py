from fastapi import FastAPI, Request, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from datetime import datetime, timedelta
from pathlib import Path
import os

# Import our models
from models import Base, Detection, Camera, AlertType, initialize_alert_types
from config import DATABASE_URL, HOST, PORT, FOSCAM_DIR

# Database imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Create database engine
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Dependency to get database session
async def get_db():
    async with SessionLocal() as session:
        yield session

# Initialize FastAPI app
app = FastAPI(title="Foscam Detection Dashboard")

# Add static file serving for images and assets
app.mount("/images", StaticFiles(directory="foscam"), name="images")
app.mount("/media", StaticFiles(directory="foscam"), name="media")
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Template setup
templates = Jinja2Templates(directory="src/templates")

# Create templates directory
Path("src/templates").mkdir(exist_ok=True)

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initialize alert types
    async with SessionLocal() as session:
        await initialize_alert_types(session)
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
        
        return templates.TemplateResponse("dashboard-modular.html", {
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

@app.get("/api/detections/heatmap")
async def get_detections_heatmap(
    days: int = 30,
    resolution: str = "day",  # hour, day, week
    camera_ids: str = None,
    per_camera: bool = False
):
    """Get detection counts aggregated by time for heatmap visualization."""
    async with SessionLocal() as session:
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        if per_camera:
            # Query with camera breakdown
            query = select(Detection.file_timestamp, Detection.camera_id, Camera.location, Camera.full_name).join(Camera).where(
                Detection.processed == True,
                Detection.file_timestamp >= start_time,
                Detection.file_timestamp <= end_time
            )
            
            # Apply camera filtering if specified
            if camera_ids:
                camera_id_list = [int(id.strip()) for id in camera_ids.split(',') if id.strip()]
                if camera_id_list:
                    query = query.where(Camera.id.in_(camera_id_list))
                else:
                    # Empty camera list, return empty result
                    return {
                        "heatmap_data": [],
                        "camera_data": {},
                        "resolution": resolution,
                        "days": days,
                        "start_time": start_time.isoformat(),
                        "end_time": end_time.isoformat(),
                        "per_camera": per_camera
                    }
            
            query = query.order_by(Detection.file_timestamp)
            result = await session.execute(query)
            detection_data = result.all()
            
            # Aggregate by camera and time bucket
            camera_buckets = {}
            camera_info = {}
            
            for timestamp, camera_id, location, camera_name in detection_data:
                # Store camera info
                if camera_id not in camera_info:
                    camera_info[camera_id] = {
                        "name": camera_name,
                        "location": location
                    }
                
                # Calculate time bucket
                if resolution == "hour":
                    bucket_time = timestamp.replace(minute=0, second=0, microsecond=0)
                elif resolution == "day":
                    bucket_time = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                elif resolution == "week":
                    days_since_monday = timestamp.weekday()
                    bucket_time = (timestamp - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                
                bucket_key = bucket_time.isoformat()
                
                if camera_id not in camera_buckets:
                    camera_buckets[camera_id] = {}
                
                camera_buckets[camera_id][bucket_key] = camera_buckets[camera_id].get(bucket_key, 0) + 1
            
            # Convert to structured format
            heatmap_data = []
            camera_data = {}
            
            # Generate all time buckets in range
            current_time = start_time
            all_buckets = []
            
            while current_time <= end_time:
                if resolution == "hour":
                    bucket_time = current_time.replace(minute=0, second=0, microsecond=0)
                    next_time = current_time + timedelta(hours=1)
                elif resolution == "day":
                    bucket_time = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
                    next_time = current_time + timedelta(days=1)
                elif resolution == "week":
                    days_since_monday = current_time.weekday()
                    bucket_time = (current_time - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                    next_time = current_time + timedelta(weeks=1)
                
                bucket_key = bucket_time.isoformat()
                if bucket_key not in [b["timestamp"] for b in all_buckets]:
                    all_buckets.append({
                        "timestamp": bucket_key,
                        "date": bucket_time.strftime('%Y-%m-%d'),
                        "time": bucket_time.strftime('%H:%M') if resolution == "hour" else None
                    })
                
                current_time = next_time
            
            # Build camera data
            for camera_id, camera_buckets_data in camera_buckets.items():
                camera_data[camera_id] = {
                    "info": camera_info[camera_id],
                    "activity": []
                }
                
                for bucket in all_buckets:
                    count = camera_buckets_data.get(bucket["timestamp"], 0)
                    camera_data[camera_id]["activity"].append({
                        "timestamp": bucket["timestamp"],
                        "count": count,
                        "date": bucket["date"],
                        "time": bucket["time"]
                    })
            
            # Build overall heatmap data (sum across cameras)
            for bucket in all_buckets:
                total_count = sum(
                    camera_buckets.get(camera_id, {}).get(bucket["timestamp"], 0)
                    for camera_id in camera_buckets.keys()
                )
                heatmap_data.append({
                    "timestamp": bucket["timestamp"],
                    "count": total_count,
                    "date": bucket["date"],
                    "time": bucket["time"]
                })
            
            return {
                "heatmap_data": heatmap_data,
                "camera_data": camera_data,
                "camera_info": camera_info,
                "resolution": resolution,
                "days": days,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "per_camera": per_camera
            }
        
        else:
            # Original implementation for backward compatibility
            # Query to get detections in time range with optional camera filtering
            if camera_ids:
                camera_id_list = [int(id.strip()) for id in camera_ids.split(',') if id.strip()]
                if camera_id_list:
                    query = select(Detection.file_timestamp).join(Camera).where(
                        Detection.processed == True,
                        Detection.file_timestamp >= start_time,
                        Detection.file_timestamp <= end_time,
                        Camera.id.in_(camera_id_list)
                    ).order_by(Detection.file_timestamp)
                else:
                    query = select(Detection.file_timestamp).where(False)
            else:
                query = select(Detection.file_timestamp).where(
                    Detection.processed == True,
                    Detection.file_timestamp >= start_time,
                    Detection.file_timestamp <= end_time
                ).order_by(Detection.file_timestamp)
            
            result = await session.execute(query)
            timestamps = [row[0] for row in result]
            
            # Aggregate in Python for better SQLite compatibility
            buckets = {}
            
            for timestamp in timestamps:
                if resolution == "hour":
                    bucket_time = timestamp.replace(minute=0, second=0, microsecond=0)
                elif resolution == "day":
                    bucket_time = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                elif resolution == "week":
                    days_since_monday = timestamp.weekday()
                    bucket_time = (timestamp - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                
                bucket_key = bucket_time.isoformat()
                buckets[bucket_key] = buckets.get(bucket_key, 0) + 1
            
            # Convert to list format
            heatmap_data = []
            for bucket_time, count in sorted(buckets.items()):
                dt = datetime.fromisoformat(bucket_time)
                heatmap_data.append({
                    "timestamp": bucket_time,
                    "count": count,
                    "date": dt.strftime('%Y-%m-%d'),
                    "time": dt.strftime('%H:%M') if resolution == "hour" else None
                })
            
            return {
                "heatmap_data": heatmap_data,
                "resolution": resolution,
                "days": days,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "per_camera": per_camera
            }

@app.get("/api/detections/heatmap-hourly")
async def get_hourly_heatmap(
    hours: int = 24,
    camera_ids: str = None
):
    """Get hourly detection heatmap for the past 24 hours with per-camera breakdown."""
    async with SessionLocal() as session:
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Query with camera breakdown
        query = select(
            Detection.file_timestamp, 
            Detection.camera_id, 
            Camera.location, 
            Camera.full_name
        ).join(Camera).where(
            Detection.processed == True,
            Detection.file_timestamp >= start_time,
            Detection.file_timestamp <= end_time
        )
        
        # Apply camera filtering if specified
        if camera_ids:
            camera_id_list = [int(id.strip()) for id in camera_ids.split(',') if id.strip()]
            if camera_id_list:
                query = query.where(Camera.id.in_(camera_id_list))
            else:
                # Empty camera list, return empty result
                return {
                    "heatmap_data": [],
                    "camera_data": {},
                    "hours": hours,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                }
        
        query = query.order_by(Detection.file_timestamp)
        result = await session.execute(query)
        detection_data = result.all()
        
        # Camera colors are now handled dynamically by the frontend
        
        # Aggregate by camera and hour
        camera_buckets = {}
        camera_info = {}
        
        for timestamp, camera_id, location, camera_name in detection_data:
            # Store camera info
            if camera_id not in camera_info:
                camera_info[camera_id] = {
                    "name": camera_name,
                    "location": location
                }
            
            # Round to hour
            bucket_time = timestamp.replace(minute=0, second=0, microsecond=0)
            bucket_key = bucket_time.isoformat()
            
            if camera_id not in camera_buckets:
                camera_buckets[camera_id] = {}
            
            camera_buckets[camera_id][bucket_key] = camera_buckets[camera_id].get(bucket_key, 0) + 1
        
        # Generate all hour buckets in range
        all_buckets = []
        current_time = start_time.replace(minute=0, second=0, microsecond=0)
        
        while current_time <= end_time:
            bucket_key = current_time.isoformat()
            all_buckets.append({
                "timestamp": bucket_key,
                "date": current_time.strftime('%Y-%m-%d'),
                "time": current_time.strftime('%H:%M'),
                "hour": current_time.hour,
                "day_name": current_time.strftime('%A')
            })
            current_time += timedelta(hours=1)
        
        # Build camera data with activity levels
        camera_data = {}
        max_counts = {}
        
        # First pass: find max count for each camera for normalization
        for camera_id, camera_buckets_data in camera_buckets.items():
            max_counts[camera_id] = max(camera_buckets_data.values()) if camera_buckets_data else 0
        
        # Second pass: build normalized data
        for camera_id in camera_info.keys():
            camera_data[camera_id] = {
                "info": camera_info[camera_id],
                "activity": [],
                "max_count": max_counts.get(camera_id, 0)
            }
            
            camera_buckets_data = camera_buckets.get(camera_id, {})
            max_count = max_counts.get(camera_id, 1)  # Avoid division by zero
            
            for bucket in all_buckets:
                count = camera_buckets_data.get(bucket["timestamp"], 0)
                
                # Calculate intensity level (0-1) for color opacity
                intensity = count / max_count if max_count > 0 else 0
                
                # Determine activity level for styling (0-4)
                if count == 0:
                    level = 0
                elif count <= max_count * 0.25:
                    level = 1
                elif count <= max_count * 0.5:
                    level = 2
                elif count <= max_count * 0.75:
                    level = 3
                else:
                    level = 4
                
                camera_data[camera_id]["activity"].append({
                    "timestamp": bucket["timestamp"],
                    "count": count,
                    "date": bucket["date"],
                    "time": bucket["time"],
                    "hour": bucket["hour"],
                    "day_name": bucket["day_name"],
                    "intensity": intensity,
                    "level": level
                })
        
        # Build overall heatmap data (sum across cameras)
        heatmap_data = []
        for bucket in all_buckets:
            total_count = sum(
                camera_buckets.get(camera_id, {}).get(bucket["timestamp"], 0)
                for camera_id in camera_buckets.keys()
            )
            heatmap_data.append({
                "timestamp": bucket["timestamp"],
                "count": total_count,
                "date": bucket["date"],
                "time": bucket["time"],
                "hour": bucket["hour"],
                "day_name": bucket["day_name"]
            })
        
        return {
            "heatmap_data": heatmap_data,
            "camera_data": camera_data,
            "camera_info": camera_info,
            "hours": hours,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }

@app.get("/api/detections/time-range")
async def get_detections_by_time_range(
    start_time: str,
    end_time: str,
    limit: int = 50,
    offset: int = 0,
    camera_ids: str = None
):
    """Get detections within a specific time range."""
    async with SessionLocal() as session:
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid datetime format")
        
        # Query detections in time range
        query = select(Detection, Camera).join(Camera).where(
            Detection.processed == True,
            Detection.file_timestamp >= start_dt,
            Detection.file_timestamp <= end_dt
        )
        
        # Apply camera filtering if specified
        if camera_ids:
            camera_id_list = [int(id.strip()) for id in camera_ids.split(',') if id.strip()]
            if camera_id_list:
                query = query.where(Camera.id.in_(camera_id_list))
        
        query = query.order_by(desc(Detection.file_timestamp)).limit(limit).offset(offset)
        
        result = await session.execute(query)
        detection_rows = result.all()
        
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
                "file_timestamp": detection.file_timestamp.isoformat(),
                "width": detection.width,
                "height": detection.height,
                "frame_count": detection.frame_count,
                "duration": detection.duration,
                "processing_time": detection.processing_time,
                "has_person": detection.has_person,
                "has_vehicle": detection.has_vehicle,
                "has_package": detection.has_package,
                "has_unusual_activity": detection.has_unusual_activity,
                "is_night_time": detection.is_night_time,
                "alert_count": detection.alert_count
            }
            
            # Add structured analysis if available
            structured_analysis = detection.get_structured_analysis()
            if structured_analysis:
                detection_data["structured_analysis"] = structured_analysis
            else:
                detection_data["structured_analysis"] = {"general": detection.description}
            
            detection_data["has_enhanced_analysis"] = bool(detection.analysis_structured)
            enhanced_detections.append(detection_data)
        
        # Get total count for pagination
        count_query = select(func.count(Detection.id)).where(
            Detection.processed == True,
            Detection.file_timestamp >= start_dt,
            Detection.file_timestamp <= end_dt
        )
        total_result = await session.execute(count_query)
        total_count = total_result.scalar()
        
        return {
            "detections": enhanced_detections,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "start_time": start_time,
            "end_time": end_time,
            "has_next": offset + limit < total_count,
            "has_prev": offset > 0
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT)


        
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
            vertical-align: top;
        }
        
        th {
            background-color: #ecf0f1;
            font-weight: 600;
            color: #2c3e50;
        }
        
        tr:hover {
            background-color: #f8f9fa;
        }
        
        tbody tr {
            min-height: 300px;
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
        
        .thumbnail-image {
            width: 400px;
            height: 267px;
            object-fit: cover;
            border-radius: 8px;
            border: 2px solid #ddd;
            transition: all 0.3s ease;
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        }
        
        .thumbnail-image:hover {
            border-color: #3498db;
            transform: scale(1.05);
            box-shadow: 0 6px 12px rgba(0,0,0,0.3);
        }
        
        .image-link {
            display: inline-block;
            text-decoration: none;
        }
        
        .video-indicator {
            color: #9b59b6;
            font-size: 0.8rem;
            font-weight: 500;
            padding: 1rem;
            display: inline-block;
        }
        
        /* Time Navigation Styles */
        .time-controls {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .time-controls-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }
        
        .time-controls-header h3 {
            margin: 0;
            color: #2c3e50;
        }
        
        .date-range-controls {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        
        .date-inputs {
            display: flex;
            align-items: center;
            gap: 1rem;
            flex-wrap: wrap;
        }
        
        .date-input {
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9rem;
        }
        
        .apply-btn {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-weight: 500;
        }
        
        .apply-btn:hover {
            background-color: #2980b9;
        }
        
        .quick-filters {
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        
        .quick-filter-btn {
            background-color: #ecf0f1;
            color: #2c3e50;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
        }
        
        .quick-filter-btn:hover {
            background-color: #bdc3c7;
        }
        
        .quick-filter-btn.active {
            background-color: #3498db;
            color: white;
        }
        
        /* GitHub-style Heatmap Styles */
        .heatmap-container {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        
        .heatmap-header {
            display: flex;
            flex-direction: column;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .heatmap-header h3 {
            margin: 0;
            color: #2c3e50;
        }
        
        .heatmap-stats {
            display: flex;
            gap: 2rem;
            flex-wrap: wrap;
        }
        
        .stat-item {
            display: flex;
            align-items: baseline;
            gap: 0.25rem;
        }
        
        .stat-number {
            font-size: 1.5rem;
            font-weight: 600;
            color: #2c3e50;
        }
        
        .stat-label {
            color: #7f8c8d;
            font-size: 0.9rem;
        }
        
        .stat-date {
            color: #7f8c8d;
            font-size: 0.8rem;
        }
        
        .calendar-heatmap {
            margin: 1rem 0;
        }
        
        .month-labels {
            display: grid;
            grid-template-columns: repeat(53, 1fr);
            gap: 2px;
            margin-bottom: 4px;
            padding-left: 30px;
        }
        
        .month-label {
            font-size: 0.75rem;
            color: #7f8c8d;
            text-align: left;
        }
        
        .calendar-grid {
            display: flex;
            gap: 8px;
        }
        
        .day-labels {
            display: flex;
            flex-direction: column;
            gap: 2px;
            width: 20px;
        }
        
        .day-labels span {
            height: 12px;
            font-size: 0.7rem;
            color: #7f8c8d;
            text-align: right;
            line-height: 12px;
        }
        
        .heatmap-grid {
            display: grid;
            grid-template-rows: repeat(7, 12px);
            grid-auto-flow: column;
            gap: 2px;
        }
        
        .heatmap-square {
            width: 12px;
            height: 12px;
            border-radius: 2px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .heatmap-square:hover {
            transform: scale(1.1);
            border: 1px solid #2c3e50;
        }
        
        /* Activity levels - GitHub-style green theme */
        .heatmap-square.level-0 {
            background-color: #ebedf0;
        }
        
        .heatmap-square.level-1 {
            background-color: #9be9a8;
        }
        
        .heatmap-square.level-2 {
            background-color: #40c463;
        }
        
        .heatmap-square.level-3 {
            background-color: #30a14e;
        }
        
        .heatmap-square.level-4 {
            background-color: #216e39;
        }
        
        .heatmap-legend {
            display: flex;
            align-items: center;
            justify-content: flex-end;
            gap: 0.5rem;
            margin-top: 1rem;
        }
        
        .legend-label {
            font-size: 0.75rem;
            color: #7f8c8d;
        }
        
        .legend-squares {
            display: flex;
            gap: 2px;
        }
        
        .legend-square {
            width: 12px;
            height: 12px;
            border-radius: 2px;
        }
        
        .legend-square.level-0 {
            background-color: #ebedf0;
        }
        
        .legend-square.level-1 {
            background-color: #9be9a8;
        }
        
        .legend-square.level-2 {
            background-color: #40c463;
        }
        
        .legend-square.level-3 {
            background-color: #30a14e;
        }
        
        .legend-square.level-4 {
            background-color: #216e39;
        }
        
        /* Pagination Styles */
        .pagination-controls {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            padding: 1rem 1.5rem;
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .pagination-info {
            color: #7f8c8d;
            font-size: 0.9rem;
        }
        
        .pagination-buttons {
            display: flex;
            gap: 0.5rem;
        }
        
        .pagination-buttons button {
            background-color: #3498db;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        
        .pagination-buttons button:hover:not(:disabled) {
            background-color: #2980b9;
        }
        
        .pagination-buttons button:disabled {
            background-color: #bdc3c7;
            cursor: not-allowed;
        }

        /* Camera Filter Styles */
        .camera-filter-controls {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .camera-select {
            min-height: 100px;
            max-height: 150px;
            padding: 0.5rem;
            border: 1px solid #ddd;
            border-radius: 4px;
            font-size: 0.9rem;
            background-color: white;
        }

        .camera-select option {
            padding: 0.3rem;
            margin: 0.1rem 0;
        }

        .camera-select option:checked {
            background-color: #3498db;
            color: white;
        }

        .selected-cameras {
            margin-top: 0.5rem;
        }

        .selected-cameras-label {
            font-weight: 500;
            color: #2c3e50;
        }

        .camera-tag {
            display: inline-block;
            background-color: #3498db;
            color: white;
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
            font-size: 0.8rem;
            margin: 0.2rem;
        }

        .camera-tag .remove {
            margin-left: 0.3rem;
            cursor: pointer;
            font-weight: bold;
        }

        .camera-tag .remove:hover {
            color: #e74c3c;
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
        
        <!-- Time Navigation Controls -->
        <div class="time-controls">
            <div class="time-controls-header">
                <h3>📅 Time Navigation</h3>
                <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
            </div>
            
            <div class="date-range-controls">
                <div class="date-inputs">
                    <label for="startDate">From:</label>
                    <input type="datetime-local" id="startDate" class="date-input">
                    <label for="endDate">To:</label>
                    <input type="datetime-local" id="endDate" class="date-input">
                    <button onclick="applyDateRange()" class="apply-btn">Apply Range</button>
                </div>
                
                <div class="quick-filters">
                    <button onclick="setQuickFilter('1h')" class="quick-filter-btn">Last Hour</button>
                    <button onclick="setQuickFilter('24h')" class="quick-filter-btn active">Last 24h</button>
                    <button onclick="setQuickFilter('7d')" class="quick-filter-btn">Last 7 Days</button>
                    <button onclick="setQuickFilter('30d')" class="quick-filter-btn">Last 30 Days</button>
                </div>
            </div>
        </div>

        <!-- Camera Filter Controls -->
        <div class="time-controls">
            <div class="time-controls-header">
                <h3>📹 Camera Filter</h3>
                <button onclick="clearCameraFilter()" class="refresh-btn">Clear Filter</button>
            </div>
            
            <div class="date-range-controls">
                <div class="camera-filter-controls">
                    <label for="cameraSelect">Select Cameras:</label>
                    <select id="cameraSelect" multiple class="camera-select">
                        <option value="">Loading cameras...</option>
                    </select>
                    <button onclick="applyCameraFilter()" class="apply-btn">Apply Filter</button>
                </div>
                
                <div id="selectedCameras" class="selected-cameras">
                    <span class="selected-cameras-label">Showing: All Cameras</span>
                </div>
            </div>
        </div>
        
        <!-- Activity Heatmap -->
        <div class="heatmap-container">
            <div class="heatmap-header">
                <h3>🔥 Detection Activity</h3>
                <div class="heatmap-stats">
                    <div class="stat-item">
                        <span id="totalActivity" class="stat-number">0</span>
                        <span class="stat-label">detections in the last year</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Busiest day:</span>
                        <span id="busiestDay" class="stat-number">0</span>
                        <span class="stat-label">detections</span>
                        <span id="busiestDate" class="stat-date"></span>
                    </div>
                </div>
            </div>
            
            <div class="calendar-heatmap">
                <div class="month-labels" id="monthLabels"></div>
                <div class="calendar-grid">
                    <div class="day-labels">
                        <span></span>
                        <span>Mon</span>
                        <span></span>
                        <span>Wed</span>
                        <span></span>
                        <span>Fri</span>
                        <span></span>
                    </div>
                    <div class="heatmap-grid" id="heatmapGrid"></div>
                </div>
            </div>
            
            <div class="heatmap-legend">
                <span class="legend-label">Less</span>
                <div class="legend-squares">
                    <div class="legend-square level-0"></div>
                    <div class="legend-square level-1"></div>
                    <div class="legend-square level-2"></div>
                    <div class="legend-square level-3"></div>
                    <div class="legend-square level-4"></div>
                </div>
                <span class="legend-label">More</span>
            </div>
        </div>
        
        <!-- Pagination Controls -->
        <div class="pagination-controls">
            <div class="pagination-info">
                <span id="paginationInfo">Loading...</span>
            </div>
            <div class="pagination-buttons">
                <button id="prevBtn" onclick="previousPage()" disabled>← Previous</button>
                <button id="nextBtn" onclick="nextPage()" disabled>Next →</button>
            </div>
        </div>
        
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
                        <th>Image</th>
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
                        <td>
                            {% if detection.detection.media_type == 'image' %}
                                <a href="/images/{{ detection.detection.filepath.replace('foscam/', '') }}" target="_blank" class="image-link">
                                    <img src="/images/{{ detection.detection.filepath.replace('foscam/', '') }}" alt="{{ detection.detection.filename }}" class="thumbnail-image">
                                </a>
                            {% else %}
                                <span class="video-indicator">🎬 Video</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        // Global variables
        let currentStartTime = null;
        let currentEndTime = null;
        let currentOffset = 0;
        let currentLimit = 50;
        let totalDetections = 0;
        let currentDetections = [];
        let selectedCameraIds = [];
        let allCameras = [];
        
        // Initialize the page
        document.addEventListener('DOMContentLoaded', function() {
            initializeDateInputs();
            loadCameras(); // Load available cameras
            setQuickFilter('24h'); // Default to last 24 hours
            updateHeatmap();
            checkAlerts();
            
            // Check alerts every 30 seconds
            setInterval(checkAlerts, 30000);
        });
        
        // Initialize date inputs with default values
        function initializeDateInputs() {
            const now = new Date();
            const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
            
            document.getElementById('endDate').value = formatDateTimeLocal(now);
            document.getElementById('startDate').value = formatDateTimeLocal(yesterday);
        }
        
        // Format date for datetime-local input
        function formatDateTimeLocal(date) {
            const offset = date.getTimezoneOffset();
            const localDate = new Date(date.getTime() - (offset * 60 * 1000));
            return localDate.toISOString().slice(0, 16);
        }

        // Load available cameras
        async function loadCameras() {
            try {
                const response = await fetch('/api/cameras');
                const data = await response.json();
                allCameras = data.cameras;
                
                const cameraSelect = document.getElementById('cameraSelect');
                cameraSelect.innerHTML = '';
                
                // Add "All Cameras" option
                const allOption = document.createElement('option');
                allOption.value = '';
                allOption.textContent = 'All Cameras';
                cameraSelect.appendChild(allOption);
                
                // Add individual cameras
                allCameras.forEach(camera => {
                    const option = document.createElement('option');
                    option.value = camera.id;
                    option.textContent = `${camera.full_name} (${camera.location})`;
                    cameraSelect.appendChild(option);
                });
                
                console.log(`Loaded ${allCameras.length} cameras`);
            } catch (error) {
                console.error('Error loading cameras:', error);
                const cameraSelect = document.getElementById('cameraSelect');
                cameraSelect.innerHTML = '<option value="">Error loading cameras</option>';
            }
        }

        // Apply camera filter
        function applyCameraFilter() {
            const cameraSelect = document.getElementById('cameraSelect');
            const selectedOptions = Array.from(cameraSelect.selectedOptions);
            
            // Get selected camera IDs
            selectedCameraIds = selectedOptions
                .map(option => option.value)
                .filter(value => value !== ''); // Remove empty "All Cameras" option
            
            updateSelectedCamerasDisplay();
            
            // Reload data with camera filter
            loadDetections();
            updateHeatmap();
        }

        // Clear camera filter
        function clearCameraFilter() {
            selectedCameraIds = [];
            const cameraSelect = document.getElementById('cameraSelect');
            cameraSelect.selectedIndex = -1; // Clear all selections
            
            updateSelectedCamerasDisplay();
            
            // Reload data without camera filter
            loadDetections();
            updateHeatmap();
        }

        // Update the display of selected cameras
        function updateSelectedCamerasDisplay() {
            const selectedCamerasDiv = document.getElementById('selectedCameras');
            
            if (selectedCameraIds.length === 0) {
                selectedCamerasDiv.innerHTML = '<span class="selected-cameras-label">Showing: All Cameras</span>';
            } else {
                const selectedCameraNames = selectedCameraIds.map(id => {
                    const camera = allCameras.find(c => c.id.toString() === id.toString());
                    return camera ? camera.full_name : `Camera ${id}`;
                });
                
                let html = '<span class="selected-cameras-label">Showing: </span>';
                selectedCameraNames.forEach((name, index) => {
                    html += `<span class="camera-tag">${name} <span class="remove" onclick="removeCameraFilter('${selectedCameraIds[index]}')">×</span></span>`;
                });
                
                selectedCamerasDiv.innerHTML = html;
            }
        }

        // Remove a specific camera from filter
        function removeCameraFilter(cameraId) {
            selectedCameraIds = selectedCameraIds.filter(id => id.toString() !== cameraId.toString());
            
            // Update the select element
            const cameraSelect = document.getElementById('cameraSelect');
            Array.from(cameraSelect.options).forEach(option => {
                if (option.value === cameraId.toString()) {
                    option.selected = false;
                }
            });
            
            updateSelectedCamerasDisplay();
            
            // Reload data
            loadDetections();
            updateHeatmap();
        }
        
        // Set quick filter timeframes
        function setQuickFilter(period) {
            const now = new Date();
            let startTime;
            
            // Remove active class from all buttons
            document.querySelectorAll('.quick-filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Add active class to clicked button
            event.target.classList.add('active');
            
            switch(period) {
                case '1h':
                    startTime = new Date(now.getTime() - 60 * 60 * 1000);
                    break;
                case '24h':
                    startTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
                    break;
                case '7d':
                    startTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    break;
                case '30d':
                    startTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                    break;
            }
            
            currentStartTime = startTime.toISOString();
            currentEndTime = now.toISOString();
            currentOffset = 0;
            
            document.getElementById('startDate').value = formatDateTimeLocal(startTime);
            document.getElementById('endDate').value = formatDateTimeLocal(now);
            
            loadDetections();
            updateHeatmap();
        }
        
        // Apply custom date range
        function applyDateRange() {
            const startDate = document.getElementById('startDate').value;
            const endDate = document.getElementById('endDate').value;
            
            if (!startDate || !endDate) {
                alert('Please select both start and end dates');
                return;
            }
            
            currentStartTime = new Date(startDate).toISOString();
            currentEndTime = new Date(endDate).toISOString();
            currentOffset = 0;
            
            // Remove active class from quick filter buttons
            document.querySelectorAll('.quick-filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            loadDetections();
            updateHeatmap();
        }
        
        // Load detections for current time range
        async function loadDetections() {
            try {
                let url = `/api/detections/time-range?start_time=${encodeURIComponent(currentStartTime)}&end_time=${encodeURIComponent(currentEndTime)}&limit=${currentLimit}&offset=${currentOffset}`;
                
                // Add camera filter if selected
                if (selectedCameraIds.length > 0) {
                    url += `&camera_ids=${selectedCameraIds.join(',')}`;
                }
                
                const response = await fetch(url);
                const data = await response.json();
                
                currentDetections = data.detections;
                totalDetections = data.total_count;
                
                updateDetectionTable(data.detections);
                updatePaginationControls(data);
                
            } catch (error) {
                console.error('Error loading detections:', error);
            }
        }
        
        // Update detection table
        function updateDetectionTable(detections) {
            const tbody = document.querySelector('.detections-table tbody');
            tbody.innerHTML = '';
            
            detections.forEach(detection => {
                const row = document.createElement('tr');
                
                const imageCell = detection.media_type === 'image' ? 
                    `<a href="/images/${detection.filepath.replace('foscam/', '')}" target="_blank" class="image-link">
                        <img src="/images/${detection.filepath.replace('foscam/', '')}" alt="${detection.filename}" class="thumbnail-image">
                    </a>` : 
                    '<span class="video-indicator">🎬 Video</span>';
                
                row.innerHTML = `
                    <td class="timestamp">${new Date(detection.file_timestamp).toLocaleString()}</td>
                    <td><span class="camera-name">${detection.camera_name}</span></td>
                    <td><span class="media-type">${detection.media_type}</span></td>
                    <td class="description">${detection.description}</td>
                    <td class="confidence">${(detection.confidence * 100).toFixed(1)}%</td>
                    <td>${imageCell}</td>
                `;
                
                tbody.appendChild(row);
            });
        }
        
        // Update pagination controls
        function updatePaginationControls(data) {
            const info = document.getElementById('paginationInfo');
            const prevBtn = document.getElementById('prevBtn');
            const nextBtn = document.getElementById('nextBtn');
            
            const start = currentOffset + 1;
            const end = Math.min(currentOffset + currentLimit, totalDetections);
            
            info.textContent = `Showing ${start}-${end} of ${totalDetections} detections`;
            
            prevBtn.disabled = !data.has_prev;
            nextBtn.disabled = !data.has_next;
        }
        
        // Pagination functions
        function previousPage() {
            if (currentOffset > 0) {
                currentOffset -= currentLimit;
                loadDetections();
            }
        }
        
        function nextPage() {
            currentOffset += currentLimit;
            loadDetections();
        }
        
        // Update heatmap
        async function updateHeatmap() {
            try {
                // Get year-long data for calendar heatmap
                let url = `/api/detections/heatmap?days=365&resolution=day`;
                
                // Add camera filter if selected
                if (selectedCameraIds.length > 0) {
                    url += `&camera_ids=${selectedCameraIds.join(',')}`;
                }
                
                const response = await fetch(url);
                const data = await response.json();
                
                createCalendarHeatmap(data.heatmap_data);
                
            } catch (error) {
                console.error('Error updating heatmap:', error);
            }
        }
        
        // Create GitHub-style calendar heatmap
        function createCalendarHeatmap(heatmapData) {
            const grid = document.getElementById('heatmapGrid');
            const monthLabels = document.getElementById('monthLabels');
            
            // Clear existing content
            grid.innerHTML = '';
            monthLabels.innerHTML = '';
            
            // Create a map of dates to counts
            const dataMap = {};
            let totalActivity = 0;
            let maxCount = 0;
            let busiestDay = { count: 0, date: null };
            
            heatmapData.forEach(item => {
                const date = new Date(item.timestamp).toDateString();
                dataMap[date] = item.count;
                totalActivity += item.count;
                if (item.count > maxCount) {
                    maxCount = item.count;
                }
                if (item.count > busiestDay.count) {
                    busiestDay = { count: item.count, date: new Date(item.timestamp) };
                }
            });
            
            // Update statistics
            document.getElementById('totalActivity').textContent = totalActivity.toLocaleString();
            document.getElementById('busiestDay').textContent = busiestDay.count;
            document.getElementById('busiestDate').textContent = busiestDay.date ? 
                busiestDay.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '';
            
            // Calculate start date (53 weeks ago from today)
            const today = new Date();
            const startDate = new Date(today);
            startDate.setDate(today.getDate() - (53 * 7 - today.getDay()));
            
            // Generate month labels
            let currentMonth = -1;
            let weekCount = 0;
            
            for (let week = 0; week < 53; week++) {
                const weekStart = new Date(startDate);
                weekStart.setDate(startDate.getDate() + week * 7);
                
                if (weekStart.getMonth() !== currentMonth && weekStart.getDate() <= 7) {
                    currentMonth = weekStart.getMonth();
                    const monthDiv = document.createElement('div');
                    monthDiv.className = 'month-label';
                    monthDiv.style.gridColumn = `${week + 1}`;
                    monthDiv.textContent = weekStart.toLocaleDateString('en-US', { month: 'short' });
                    monthLabels.appendChild(monthDiv);
                }
            }
            
            // Generate calendar squares
            for (let week = 0; week < 53; week++) {
                for (let day = 0; day < 7; day++) {
                    const date = new Date(startDate);
                    date.setDate(startDate.getDate() + week * 7 + day);
                    
                    // Skip future dates
                    if (date > today) continue;
                    
                    const square = document.createElement('div');
                    square.className = 'heatmap-square';
                    
                    const dateKey = date.toDateString();
                    const count = dataMap[dateKey] || 0;
                    
                    // Calculate activity level (0-4)
                    let level = 0;
                    if (count > 0) {
                        if (maxCount <= 4) {
                            level = Math.min(count, 4);
                        } else {
                            const percentage = count / maxCount;
                            if (percentage <= 0.25) level = 1;
                            else if (percentage <= 0.5) level = 2;
                            else if (percentage <= 0.75) level = 3;
                            else level = 4;
                        }
                    }
                    
                    square.classList.add(`level-${level}`);
                    square.title = `${count} detection${count !== 1 ? 's' : ''} on ${date.toLocaleDateString()}`;
                    
                    // Add click handler
                    square.addEventListener('click', () => {
                        jumpToDay(date);
                    });
                    
                    grid.appendChild(square);
                }
            }
        }
        
        // Jump to specific day from heatmap click
        function jumpToDay(date) {
            const startOfDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
            const endOfDay = new Date(date.getFullYear(), date.getMonth(), date.getDate() + 1);
            
            currentStartTime = startOfDay.toISOString();
            currentEndTime = endOfDay.toISOString();
            currentOffset = 0;
            
            // Update date inputs
            document.getElementById('startDate').value = formatDateTimeLocal(startOfDay);
            document.getElementById('endDate').value = formatDateTimeLocal(endOfDay);
            
            // Remove active class from quick filter buttons
            document.querySelectorAll('.quick-filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            loadDetections();
        }
        
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
    </script>
</body>
</html>'''

# Save the template
with open("templates/dashboard.html", "w") as f:
    f.write(dashboard_html)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT) 