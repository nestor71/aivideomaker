import os
import tempfile
from pathlib import Path
from typing import Dict, Optional, List
import asyncio
from concurrent.futures import ThreadPoolExecutor
from fastapi import HTTPException

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    whisper = None
    HAS_WHISPER = False

try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    GoogleTranslator = None
    HAS_TRANSLATOR = False

try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    gTTS = None
    HAS_GTTS = False

# Lazy import for startup issues
# from moviepy.editor import VideoFileClip
from app.core.logger import logger
from app.core.config import settings


class FreeAIService:
    """
    Servizio AI gratuito usando:
    - OpenAI Whisper (locale) per trascrizione
    - Google Translate (gratuito) per traduzione
    - Google TTS (gratuito) per sintesi vocale
    """
    
    def __init__(self):
        self.whisper_model = None
        self.model_size = os.getenv("WHISPER_MODEL", "small")  # tiny, small, medium, large
        
        # Inizializza Whisper se disponibile
        if HAS_WHISPER:
            try:
                logger.info(f"Loading Whisper model: {self.model_size}")
                self.whisper_model = whisper.load_model(self.model_size)
                logger.info("✅ Whisper model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}")
                self.whisper_model = None
        else:
            logger.warning("Whisper not available - transcription will be disabled")
    
    def is_available(self) -> Dict[str, bool]:
        """Check which services are available"""
        return {
            "transcription": HAS_WHISPER and self.whisper_model is not None,
            "translation": HAS_TRANSLATOR,
            "text_to_speech": HAS_GTTS
        }
    
    async def transcribe_audio(self, video_path: Path, language: Optional[str] = None) -> Dict[str, any]:
        """
        Trascrivi audio usando Whisper locale (GRATUITO)
        """
        if not self.whisper_model:
            raise Exception("Whisper model not available")
        
        try:
            logger.info(f"Transcribing video: {video_path}")
            
            # Estrai audio dal video
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio_path = temp_audio.name
            
            try:
                # Lazy import moviepy when needed
                try:
                    from moviepy.editor import VideoFileClip
                    clip = VideoFileClip(str(video_path))
                except ImportError:
                    logger.warning("moviepy not available, video processing disabled")
                    raise HTTPException(status_code=503, detail="Video processing temporarily unavailable")
                logger.info(f"Original video duration: {clip.duration}s")
                if clip.audio is None:
                    raise Exception("No audio track found in video")
                logger.info(f"Audio track duration: {clip.audio.duration}s")
                clip.audio.write_audiofile(temp_audio_path, logger=None)
                clip.close()
                
                # Trascrizione con Whisper
                options = {
                    "task": "transcribe",
                    "fp16": False  # Compatibility
                }
                if language and language != "auto":
                    options["language"] = language
                
                # Esegui trascrizione in thread separato per non bloccare
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    result = await loop.run_in_executor(
                        executor, 
                        lambda: self.whisper_model.transcribe(temp_audio_path, **options)
                    )
                
                # Detect language se non specificato
                detected_language = result.get("language", "unknown")
                transcribed_text = result.get("text", "").strip()
                
                logger.info(f"✅ Transcription completed. Detected language: {detected_language}")
                logger.info(f"Transcribed text length: {len(transcribed_text)} characters")
                logger.info(f"Text preview: {transcribed_text[:200]}...")
                
                return {
                    "text": transcribed_text,
                    "language": detected_language,
                    "segments": result.get("segments", [])
                }
                
            finally:
                # Cleanup temp file
                try:
                    os.unlink(temp_audio_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise Exception(f"Transcription failed: {str(e)}")
    
    async def translate_text(self, text: str, target_language: str, source_language: str = "auto") -> str:
        """
        Traduci testo usando Google Translate (GRATUITO)
        """
        if not HAS_TRANSLATOR:
            raise Exception("Translator not available")
        
        try:
            logger.info(f"Translating text to {target_language}")
            
            # Gestisci testi lunghi dividendoli in chunk
            max_length = 4500  # Google Translate limit
            
            if len(text) <= max_length:
                translator = GoogleTranslator(source=source_language, target=target_language)
                result = translator.translate(text)
                return result
            else:
                # Dividi il testo in chunks
                chunks = []
                words = text.split()
                current_chunk = []
                current_length = 0
                
                for word in words:
                    word_length = len(word) + 1
                    if current_length + word_length > max_length and current_chunk:
                        chunks.append(' '.join(current_chunk))
                        current_chunk = [word]
                        current_length = word_length
                    else:
                        current_chunk.append(word)
                        current_length += word_length
                
                if current_chunk:
                    chunks.append(' '.join(current_chunk))
                
                # Traduci ogni chunk
                translated_chunks = []
                for i, chunk in enumerate(chunks):
                    logger.info(f"Translating chunk {i+1}/{len(chunks)}")
                    translator = GoogleTranslator(source=source_language, target=target_language)
                    translated_chunk = translator.translate(chunk)
                    translated_chunks.append(translated_chunk)
                
                return ' '.join(translated_chunks)
                
        except Exception as e:
            logger.error(f"Translation error: {e}")
            raise Exception(f"Translation failed: {str(e)}")
    
    async def translate_segments(self, segments: List[dict], target_language: str) -> List[dict]:
        """Traduci segmenti mantenendo i timestamp"""
        translated_segments = []
        
        for segment in segments:
            try:
                translated_text = await self.translate_text(
                    segment["text"], 
                    target_language
                )
                
                translated_segment = segment.copy()
                translated_segment["text"] = translated_text
                translated_segments.append(translated_segment)
                
            except Exception as e:
                logger.warning(f"Failed to translate segment: {e}")
                # Keep original if translation fails
                translated_segments.append(segment)
        
        return translated_segments
    
    async def generate_speech(self, text: str, language: str, output_path: Path) -> Path:
        """
        Genera audio da testo usando Google TTS (GRATUITO)
        """
        if not HAS_GTTS:
            raise Exception("Google TTS not available")
        
        try:
            logger.info(f"Generating speech in {language}")
            
            # Gestisci testi lunghi dividendoli in chunk per gTTS
            max_length = 4500
            
            if len(text) <= max_length:
                # Testo breve, genera direttamente
                loop = asyncio.get_event_loop()
                with ThreadPoolExecutor() as executor:
                    await loop.run_in_executor(
                        executor,
                        lambda: self._generate_speech_sync(text, language, output_path)
                    )
            else:
                # Testo lungo, dividi in chunk e concatena audio
                logger.info(f"Text too long ({len(text)} chars), processing in chunks")
                await self._generate_speech_chunked(text, language, output_path)
            
            logger.info(f"✅ Speech generated: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Speech generation error: {e}")
            raise Exception(f"Speech generation failed: {str(e)}")
    
    def _generate_speech_sync(self, text: str, language: str, output_path: Path):
        """Synchronous speech generation"""
        tts = gTTS(text=text, lang=language, slow=False)
        tts.save(str(output_path))
    
    async def _generate_speech_chunked(self, text: str, language: str, output_path: Path):
        """Generate speech for long text by splitting into chunks"""
        import tempfile
        from pydub import AudioSegment
        
        max_length = 4500
        
        # Dividi il testo in frasi per evitare di tagliare a metà
        sentences = text.replace('. ', '.|').replace('! ', '!|').replace('? ', '?|').split('|')
        
        chunks = []
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence) + 1
            if current_length + sentence_length > max_length and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_length = sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        logger.info(f"Generating speech in {len(chunks)} chunks")
        
        # Genera audio per ogni chunk
        chunk_files = []
        loop = asyncio.get_event_loop()
        
        with ThreadPoolExecutor() as executor:
            for i, chunk in enumerate(chunks):
                chunk_path = output_path.parent / f"temp_chunk_{i}.mp3"
                
                await loop.run_in_executor(
                    executor,
                    lambda c=chunk, p=chunk_path: self._generate_speech_sync(c, language, p)
                )
                
                chunk_files.append(str(chunk_path))
        
        # Concatena tutti gli audio chunk
        combined = AudioSegment.empty()
        for chunk_file in chunk_files:
            chunk_audio = AudioSegment.from_mp3(chunk_file)
            combined += chunk_audio
        
        # Salva il file finale
        combined.export(str(output_path), format="mp3")
        
        # Cleanup files temporanei
        for chunk_file in chunk_files:
            try:
                Path(chunk_file).unlink()
            except:
                pass
                
        logger.info(f"✅ Combined speech generated from {len(chunks)} chunks")
    
    def create_srt_subtitles(self, segments: List[dict]) -> str:
        """Crea contenuto SRT dai segmenti"""
        def format_timestamp(seconds):
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            millisecs = int((seconds % 1) * 1000)
            return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
        
        srt_content = ""
        for i, segment in enumerate(segments, 1):
            start = format_timestamp(segment["start"])
            end = format_timestamp(segment["end"])
            text = segment["text"].strip()
            
            srt_content += f"{i}\n{start} --> {end}\n{text}\n\n"
        
        return srt_content
    
    def get_supported_languages(self) -> Dict[str, Dict[str, List[str]]]:
        """Lista lingue supportate per ogni servizio"""
        return {
            "transcription": {
                "whisper": ["auto", "en", "it", "es", "fr", "de", "pt", "ru", "ja", "ko", "zh", "ar", "hi", "nl", "pl", "tr", "sv", "da", "no", "fi"]
            },
            "translation": {
                "google": ["en", "it", "es", "fr", "de", "pt", "ru", "ja", "ko", "zh", "ar", "hi", "nl", "pl", "tr", "sv", "da", "no", "fi"]
            },
            "text_to_speech": {
                "google": ["en", "it", "es", "fr", "de", "pt", "ru", "ja", "ko", "zh", "ar", "hi", "nl", "pl", "tr", "sv", "da", "no", "fi"]
            }
        }


# Global instance
free_ai_service = FreeAIService()