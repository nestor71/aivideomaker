from pydantic import BaseModel
from typing import Optional, Dict, List

class VideoSettings(BaseModel):
    logo_overlay: bool = False
    cta_overlay: bool = False
    transcription: bool = False
    translation: bool = False
    thumbnail_generation: bool = False
    metadata_generation: bool = False
    youtube_upload: bool = False

class LogoSettings(BaseModel):
    position: str = "top_right"
    size: int = 10
    start_time: float = 0.0
    end_time: Optional[float] = None

class CTASettings(BaseModel):
    position: str = "bottom_right"
    size: int = 20
    start_time: float = 0.0
    end_time: Optional[float] = None
    chroma_key: bool = False
    chroma_color: str = "#00ff00"

class ThumbnailSettings(BaseModel):
    auto_generate: bool = True
    custom_text: str = ""
    font_size: int = 48
    text_color: str = "#ffffff"
    custom_images: List[str] = []

class MetadataSettings(BaseModel):
    auto_generate: bool = True
    global_words: List[str] = []
    global_hashtags: List[str] = []
    global_tags: List[str] = []

class YouTubeSettings(BaseModel):
    connected: bool = False
    channel_id: Optional[str] = None
    privacy: str = "private"
    category: str = "22"

class AudioTranslationSettings(BaseModel):
    original_language: str = "auto"
    target_language: str = "it"
    replace_audio: bool = True
    keep_original: bool = False

class FileOutputSettings(BaseModel):
    save_video: bool = True
    save_original_transcript: bool = True
    save_translated_transcript: bool = True
    save_original_subtitles: bool = True
    save_translated_subtitles: bool = True
    save_translated_audio: bool = False

class UserSettings(BaseModel):
    language: str = "en"
    video_settings: VideoSettings = VideoSettings()
    logo_settings: LogoSettings = LogoSettings()
    cta_settings: CTASettings = CTASettings()
    thumbnail_settings: ThumbnailSettings = ThumbnailSettings()
    metadata_settings: MetadataSettings = MetadataSettings()
    youtube_settings: YouTubeSettings = YouTubeSettings()
    audio_translation_settings: AudioTranslationSettings = AudioTranslationSettings()
    file_output_settings: FileOutputSettings = FileOutputSettings()