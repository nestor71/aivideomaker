import json
import os
from pathlib import Path
from typing import Dict, Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from app.core.config import settings
from app.core.logger import logger

class YouTubeService:
    def __init__(self):
        self.client_id = settings.YOUTUBE_CLIENT_ID
        self.client_secret = settings.YOUTUBE_CLIENT_SECRET
        self.redirect_uri = "http://localhost:8000/api/youtube/callback"
        self.scopes = [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly"
        ]
    
    async def get_auth_url(self) -> str:
        if not self.client_id or not self.client_secret:
            raise Exception("YouTube API credentials not configured")
        
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        return authorization_url
    
    async def handle_callback(self, code: str, session_id: str) -> Dict[str, str]:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )
        flow.redirect_uri = self.redirect_uri
        
        # Exchange code for token
        flow.fetch_token(code=code)
        
        # Save credentials
        credentials = flow.credentials
        creds_path = Path(f"app/static/uploads/youtube_creds_{session_id}.json")
        
        with open(creds_path, 'w') as f:
            json.dump({
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }, f)
        
        # Get channel info
        youtube = build('youtube', 'v3', credentials=credentials)
        channels_response = youtube.channels().list(
            part='snippet,contentDetails,statistics',
            mine=True
        ).execute()
        
        if channels_response['items']:
            channel = channels_response['items'][0]
            return {
                'channel_id': channel['id'],
                'channel_name': channel['snippet']['title'],
                'subscribers': channel['statistics'].get('subscriberCount', '0')
            }
        else:
            raise Exception("No YouTube channel found for this account")
    
    async def disconnect(self, session_id: str):
        creds_path = Path(f"app/static/uploads/youtube_creds_{session_id}.json")
        if creds_path.exists():
            creds_path.unlink()
    
    async def upload_video(self, session_id: str, video_path: Path, metadata: Dict, thumbnail_path: Optional[Path] = None) -> str:
        creds_path = Path(f"app/static/uploads/youtube_creds_{session_id}.json")
        if not creds_path.exists():
            raise Exception("Not authenticated with YouTube")
        
        # Load credentials
        with open(creds_path, 'r') as f:
            creds_data = json.load(f)
        
        credentials = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        # Build YouTube service
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # Prepare video metadata
        body = {
            'snippet': {
                'title': metadata.get('title', 'Untitled Video'),
                'description': metadata.get('description', ''),
                'tags': metadata.get('tags', []),
                'categoryId': metadata.get('category', '22')
            },
            'status': {
                'privacyStatus': metadata.get('privacy', 'private'),
                'selfDeclaredMadeForKids': False
            }
        }
        
        # Upload video
        media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype='video/*')
        
        request = youtube.videos().insert(
            part=','.join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
        
        video_id = response['id']
        
        # Upload thumbnail if provided
        if thumbnail_path and thumbnail_path.exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumbnail_path), mimetype='image/jpeg')
                ).execute()
            except Exception as e:
                logger.error(f"Failed to upload thumbnail: {e}", exc_info=True)
        
        return f"https://www.youtube.com/watch?v={video_id}"
    
    async def get_channel_info(self, session_id: str) -> Optional[Dict]:
        creds_path = Path(f"app/static/uploads/youtube_creds_{session_id}.json")
        if not creds_path.exists():
            return None
        
        try:
            with open(creds_path, 'r') as f:
                creds_data = json.load(f)
            
            credentials = Credentials(
                token=creds_data['token'],
                refresh_token=creds_data['refresh_token'],
                token_uri=creds_data['token_uri'],
                client_id=creds_data['client_id'],
                client_secret=creds_data['client_secret'],
                scopes=creds_data['scopes']
            )
            
            youtube = build('youtube', 'v3', credentials=credentials)
            channels_response = youtube.channels().list(
                part='snippet,contentDetails,statistics',
                mine=True
            ).execute()
            
            if channels_response['items']:
                channel = channels_response['items'][0]
                return {
                    'channel_id': channel['id'],
                    'channel_name': channel['snippet']['title'],
                    'subscribers': channel['statistics'].get('subscriberCount', '0')
                }
        except Exception as e:
            logger.error(f"Error getting channel info: {e}", exc_info=True)
        
        return None