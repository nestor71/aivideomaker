from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, TextClip
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from pathlib import Path
from typing import Union, Optional
from app.core.logger import logger
import tempfile


class WatermarkService:
    """Service for adding watermarks to videos (free tier)."""
    
    def __init__(self):
        self.default_watermark_text = "Created with AIVideoMaker - Free Tier"
        self.watermark_opacity = 0.7
        self.watermark_position = ("right", "bottom")
        
    async def add_watermark_to_video(
        self,
        video_path: Path,
        output_path: Path,
        watermark_type: str = "text",
        watermark_content: Optional[str] = None,
        opacity: float = 0.7,
        position: tuple = ("right", "bottom")
    ) -> Path:
        """
        Add watermark to video.
        
        Args:
            video_path: Path to input video
            output_path: Path for output video
            watermark_type: "text" or "image"
            watermark_content: Text content or path to image
            opacity: Watermark opacity (0-1)
            position: Position tuple ("left"/"center"/"right", "top"/"center"/"bottom")
            
        Returns:
            Path to watermarked video
        """
        try:
            logger.info(f"Adding watermark to video: {video_path}")
            
            # Load main video
            main_clip = VideoFileClip(str(video_path))
            
            if watermark_type == "text":
                watermark_clip = self._create_text_watermark(
                    text=watermark_content or self.default_watermark_text,
                    duration=main_clip.duration,
                    video_size=main_clip.size
                )
            elif watermark_type == "image":
                if not watermark_content or not Path(watermark_content).exists():
                    # Fall back to text watermark if image not found
                    watermark_clip = self._create_text_watermark(
                        text=self.default_watermark_text,
                        duration=main_clip.duration,
                        video_size=main_clip.size
                    )
                else:
                    watermark_clip = self._create_image_watermark(
                        image_path=watermark_content,
                        duration=main_clip.duration,
                        video_size=main_clip.size
                    )
            else:
                raise ValueError(f"Unsupported watermark type: {watermark_type}")
            
            # Set opacity and position
            watermark_clip = watermark_clip.with_opacity(opacity)
            watermark_clip = watermark_clip.with_position(position)
            
            # Composite video with watermark
            final_clip = CompositeVideoClip([main_clip, watermark_clip])
            
            # Write output
            final_clip.write_videofile(
                str(output_path),
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True,
                logger=None  # Suppress moviepy logs
            )
            
            # Clean up
            main_clip.close()
            watermark_clip.close()
            final_clip.close()
            
            logger.info(f"Watermark added successfully: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error adding watermark to video {video_path}: {e}")
            raise Exception(f"Watermark processing failed: {str(e)}")
    
    def _create_text_watermark(
        self, 
        text: str, 
        duration: float, 
        video_size: tuple,
        font_size: Optional[int] = None
    ) -> TextClip:
        """Create text watermark clip."""
        try:
            # Calculate font size based on video dimensions
            if font_size is None:
                video_width = video_size[0]
                font_size = max(16, min(32, video_width // 40))
            
            # Create text clip
            text_clip = TextClip(
                text,
                fontsize=font_size,
                color='white',
                font='Arial-Bold',  # Use a common font
                stroke_color='black',
                stroke_width=1
            ).with_duration(duration)
            
            return text_clip
            
        except Exception as e:
            logger.error(f"Error creating text watermark: {e}")
            # Fallback to simple text without stroke
            return TextClip(
                text,
                fontsize=font_size or 24,
                color='white'
            ).with_duration(duration)
    
    def _create_image_watermark(
        self, 
        image_path: str, 
        duration: float, 
        video_size: tuple,
        max_size_percent: float = 0.15
    ) -> ImageClip:
        """Create image watermark clip."""
        try:
            # Load and resize image
            with Image.open(image_path) as img:
                # Convert to RGBA if needed
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Calculate target size (percentage of video size)
                video_width, video_height = video_size
                max_width = int(video_width * max_size_percent)
                max_height = int(video_height * max_size_percent)
                
                # Maintain aspect ratio
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                    temp_path = temp_file.name
                    img.save(temp_path, 'PNG')
            
            # Create ImageClip
            image_clip = ImageClip(temp_path, duration=duration)
            
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            
            return image_clip
            
        except Exception as e:
            logger.error(f"Error creating image watermark: {e}")
            # Fallback to text watermark
            return self._create_text_watermark(
                "AIVideoMaker", 
                duration, 
                video_size
            )
    
    async def create_branded_watermark(
        self, 
        duration: float, 
        video_size: tuple
    ) -> ImageClip:
        """Create branded AIVideoMaker watermark."""
        try:
            # Create a simple branded watermark using PIL
            watermark_width = min(200, video_size[0] // 4)
            watermark_height = 60
            
            # Create image
            img = Image.new('RGBA', (watermark_width, watermark_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            
            # Try to use a nice font
            try:
                # Try to load a system font
                font = ImageFont.truetype("Arial.ttf", 16)
            except:
                try:
                    # Fallback to default font
                    font = ImageFont.load_default()
                except:
                    font = None
            
            # Draw background
            draw.rounded_rectangle(
                [(5, 5), (watermark_width - 5, watermark_height - 5)],
                radius=10,
                fill=(0, 0, 0, 128)  # Semi-transparent black
            )
            
            # Draw text
            text = "AIVideoMaker"
            if font:
                # Get text size for centering
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                
                x = (watermark_width - text_width) // 2
                y = (watermark_height - text_height) // 2
                
                draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)
            else:
                # Simple text without font
                draw.text((10, 20), text, fill=(255, 255, 255, 255))
            
            # Add small "Free" badge
            draw.rounded_rectangle(
                [(watermark_width - 40, watermark_height - 20), (watermark_width - 5, watermark_height - 5)],
                radius=5,
                fill=(255, 100, 100, 200)  # Red badge
            )
            draw.text((watermark_width - 35, watermark_height - 18), "Free", fill=(255, 255, 255, 255))
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                temp_path = temp_file.name
                img.save(temp_path, 'PNG')
            
            # Create ImageClip
            watermark_clip = ImageClip(temp_path, duration=duration)
            
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
            
            return watermark_clip
            
        except Exception as e:
            logger.error(f"Error creating branded watermark: {e}")
            # Fallback to text watermark
            return self._create_text_watermark(
                "AIVideoMaker - Free Tier",
                duration,
                video_size
            )
    
    async def should_add_watermark(self, tier: str, user_preference: bool = True) -> bool:
        """Determine if watermark should be added based on tier and user preference."""
        if tier == "free":
            return True  # Always add watermark for free tier
        elif tier == "premium":
            return False  # Never add watermark for premium tier (unless requested)
        
        return user_preference  # Default behavior


# Global instance
watermark_service = WatermarkService()