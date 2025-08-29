import asyncio
import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
# Lazy imports to avoid startup issues
# import cv2
# import numpy as np
# from moviepy.editor import (
#     VideoFileClip, ImageClip, CompositeVideoClip, 
#     TextClip, ColorClip, AudioFileClip
)
from PIL import Image, ImageDraw, ImageFont
from app.core.config import settings
from app.core.logger import logger
from app.models.settings import UserSettings
from app.services.free_ai_service import free_ai_service
from app.services.usage_monitor import usage_monitor
from app.database.models import User, UsageRecord
from app.database.base import get_session
import re

class VideoProcessor:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.upload_dir = Path(f"app/static/uploads/{session_id}")
        self.output_dir = Path(f"app/static/outputs/{session_id}")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def start_processing(self, user_settings: UserSettings) -> str:
        task_id = str(uuid.uuid4())
        
        # Start processing in background
        asyncio.create_task(self._process_video(task_id, user_settings))
        
        return task_id
    
    async def _process_video(self, task_id: str, user_settings: UserSettings):
        try:
            await self._update_progress(task_id, 0, "Starting video processing...")
            
            # Load main video
            video_files = list(self.upload_dir.glob("video_*"))
            if not video_files:
                raise Exception("No video file found")
            
            main_video_path = video_files[0]
            clip = VideoFileClip(str(main_video_path))
            
            processed_clips = [clip]
            
            # Apply logo overlay
            if user_settings.video_settings.logo_overlay:
                await self._update_progress(task_id, 10, "Adding logo overlay...")
                logo_clip = await self._create_logo_overlay(clip, user_settings.logo_settings)
                if logo_clip:
                    processed_clips.append(logo_clip)
            
            # Apply CTA overlay
            if user_settings.video_settings.cta_overlay:
                await self._update_progress(task_id, 20, "Adding call-to-action overlay...")
                cta_clip = await self._create_cta_overlay(clip, user_settings.cta_settings)
                if cta_clip:
                    processed_clips.append(cta_clip)
            
            # Create final composition
            await self._update_progress(task_id, 30, "Compositing video...")
            final_clip = CompositeVideoClip(processed_clips)
            
            # Audio processing (transcription and/or translation)
            transcript_files = []
            if user_settings.video_settings.transcription or user_settings.video_settings.translation:
                await self._update_progress(task_id, 40, "Processing audio...")
                
                if user_settings.video_settings.translation:
                    # Audio translation (includes transcription)
                    await self._update_progress(task_id, 45, "Translating audio...")
                    translation_result = await self._translate_audio_with_files(
                        main_video_path,
                        user_settings, 
                        user_settings.audio_translation_settings,
                        task_id
                    )
                    
                    translated_audio_path = translation_result['audio_path']
                    transcript_files.extend(translation_result['transcript_files'])
                    
                    # Replace the audio in the video if specified
                    if user_settings.audio_translation_settings.replace_audio:
                        await self._update_progress(task_id, 50, "Replacing audio track...")
                        translated_audio_clip = AudioFileClip(str(translated_audio_path))
                        
                        # Set the translated audio to the video
                        if hasattr(final_clip, 'set_audio'):
                            final_clip = final_clip.with_audio(translated_audio_clip)
                        else:
                            # For CompositeVideoClip, we need to update the audio of the base video
                            if isinstance(final_clip, CompositeVideoClip):
                                # Get the main video clip and set its audio
                                main_clip = final_clip.clips[0].with_audio(translated_audio_clip)
                                # Recreate the composite with the updated audio
                                final_clip = CompositeVideoClip([main_clip] + final_clip.clips[1:])
                            else:
                                final_clip = final_clip.with_audio(translated_audio_clip)
                        
                elif user_settings.video_settings.transcription:
                    # Just transcription without translation
                    await self._update_progress(task_id, 45, "Transcribing audio...")
                    transcript_result = await self._transcribe_audio_with_files(
                        main_video_path,
                        user_settings,
                        user_settings.audio_translation_settings.original_language if user_settings.audio_translation_settings.original_language != "auto" else None,
                        task_id
                    )
                    transcript_files.extend(transcript_result['transcript_files'])
            
            # Generate metadata
            if user_settings.video_settings.metadata_generation:
                await self._update_progress(task_id, 55, "Generating SEO metadata...")
                metadata = await self._generate_metadata(clip, user_settings.metadata_settings)
            
            # Generate thumbnail
            if user_settings.video_settings.thumbnail_generation:
                await self._update_progress(task_id, 65, "Creating thumbnail...")
                thumbnail_path = await self._create_thumbnail(clip, user_settings.thumbnail_settings)
            
            # Export final video using chunked processing for efficiency (only if requested)
            output_path = None
            if user_settings.file_output_settings.save_video:
                await self._update_progress(task_id, 75, "Exporting final video...")
                
                # Generate smart filename
                original_filename = Path(main_video_path).name
                smart_name = self._generate_smart_filename(
                    original_filename, 
                    "video", 
                    user_settings.audio_translation_settings.target_language,
                    "it"  # TODO: Get from user preferences
                )
                output_path = self.output_dir / f"{smart_name}.mp4"
                
                # Use chunked export for better memory management
                await self._export_video_chunked(final_clip, output_path, task_id)
            else:
                await self._update_progress(task_id, 90, "Skipping video export (not requested)...")
            
            # Upload to YouTube if enabled
            if user_settings.video_settings.youtube_upload and user_settings.youtube_settings.connected:
                await self._update_progress(task_id, 90, "Uploading to YouTube...")
                youtube_url = await self._upload_to_youtube(output_path, metadata, thumbnail_path)
            
            # Cleanup
            final_clip.close()
            clip.close()
            
            await self._update_progress(task_id, 100, "Processing completed!")
            await self._complete_processing(task_id, str(output_path), transcript_files)
            
        except Exception as e:
            logger.error(f"Video processing failed for task {task_id}: {str(e)}", exc_info=True)
            await self._update_progress(task_id, 0, f"Error: {str(e)}", "failed")
    
    async def _create_logo_overlay(self, main_clip: VideoFileClip, logo_settings) -> Optional[ImageClip]:
        logo_files = list(self.upload_dir.glob("logo_*"))
        if not logo_files:
            return None
        
        logo_path = logo_files[0]
        
        # Calculate position
        video_w, video_h = main_clip.size
        logo_size_percent = logo_settings.size / 100
        
        # Load and resize logo
        logo = ImageClip(str(logo_path), duration=main_clip.duration)
        logo = logo.resized(height=int(video_h * logo_size_percent))
        
        # Position mapping
        positions = {
            "top_left": ("left", "top"),
            "top_right": ("right", "top"),
            "bottom_left": ("left", "bottom"),
            "bottom_right": ("right", "bottom"),
            "center": ("center", "center")
        }
        
        position = positions.get(logo_settings.position, ("right", "top"))
        logo = logo.with_position(position)
        
        # Set timing
        start_time = logo_settings.start_time
        end_time = logo_settings.end_time if logo_settings.end_time else main_clip.duration
        logo = logo.with_start(start_time).with_end(min(end_time, main_clip.duration))
        
        return logo
    
    async def _create_cta_overlay(self, main_clip: VideoFileClip, cta_settings) -> Optional[Union[VideoFileClip, ImageClip]]:
        cta_files = list(self.upload_dir.glob("cta_*"))
        if not cta_files:
            return None
        
        cta_path = cta_files[0]
        
        # Determine if it's video or image
        if cta_path.suffix.lower() in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
            cta_clip = VideoFileClip(str(cta_path))
        else:
            cta_clip = ImageClip(str(cta_path), duration=main_clip.duration)
        
        # Apply chroma key if enabled
        if cta_settings.chroma_key and hasattr(cta_clip, 'mask'):
            cta_clip = await self._apply_chroma_key(cta_clip, cta_settings.chroma_color)
        
        # Calculate position and size
        video_w, video_h = main_clip.size
        cta_size_percent = cta_settings.size / 100
        
        cta_clip = cta_clip.resized(height=int(video_h * cta_size_percent))
        
        # Position mapping
        positions = {
            "top_left": ("left", "top"),
            "top_right": ("right", "top"),
            "bottom_left": ("left", "bottom"),
            "bottom_right": ("right", "bottom"),
            "center": ("center", "center")
        }
        
        position = positions.get(cta_settings.position, ("right", "bottom"))
        cta_clip = cta_clip.with_position(position)
        
        # Set timing
        start_time = cta_settings.start_time
        
        if cta_settings.end_time:
            # Se è specificato un tempo di fine, usa quello
            end_time = min(cta_settings.end_time, main_clip.duration)
            cta_clip = cta_clip.with_start(start_time).with_end(end_time)
        else:
            # Se tempo di fine è vuoto, riproduci la CTA completamente
            cta_duration = cta_clip.duration
            end_time = start_time + cta_duration
            
            # Se la CTA supera la durata del video principale, estendi il video principale
            if end_time > main_clip.duration:
                # La CTA determina la durata finale
                cta_clip = cta_clip.with_start(start_time)
            else:
                # La CTA finisce prima della fine del video principale
                cta_clip = cta_clip.with_start(start_time).with_end(end_time)
        
        return cta_clip
    
    async def _apply_chroma_key(self, clip, chroma_color: str):
        # Convert hex color to RGB
        hex_color = chroma_color.lstrip('#')
        rgb_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        def mask_function(get_frame, t):
            frame = get_frame(t)
            # Simple chroma key implementation
            mask = np.all(np.abs(frame - rgb_color) > 30, axis=2)
            return mask.astype(np.uint8) * 255
        
        # Use image_transform to apply chroma key effect
        def apply_chroma(frame):
            # Create mask for the frame
            mask = np.all(np.abs(frame - rgb_color) > 30, axis=2)
            # Apply transparency where mask is False (chroma color detected)
            alpha = mask.astype(np.uint8) * 255
            # Add alpha channel to frame
            rgba_frame = np.dstack([frame, alpha])
            return rgba_frame
        
        # Apply the chroma key transformation
        clip = clip.image_transform(apply_chroma, apply_to=['mask'])
        return clip
    
    async def _transcribe_audio(self, video_path: Path, language: str = None) -> Dict[str, str]:
        # Try free AI service first
        if free_ai_service.is_available()["transcription"]:
            try:
                logger.info("Using FREE Whisper for transcription")
                result = await free_ai_service.transcribe_audio(video_path, language)
                return {
                    "text": result["text"],
                    "language": result["language"],
                    "segments": result.get("segments", [])
                }
            except Exception as e:
                logger.warning(f"Free transcription failed: {e}")
        
        # Fallback to OpenAI if available
        if settings.OPENAI_API_KEY:
            logger.info("Falling back to OpenAI transcription")
            return await self._transcribe_audio_openai(video_path, language)
        
        return {"text": "No transcription service available", "language": "unknown"}

    async def _transcribe_audio_openai(self, video_path: Path, language: str = None) -> Dict[str, str]:
        try:
            # Extract audio from video
            clip = VideoFileClip(str(video_path))
            audio_path = video_path.with_suffix('.wav')
            clip.audio.write_audiofile(str(audio_path))
            clip.close()
            
            # Transcribe using OpenAI Whisper
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            with open(audio_path, "rb") as audio_file:
                if language and language != "auto":
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language=language
                    )
                else:
                    transcript = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
            
            # Cleanup
            audio_path.unlink()
            
            detected_language = await self._detect_language(transcript.text) if not language or language == "auto" else language
            
            return {
                "text": transcript.text,
                "language": detected_language
            }
        except Exception as e:
            return {"text": f"OpenAI transcription error: {str(e)}", "language": "unknown"}
    
    async def _detect_language(self, text: str) -> str:
        """Detect the language of the given text using OpenAI."""
        if not settings.OPENAI_API_KEY:
            return "unknown"
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Detect the language of the following text and return only the ISO 639-1 language code (e.g., 'en' for English, 'it' for Italian, 'es' for Spanish, etc.). If uncertain, return 'en'."},
                    {"role": "user", "content": text[:500]}  # Limit text length for API efficiency
                ]
            )
            
            detected_lang = response.choices[0].message.content.strip().lower()
            # Validate that it's a proper language code
            if len(detected_lang) == 2 and detected_lang.isalpha():
                return detected_lang
            else:
                return "en"  # Default to English if detection fails
                
        except Exception as e:
            return "en"  # Default to English on error
    
    async def _translate_text(self, text: str, target_language: str = "Italian") -> str:
        # Try free translation service first
        if free_ai_service.is_available()["translation"]:
            try:
                logger.info(f"Using FREE Google Translate for translation to {target_language}")
                # Convert language name to code
                lang_code = self._get_language_code(target_language)
                result = await free_ai_service.translate_text(text, lang_code)
                return result
            except Exception as e:
                logger.warning(f"Free translation failed: {e}")
        
        # Fallback to OpenAI if available
        if settings.OPENAI_API_KEY:
            logger.info("Falling back to OpenAI translation")
            return await self._translate_text_openai(text, target_language)
        
        return f"No translation service available"
    
    async def _translate_text_openai(self, text: str, target_language: str = "Italian") -> str:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"Translate the following text to {target_language}:"},
                    {"role": "user", "content": text}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"OpenAI translation error: {str(e)}"
    
    async def _transcribe_audio_with_files(self, video_path: Path, user_settings: UserSettings, language: str = None, task_id: str = None):
        """Transcribe audio and save transcript files (.txt and .srt)"""
        transcript_data = await self._transcribe_audio(video_path, language)
        
        # Save transcript files based on user preferences
        transcript_files = []
        if transcript_data and transcript_data.get("text"):
            original_filename = Path(video_path).name
            
            # Save original transcript as .txt file
            if user_settings.file_output_settings.save_original_transcript:
                smart_name = self._generate_smart_filename(original_filename, "transcript_original", "original", "it")
                txt_path = self.output_dir / f"{smart_name}.txt"
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(transcript_data["text"])
                transcript_files.append(str(txt_path))
            
            # Save original subtitles as .srt file
            if user_settings.file_output_settings.save_original_subtitles:
                smart_name = self._generate_smart_filename(original_filename, "subtitles_original", "original", "it")
                srt_path = self.output_dir / f"{smart_name}.srt"
                await self._create_srt_file(transcript_data["text"], srt_path)
                transcript_files.append(str(srt_path))
        
        return {
            "transcript_data": transcript_data,
            "transcript_files": transcript_files
        }
    
    async def _translate_audio_with_files(self, video_path: Path, user_settings: UserSettings, audio_settings, task_id: str):
        """Translate audio and save both original and translated transcript files"""
        # Get original transcription first
        transcript_result = await self._transcribe_audio_with_files(video_path, user_settings, 
            audio_settings.original_language if audio_settings.original_language != "auto" else None, 
            task_id)
        
        transcript_data = transcript_result["transcript_data"]
        transcript_files = transcript_result["transcript_files"]
        
        if not transcript_data or not transcript_data.get("text"):
            raise Exception("Failed to transcribe original audio")
        
        # Translate the text
        target_language_name = self._get_language_name(audio_settings.target_language)
        translated_text = await self._translate_text(transcript_data["text"], target_language_name)
        
        # Save translated transcript files based on user preferences
        if translated_text and not translated_text.startswith("Translation error"):
            original_filename = Path(video_path).name
            
            # Save translated .txt file
            if user_settings.file_output_settings.save_translated_transcript:
                smart_name = self._generate_smart_filename(original_filename, "transcript_translated", audio_settings.target_language, "it")
                translated_txt_path = self.output_dir / f"{smart_name}.txt"
                with open(translated_txt_path, 'w', encoding='utf-8') as f:
                    f.write(translated_text)
                transcript_files.append(str(translated_txt_path))
            
            # Save translated .srt file
            if user_settings.file_output_settings.save_translated_subtitles:
                smart_name = self._generate_smart_filename(original_filename, "subtitles_translated", audio_settings.target_language, "it")
                translated_srt_path = self.output_dir / f"{smart_name}.srt"
                await self._create_srt_file(translated_text, translated_srt_path)
                transcript_files.append(str(translated_srt_path))
        
        # Generate the translated audio
        audio_path = await self._generate_translated_audio(translated_text, audio_settings, video_path)
        
        # Save translated audio file if requested
        if user_settings.file_output_settings.save_translated_audio and audio_path:
            transcript_files.append(str(audio_path))
        
        return {
            "audio_path": audio_path,
            "transcript_files": transcript_files,
            "original_text": transcript_data["text"],
            "translated_text": translated_text
        }
    
    async def _generate_translated_audio(self, translated_text: str, audio_settings, video_path: Path) -> Path:
        """Generate speech from translated text"""
        speech_path = video_path.parent / f"translated_audio_{audio_settings.target_language}.mp3"
        
        # Try free TTS service first
        if free_ai_service.is_available()["text_to_speech"]:
            try:
                logger.info("Using FREE Google TTS for speech generation")
                result_path = await free_ai_service.generate_speech(
                    translated_text, 
                    audio_settings.target_language, 
                    speech_path
                )
                return result_path
            except Exception as e:
                logger.warning(f"Free TTS failed: {e}")
        
        # Fallback to OpenAI if available
        if settings.OPENAI_API_KEY:
            logger.info("Falling back to OpenAI TTS")
            return await self._generate_translated_audio_openai(translated_text, audio_settings, video_path)
        
        raise Exception("No text-to-speech service available")
    
    async def _generate_translated_audio_openai(self, translated_text: str, audio_settings, video_path: Path) -> Path:
        """Generate speech using OpenAI TTS"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            speech_path = video_path.parent / f"translated_audio_{audio_settings.target_language}.mp3"
            
            response = client.audio.speech.create(
                model="tts-1",
                voice="alloy",
                input=translated_text
            )
            
            with open(speech_path, 'wb') as f:
                f.write(response.content)
            
            return speech_path
            
        except Exception as e:
            raise Exception(f"OpenAI TTS error: {str(e)}")
    
    async def _create_srt_file(self, text: str, srt_path: Path):
        """Create a basic .srt subtitle file from text"""
        # Split text into sentences for basic subtitles
        sentences = []
        current_sentence = ""
        
        for char in text:
            current_sentence += char
            if char in '.!?':
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                current_sentence = ""
        
        # Add remaining text if any
        if current_sentence.strip():
            sentences.append(current_sentence.strip())
        
        # Create SRT format
        # Assume 3 seconds per subtitle for basic timing
        subtitle_duration = 3.0
        srt_content = ""
        
        for i, sentence in enumerate(sentences):
            start_time = i * subtitle_duration
            end_time = start_time + subtitle_duration
            
            # Format time as SRT timestamp (HH:MM:SS,mmm)
            def format_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = int(seconds % 60)
                millisecs = int((seconds % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"
            
            srt_content += f"{i + 1}\n"
            srt_content += f"{format_time(start_time)} --> {format_time(end_time)}\n"
            srt_content += f"{sentence}\n\n"
        
        # Save SRT file
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write(srt_content)

    async def _translate_audio(self, video_path: Path, audio_settings) -> Path:
        """Translate the audio in the video to target language using text-to-speech."""
        if not settings.OPENAI_API_KEY:
            raise Exception("Audio translation requires OpenAI API key")
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # First, transcribe the original audio
            transcript_data = await self._transcribe_audio(
                video_path, 
                audio_settings.original_language if audio_settings.original_language != "auto" else None
            )
            
            original_text = transcript_data["text"]
            detected_language = transcript_data["language"]
            
            # Translate the text to target language
            target_language_name = self._get_language_name(audio_settings.target_language)
            translated_text = await self._translate_text(original_text, target_language_name)
            
            # Generate speech from translated text
            speech_path = video_path.parent / f"translated_audio_{audio_settings.target_language}.mp3"
            
            response = client.audio.speech.create(
                model="tts-1",
                voice="alloy",  # You could make this configurable
                input=translated_text
            )
            
            # Save the audio file
            with open(speech_path, 'wb') as f:
                f.write(response.content)
            
            return speech_path
            
        except Exception as e:
            raise Exception(f"Audio translation error: {str(e)}")
    
    def _get_language_name(self, lang_code: str) -> str:
        """Convert language code to full language name for translation."""
        language_names = {
            "en": "English",
            "it": "Italian", 
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "pt": "Portuguese",
            "ru": "Russian",
            "ja": "Japanese",
            "ko": "Korean",
            "zh": "Chinese",
            "ar": "Arabic",
            "hi": "Hindi",
            "nl": "Dutch",
            "pl": "Polish",
            "tr": "Turkish",
            "sv": "Swedish",
            "da": "Danish",
            "no": "Norwegian",
            "fi": "Finnish"
        }
        return language_names.get(lang_code, "English")
    
    def _get_language_code(self, language_name: str) -> str:
        """Convert language name to code for free services."""
        name_to_code = {
            "English": "en",
            "Italian": "it",
            "Spanish": "es", 
            "French": "fr",
            "German": "de",
            "Portuguese": "pt",
            "Russian": "ru",
            "Japanese": "ja",
            "Korean": "ko",
            "Chinese": "zh",
            "Arabic": "ar",
            "Hindi": "hi",
            "Dutch": "nl",
            "Polish": "pl",
            "Turkish": "tr",
            "Swedish": "sv",
            "Danish": "da",
            "Norwegian": "no",
            "Finnish": "fi"
        }
        return name_to_code.get(language_name, "en")
    
    async def _generate_metadata(self, clip, metadata_settings) -> Dict[str, Any]:
        if not settings.OPENAI_API_KEY:
            return {"title": "Generated Video", "description": "Video processed by AIVideoMaker"}
        
        try:
            # Extract key frame for analysis
            frame = clip.get_frame(clip.duration / 2)
            
            # Generate metadata using AI
            from openai import OpenAI
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Generate SEO-optimized title, description, tags, and hashtags for a video. Response should be in JSON format."},
                    {"role": "user", "content": f"Generate metadata for a video. Duration: {clip.duration:.1f}s, Resolution: {clip.size[0]}x{clip.size[1]}"}
                ]
            )
            
            metadata = json.loads(response.choices[0].message.content)
            
            # Add global words if specified
            if metadata_settings.global_words:
                title = metadata.get("title", "")
                for word in metadata_settings.global_words:
                    if word not in title:
                        title = f"{word} - {title}"
                metadata["title"] = title
            
            return metadata
        except Exception as e:
            return {"title": "Generated Video", "description": f"Video processed by AIVideoMaker. Error: {str(e)}"}
    
    async def _create_thumbnail(self, clip: VideoFileClip, thumbnail_settings) -> Path:
        # Extract frame from middle of video
        frame = clip.get_frame(clip.duration / 2)
        
        # Convert to PIL Image
        thumbnail = Image.fromarray(frame.astype('uint8'), 'RGB')
        
        # Add custom text if specified
        if thumbnail_settings.custom_text:
            draw = ImageDraw.Draw(thumbnail)
            
            # Try to use a font, fall back to default if not available
            try:
                font = ImageFont.truetype("arial.ttf", thumbnail_settings.font_size)
            except:
                font = ImageFont.load_default()
            
            # Calculate text position (center)
            text_bbox = draw.textbbox((0, 0), thumbnail_settings.custom_text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            x = (thumbnail.width - text_width) // 2
            y = (thumbnail.height - text_height) // 2
            
            # Add text with outline for better visibility
            outline_width = 2
            for adj_x in range(-outline_width, outline_width + 1):
                for adj_y in range(-outline_width, outline_width + 1):
                    draw.text((x + adj_x, y + adj_y), thumbnail_settings.custom_text, 
                             font=font, fill=(0, 0, 0))
            
            draw.text((x, y), thumbnail_settings.custom_text, 
                     font=font, fill=thumbnail_settings.text_color)
        
        # Save thumbnail
        thumbnail_path = self.output_dir / "thumbnail.jpg"
        thumbnail.save(thumbnail_path, "JPEG", quality=95)
        
        return thumbnail_path
    
    async def _upload_to_youtube(self, video_path: Path, metadata: Dict, thumbnail_path: Path) -> str:
        # This would integrate with YouTube API
        # For now, return a placeholder
        return "https://youtube.com/watch?v=placeholder"
    
    async def _update_progress(self, task_id: str, percentage: int, message: str, status: str = "processing"):
        progress_file = Path(f"app/static/uploads/progress_{task_id}.json")
        progress_data = {
            "status": status,
            "percentage": percentage,
            "message": message,
            "timestamp": str(asyncio.get_event_loop().time())
        }
        
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)
    
    async def _complete_processing(self, task_id: str, output_path: str, transcript_files: list = None):
        progress_file = Path(f"app/static/uploads/progress_{task_id}.json")
        progress_data = {
            "status": "completed",
            "percentage": 100,
            "message": "Processing completed successfully!",
            "output_path": output_path,
            "transcript_files": transcript_files or [],
            "timestamp": str(asyncio.get_event_loop().time())
        }
        
        with open(progress_file, 'w') as f:
            json.dump(progress_data, f)
    
    def _generate_smart_filename(self, original_filename: str, file_type: str, target_language: str, user_language: str = "it") -> str:
        """
        Generate smart filenames based on original name and target language
        """
        # Extract original filename without extension and UUID prefix
        base_name = Path(original_filename).stem
        
        # Remove UUID prefix pattern: video_xxxxx-xxxx-xxxx_REALNAME
        base_name = re.sub(r'^video_[a-f0-9-]+_', '', base_name)
        
        # Keep original filename characters, just clean up problematic ones for filesystem
        base_name = re.sub(r'[<>:"/\\|?*]', '', base_name).strip()
        
        # Translation templates by user interface language
        templates = {
            "it": {
                "video": "{base_name} tradotto in italiano",
                "subtitles_original": "{base_name} sottotitoli originali",
                "subtitles_translated": "{base_name} sottotitoli tradotti in italiano", 
                "transcript_original": "{base_name} trascrizione originale",
                "transcript_translated": "{base_name} trascrizione tradotta in italiano"
            },
            "en": {
                "video": "{base_name} translated into english",
                "subtitles_original": "{base_name} original subtitles",
                "subtitles_translated": "{base_name} subtitles translated into english",
                "transcript_original": "{base_name} original transcript", 
                "transcript_translated": "{base_name} transcript translated into english"
            },
            "es": {
                "video": "{base_name} traducido al español",
                "subtitles_original": "{base_name} subtítulos originales",
                "subtitles_translated": "{base_name} subtítulos traducidos al español",
                "transcript_original": "{base_name} transcripción original",
                "transcript_translated": "{base_name} transcripción traducida al español"
            },
            "fr": {
                "video": "{base_name} traduit en français",
                "subtitles_original": "{base_name} sous-titres originaux", 
                "subtitles_translated": "{base_name} sous-titres traduits en français",
                "transcript_original": "{base_name} transcription originale",
                "transcript_translated": "{base_name} transcription traduite en français"
            }
        }
        
        # Language name mapping
        lang_names = {
            "it": {"it": "italiano", "en": "italian", "es": "italiano", "fr": "italien"},
            "en": {"it": "inglese", "en": "english", "es": "inglés", "fr": "anglais"},
            "es": {"it": "spagnolo", "en": "spanish", "es": "español", "fr": "espagnol"},
            "fr": {"it": "francese", "en": "french", "es": "francés", "fr": "français"},
            "de": {"it": "tedesco", "en": "german", "es": "alemán", "fr": "allemand"},
            "pt": {"it": "portoghese", "en": "portuguese", "es": "portugués", "fr": "portugais"}
        }
        
        # Get template for user language (fallback to Italian)
        template_set = templates.get(user_language, templates["it"])
        template = template_set.get(file_type, "{base_name} {file_type}")
        
        # Replace target language in template  
        if target_language in lang_names and target_language != user_language:
            target_lang_name = lang_names[target_language].get(user_language, target_language)
            # Replace language placeholders based on user interface language
            if user_language == "it":
                template = template.replace("italiano", target_lang_name)
            elif user_language == "en":
                template = template.replace("english", target_lang_name)
            elif user_language == "es":  
                template = template.replace("español", target_lang_name)
            elif user_language == "fr":
                template = template.replace("français", target_lang_name)
        
        return template.format(base_name=base_name)
    
    async def _export_video_chunked(self, final_clip, output_path: Path, task_id: str, chunk_duration: int = 60):
        """
        Export video in chunks to handle long videos efficiently
        chunk_duration: Duration of each chunk in seconds (default 1 minute)
        """
        try:
            total_duration = final_clip.duration
            logger.info(f"Processing video with chunked export: {total_duration}s in {chunk_duration}s chunks")
            
            # Safety check for duration consistency
            if hasattr(final_clip, 'audio') and final_clip.audio and hasattr(final_clip.audio, 'duration'):
                audio_duration = final_clip.audio.duration
                if abs(total_duration - audio_duration) > 1.0:  # Allow 1 second tolerance
                    logger.warning(f"Duration mismatch: video={total_duration}s, audio={audio_duration}s")
                    total_duration = min(total_duration, audio_duration)  # Use shorter duration
                    logger.info(f"Using corrected duration: {total_duration}s")
            
            if total_duration <= chunk_duration:
                # Video is short enough, use normal export
                await self._update_progress(task_id, 75, "Exporting video...")
                final_clip.write_videofile(
                    str(output_path),
                    codec='libx264',
                    audio_codec='aac',
                    preset='ultrafast',
                    threads=0,  # Use all cores
                    ffmpeg_params=[
                        '-crf', '23',  # High quality
                        '-movflags', '+faststart'
                    ],
                    temp_audiofile='temp-audio.m4a',
                    remove_temp=True,
                    logger=None
                )
                return output_path
            
            # Create chunks
            num_chunks = int(np.ceil(total_duration / chunk_duration))
            chunk_files = []
            
            await self._update_progress(task_id, 70, f"Processing {num_chunks} chunks...")
            
            for i in range(num_chunks):
                start_time = i * chunk_duration
                end_time = min((i + 1) * chunk_duration, total_duration)
                
                # Create chunk
                chunk_clip = final_clip.subclipped(start_time, end_time)
                chunk_path = self.output_dir / f"chunk_{i:03d}_{task_id}.mp4"
                
                progress = 70 + (i / num_chunks) * 20  # 70-90% for chunks
                await self._update_progress(task_id, int(progress), f"Processing chunk {i+1}/{num_chunks}...")
                
                # Export chunk with optimized settings for speed
                chunk_clip.write_videofile(
                    str(chunk_path),
                    codec='libx264',
                    audio_codec='aac',
                    preset='ultrafast',  # Fastest encoding
                    threads=0,  # Use all available cores
                    ffmpeg_params=[
                        '-crf', '23',  # Quality setting (23 = high quality)
                        '-movflags', '+faststart',  # Web optimization
                        '-tune', 'film'  # Optimize for film content
                    ],
                    logger=None,
                    temp_audiofile=f'temp-audio-{i}.m4a',
                    remove_temp=True
                )
                
                chunk_files.append(str(chunk_path))
                chunk_clip.close()
                
                # Verify chunk was created
                if chunk_path.exists():
                    logger.info(f"✅ Chunk {i+1}/{num_chunks} created: {chunk_path.stat().st_size} bytes")
                else:
                    logger.error(f"❌ Failed to create chunk {i+1}/{num_chunks}: {chunk_path}")
                
                # Force garbage collection
                import gc
                gc.collect()
            
            # Verify all chunks were created successfully
            missing_chunks = [f for f in chunk_files if not Path(f).exists()]
            if missing_chunks:
                raise Exception(f"Missing chunk files: {missing_chunks}")
            
            # Concatenate chunks using ffmpeg (much faster than MoviePy)
            await self._update_progress(task_id, 90, "Merging chunks...")
            await self._concatenate_chunks_ffmpeg(chunk_files, output_path)
            
            # Cleanup chunk files
            for chunk_file in chunk_files:
                try:
                    Path(chunk_file).unlink()
                except:
                    pass
                    
            logger.info(f"Chunked export completed: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Chunked export failed: {str(e)}")
            raise
    
    async def _concatenate_chunks_ffmpeg(self, chunk_files: List[str], output_path: Path):
        """Use ffmpeg to concatenate video chunks efficiently"""
        import subprocess
        import tempfile
        
        # Create file list for ffmpeg concat with absolute paths
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            for chunk_file in chunk_files:
                # Convert to absolute path and escape for ffmpeg
                abs_path = Path(chunk_file).absolute()
                f.write(f"file '{abs_path}'\n")
            concat_list = f.name
        
        try:
            # Use ffmpeg concat with re-encoding for compatibility
            cmd = [
                'ffmpeg', '-y',  # -y to overwrite output file
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_list,
                '-c:v', 'libx264',  # Re-encode video for compatibility
                '-c:a', 'aac',      # Re-encode audio
                '-preset', 'ultrafast',
                '-crf', '23',
                str(output_path)
            ]
            
            # Run ffmpeg in executor to not block
            loop = asyncio.get_event_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(cmd, capture_output=True, text=True, check=True)
            )
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg concatenation failed: {e}")
            logger.error(f"FFmpeg stdout: {e.stdout}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            raise Exception(f"Video concatenation failed: {e.stderr}")
            
        except Exception as e:
            logger.error(f"Concatenation error: {str(e)}")
            raise
            
        finally:
            # Cleanup concat list file
            try:
                Path(concat_list).unlink()
            except:
                pass