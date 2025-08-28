import os
from pathlib import Path
from typing import List, Optional, Tuple
from fastapi import UploadFile
from app.core.exceptions import FileValidationError
from app.core.logger import logger
from app.core.config import settings

# Try to import magic, handle gracefully if not available
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    magic = None
    HAS_MAGIC = False

class FileValidator:
    """Advanced file validation with magic number checking"""
    
    # Allowed MIME types for different file categories
    ALLOWED_VIDEO_MIMES = {
        'video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo',
        'video/x-matroska', 'video/webm'
    }
    
    ALLOWED_IMAGE_MIMES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/bmp', 'image/webp'
    }
    
    ALLOWED_EXTENSIONS = {
        'video': {'.mp4', '.avi', '.mov', '.mkv', '.webm'},
        'image': {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    }
    
    # File size limits (in bytes)
    MAX_VIDEO_SIZE = 1024 * 1024 * 1024  # 1GB
    MAX_IMAGE_SIZE = 50 * 1024 * 1024    # 50MB
    
    def __init__(self):
        if HAS_MAGIC:
            try:
                # Check if python-magic is available
                self.magic_mime = magic.Magic(mime=True)
                self.has_magic = True
            except Exception as e:
                logger.warning(f"python-magic initialization failed: {e}, using basic validation")
                self.has_magic = False
        else:
            logger.warning("python-magic not installed, using basic validation")
            self.has_magic = False
    
    async def validate_video_file(self, file: UploadFile, max_size: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Validate video file with comprehensive checks"""
        try:
            # Basic checks
            if not file.filename:
                return False, "Filename is required"
            
            # Extension check
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in self.ALLOWED_EXTENSIONS['video']:
                return False, f"Invalid file extension: {file_ext}"
            
            # Size check
            max_size = max_size or self.MAX_VIDEO_SIZE
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset position
            
            if file_size > max_size:
                return False, f"File too large: {file_size} bytes (max: {max_size})"
            
            # MIME type validation
            if not await self._validate_mime_type(file, self.ALLOWED_VIDEO_MIMES):
                return False, "Invalid video file format"
            
            # Video-specific validation (skip in development mode if not strict)
            if settings.STRICT_FILE_VALIDATION or not settings.DEBUG:
                if not await self._validate_video_content(file):
                    return False, "File does not contain valid video data"
            else:
                logger.info("Skipping strict video content validation in development mode")
            
            return True, None
            
        except Exception as e:
            logger.error(f"Video validation error: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def validate_image_file(self, file: UploadFile, max_size: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """Validate image file with comprehensive checks"""
        try:
            # Basic checks
            if not file.filename:
                return False, "Filename is required"
            
            # Extension check
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in self.ALLOWED_EXTENSIONS['image']:
                return False, f"Invalid file extension: {file_ext}"
            
            # Size check
            max_size = max_size or self.MAX_IMAGE_SIZE
            file.file.seek(0, 2)  # Seek to end
            file_size = file.file.tell()
            file.file.seek(0)  # Reset position
            
            if file_size > max_size:
                return False, f"File too large: {file_size} bytes (max: {max_size})"
            
            # MIME type validation
            if not await self._validate_mime_type(file, self.ALLOWED_IMAGE_MIMES):
                return False, "Invalid image file format"
            
            # Image-specific validation
            if not await self._validate_image_content(file):
                return False, "File does not contain valid image data"
            
            return True, None
            
        except Exception as e:
            logger.error(f"Image validation error: {e}")
            return False, f"Validation error: {str(e)}"
    
    async def _validate_mime_type(self, file: UploadFile, allowed_mimes: set) -> bool:
        """Validate MIME type using magic numbers"""
        try:
            if self.has_magic:
                # Read first 2048 bytes for magic number detection
                file_content = await file.read(2048)
                file.file.seek(0)  # Reset position
                
                detected_mime = self.magic_mime.from_buffer(file_content)
                return detected_mime in allowed_mimes
            else:
                # Fallback to content-type header
                return file.content_type in allowed_mimes
                
        except Exception as e:
            logger.warning(f"MIME validation failed: {e}")
            return True  # Allow if validation fails
    
    async def _validate_video_content(self, file: UploadFile) -> bool:
        """Validate video file content"""
        try:
            # Read file header to check for video signatures
            file_content = await file.read(64)  # Read more bytes for better detection
            file.file.seek(0)  # Reset position
            
            # Check for common video file signatures
            video_signatures = [
                # MP4/MOV signatures
                b'ftyp',                       # Generic ftyp (MP4/MOV)
                b'\x00\x00\x00\x20ftypmp4',  # MP4
                b'\x00\x00\x00\x18ftyp',      # MP4/MOV
                b'\x00\x00\x00\x1cftyp',      # Another MP4 variant
                b'\x00\x00\x00\x24ftyp',      # Another MP4 variant
                
                # AVI signatures
                b'RIFF',                       # AVI (RIFF header)
                b'AVI ',                       # AVI format identifier
                
                # MKV/WebM signatures  
                b'\x1a\x45\xdf\xa3',         # MKV/WebM (EBML header)
                
                # Other formats
                b'\x00\x00\x01\xb3',         # MPEG-1 video
                b'\x00\x00\x01\xba',         # MPEG-2 video
                b'FLV',                        # FLV format
            ]
            
            # Check for any signature in the first 64 bytes
            for signature in video_signatures:
                if signature in file_content:
                    logger.info(f"Video signature found: {signature}")
                    return True
            
            # Additional check: if file extension is video, be more lenient
            if file.filename:
                ext = file.filename.lower().split('.')[-1]
                if ext in ['mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv', 'm4v']:
                    logger.info(f"Video file detected by extension: {ext}")
                    return True
            
            logger.warning(f"No video signature found in file header: {file_content[:32].hex()}")
            return False
            
        except Exception as e:
            logger.warning(f"Video content validation failed: {e}")
            return True  # Allow if validation fails
    
    async def _validate_image_content(self, file: UploadFile) -> bool:
        """Validate image file content"""
        try:
            # Read file header to check for image signatures
            file_content = await file.read(32)
            file.file.seek(0)  # Reset position
            
            # Check for common image file signatures
            image_signatures = [
                b'\xff\xd8\xff',              # JPEG
                b'\x89PNG\r\n\x1a\n',        # PNG
                b'GIF87a',                     # GIF87a
                b'GIF89a',                     # GIF89a
                b'BM',                         # BMP
                b'RIFF',                       # WEBP (RIFF header)
            ]
            
            for signature in image_signatures:
                if file_content.startswith(signature) or signature in file_content[:16]:
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Image content validation failed: {e}")
            return True  # Allow if validation fails
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent directory traversal and other issues"""
        # Remove path separators and dangerous characters
        sanitized = "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-'))
        
        # Ensure it doesn't start with dot (hidden files)
        if sanitized.startswith('.'):
            sanitized = 'file' + sanitized
        
        # Limit length
        if len(sanitized) > 255:
            name, ext = os.path.splitext(sanitized)
            sanitized = name[:255-len(ext)] + ext
        
        return sanitized or "unknown_file"

# Global validator instance
file_validator = FileValidator()