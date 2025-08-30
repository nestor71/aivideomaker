import os
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path
import tempfile
from app.core.config import settings
from app.core.logger import logger

try:
    from elevenlabs.client import ElevenLabs
    from elevenlabs import VoiceSettings, save
    HAS_ELEVENLABS = True
except ImportError:
    ElevenLabs = None
    VoiceSettings = None
    save = None
    HAS_ELEVENLABS = False

class ElevenLabsService:
    """
    Servizio ElevenLabs per voice cloning e lip sync.
    SOLO per utenti Premium (€19.99/mese).
    """
    
    def __init__(self):
        self.api_key = settings.ELEVENLABS_API_KEY
        self.default_voice_id = settings.ELEVENLABS_VOICE_ID
        self.model_id = settings.ELEVENLABS_MODEL_ID
        self.client = None
        
        if not self.api_key or not HAS_ELEVENLABS:
            logger.warning("ElevenLabs not configured - Premium voice features disabled")
        else:
            try:
                self.client = ElevenLabs(api_key=self.api_key)
                logger.info("ElevenLabs client initialized successfully")
            except Exception as e:
                logger.error(f"ElevenLabs client initialization failed: {str(e)}")
                self.client = None
    
    async def clone_voice_from_video(self, video_path: str, voice_name: str) -> Optional[str]:
        """
        Clona la voce dal video originale.
        Returns: voice_id se successo, None se errore.
        """
        if not self.api_key:
            logger.error("ElevenLabs API key not configured")
            return None
            
        try:
            # Estrai audio dal video
            audio_path = await self._extract_audio_from_video(video_path)
            if not audio_path:
                return None
            
            # Clona la voce
            voice_id = await self._create_voice_clone(audio_path, voice_name)
            
            # Cleanup
            if os.path.exists(audio_path):
                os.remove(audio_path)
                
            return voice_id
            
        except Exception as e:
            logger.error(f"Voice cloning error: {str(e)}")
            return None
    
    async def generate_speech_with_cloned_voice(
        self, 
        text: str, 
        voice_id: str, 
        output_path: str
    ) -> bool:
        """
        Genera speech con voce clonata + lip sync.
        """
        if not self.api_key:
            logger.error("ElevenLabs API key not configured")
            return False
            
        try:
            url = f"{self.base_url}/text-to-speech/{voice_id}"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": self.api_key
            }
            
            data = {
                "text": text,
                "model_id": self.model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers) as response:
                    if response.status == 200:
                        audio_content = await response.read()
                        with open(output_path, "wb") as f:
                            f.write(audio_content)
                        logger.info(f"ElevenLabs speech generated: {output_path}")
                        return True
                    else:
                        error = await response.text()
                        logger.error(f"ElevenLabs API error: {response.status} - {error}")
                        return False
                        
        except Exception as e:
            logger.error(f"Speech generation error: {str(e)}")
            return False
    
    async def sync_audio_to_lips(
        self, 
        video_path: str, 
        audio_path: str, 
        output_path: str
    ) -> bool:
        """
        Sincronizza l'audio generato con il movimento delle labbra.
        Usa librerie come wav2lip o similari.
        """
        try:
            # Placeholder per lip sync - implementazione dipende dalla libreria scelta
            # Opzioni: wav2lip, SadTalker, etc.
            
            logger.info("Lip sync functionality - to be implemented with wav2lip")
            
            # Per ora copia il video originale
            # TODO: Implementare vera sincronizzazione labiale
            import shutil
            shutil.copy2(video_path, output_path)
            
            return True
            
        except Exception as e:
            logger.error(f"Lip sync error: {str(e)}")
            return False
    
    async def _extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """Estrae audio dal video per voice cloning."""
        try:
            # Usa moviepy per estrarre audio
            from moviepy.editor import VideoFileClip
            
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                audio_path = tmp.name
            
            video = VideoFileClip(video_path)
            audio = video.audio
            
            # Prendi solo i primi 30 secondi per il cloning
            if audio.duration > 30:
                audio = audio.subclip(0, 30)
            
            audio.write_audiofile(audio_path, verbose=False, logger=None)
            video.close()
            
            return audio_path
            
        except Exception as e:
            logger.error(f"Audio extraction error: {str(e)}")
            return None
    
    async def _create_voice_clone(self, audio_path: str, voice_name: str) -> Optional[str]:
        """Crea un clone della voce usando ElevenLabs."""
        try:
            url = f"{self.base_url}/voices/add"
            headers = {"xi-api-key": self.api_key}
            
            # Prepara i file per l'upload
            with open(audio_path, "rb") as audio_file:
                files = {
                    "files": ("sample.wav", audio_file, "audio/wav")
                }
                data = {
                    "name": voice_name,
                    "description": f"Voice cloned from video - {voice_name}",
                    "labels": '{"accent": "neutral", "age": "adult"}'
                }
                
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, 
                        data=data, 
                        headers=headers
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            voice_id = result.get("voice_id")
                            logger.info(f"Voice cloned successfully: {voice_id}")
                            return voice_id
                        else:
                            error = await response.text()
                            logger.error(f"Voice cloning error: {response.status} - {error}")
                            return None
                            
        except Exception as e:
            logger.error(f"Voice clone creation error: {str(e)}")
            return None
    
    async def get_voice_list(self) -> List[Dict[str, Any]]:
        """Ottiene la lista delle voci disponibili."""
        if not self.api_key:
            return []
            
        try:
            url = f"{self.base_url}/voices"
            headers = {"xi-api-key": self.api_key}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get("voices", [])
                    else:
                        logger.error(f"Voice list error: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"Voice list retrieval error: {str(e)}")
            return []

# Global instance
elevenlabs_service = ElevenLabsService()