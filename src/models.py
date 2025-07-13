from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, Index, select
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import json

Base = declarative_base()

class Camera(Base):
    """Camera information table - normalized camera data"""
    __tablename__ = "cameras"
    
    id = Column(Integer, primary_key=True, index=True)
    location = Column(String(50), nullable=False, index=True)  # ami_frontyard_left, kitchen, etc.
    device_name = Column(String(100), nullable=False, index=True)  # FoscamCamera_00626EFE8B21, etc.
    device_type = Column(String(20), nullable=False, index=True)  # FoscamCamera, R2, R2C
    
    # Full camera identifier for display
    full_name = Column(String(150), nullable=False, index=True)  # location_device_name
    
    # Camera metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow, index=True)
    is_active = Column(Boolean, default=True, index=True)
    
    # Statistics (can be updated periodically)
    total_detections = Column(Integer, default=0)
    total_alerts = Column(Integer, default=0)
    
    # Relationship to detections
    detections = relationship("Detection", back_populates="camera")
    
    # Composite unique constraint
    __table_args__ = (
        Index('ix_camera_location_device', 'location', 'device_name'),
    )

class AlertType(Base):
    """Alert types lookup table"""
    __tablename__ = "alert_types"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(200))
    priority = Column(Integer, default=1, index=True)  # 1=low, 2=medium, 3=high, 4=critical
    
    # Relationship to detection alerts
    detection_alerts = relationship("DetectionAlert", back_populates="alert_type")

class Detection(Base):
    """Optimized detection table for foscam data"""
    __tablename__ = "detections"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # File information
    filename = Column(String(100), nullable=False, index=True)
    filepath = Column(String(500), nullable=False, unique=True, index=True)
    media_type = Column(String(10), nullable=False, index=True)  # 'image' or 'video'
    
    # Foscam-specific fields
    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=False, index=True)
    motion_detection_type = Column(String(10), index=True)  # 'MD', 'HMD', etc.
    
    # Processing status
    processed = Column(Boolean, default=True, index=True)
    processing_time = Column(Float)
    
    # AI analysis results
    description = Column(Text)
    confidence = Column(Float, index=True)  # For filtering by confidence
    
    # Structured analysis results (JSON)
    analysis_structured = Column(Text)  # JSON of detailed analysis breakdown
    
    # Timestamps - critical for time-based queries
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)  # Processing time
    file_timestamp = Column(DateTime, nullable=False, index=True)  # From filename
    
    # Media properties
    width = Column(Integer)
    height = Column(Integer)
    frame_count = Column(Integer, nullable=True)  # For videos
    duration = Column(Float, nullable=True)  # For videos in seconds
    
    # Quick alert flags for fast filtering (denormalized for performance)
    has_person = Column(Boolean, default=False, index=True)
    has_vehicle = Column(Boolean, default=False, index=True)
    has_package = Column(Boolean, default=False, index=True)
    has_unusual_activity = Column(Boolean, default=False, index=True)
    is_night_time = Column(Boolean, default=False, index=True)
    alert_count = Column(Integer, default=0, index=True)
    
    # Relationships
    camera = relationship("Camera", back_populates="detections")
    alerts = relationship("DetectionAlert", back_populates="detection")
    
    # Complex indexes for common query patterns
    __table_args__ = (
        # Time-based queries
        Index('ix_detection_file_timestamp_camera', 'file_timestamp', 'camera_id'),
        Index('ix_detection_timestamp_media_type', 'timestamp', 'media_type'),
        
        # Alert filtering
        Index('ix_detection_alerts', 'has_person', 'has_vehicle', 'has_package'),
        Index('ix_detection_alerts_time', 'alert_count', 'file_timestamp'),
        
        # Camera-specific queries
        Index('ix_detection_camera_time', 'camera_id', 'file_timestamp'),
        Index('ix_detection_camera_media', 'camera_id', 'media_type', 'processed'),
        
        # Confidence-based filtering
        Index('ix_detection_confidence_time', 'confidence', 'file_timestamp'),
    )
    
    def get_structured_analysis(self):
        """Parse structured analysis JSON"""
        if self.analysis_structured:
            try:
                return json.loads(self.analysis_structured)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_structured_analysis(self, analysis_dict):
        """Set structured analysis as JSON"""
        if analysis_dict:
            self.analysis_structured = json.dumps(analysis_dict)

    # Legacy compatibility properties
    @property
    def camera_name(self):
        """Legacy compatibility - get camera name from relationship"""
        return self.camera.full_name if self.camera else "unknown"

