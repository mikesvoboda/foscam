#!/usr/bin/env python3
"""
Backfill Thumbnail Paths for Existing Video Detections
"""
import asyncio
import sys
from pathlib import Path

sys.path.append('.')

from src.video_converter import VideoConverter
from src.models import Base, Detection
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from src.config import DATABASE_URL

async def backfill_thumbnails():
    """Backfill thumbnail paths for existing video detections."""
    print("🎬 Backfilling thumbnail paths for existing video detections")
    print("=" * 60)
    
    # Initialize video converter
    converter = VideoConverter()
    
    # Database setup
    engine = create_async_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with SessionLocal() as session:
        # Get all video detections without thumbnail paths
        result = await session.execute(
            select(Detection).where(
                Detection.media_type == 'video',
                Detection.thumbnail_path.is_(None)
            )
        )
        video_detections = result.scalars().all()
        
        print(f"Found {len(video_detections)} video detections without thumbnails")
        
        updated_count = 0
        
        for detection in video_detections:
            video_path = Path(detection.filepath)
            
            if video_path.exists():
                print(f"🎬 Processing: {video_path.name}")
                
                try:
                    # Generate thumbnail
                    thumbnail_result = await converter.generate_thumbnail(video_path)
                    
                    if thumbnail_result["success"]:
                        # Update detection with thumbnail path
                        detection.thumbnail_path = str(thumbnail_result["thumbnail_path"])
                        updated_count += 1
                        print(f"✅ Thumbnail generated: {thumbnail_result['thumbnail_path']}")
                    else:
                        print(f"❌ Failed to generate thumbnail: {thumbnail_result.get('error', 'Unknown error')}")
                        
                except Exception as e:
                    print(f"❌ Error processing {video_path.name}: {e}")
            else:
                print(f"❌ Video file not found: {video_path}")
        
        # Commit all changes
        await session.commit()
        
        print(f"\n📊 Backfill Complete!")
        print(f"   Total video detections: {len(video_detections)}")
        print(f"   Successfully updated: {updated_count}")
        print(f"   Success rate: {updated_count/len(video_detections)*100:.1f}%")

if __name__ == "__main__":
    asyncio.run(backfill_thumbnails()) 