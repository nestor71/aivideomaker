from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from sqlalchemy.orm import Session
import json
import os
import uuid
import shutil
import requests
import zipfile
import io
from pathlib import Path
from urllib.parse import urlparse
from pydantic import BaseModel
from datetime import datetime
from app.core.config import settings
from app.core.i18n import i18n
from app.models.settings import UserSettings
from app.services.file_handler import FileHandler
# Temporarily disabled for startup issues
# from app.services.video_processor import VideoProcessor
from app.services.youtube_service import YouTubeService
from app.database.base import get_session
from app.services.free_ai_service import free_ai_service

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

class VideoDownloadRequest(BaseModel):
    url: str

@router.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    return templates.TemplateResponse("files.html", {"request": request})

@router.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})



@router.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {"request": request})

@router.get("/privacy", response_class=HTMLResponse)
async def privacy_page(request: Request):
    return templates.TemplateResponse("privacy.html", {"request": request})

@router.get("/terms-it", response_class=HTMLResponse)
async def terms_page_it(request: Request):
    return templates.TemplateResponse("terms_it.html", {"request": request})

@router.get("/privacy-it", response_class=HTMLResponse)
async def privacy_page_it(request: Request):
    return templates.TemplateResponse("privacy_it.html", {"request": request})

@router.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "aivideomaker"
    }

@router.get("/api/translations/{lang}")
async def get_translations(lang: str):
    if lang not in ["en", "it"]:
        raise HTTPException(status_code=404, detail="Language not found")
    
    translations_file = Path(f"app/locales/{lang}/translations.json")
    if not translations_file.exists():
        raise HTTPException(status_code=404, detail="Translation file not found")
    
    with open(translations_file, 'r', encoding='utf-8') as f:
        translations = json.load(f)
    
    return translations

@router.get("/api/settings")
async def get_settings(request: Request):
    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    settings_file = Path(f"app/static/uploads/settings_{session_id}.json")
    
    if settings_file.exists():
        with open(settings_file, 'r') as f:
            return json.load(f)
    else:
        return UserSettings().dict()

@router.post("/api/settings")
async def save_settings(settings: UserSettings, request: Request):
    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    settings_file = Path(f"app/static/uploads/settings_{session_id}.json")
    
    # Ensure uploads directory exists
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(settings_file, 'w') as f:
        json.dump(settings.dict(), f)
    
    response = JSONResponse({"status": "success"})
    response.set_cookie("session_id", session_id)
    return response

