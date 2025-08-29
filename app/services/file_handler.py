import os
import uuid
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
# Lazy import for moviepy to avoid startup issues
# from moviepy.editor import VideoFileClip
from PIL import Image
import mimetypes
from app.core.validators import file_validator
from app.core.logger import logger
from app.core.exceptions import FileValidationError, create_http_exception

class FileHandler:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.upload_dir = Path(f"app/static/uploads/{session_id}")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def save_video(self, file: UploadFile) -> dict:
        # Advanced validation
        is_valid, error_msg = await file_validator.validate_video_file(file)
        if not is_valid:
            logger.warning(f"Video validation failed: {error_msg}")
            raise create_http_exception(400, f"Video validation failed: {error_msg}")
        
        file_ext = Path(file.filename).suffix
        
        # Sanitize filename
        safe_filename = file_validator.sanitize_filename(file.filename)
        filename = f"video_{uuid.uuid4()}_{safe_filename}"
        file_path = self.upload_dir / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get video info
        try:
            # Lazy import moviepy when needed
            try:
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(str(file_path))
            except ImportError:
                logger.warning("moviepy not available, video processing disabled")
                raise HTTPException(status_code=503, detail="Video processing temporarily unavailable")
            video_info = {
                "url": f"/static/uploads/{self.session_id}/{filename}",
                "filename": filename,
                "width": clip.w,
                "height": clip.h,
                "duration": clip.duration,
                "format": file_ext[1:].upper(),
                "size": file_path.stat().st_size
            }
            clip.close()
            return video_info
        except Exception as e:
            file_path.unlink()  # Remove file if processing failed
            raise HTTPException(status_code=400, detail=f"Error processing video: {str(e)}")
    
    async def save_logo(self, file: UploadFile) -> dict:
        # Advanced validation
        is_valid, error_msg = await file_validator.validate_image_file(file)
        if not is_valid:
            logger.warning(f"Logo validation failed: {error_msg}")
            raise create_http_exception(400, f"Logo validation failed: {error_msg}")
        
        file_ext = Path(file.filename).suffix
        
        filename = f"logo_{uuid.uuid4()}{file_ext}"
        file_path = self.upload_dir / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get image info
        try:
            with Image.open(file_path) as img:
                logo_info = {
                    "url": f"/static/uploads/{self.session_id}/{filename}",
                    "filename": filename,
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "size": file_path.stat().st_size
                }
            return logo_info
        except Exception as e:
            file_path.unlink()  # Remove file if processing failed
            raise HTTPException(status_code=400, detail=f"Error processing logo: {str(e)}")
    
    async def save_cta(self, file: UploadFile) -> dict:
        mime_type = file.content_type
        
        if mime_type.startswith("video/"):
            return await self._save_cta_video(file)
        elif mime_type.startswith("image/"):
            return await self._save_cta_image(file)
        else:
            raise HTTPException(status_code=400, detail="File must be a video or image")
    
    async def _save_cta_video(self, file: UploadFile) -> dict:
        file_ext = Path(file.filename).suffix
        if file_ext.lower() not in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            raise HTTPException(status_code=400, detail="Unsupported video format")
        
        filename = f"cta_{uuid.uuid4()}{file_ext}"
        file_path = self.upload_dir / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get video info
        try:
            # Lazy import moviepy when needed
            try:
                from moviepy.editor import VideoFileClip
                clip = VideoFileClip(str(file_path))
            except ImportError:
                logger.warning("moviepy not available, video processing disabled")
                raise HTTPException(status_code=503, detail="Video processing temporarily unavailable")
            cta_info = {
                "url": f"/static/uploads/{self.session_id}/{filename}",
                "filename": filename,
                "type": "video",
                "width": clip.w,
                "height": clip.h,
                "duration": clip.duration,
                "format": file_ext[1:].upper(),
                "size": file_path.stat().st_size
            }
            clip.close()
            return cta_info
        except Exception as e:
            file_path.unlink()  # Remove file if processing failed
            raise HTTPException(status_code=400, detail=f"Error processing CTA video: {str(e)}")
    
    async def _save_cta_image(self, file: UploadFile) -> dict:
        file_ext = Path(file.filename).suffix
        if file_ext.lower() not in ['.png', '.jpg', '.jpeg', '.gif', '.bmp']:
            raise HTTPException(status_code=400, detail="Unsupported image format")
        
        filename = f"cta_{uuid.uuid4()}{file_ext}"
        file_path = self.upload_dir / filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get image info
        try:
            with Image.open(file_path) as img:
                cta_info = {
                    "url": f"/static/uploads/{self.session_id}/{filename}",
                    "filename": filename,
                    "type": "image",
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "size": file_path.stat().st_size
                }
            return cta_info
        except Exception as e:
            file_path.unlink()  # Remove file if processing failed
            raise HTTPException(status_code=400, detail=f"Error processing CTA image: {str(e)}")
    
    def get_upload_path(self, filename: str) -> Path:
        return self.upload_dir / filename
    
    def cleanup_old_files(self, max_age_hours: int = 24):
        """Clean up files older than max_age_hours"""
        import time
        current_time = time.time()
        
        for file_path in self.upload_dir.iterdir():
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_hours * 3600:
                    file_path.unlink()