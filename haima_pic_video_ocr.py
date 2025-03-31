#!/usr/bin/env python3
import datetime
import os
import time
import logging
from pathlib import Path
from typing import List, Tuple, Optional

import easyocr
import piexif
import pytesseract
from PIL import Image
import cv2
import ddddocr

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_PIC_WIDTH = 2560
PIC_2560_CROP_BOX = (16, 38, 349, 89)
MEDIA_FOLDER = Path('./海马爸比')
TIME_FOLDER = Path('./时间图片')
TESSERACT_CONFIG = '-c tessedit_char_whitelist=-0123456789 --psm 6'
VALID_DATE_RANGE = {
    'start': datetime.datetime(2023, 9, 17),
    'end': datetime.datetime.now()
}

# Initialize OCR engines
easyocr_reader = easyocr.Reader(['en'])
dddd_ocr = ddddocr.DdddOcr()
dddd_ocr_beta = ddddocr.DdddOcr(beta=True)

class MediaProcessor:
    def __init__(self):
        self._setup_folders()
    
    def _setup_folders(self) -> None:
        """Create necessary folders if they don't exist."""
        MEDIA_FOLDER.mkdir(exist_ok=True)
        TIME_FOLDER.mkdir(exist_ok=True)
    
    def set_media_time(self, media_path: Path, media_date: str) -> bool:
        """
        Set the timestamp of a media file.
        
        Args:
            media_path: Path to the media file
            media_date: Date in YYYY-mm-dd format
        
        Returns:
            bool: True if successful, False otherwise
        """
        success = False
        media_time = media_date.replace('-', ':') + " 12:00:00"
        
        # Update EXIF data for images
        if media_path.suffix.upper() in ['.JPG', '.JPEG']:
            try:
                exif_dict = piexif.load(str(media_path))
                exif_dict['0th'][piexif.ImageIFD.DateTime] = media_time
                exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = media_time
                exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = media_time
                exif_bytes = piexif.dump(exif_dict)
                piexif.insert(exif_bytes, str(media_path))
                success = True
            except Exception as e:
                logger.warning(f"Failed to update EXIF data for {media_path}: {e}")
        
        # Update file modification time
        try:
            mod_time = time.mktime(time.strptime(media_time, '%Y:%m:%d %H:%M:%S'))
            os.utime(media_path, (mod_time, mod_time))
            success = True
        except Exception as e:
            logger.error(f"Failed to update file timestamp for {media_path}: {e}")
        
        return success
    
    def change_media_name(self, media_path: Path, media_date: str, prefix: str) -> None:
        """
        Rename media file with date and prefix.
        
        Args:
            media_path: Path to the media file
            media_date: Date in YYYY-mm-dd format
            prefix: Prefix for the new filename
        """
        suffix = media_path.suffix
        count = 1
        new_name = f"{prefix}{media_date}{suffix}"
        
        while (MEDIA_FOLDER / new_name).exists():
            new_name = f"{prefix}{media_date}_{count}{suffix}"
            count += 1
        
        new_path = MEDIA_FOLDER / new_name
        media_path.rename(new_path)
        logger.info(f"Renamed {media_path.name} to {new_name}")

    def crop_pic(self, pic_path: Path) -> Path:
        """
        Crop image to focus on the time area.
        
        Args:
            pic_path: Path to the original image
        
        Returns:
            Path: Path to the cropped image
        """
        new_pic_path = TIME_FOLDER / pic_path.name
        pic_origin = Image.open(pic_path)
        pic_width = pic_origin.size[0]
        
        # Calculate crop box based on image width
        if pic_width != DEFAULT_PIC_WIDTH:
            pic_crop_box = tuple(int((pic_width / DEFAULT_PIC_WIDTH) * coord) for coord in PIC_2560_CROP_BOX)
        else:
            pic_crop_box = PIC_2560_CROP_BOX
        
        pic_new = pic_origin.crop(pic_crop_box)
        pic_new.save(new_pic_path)
        return new_pic_path

    def upgrade_pic_date(self, pic_date: str) -> str:
        """
        Clean and standardize date string.
        
        Args:
            pic_date: Raw date string from OCR
        
        Returns:
            str: Cleaned date string
        """
        return ''.join(filter(str.isdigit, pic_date.strip().replace('-', '').replace('z', '2')))

    def check_date_valid(self, pic_date: str) -> bool:
        """
        Validate if the date is within acceptable range.
        
        Args:
            pic_date: Date string in YYYY-mm-dd format
        
        Returns:
            bool: True if date is valid, False otherwise
        """
        try:
            date = datetime.datetime.strptime(pic_date, '%Y-%m-%d')
            return VALID_DATE_RANGE['start'] < date <= VALID_DATE_RANGE['end']
        except ValueError:
            return False

    def ocr_haima_pic_to_string(self, pic_path: Path) -> Optional[str]:
        """
        Perform OCR on image to extract date.
        
        Args:
            pic_path: Path to the image
        
        Returns:
            Optional[str]: Extracted date in YYYY-mm-dd format or None if failed
        """
        result_list = []
        
        # EasyOCR
        try:
            easyocr_result = easyocr_reader.readtext(str(pic_path), detail=0, allowlist='-0123456789')
            if easyocr_result:
                easy_pic_date = self.upgrade_pic_date(easyocr_result[0])
                try:
                    easy_pic_date = datetime.datetime.strptime(easy_pic_date, "%Y%m%d").strftime('%Y-%m-%d')
                    if self.check_date_valid(easy_pic_date):
                        result_list.append(easy_pic_date)
                except ValueError:
                    pass
        except Exception as e:
            logger.warning(f"EasyOCR failed: {e}")
        
        # Tesseract
        try:
            tesseract_pic_date = pytesseract.image_to_string(Image.open(pic_path), config=TESSERACT_CONFIG, lang='eng')
            tesseract_pic_date = self.upgrade_pic_date(tesseract_pic_date)
            try:
                tesseract_pic_date = datetime.datetime.strptime(tesseract_pic_date, "%Y%m%d").strftime('%Y-%m-%d')
                if self.check_date_valid(tesseract_pic_date):
                    result_list.append(tesseract_pic_date)
            except ValueError:
                pass
        except Exception as e:
            logger.warning(f"Tesseract failed: {e}")
        
        # DdddOCR
        try:
            with open(pic_path, "rb") as f:
                image = f.read()
            dddd_pic_date = self.upgrade_pic_date(dddd_ocr.classification(image))
            try:
                dddd_pic_date = datetime.datetime.strptime(dddd_pic_date, "%Y%m%d").strftime('%Y-%m-%d')
                if self.check_date_valid(dddd_pic_date):
                    result_list.append(dddd_pic_date)
            except ValueError:
                pass
        except Exception as e:
            logger.warning(f"DdddOCR failed: {e}")
        
        # DdddOCR Beta
        try:
            dddd_beta_pic_date = self.upgrade_pic_date(dddd_ocr_beta.classification(image))
            try:
                dddd_beta_pic_date = datetime.datetime.strptime(dddd_beta_pic_date, "%Y%m%d").strftime('%Y-%m-%d')
                if self.check_date_valid(dddd_beta_pic_date):
                    result_list.append(dddd_beta_pic_date)
            except ValueError:
                pass
        except Exception as e:
            logger.warning(f"DdddOCR Beta failed: {e}")
        
        if not result_list:
            return None
        
        # Use majority voting for final result
        result_set = set(result_list)
        if len(result_set) != len(result_list):
            result_dict = {date: result_list.count(date) for date in result_set}
            result_list = sorted(result_dict.items(), key=lambda x: x[1], reverse=True)
            logger.info(f"OCR results - majority voting: {result_list}")
            return result_list[0][0]
        else:
            logger.info(f"OCR results - all agree: {result_list}")
            return result_list[0]

    def process_media_files(self) -> None:
        """Process all media files in the media folder."""
        files = list(MEDIA_FOLDER.glob('*'))
        pics = [f for f in files if f.suffix.upper() in ['.JPG', '.JPEG', '.PNG'] and not f.name.startswith('IMG_HM_')]
        videos = [f for f in files if f.suffix.upper() == '.MP4' and not f.name.startswith('V_HM_')]
        
        if not pics and not videos:
            logger.info("No new media files to process")
            return
        
        logger.info(f"Found {len(pics)} images and {len(videos)} videos to process")
        
        # Process images
        for pic_path in pics:
            logger.info(f"Processing image: {pic_path.name}")
            try:
                orc_pic_path = self.crop_pic(pic_path)
                pic_date = self.ocr_haima_pic_to_string(orc_pic_path)
                
                if pic_date and self.set_media_time(pic_path, pic_date):
                    self.change_media_name(pic_path, pic_date, 'IMG_HM_')
                    logger.info(f"Successfully processed {pic_path.name}")
                else:
                    logger.warning(f"Failed to process {pic_path.name}")
            except Exception as e:
                logger.error(f"Error processing {pic_path.name}: {e}")
        
        # Process videos
        for video_path in videos:
            logger.info(f"Processing video: {video_path.name}")
            try:
                save_temp_pic_path = TIME_FOLDER / f"{video_path.stem}.jpg"
                
                # Extract first frame
                cap = cv2.VideoCapture(str(video_path))
                ret, frame = cap.read()
                if not ret:
                    logger.error(f"Failed to read video: {video_path.name}")
                    continue
                cv2.imwrite(str(save_temp_pic_path), frame)
                cap.release()
                
                # Process frame
                orc_pic_path = self.crop_pic(save_temp_pic_path)
                video_date = self.ocr_haima_pic_to_string(orc_pic_path)
                
                if video_date and self.set_media_time(video_path, video_date):
                    self.change_media_name(video_path, video_date, 'V_HM_')
                    logger.info(f"Successfully processed {video_path.name}")
                else:
                    logger.warning(f"Failed to process {video_path.name}")
            except Exception as e:
                logger.error(f"Error processing {video_path.name}: {e}")

def main():
    """Main entry point."""
    try:
        processor = MediaProcessor()
        processor.process_media_files()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
