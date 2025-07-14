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

# Import our models
from models import Base, Detection, Camera, AlertType, initialize_alert_types
from config import DATABASE_URL, HOST, PORT, FOSCAM_DIR
from video_converter import video_converter
from gpu_monitor import gpu_monitor

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
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    start_date: str = Query(None),
    end_date: str = Query(None),
    camera_ids: str = Query(None)
):
    """Get detections with pagination and filtering."""
    async with SessionLocal() as session:
        # Build query
        query = select(Detection, Camera).join(Camera).where(Detection.processed == True)
        
        # Date filtering
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
                query = query.where(Detection.file_timestamp >= start_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format")
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
                query = query.where(Detection.file_timestamp <= end_dt)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format")
        
        # Camera filtering
        if camera_ids:
            camera_id_list = [int(id.strip()) for id in camera_ids.split(',') if id.strip()]
            if camera_id_list:
                query = query.where(Camera.id.in_(camera_id_list))
        
        # Get total count for pagination
        count_query = select(func.count(Detection.id)).select_from(query.subquery())
        total_result = await session.execute(count_query)
        total = total_result.scalar()
        
        # Apply pagination
        offset = (page - 1) * per_page
        query = query.order_by(desc(Detection.file_timestamp)).limit(per_page).offset(offset)
        
        result = await session.execute(query)
        detection_rows = result.all()
        
        # Format response
        detections = []
        for detection, camera in detection_rows:
            # Extract the relative path from the full filepath (remove 'foscam/' prefix)
            media_filename = None
            if detection.filepath:
                # Remove 'foscam/' prefix if present to get the relative path for /media/ mount
                filepath_str = str(detection.filepath)
                media_filename = filepath_str.replace('foscam/', '') if filepath_str.startswith('foscam/') else filepath_str
            
            detections.append({
                "id": detection.id,
                "timestamp": detection.file_timestamp.isoformat() if detection.file_timestamp else detection.timestamp.isoformat(),
                "camera_location": camera.location,
                "media_type": detection.media_type,
                "description": detection.description or "No description",
                "confidence": round(detection.confidence, 1) if detection.confidence else 0,
                "media_filename": media_filename
            })
        
        return {
            "detections": detections,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page
            }
        }

@app.get("/api/detections/heatmap")
async def get_detections_heatmap(
    days: int = 30,
    resolution: str = "day",
    camera_ids: str = None,
    per_camera: bool = False
):
    """Get detection counts aggregated by time for heatmap visualization."""
    async with SessionLocal() as session:
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
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
        
        # Aggregate by day
        daily_counts = {}
        camera_breakdown = {}
        
        for timestamp, camera_id, location in detection_data:
            date_key = timestamp.date().isoformat()
            
            # Overall count
            daily_counts[date_key] = daily_counts.get(date_key, 0) + 1
            
            # Per-camera breakdown if requested
            if per_camera:
                if date_key not in camera_breakdown:
                    camera_breakdown[date_key] = {}
                camera_breakdown[date_key][location] = camera_breakdown[date_key].get(location, 0) + 1
        
        # Convert to list format
        heatmap_data = []
        for date_str, count in sorted(daily_counts.items()):
            item = {
                "timestamp": date_str,
                "count": count
            }
            if per_camera and date_str in camera_breakdown:
                item["camera_breakdown"] = camera_breakdown[date_str]
            heatmap_data.append(item)
        
        return {"heatmap_data": heatmap_data}

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
async def get_cameras():
    """Get all cameras."""
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
                "full_name": camera.full_name,
                "is_active": camera.is_active
            })
        
        return {"cameras": camera_data}

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
async def get_video_thumbnail(detection_id: int):
    """Get or generate video thumbnail"""
    # Get detection
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Detection).filter(Detection.id == detection_id)
        )
        detection = result.scalar_one_or_none()
        
        if not detection:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        if detection.media_type != 'video':
            raise HTTPException(status_code=400, detail="Detection is not a video")
        
        original_path = Path(detection.filepath)
        thumbnail_path = video_converter.get_thumbnail_path(original_path)
        
        # Generate thumbnail if it doesn't exist
        if not thumbnail_path.exists():
            result = await video_converter.generate_thumbnail(original_path)
            if not result['success']:
                raise HTTPException(status_code=500, detail=f"Thumbnail generation failed: {result['error']}")
        
        return FileResponse(thumbnail_path, media_type="image/jpeg")

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
    """Serve the main project README.md with enhanced styling"""
    try:
        # Get the project root README.md
        readme_path = Path(__file__).parent.parent / "README.md"
        
        if not readme_path.exists():
            raise HTTPException(status_code=404, detail="README.md not found")
        
        # Read and render the markdown
        async with aiofiles.open(readme_path, 'r', encoding='utf-8') as f:
            markdown_content = await f.read()
        
        # Render markdown to HTML with extensions (added 'toc' back for anchor generation)
        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables', 'toc'])
        html_content = md.convert(markdown_content)
        
        # Create a proper HTML page with styling
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
        
        .content {{
            margin-top: 20px;
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
        
        <a href="javascript:window.close()" class="back-link">← Close Window</a>
        
        <div class="content">
            {html_content}
        </div>
    </div>
</body>
<script>
    // Initialize Mermaid with custom configuration
    mermaid.initialize({{
        startOnLoad: true,
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
</script>
</html>
        """
        
        return HTMLResponse(content=html_page)
        
    except Exception as e:
        # logger.error(f"Error serving project README: {e}") # Original code had this line commented out
        raise HTTPException(status_code=500, detail=f"Error loading README: {str(e)}")

@app.get("/docs/{doc_path:path}", response_class=HTMLResponse)
async def serve_markdown_doc(doc_path: str):
    """Serve markdown documentation with enhanced styling and mermaid support"""
    try:
        # Security: Validate the path to prevent directory traversal
        if ".." in doc_path or doc_path.startswith("/"):
            raise HTTPException(status_code=400, detail="Invalid path")
        
        # Construct the full path to the documentation file
        docs_dir = Path(__file__).parent.parent / "docs"
        file_path = docs_dir / doc_path
        
        # Ensure the file exists and is within the docs directory
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Documentation file not found")
        
        # Verify the resolved path is still within docs directory (security)
        try:
            file_path.resolve().relative_to(docs_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Access denied")
        
        # Read and render the markdown
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            markdown_content = await f.read()
        
        # Render markdown to HTML with extensions (added 'toc' back for anchor generation)
        md = markdown.Markdown(extensions=['codehilite', 'fenced_code', 'tables', 'toc'])
        html_content = md.convert(markdown_content)
        
        # Create a proper HTML page with styling
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
        
        .content {{
            margin-top: 20px;
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
        startOnLoad: true,
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
</script>
</html>
        """
        
        return HTMLResponse(content=html_page)
        
    except HTTPException:
        raise
    except Exception as e:
        # logger.error(f"Error serving markdown documentation {doc_path}: {e}") # Original code had this line commented out
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
    """Get GPU summary statistics"""
    try:
        stats = gpu_monitor.get_summary_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=HOST, port=PORT) 