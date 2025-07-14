from fastapi import FastAPI, Request, Query, HTTPException, Depends
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, selectinload
from datetime import datetime, timedelta
from pathlib import Path
import os
import markdown
import aiofiles
import time
import traceback

# Import our models
from src.models import Base, Detection, Camera, AlertType, initialize_alert_types
from src.config import DATABASE_URL, HOST, PORT, FOSCAM_DIR
from src.video_converter import video_converter
from src.gpu_monitor import gpu_monitor
from src.logging_config import setup_logger, setup_uvicorn_logging

# Set up logging
logger = setup_logger("webui", "INFO")

# Database imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Create database engine
engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Dependency to get database session
async def get_db():
    """Database dependency with logging"""
    start_time = time.time()
    try:
        async with SessionLocal() as session:
            logger.debug("Database session created")
            yield session
    except Exception as e:
        logger.error(f"Database session error: {e}")
        raise
    finally:
        duration = time.time() - start_time
        logger.debug(f"Database session closed (duration: {duration:.3f}s)")

# Initialize FastAPI app
app = FastAPI(title="Foscam Detection Dashboard")
logger.info("FastAPI app initialized")

# Add static file serving for images and assets
app.mount("/images", StaticFiles(directory="foscam"), name="images")
app.mount("/media", StaticFiles(directory="foscam"), name="media")
app.mount("/static", StaticFiles(directory="src/static"), name="static")
logger.info("Static file mounts configured")

# Template setup
templates = Jinja2Templates(directory="src/templates")
logger.info("Templates configured")

# Create templates directory
Path("src/templates").mkdir(exist_ok=True)

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    logger.info("Starting application startup sequence")
    try:
        async with engine.begin() as conn:
            logger.info("Creating database tables")
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")
    
        # Initialize alert types
        async with SessionLocal() as session:
            logger.info("Initializing alert types")
            await initialize_alert_types(session)
            await session.commit()
            logger.info("Alert types initialized successfully")
        
        logger.info("Application startup completed successfully")
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        logger.error(f"Startup error traceback: {traceback.format_exc()}")
        raise

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Home page with dashboard"""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    logger.info(f"Home page request from {client_ip}")
    
    try:
        # Get recent detections for dashboard
        logger.debug("Fetching recent detections for dashboard")
        # Read the dashboard template
        template_path = Path("src/templates/dashboard.html")
        
        if not template_path.exists():
            logger.error(f"Dashboard template not found: {template_path}")
            return HTMLResponse(content="Dashboard template not found", status_code=500)
        
        async with aiofiles.open(template_path, 'r') as f:
            dashboard_content = await f.read()
        
        # Add timestamp for cache-busting
        timestamp = str(int(time.time()))
        dashboard_content = dashboard_content.replace('{{ timestamp }}', timestamp)
        
        duration = time.time() - start_time
        logger.info(f"Home page served successfully to {client_ip} (duration: {duration:.3f}s)")
        return HTMLResponse(content=dashboard_content)
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Home page error for {client_ip}: {e} (duration: {duration:.3f}s)")
        logger.error(f"Home page error traceback: {traceback.format_exc()}")
        return HTMLResponse(content="Internal server error", status_code=500)

@app.get("/api/detections")
async def get_detections(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    start_date: str = Query(None),
    end_date: str = Query(None),
    camera_ids: str = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated detections with filtering"""
    start_time = time.time()
    logger.info(f"API detections request - page: {page}, per_page: {per_page}, start_date: {start_date}, end_date: {end_date}, camera_ids: {camera_ids}")
    
    try:
        # Start with base query
        query = select(Detection).options(selectinload(Detection.camera))
        
        # Apply date filters
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.where(Detection.timestamp >= start_dt)
                logger.debug(f"Applied start date filter: {start_dt}")
            except ValueError as e:
                logger.warning(f"Invalid start_date format: {start_date} - {e}")
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.where(Detection.timestamp <= end_dt)
                logger.debug(f"Applied end date filter: {end_dt}")
            except ValueError as e:
                logger.warning(f"Invalid end_date format: {end_date} - {e}")
        
        # Apply camera filter
        if camera_ids:
            try:
                camera_id_list = [int(id.strip()) for id in camera_ids.split(',')]
                query = query.where(Detection.camera_id.in_(camera_id_list))
                logger.debug(f"Applied camera filter: {camera_id_list}")
            except ValueError as e:
                logger.warning(f"Invalid camera_ids format: {camera_ids} - {e}")
        
        # Get total count
        logger.debug("Counting total detections")
        count_query = select(func.count()).select_from(query.subquery())
        total_count = await db.execute(count_query)
        total = total_count.scalar()
        logger.debug(f"Total detections matching filter: {total}")
        
        # Apply pagination and ordering
        query = query.order_by(desc(Detection.timestamp))
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)
        
        # Execute query
        logger.debug(f"Executing detections query with offset: {offset}, limit: {per_page}")
        result = await db.execute(query)
        detections = result.scalars().all()
        
        # Convert to response format
        logger.debug(f"Converting {len(detections)} detections to response format")
        detection_list = []
        for detection in detections:
            detection_dict = {
                "id": detection.id,
                "camera_id": detection.camera_id,
                "camera_location": detection.camera.full_name if detection.camera else "Unknown",
                "timestamp": detection.timestamp.isoformat(),
                "file_timestamp": detection.file_timestamp.isoformat() if detection.file_timestamp else None,
                "confidence": detection.confidence,
                "media_type": detection.media_type,
                "motion_detection_type": detection.motion_detection_type,
                "media_filename": detection.filepath,
                "filename": detection.filename,
                "description": detection.description,
                "processed": detection.processed,
                "processing_time": detection.processing_time,
                "width": detection.width,
                "height": detection.height,
                "frame_count": detection.frame_count,
                "duration": detection.duration,
                "has_person": detection.has_person,
                "has_vehicle": detection.has_vehicle,
                "has_package": detection.has_package,
                "has_unusual_activity": detection.has_unusual_activity,
                "is_night_time": detection.is_night_time,
                "alert_count": detection.alert_count,
                "analysis_structured": detection.analysis_structured
            }
            detection_list.append(detection_dict)
        
        response_data = {
            "detections": detection_list,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page
        }
        
        duration = time.time() - start_time
        logger.info(f"API detections response - total: {total}, returned: {len(detections)}, page: {page}/{response_data['total_pages']} (duration: {duration:.3f}s)")
        return JSONResponse(content=response_data)
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"API detections error: {e} (duration: {duration:.3f}s)")
        logger.error(f"API detections error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/detections/heatmap")