class DetectionAlert(Base):
    """Junction table for detection alerts - many-to-many relationship"""
    __tablename__ = "detection_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    detection_id = Column(Integer, ForeignKey('detections.id'), nullable=False, index=True)
    alert_type_id = Column(Integer, ForeignKey('alert_types.id'), nullable=False, index=True)
    
    # Alert metadata
    confidence = Column(Float)  # Confidence for this specific alert
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    detection = relationship("Detection", back_populates="alerts")
    alert_type = relationship("AlertType", back_populates="detection_alerts")
    
    # Composite indexes
    __table_args__ = (
        Index('ix_detection_alert_detection_type', 'detection_id', 'alert_type_id'),
        Index('ix_detection_alert_time_type', 'detected_at', 'alert_type_id'),
    )

class ProcessingStats(Base):
    """Processing statistics and performance metrics"""
    __tablename__ = "processing_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Time period
    date = Column(DateTime, nullable=False, index=True)
    hour = Column(Integer, index=True)  # Hour of day (0-23)
    
    # Camera information
    camera_id = Column(Integer, ForeignKey('cameras.id'), nullable=False, index=True)
    
    # Processing metrics
    files_processed = Column(Integer, default=0)
    images_processed = Column(Integer, default=0)
    videos_processed = Column(Integer, default=0)
    
    # Performance metrics
    avg_processing_time = Column(Float)
    total_processing_time = Column(Float)
    avg_confidence = Column(Float)
    
    # Alert metrics
    total_alerts = Column(Integer, default=0)
    person_alerts = Column(Integer, default=0)
    vehicle_alerts = Column(Integer, default=0)
    package_alerts = Column(Integer, default=0)
    
    # Relationships
    camera = relationship("Camera")
    
    # Indexes for statistics queries
    __table_args__ = (
        Index('ix_stats_date_camera', 'date', 'camera_id'),
        Index('ix_stats_date_hour', 'date', 'hour'),
    )

# Database utility functions
async def get_or_create_camera(session, location: str, device_name: str):
    """Get or create camera record"""
    # Determine device type
    device_type = "Unknown"
    if device_name.startswith("FoscamCamera_"):
        device_type = "FoscamCamera"
    elif device_name.startswith("R2C_"):
        device_type = "R2C"
    elif device_name.startswith("R2_"):
        device_type = "R2"
    
    full_name = f"{location}_{device_name}"
    
    # Try to find existing camera
    camera = await session.execute(select(Camera).filter(
        Camera.location == location,
        Camera.device_name == device_name
    ))
    camera = camera.scalar()
    
    if not camera:
        camera = Camera(
            location=location,
            device_name=device_name,
            device_type=device_type,
            full_name=full_name
        )
        session.add(camera)
        await session.flush()  # Get the ID
    else:
        # Update last seen
        camera.last_seen = datetime.utcnow()
    
    return camera

async def initialize_alert_types(session):
    """Initialize standard alert types"""
    standard_alerts = [
        ("PERSON_DETECTED", "Person detected in scene", 2),
        ("VEHICLE_DETECTED", "Vehicle detected in scene", 2),
        ("PACKAGE_DETECTED", "Package or delivery detected", 3),
        ("UNUSUAL_ACTIVITY", "Unusual or suspicious activity", 4),
        ("NIGHT_TIME", "Activity during night hours", 1),
        ("MULTIPLE_PEOPLE", "Multiple people detected", 2),
        ("UNKNOWN_PERSON", "Unknown person detected", 3),
        ("DELIVERY_EVENT", "Delivery event detected", 2),
    ]
    
    for name, description, priority in standard_alerts:
        existing = await session.execute(select(AlertType).filter(AlertType.name == name))
        existing = existing.scalar()
        if not existing:
            alert_type = AlertType(
                name=name,
                description=description,
                priority=priority
            )
            session.add(alert_type)

def get_alert_flags_from_alerts(alerts: list) -> dict:
    """Extract alert flags from alert list"""
    alert_names = [alert.lower() for alert in alerts] if alerts else []
    
    return {
        'has_person': 'person_detected' in alert_names,
        'has_vehicle': 'vehicle_detected' in alert_names,
        'has_package': 'package_detected' in alert_names,
        'has_unusual_activity': 'unusual_activity' in alert_names,
        'is_night_time': 'night_time' in alert_names,
        'alert_count': len(alerts) if alerts else 0
    }

def extract_motion_detection_type(filename: str) -> str:
    """Extract motion detection type from filename"""
    if filename.startswith("MDAlarm_"):
        return "MD"
    elif filename.startswith("HMDAlarm_"):
        return "HMD"
    elif filename.startswith("MDalarm_"):
        return "MD"
    return "Unknown" 