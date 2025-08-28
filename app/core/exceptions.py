from fastapi import HTTPException
from typing import Any, Dict, Optional

class AIVideoMakerException(Exception):
    """Base exception for AIVideoMaker application"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class VideoProcessingError(AIVideoMakerException):
    """Raised when video processing fails"""
    pass

class FileValidationError(AIVideoMakerException):
    """Raised when file validation fails"""
    pass

class YouTubeAPIError(AIVideoMakerException):
    """Raised when YouTube API operations fail"""
    pass

class OpenAIAPIError(AIVideoMakerException):
    """Raised when OpenAI API operations fail"""
    pass

class SessionError(AIVideoMakerException):
    """Raised when session operations fail"""
    pass

def create_http_exception(
    status_code: int,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> HTTPException:
    """Create a standardized HTTP exception"""
    detail = {"message": message}
    if details:
        detail.update(details)
    return HTTPException(status_code=status_code, detail=detail)