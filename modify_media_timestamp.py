#!/usr/bin/env python3
import os
import time
import piexif
import argparse
from datetime import datetime, timedelta

def validate_date(date_str):
    """
    Validate the input date string and return datetime object.
    
    Args:
        date_str (str): Date string in YYYY-mm-dd format
    
    Returns:
        datetime: Validated datetime object or None if invalid
    """
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d')
        # Check if date is not in the future and not too old (e.g., not before 2000)
        if date > datetime.now():
            print(f"Error: Date {date_str} is in the future")
            return None
        if date < datetime(2000, 1, 1):
            print(f"Error: Date {date_str} is too old (before 2000)")
            return None
        return date
    except ValueError:
        print(f"Error: Invalid date format. Please use YYYY-mm-dd format (e.g., 2024-03-20)")
        return None

def set_media_time(media_path, media_date):
    """
    Set the timestamp of a media file to the specified date.
    
    Args:
        media_path (str): Path to the media file
        media_date (str): Date in YYYY-mm-dd format
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Validate input date
    date = validate_date(media_date)
    if not date:
        return False
    
    success = False
    media_time = date.strftime('%Y:%m:%d 12:00:00')
    
    # Handle images with EXIF data
    image_extensions = ('.JPG', '.JPEG', '.PNG', '.TIFF', '.TIF')
    if media_path.upper().endswith(image_extensions):
        try:
            exif_dict = piexif.load(media_path)
            exif_dict['0th'][piexif.ImageIFD.DateTime] = media_time
            exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = media_time
            exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = media_time
            exif_bytes = piexif.dump(exif_dict)
            piexif.insert(exif_bytes, media_path)
            success = True
            print(f"Updated EXIF data for {os.path.basename(media_path)}")
        except Exception as e:
            print(f"Warning: Could not update EXIF data: {e}")
    
    # Update file modification time for all media types
    try:
        mod_time = time.mktime(date.replace(hour=12).timetuple())
        os.utime(media_path, (mod_time, mod_time))
        success = True
        print(f"Updated file timestamp for {os.path.basename(media_path)}")
    except Exception as e:
        print(f"Error updating file timestamp: {e}")
    
    return success

def main():
    parser = argparse.ArgumentParser(
        description='Modify the timestamp of media files (images and videos)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('file', help='Path to the media file')
    parser.add_argument('date', help='New date in YYYY-mm-dd format (e.g., 2024-03-20)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show detailed information')
    
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist.")
        return
    
    # Process the file
    if set_media_time(args.file, args.date):
        print(f"Successfully updated timestamp for {os.path.basename(args.file)} to {args.date}")
    else:
        print("Failed to update timestamp")

if __name__ == "__main__":
    main() 