async def get_detections_heatmap(
    days: int = 30,
    resolution: str = "day",
    camera_ids: str = None,
    per_camera: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get detection heatmap data with extensive logging"""
    start_time = time.time()
    logger.info(f"API heatmap request - days: {days}, resolution: {resolution}, camera_ids: {camera_ids}, per_camera: {per_camera}")
    
    try:
        # Validate resolution
        if resolution not in ["day", "hour"]:
            logger.warning(f"Invalid resolution parameter: {resolution}")
            raise HTTPException(status_code=400, detail="Resolution must be 'day' or 'hour'")
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        logger.debug(f"Heatmap date range: {start_date} to {end_date}")
        
        # Build base query
        query = select(Detection).where(
            Detection.timestamp >= start_date,
            Detection.timestamp <= end_date,
            Detection.processed == True
        )
        
        # Apply camera filter
        if camera_ids:
            try:
                camera_id_list = [int(id.strip()) for id in camera_ids.split(',')]
                query = query.where(Detection.camera_id.in_(camera_id_list))
                logger.debug(f"Applied camera filter to heatmap: {camera_id_list}")
            except ValueError as e:
                logger.warning(f"Invalid camera_ids format in heatmap: {camera_ids} - {e}")
        
        # Execute query
        logger.debug("Executing heatmap query")
        result = await db.execute(query)
        detections = result.scalars().all()
        logger.debug(f"Retrieved {len(detections)} detections for heatmap")
        
        # Process data based on resolution
        heatmap_data = {}
        
        if resolution == "day":
            # Group by date
            for detection in detections:
                date_key = detection.timestamp.date().isoformat()
                if per_camera:
                    camera_key = f"{detection.camera_id}"
                    if camera_key not in heatmap_data:
                        heatmap_data[camera_key] = {}
                    heatmap_data[camera_key][date_key] = heatmap_data[camera_key].get(date_key, 0) + 1
                else:
                    heatmap_data[date_key] = heatmap_data.get(date_key, 0) + 1
        
        elif resolution == "hour":
            # Group by hour
            for detection in detections:
                hour_key = detection.timestamp.strftime("%Y-%m-%d %H:00")
                if per_camera:
                    camera_key = f"{detection.camera_id}"
                    if camera_key not in heatmap_data:
                        heatmap_data[camera_key] = {}
                    heatmap_data[camera_key][hour_key] = heatmap_data[camera_key].get(hour_key, 0) + 1
                else:
                    heatmap_data[hour_key] = heatmap_data.get(hour_key, 0) + 1
        
        duration = time.time() - start_time
        logger.info(f"API heatmap response - processed {len(detections)} detections, resolution: {resolution}, data points: {len(heatmap_data)} (duration: {duration:.3f}s)")
        
        return JSONResponse(content={
            "heatmap_data": heatmap_data,
            "resolution": resolution,
            "days": days,
            "per_camera": per_camera,
            "total_detections": len(detections)
        })
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"API heatmap error: {e} (duration: {duration:.3f}s)")
        logger.error(f"API heatmap error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/detections/heatmap-hourly")
async def get_hourly_heatmap(
    per_camera: bool = False,
    camera_ids: str = None
):
    """Get hourly detection heatmap for the past 24 hours."""
    async with SessionLocal() as session:
        # Calculate time range (last 24 hours)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        
        # Build query
        query = select(Detection.file_timestamp, Detection.camera_id, Camera.location).join(Camera).where(
            Detection.processed == True,
            Detection.file_timestamp >= start_time,
            Detection.file_timestamp <= end_time
        )
        
        # Apply camera filtering if specified
        if camera_ids:
            camera_id_list = [int(id.strip()) for id in camera_ids.split(',') if id.strip()]
            if camera_id_list:
                query = query.where(Camera.id.in_(camera_id_list))
        
        result = await session.execute(query)
        detection_data = result.all()
        
        # Aggregate by hour
        hourly_counts = {}
        camera_breakdown = {}
        
        for timestamp, camera_id, location in detection_data:
            hour = timestamp.hour
            
            # Overall count
            hourly_counts[hour] = hourly_counts.get(hour, 0) + 1
            
            # Per-camera breakdown if requested
            if per_camera:
                if hour not in camera_breakdown:
                    camera_breakdown[hour] = {}
                camera_breakdown[hour][location] = camera_breakdown[hour].get(location, 0) + 1
        
        # Convert to list format (24 hours)
        heatmap_data = []
        for hour in range(24):
            item = {
                "hour": hour,
                "count": hourly_counts.get(hour, 0)
            }
            if per_camera and hour in camera_breakdown:
                item["camera_breakdown"] = camera_breakdown[hour]
            heatmap_data.append(item)
        
        return {"heatmap_data": heatmap_data}

@app.get("/api/cameras")
async def get_cameras(db: AsyncSession = Depends(get_db)):
    """Get all cameras with extensive logging"""
    start_time = time.time()
    logger.info("API cameras request")
    
    try:
        logger.debug("Fetching all cameras")
        result = await db.execute(select(Camera))
        cameras = result.scalars().all()
        
        camera_list = []
        for camera in cameras:
            camera_dict = {
                "id": camera.id,
                "name": camera.full_name,
                "location": camera.location,
                "device_name": camera.device_name,
                "is_active": camera.is_active,
                "last_seen": camera.last_seen.isoformat() if camera.last_seen else None
            }
            camera_list.append(camera_dict)
        
        duration = time.time() - start_time
        logger.info(f"API cameras response - returned {len(cameras)} cameras (duration: {duration:.3f}s)")
        return JSONResponse(content={"cameras": camera_list})
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"API cameras error: {e} (duration: {duration:.3f}s)")
        logger.error(f"API cameras error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/detections/stats")
async def get_stats(
    camera_ids: str = Query(None)
):
    """Get detection statistics."""
    async with SessionLocal() as session:
        # Base query
        query = select(func.count(Detection.id)).where(Detection.processed == True)
        
        # Apply camera filtering if specified
        if camera_ids:
            camera_id_list = [int(id.strip()) for id in camera_ids.split(',') if id.strip()]
            if camera_id_list:
                query = query.join(Camera).where(Camera.id.in_(camera_id_list))
        
        # Get stats for different time periods
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        # Today
        today_result = await session.execute(
            query.where(Detection.file_timestamp >= today)
        )
        today_count = today_result.scalar()
        
        # Week
        week_result = await session.execute(
            query.where(Detection.file_timestamp >= week_ago)
        )
        week_count = week_result.scalar()
        
        # Month
        month_result = await session.execute(
            query.where(Detection.file_timestamp >= month_ago)
        )
        month_count = month_result.scalar()
        
        # Total
        total_result = await session.execute(query)
        total_count = total_result.scalar()
        
        return {
            "stats": {
                "today": today_count,
                "week": week_count,
                "month": month_count,
                "total": total_count
            }
        }

@app.get("/api/video/convert/{detection_id}")
async def convert_video(detection_id: int):
    """Convert a video to browser-friendly format."""
    async with SessionLocal() as session:
        # Get detection record
        result = await session.execute(
            select(Detection).where(Detection.id == detection_id)
        )
        detection = result.scalar_one_or_none()
        
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        if detection.media_type != 'video':
            raise HTTPException(status_code=400, detail="Detection is not a video")
        
        # Get original video path
        original_path = Path(detection.filepath)
        if not original_path.exists():
            raise HTTPException(status_code=404, detail="Original video file not found")
        
        # Convert video
        result = await video_converter.convert_video(original_path)
        
        if result["success"]:
            return {
                "success": True,
                "detection_id": detection_id,
                "converted": not result.get("cached", False),
                "conversion_time": result.get("conversion_time"),
                "file_size": result["file_size"],
                "original_size": result.get("original_size"),
                "converted_url": f"/api/video/stream/{detection_id}"
            }
        else:
            raise HTTPException(status_code=500, detail=result["error"])

@app.get("/api/video/stream/{detection_id}")
async def stream_video(detection_id: int):
    """Stream converted video file"""
    # Get detection
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Detection).filter(Detection.id == detection_id)
        )
        detection = result.scalar_one_or_none()
        
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        original_path = Path(detection.filepath)
        converted_path = video_converter.get_converted_path(original_path)
        
        if not converted_path.exists():
            raise HTTPException(status_code=404, detail="Converted video not found")
        
        return FileResponse(converted_path)

@app.get("/api/video/thumbnail/{detection_id}")
async def get_video_thumbnail(detection_id: int, db: AsyncSession = Depends(get_db)):
    """Get video thumbnail with extensive logging"""
    start_time = time.time()
    logger.info(f"API video thumbnail request - detection_id: {detection_id}")
    
    try:
        # Get detection from database
        logger.debug(f"Fetching detection {detection_id} from database")
        result = await db.execute(select(Detection).where(Detection.id == detection_id))
        detection = result.scalar_one_or_none()
        
        if not detection:
            logger.warning(f"Detection {detection_id} not found for thumbnail")
            raise HTTPException(status_code=404, detail="Detection not found")
        
        # Check if thumbnail exists
        thumbnail_path = Path(detection.thumbnail_path) if detection.thumbnail_path else None
        
        if not thumbnail_path or not thumbnail_path.exists():
            logger.warning(f"Thumbnail file not found for detection {detection_id}: {thumbnail_path}")
            raise HTTPException(status_code=404, detail="Thumbnail not found")
        
        duration = time.time() - start_time
        logger.info(f"API video thumbnail response - detection_id: {detection_id}, file: {thumbnail_path} (duration: {duration:.3f}s)")
        
        return FileResponse(
            path=str(thumbnail_path),
            media_type="image/jpeg",
            headers={"Cache-Control": "max-age=3600"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"API video thumbnail error for detection {detection_id}: {e} (duration: {duration:.3f}s)")
        logger.error(f"API video thumbnail error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/thumbnails/{filename:path}")
async def serve_thumbnail(filename: str):
    """Serve video thumbnail files"""
    thumbnail_path = video_converter.thumbnail_dir / filename
    
    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    
    return FileResponse(thumbnail_path, media_type="image/jpeg")

@app.get("/api/video/info/{detection_id}")
async def get_video_info(detection_id: int):
    """Get information about a video and its conversion status."""
    async with SessionLocal() as session:
        # Get detection record
        result = await session.execute(
            select(Detection).where(Detection.id == detection_id)
        )
        detection = result.scalar_one_or_none()
        
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        if detection.media_type != 'video':
            raise HTTPException(status_code=400, detail="Detection is not a video")
        
        # Get original video path
        original_path = Path(detection.filepath)
        if not original_path.exists():
            raise HTTPException(status_code=404, detail="Original video file not found")
        
        # Check conversion status
        is_converted = video_converter.is_already_converted(original_path)
        original_info = video_converter.get_video_info(original_path)
        
        response = {
            "detection_id": detection_id,
            "filename": detection.filename,
            "original_path": str(original_path),
            "is_converted": is_converted,
            "original_info": original_info
        }
        
        if is_converted:
            converted_path = video_converter.get_converted_path(original_path)
            converted_info = video_converter.get_video_info(converted_path)
            response["converted_info"] = converted_info
            response["converted_url"] = f"/api/video/stream/{detection_id}"
        
        return response

# Markdown Documentation Endpoints
@app.get("/docs/project-readme", response_class=HTMLResponse)
async def serve_project_readme():
    """Serve the main project README.md with basic styling"""
    start_time = time.time()
    logger.info("Documentation request - project README")
    
    try:
        # Get the project root README.md
        readme_path = Path(__file__).parent.parent / "README.md"
        
        if not readme_path.exists():
            logger.warning("README.md not found")
            raise HTTPException(status_code=404, detail="README.md not found")
        
        # Read the markdown content
        async with aiofiles.open(readme_path, 'r', encoding='utf-8') as f:
            markdown_content = await f.read()
        
        # Render markdown to HTML with extensions (including TOC for anchor generation)
        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables', 'toc'])
        html_content = md.convert(markdown_content)
        
        # Create a simple HTML page
        html_page = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Foscam Detection System - README</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            background-color: #ffffff;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .container {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            padding: 40px;
            margin-bottom: 20px;
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}
        
        h1 {{ font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 10px; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 8px; }}
        h3 {{ font-size: 1.25em; }}
        
        pre {{
            background-color: #f6f8fa;
            border-radius: 6px;
            font-size: 85%;
            line-height: 1.45;
            overflow: auto;
            padding: 16px;
        }}
        
        code {{
            background-color: rgba(27,31,35,0.05);
            border-radius: 3px;
            font-size: 85%;
            margin: 0;
            padding: 0.2em 0.4em;
        }}
        
        pre code {{
            background-color: transparent;
            border: 0;
            display: inline;
            line-height: inherit;
            margin: 0;
            overflow: visible;
            padding: 0;
            word-wrap: normal;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }}
        
        th, td {{
            border: 1px solid #dfe2e5;
            padding: 6px 13px;
            text-align: left;
        }}
        
        th {{
            background-color: #f6f8fa;
            font-weight: 600;
        }}
        
        .back-link {{
            display: inline-block;
            margin-bottom: 20px;
            color: #0366d6;
            text-decoration: none;
            font-weight: 500;
        }}
        
        .back-link:hover {{
            text-decoration: underline;
        }}
        
        /* Mermaid diagram styling */
        .mermaid {{
            background-color: #f8f9fa;
            border: 1px solid #e1e4e8;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
        }}
        
        /* Enhanced code syntax highlighting */
        .codehilite {{
            background-color: #f6f8fa;
            border-radius: 6px;
            padding: 16px;
            margin: 16px 0;
        }}
        
        .codehilite pre {{
            margin: 0;
            background-color: transparent;
            padding: 0;
        }}
        
        /* Responsive design */
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            
            .container {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #0366d6; margin: 0;">📚 Foscam Detection System Documentation</h1>
            <p style="color: #586069; margin: 10px 0 0 0;">Comprehensive system documentation with architectural diagrams</p>
        </div>
        
        <a href="/" class="back-link">← Back to Dashboard</a>
        
        <div class="content">
            {html_content}
        </div>
    </div>
</body>
<script>
    // Initialize Mermaid with custom configuration
    mermaid.initialize({{
        startOnLoad: false,  // We'll manually trigger rendering
        theme: 'default',
        themeVariables: {{
            primaryColor: '#0366d6',
            primaryTextColor: '#24292e',
            primaryBorderColor: '#e1e4e8',
            lineColor: '#d1d5da',
            secondaryColor: '#f6f8fa',
            tertiaryColor: '#fafbfc'
        }}
    }});
    
    // Convert mermaid code blocks to mermaid divs and render
    document.addEventListener('DOMContentLoaded', function() {{
        // Find all code blocks with language-mermaid class
        const mermaidCodeBlocks = document.querySelectorAll('code.language-mermaid');
        
        mermaidCodeBlocks.forEach(function(codeBlock, index) {{
            // Get the mermaid code content
            const mermaidCode = codeBlock.textContent;
            
            // Create a new mermaid div
            const mermaidDiv = document.createElement('div');
            mermaidDiv.className = 'mermaid';
            mermaidDiv.id = 'mermaid-' + index;
            mermaidDiv.textContent = mermaidCode;
            
            // Replace the entire pre/code structure with the mermaid div
            const preElement = codeBlock.closest('pre');
            if (preElement) {{
                preElement.parentNode.replaceChild(mermaidDiv, preElement);
            }}
        }});
        
        // Now render all mermaid diagrams
        mermaid.run();
    }});
</script>
</html>
        """
        
        duration = time.time() - start_time
        logger.info(f"Documentation served successfully - project README (duration: {duration:.3f}s)")
        return HTMLResponse(content=html_page)
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Documentation error - project README: {e} (duration: {duration:.3f}s)")
        logger.error(f"Documentation error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error loading README: {str(e)}")

@app.get("/docs/{doc_path:path}", response_class=HTMLResponse)
async def serve_markdown_doc(doc_path: str):
    """Serve markdown documentation with basic styling"""
    start_time = time.time()
    logger.info(f"Documentation request - {doc_path}")
    
    try:
        # Security: Validate the path to prevent directory traversal
        if ".." in doc_path or doc_path.startswith("/"):
            logger.warning(f"Invalid documentation path attempted: {doc_path}")
            raise HTTPException(status_code=400, detail="Invalid path")
        
        # Construct the full path to the documentation file
        docs_dir = Path(__file__).parent.parent / "docs"
        file_path = docs_dir / doc_path
        
        # Ensure the file exists and is within the docs directory
        if not file_path.exists():
            logger.warning(f"Documentation file not found: {doc_path}")
            raise HTTPException(status_code=404, detail="Documentation file not found")
        
        # Verify the resolved path is still within docs directory (security)
        try:
            file_path.resolve().relative_to(docs_dir.resolve())
        except ValueError:
            logger.warning(f"Access denied to documentation path: {doc_path}")
            raise HTTPException(status_code=400, detail="Access denied")
        
        # Read and render the markdown
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            markdown_content = await f.read()
        
        # Simple markdown to HTML conversion
        md = markdown.Markdown(extensions=['fenced_code', 'tables'])
        html_content = md.convert(markdown_content)
        
        # Create a simple HTML page
        html_page = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doc_path} - Foscam Documentation</title>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10.9.0/dist/mermaid.min.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            background-color: #ffffff;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .container {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            padding: 40px;
            margin-bottom: 20px;
        }}
        
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}
        
        h1 {{ font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 10px; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 8px; }}
        h3 {{ font-size: 1.25em; }}
        
        pre {{
            background-color: #f6f8fa;
            border-radius: 6px;
            font-size: 85%;
            line-height: 1.45;
            overflow: auto;
            padding: 16px;
        }}
        
        code {{
            background-color: rgba(27,31,35,0.05);
            border-radius: 3px;
            font-size: 85%;
            margin: 0;
            padding: 0.2em 0.4em;
        }}
        
        pre code {{
            background-color: transparent;
            border: 0;
            display: inline;
            line-height: inherit;
            margin: 0;
            overflow: visible;
            padding: 0;
            word-wrap: normal;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }}
        
        th, td {{
            border: 1px solid #dfe2e5;
            padding: 6px 13px;
            text-align: left;
        }}
        
        th {{
            background-color: #f6f8fa;
            font-weight: 600;
        }}
        
        .back-link {{
            display: inline-block;
            margin-bottom: 20px;
            color: #0366d6;
            text-decoration: none;
            font-weight: 500;
        }}
        
        .back-link:hover {{
            text-decoration: underline;
        }}
        
        /* Mermaid diagram styling */
        .mermaid {{
            background-color: #f8f9fa;
            border: 1px solid #e1e4e8;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
        }}
        
        /* Enhanced code syntax highlighting */
        .codehilite {{
            background-color: #f6f8fa;
            border-radius: 6px;
            padding: 16px;
            margin: 16px 0;
        }}
        
        .codehilite pre {{
            margin: 0;
            background-color: transparent;
            padding: 0;
        }}
        
        /* Responsive design */
        @media (max-width: 768px) {{
            body {{
                padding: 10px;
            }}
            
            .container {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div style="text-align: center; margin-bottom: 20px;">
            <h1 style="color: #0366d6; margin: 0;">📚 Foscam Documentation</h1>
            <p style="color: #586069; margin: 10px 0 0 0;">{doc_path}</p>
        </div>
        
        <a href="/" class="back-link">← Back to Dashboard</a>
        
        <div class="content">
            {html_content}
        </div>
    </div>
</body>
<script>
    // Initialize Mermaid with custom configuration
    mermaid.initialize({{
        startOnLoad: false,  // We'll manually trigger rendering
        theme: 'default',
        themeVariables: {{
            primaryColor: '#0366d6',
            primaryTextColor: '#24292e',
            primaryBorderColor: '#e1e4e8',
            lineColor: '#d1d5da',
            secondaryColor: '#f6f8fa',
            tertiaryColor: '#fafbfc'
        }}
    }});
    
    // Convert mermaid code blocks to mermaid divs and render
    document.addEventListener('DOMContentLoaded', function() {{
        // Find all code blocks with language-mermaid class
        const mermaidCodeBlocks = document.querySelectorAll('code.language-mermaid');
        
        mermaidCodeBlocks.forEach(function(codeBlock, index) {{
            // Get the mermaid code content
            const mermaidCode = codeBlock.textContent;
            
            // Create a new mermaid div
            const mermaidDiv = document.createElement('div');
            mermaidDiv.className = 'mermaid';
            mermaidDiv.id = 'mermaid-' + index;
            mermaidDiv.textContent = mermaidCode;
            
            // Replace the entire pre/code structure with the mermaid div
            const preElement = codeBlock.closest('pre');
            if (preElement) {{
                preElement.parentNode.replaceChild(mermaidDiv, preElement);
            }}
        }});
        
        // Now render all mermaid diagrams
        mermaid.run();
    }});
</script>
</html>
        """
        
        duration = time.time() - start_time
        logger.info(f"Documentation served successfully - {doc_path} (duration: {duration:.3f}s)")
        return HTMLResponse(content=html_page)
        
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Documentation error - {doc_path}: {e} (duration: {duration:.3f}s)")
        logger.error(f"Documentation error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error loading documentation: {str(e)}")

# GPU Monitoring API Endpoints
@app.get("/api/gpu/current")
async def get_current_gpu_metrics():
    """Get current GPU metrics"""
    try:
        metrics = gpu_monitor.get_latest_metrics()
        if metrics:
            return {"success": True, "data": metrics}
        else:
            return {"success": False, "error": "No GPU metrics available"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/gpu/history")
async def get_gpu_history(minutes: int = Query(5, ge=1, le=60)):
    """Get GPU metrics history for the last N minutes"""
    try:
        history = gpu_monitor.get_metrics_history(minutes)
        return {"success": True, "data": history}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/gpu/stats")
async def get_gpu_stats():
    """Get GPU statistics"""
    start_time = time.time()
    logger.info("API GPU stats request")
    
    try:
        stats = gpu_monitor.get_stats()
        duration = time.time() - start_time
        logger.info(f"API GPU stats response (duration: {duration:.3f}s)")
        return JSONResponse(content=stats)
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"API GPU stats error: {e} (duration: {duration:.3f}s)")
        logger.error(f"API GPU stats error traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

# Main function for running with uvicorn
if __name__ == "__main__":
    import uvicorn
    
    # Set up uvicorn logging
    uvicorn_log_config = setup_uvicorn_logging("webui")
    
    logger.info("Starting Foscam Detection Dashboard Web UI")
    logger.info(f"Server will run on http://0.0.0.0:7999")
    
    try:
        uvicorn.run(
            "src.web_app:app",
            host="0.0.0.0",
            port=7999,
            log_config=uvicorn_log_config,
            reload=False,
            access_log=True
        )
    except Exception as e:
        logger.error(f"Failed to start uvicorn server: {e}")
        logger.error(f"Uvicorn startup error traceback: {traceback.format_exc()}")
        raise 