@router.post("/api/upload/video")
async def upload_video(request: Request, file: UploadFile = File(...)):
    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    file_handler = FileHandler(session_id)
    
    try:
        video_info = await file_handler.save_video(file)
        response = JSONResponse(video_info)
        response.set_cookie("session_id", session_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/upload/logo")
async def upload_logo(request: Request, file: UploadFile = File(...)):
    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    file_handler = FileHandler(session_id)
    
    try:
        logo_info = await file_handler.save_logo(file)
        response = JSONResponse(logo_info)
        response.set_cookie("session_id", session_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/upload/cta")
async def upload_cta(request: Request, file: UploadFile = File(...)):
    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    file_handler = FileHandler(session_id)
    
    try:
        cta_info = await file_handler.save_cta(file)
        response = JSONResponse(cta_info)
        response.set_cookie("session_id", session_id)
        return response
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/youtube/auth")
async def youtube_auth():
    youtube_service = YouTubeService()
    try:
        auth_url = await youtube_service.get_auth_url()
        return {"auth_url": auth_url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/youtube/callback")
async def youtube_callback(request: Request, code: str):
    youtube_service = YouTubeService()
    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    
    try:
        channel_info = await youtube_service.handle_callback(code, session_id)
        
        # Update user settings
        settings_file = Path(f"app/static/uploads/settings_{session_id}.json")
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                user_settings = json.load(f)
        else:
            user_settings = UserSettings().dict()
        
        user_settings["youtube_settings"]["connected"] = True
        user_settings["youtube_settings"]["channel_id"] = channel_info["channel_id"]
        user_settings["youtube_settings"]["channel_name"] = channel_info["channel_name"]
        
        with open(settings_file, 'w') as f:
            json.dump(user_settings, f)
        
        return templates.TemplateResponse("youtube_success.html", {
            "request": request,
            "channel_name": channel_info["channel_name"]
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/youtube/disconnect")
async def youtube_disconnect(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id:
        youtube_service = YouTubeService()
        await youtube_service.disconnect(session_id)
    
    return {"status": "success"}


@router.get("/api/setup-admin-role")
async def setup_admin_role_get(db: Session = Depends(get_session)):
    """GET version for easier browser access"""
    return await setup_admin_role_logic(db)


@router.post("/api/setup-admin-role") 
async def setup_admin_role_post(db: Session = Depends(get_session)):
    """POST version for API calls"""
    return await setup_admin_role_logic(db)


async def setup_admin_role_logic(db: Session):
    """Logic for setting up admin roles"""
    from app.core.config import settings
    from app.database.models import UserRole, User
    
    try:
        admin_emails = settings.ADMIN_EMAIL_ADDRESSES
        
        if not admin_emails:
            return {"error": "No admin emails configured", "admin_emails": []}
        
        # Find users with admin emails
        admin_users = db.query(User).filter(User.email.in_(admin_emails)).all()
        
        if not admin_users:
            return {
                "error": "No users found with admin emails", 
                "admin_emails": admin_emails,
                "suggestion": "Make sure you're registered with one of these emails"
            }
        
        updated_count = 0
        updated_users = []
        all_users = []
        
        for user in admin_users:
            user_info = {"email": user.email, "id": user.id, "current_role": user.role.value}
            all_users.append(user_info)
            
            if user.role != UserRole.ADMIN:
                user.role = UserRole.ADMIN
                updated_count += 1
                updated_users.append(user_info)
        
        if updated_count > 0:
            db.commit()
        
        return {
            "success": True,
            "message": f"Updated {updated_count} user(s) to admin role",
            "updated_users": updated_users,
            "all_admin_users": all_users,
            "admin_emails": admin_emails
        }
        
    except Exception as e:
        db.rollback()
        return {"error": str(e), "success": False}

@router.post("/api/process")
async def process_video(
    settings: UserSettings, 
    request: Request,
    db: Session = Depends(get_session)
):
    from app.auth.dependencies import get_current_user_or_anonymous
    from app.middleware.tier_enforcement import TierEnforcement
    
    # Get current user (if any)
    current_user = await get_current_user_or_anonymous(request, db=db)
    
    # Check processing permissions (requires authentication)
    try:
        permissions = await TierEnforcement.check_processing_permission(current_user, db)
    except HTTPException as e:
        # Return detailed error for frontend
        raise e
    
    # Get session ID (fallback for anonymous users during upload)
    session_id = request.cookies.get("session_id")
    if not session_id and current_user:
        session_id = str(current_user.id)  # Use user ID as session for authenticated users
    elif not session_id:
        raise HTTPException(status_code=400, detail="No session found")
    
    try:
        # Temporarily disabled - video processing unavailable
        raise HTTPException(status_code=503, detail="Video processing temporarily unavailable during deployment")
        # processor = VideoProcessor(session_id)
        
        # Pass tier information to processor
        processing_options = {
            "tier": permissions["tier"],
            "features": permissions["features"],
            "user_id": current_user.id if current_user else None
        }
        
        task_id = await processor.start_processing(settings, processing_options)
        return {"task_id": task_id, "status": "started", "tier": permissions["tier"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    try:
        progress_file = Path(f"app/static/uploads/progress_{task_id}.json")
        if progress_file.exists():
            with open(progress_file, 'r') as f:
                return json.load(f)
        else:
            return {"status": "not_found"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/api/ai-services/status")
async def get_ai_services_status():
    """Get status of available AI services (free vs paid)"""
    free_services = free_ai_service.is_available()
    openai_available = bool(settings.OPENAI_API_KEY)
    
    return {
        "free_services": {
            "transcription": {
                "available": free_services["transcription"],
                "provider": "OpenAI Whisper (local)",
                "cost": "Free"
            },
            "translation": {
                "available": free_services["translation"], 
                "provider": "Google Translate",
                "cost": "Free"
            },
            "text_to_speech": {
                "available": free_services["text_to_speech"],
                "provider": "Google TTS", 
                "cost": "Free"
            }
        },
        "paid_services": {
            "openai_available": openai_available,
            "transcription": {
                "available": openai_available,
                "provider": "OpenAI Whisper API",
                "cost": "$0.006/minute"
            },
            "translation": {
                "available": openai_available,
                "provider": "OpenAI GPT",
                "cost": "$0.001-0.002/request"
            },
            "text_to_speech": {
                "available": openai_available,
                "provider": "OpenAI TTS",
                "cost": "$15/1M characters"
            },
            "metadata_generation": {
                "available": openai_available,
                "provider": "OpenAI GPT",
                "cost": "$0.001-0.002/request"
            }
        },
        "supported_languages": free_ai_service.get_supported_languages()
    }

@router.post("/api/download-video")
async def download_video(request: VideoDownloadRequest, http_request: Request):
    try:
        session_id = http_request.cookies.get("session_id", str(uuid.uuid4()))
        upload_dir = Path(f"app/static/uploads/{session_id}")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Validate URL
        parsed_url = urlparse(request.url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        # Get file extension from URL
        path = parsed_url.path
        filename = path.split('/')[-1] if '/' in path else 'video'
        
        # If no extension, default to .mp4
        if '.' not in filename:
            filename += '.mp4'
        
        # Generate unique filename
        unique_filename = f"video_{session_id}_{uuid.uuid4().hex[:8]}_{filename}"
        file_path = upload_dir / unique_filename
        
        # Download the video
        response = requests.get(request.url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Check if it's actually a video by content type
        content_type = response.headers.get('content-type', '').lower()
        if not any(video_type in content_type for video_type in ['video/', 'application/octet-stream']):
            raise HTTPException(status_code=400, detail="URL does not point to a video file")
        
        # Write file
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Get video info using moviepy
        from moviepy import VideoFileClip
        try:
            clip = VideoFileClip(str(file_path))
            file_info = {
                "width": clip.size[0],
                "height": clip.size[1], 
                "duration": clip.duration,
                "format": filename.split('.')[-1].upper()
            }
            clip.close()
        except Exception as e:
            # If moviepy fails, provide basic info
            file_info = {
                "width": 0,
                "height": 0,
                "duration": 0,
                "format": filename.split('.')[-1].upper()
            }
        
        return {
            "message": "Video downloaded successfully",
            "filename": unique_filename,
            "file_info": file_info
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to download video: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

@router.get("/api/uploads/{filename}")
async def get_uploaded_file(filename: str, request: Request):
    """Serve uploaded files for preview"""
    session_id = request.cookies.get("session_id", "")
    if not session_id:
        raise HTTPException(status_code=404, detail="Session not found")
    
    file_path = Path(f"app/static/uploads/{session_id}/{filename}")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(file_path)

# File management endpoints
class FileDeleteRequest(BaseModel):
    path: str

@router.get("/api/files")
async def list_files(request: Request):
    """List all generated files for the current session"""
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            return {"files": []}
        
        output_dir = Path(f"app/static/outputs/{session_id}")
        if not output_dir.exists():
            return {"files": []}
        
        files = []
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "name": file_path.name,
                    "path": str(file_path.relative_to(Path("app/static"))),
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "type": file_path.suffix.lower().lstrip('.')
                })
        
        # Sort by creation time (newest first)
        files.sort(key=lambda x: x["created"], reverse=True)
        
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing files: {str(e)}")

@router.get("/api/files/download")
async def download_file(path: str, request: Request):
    """Download a specific file"""
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Security check - ensure path is within allowed directory
        file_path = Path(f"app/static/{path}")
        allowed_base = Path(f"app/static/outputs/{session_id}").resolve()
        
        try:
            file_path = file_path.resolve()
            file_path.relative_to(allowed_base)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileResponse(
            file_path, 
            filename=file_path.name,
            media_type='application/octet-stream'
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")

@router.post("/api/files/delete")
async def delete_file(file_request: FileDeleteRequest, request: Request):
    """Delete a specific file"""
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Security check - ensure path is within allowed directory
        file_path = Path(f"app/static/{file_request.path}")
        allowed_base = Path(f"app/static/outputs/{session_id}").resolve()
        
        try:
            file_path = file_path.resolve()
            file_path.relative_to(allowed_base)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if file_path.exists():
            file_path.unlink()
            return {"message": "File deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

@router.post("/api/files/clear")
async def clear_all_files(request: Request):
    """Delete all files for the current session"""
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=404, detail="Session not found")
        
        output_dir = Path(f"app/static/outputs/{session_id}")
        if output_dir.exists():
            shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        return {"message": "All files cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing files: {str(e)}")

@router.get("/api/files/download-all")
async def download_all_files(request: Request):
    """Download all files as a ZIP archive"""
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=404, detail="Session not found")
        
        output_dir = Path(f"app/static/outputs/{session_id}")
        if not output_dir.exists() or not any(output_dir.rglob("*")):
            raise HTTPException(status_code=404, detail="No files found")
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    arcname = file_path.name  # Just the filename, not full path
                    zip_file.write(file_path, arcname)
        
        zip_buffer.seek(0)
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.getvalue()),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=generated_files_{session_id}.zip"}
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating ZIP: {str(e)}")

@router.get("/api/files/preview")
async def preview_file(path: str, request: Request):
    """Preview a file (for images/videos)"""
    try:
        session_id = request.cookies.get("session_id")
        if not session_id:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Security check - ensure path is within allowed directory
        file_path = Path(f"app/static/{path}")
        allowed_base = Path(f"app/static/outputs/{session_id}").resolve()
        
        try:
            file_path = file_path.resolve()
            file_path.relative_to(allowed_base)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Return the file with appropriate media type for preview
        extension = file_path.suffix.lower()
        media_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.txt': 'text/plain',
            '.srt': 'text/plain'
        }
        
        media_type = media_types.get(extension, 'application/octet-stream')
        
        return FileResponse(file_path, media_type=media_type)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error previewing file: {str(e)}")