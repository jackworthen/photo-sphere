#!/usr/bin/env python3
"""
PhotoSphere Application
A robust application for organizing and cataloging photography with metadata extraction,
tagging, categorization, and search capabilities.

Requirements:
pip install PySide6 Pillow exifread
"""

import sys
import os
import sqlite3
import json
import shutil
import platform
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem,
    QLabel, QLineEdit, QPushButton, QTextEdit, QScrollArea, QFrame,
    QDialog, QDialogButtonBox, QFormLayout, QComboBox, QMessageBox,
    QProgressBar, QStatusBar, QMenuBar, QMenu, QFileDialog, QTabWidget,
    QGroupBox, QCheckBox, QSpinBox, QDateEdit, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QDate, QTimer, QPoint
from PySide6.QtGui import QPixmap, QIcon, QDragEnterEvent, QDropEvent, QAction, QTransform

from PIL import Image
from PIL.ExifTags import TAGS
import exifread


def get_app_data_dir() -> Path:
    """Get the OS-specific application data directory."""
    app_name = "PhotoSphere"
    
    system = platform.system()
    
    if system == "Windows":
        # Windows: %APPDATA%\PhotoSphere
        app_data = os.environ.get('APPDATA')
        if app_data:
            return Path(app_data) / app_name
        else:
            return Path.home() / "AppData" / "Roaming" / app_name
    
    elif system == "Darwin":  # macOS
        # macOS: ~/Library/Application Support/PhotoSphere
        return Path.home() / "Library" / "Application Support" / app_name
    
    else:  # Linux and other Unix-like systems
        # Linux: ~/.local/share/PhotoSphere
        xdg_data_home = os.environ.get('XDG_DATA_HOME')
        if xdg_data_home:
            return Path(xdg_data_home) / app_name
        else:
            return Path.home() / ".local" / "share" / app_name


class DatabaseManager:
    """Handles all database operations for the PhotoSphere catalog."""
    
    def __init__(self, db_name: str = "photo_catalog.db"):
        # Get OS-specific application data directory
        self.app_data_dir = get_app_data_dir()
        
        # Create the directory if it doesn't exist
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Set the full database path
        self.db_path = self.app_data_dir / db_name
        
        print(f"Database location: {self.db_path}")
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            
            # Photos table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL UNIQUE,
                    file_size INTEGER,
                    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    date_taken TIMESTAMP,
                    camera_make TEXT,
                    camera_model TEXT,
                    lens_model TEXT,
                    focal_length REAL,
                    aperture REAL,
                    shutter_speed TEXT,
                    iso INTEGER,
                    flash TEXT,
                    orientation INTEGER,
                    width INTEGER,
                    height INTEGER,
                    gps_latitude REAL,
                    gps_longitude REAL,
                    gps_altitude REAL,
                    gps_location_name TEXT,
                    metadata_json TEXT
                )
            ''')
            
            # Check if GPS columns exist and add them if they don't (migration)
            cursor.execute("PRAGMA table_info(photos)")
            columns = [column[1] for column in cursor.fetchall()]
            
            gps_columns = [
                ('gps_latitude', 'REAL'),
                ('gps_longitude', 'REAL'),
                ('gps_altitude', 'REAL'),
                ('gps_location_name', 'TEXT')
            ]
            
            for column_name, column_type in gps_columns:
                if column_name not in columns:
                    try:
                        cursor.execute(f"ALTER TABLE photos ADD COLUMN {column_name} {column_type}")
                        print(f"Added column {column_name} to photos table")
                    except Exception as e:
                        print(f"Error adding column {column_name}: {e}")
            
            # Categories table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    color TEXT DEFAULT '#3498db'
                )
            ''')
            
            # Tags table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT DEFAULT '#27ae60'
                )
            ''')
            
            # Photo categories relationship
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS photo_categories (
                    photo_id INTEGER,
                    category_id INTEGER,
                    PRIMARY KEY (photo_id, category_id),
                    FOREIGN KEY (photo_id) REFERENCES photos (id) ON DELETE CASCADE,
                    FOREIGN KEY (category_id) REFERENCES categories (id) ON DELETE CASCADE
                )
            ''')
            
            # Photo tags relationship
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS photo_tags (
                    photo_id INTEGER,
                    tag_id INTEGER,
                    PRIMARY KEY (photo_id, tag_id),
                    FOREIGN KEY (photo_id) REFERENCES photos (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()
    
    def add_photo(self, photo_data: Dict) -> int:
        """Add a new photo to the database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO photos (
                    filename, filepath, file_size, date_taken, camera_make,
                    camera_model, lens_model, focal_length, aperture,
                    shutter_speed, iso, flash, orientation, width, height,
                    gps_latitude, gps_longitude, gps_altitude, gps_location_name,
                    metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                photo_data.get('filename'),
                photo_data.get('filepath'),
                photo_data.get('file_size'),
                photo_data.get('date_taken'),
                photo_data.get('camera_make'),
                photo_data.get('camera_model'),
                photo_data.get('lens_model'),
                photo_data.get('focal_length'),
                photo_data.get('aperture'),
                photo_data.get('shutter_speed'),
                photo_data.get('iso'),
                photo_data.get('flash'),
                photo_data.get('orientation'),
                photo_data.get('width'),
                photo_data.get('height'),
                photo_data.get('gps_latitude'),
                photo_data.get('gps_longitude'),
                photo_data.get('gps_altitude'),
                photo_data.get('gps_location_name'),
                json.dumps(photo_data.get('metadata', {}))
            ))
            return cursor.lastrowid
    
    def get_database_info(self) -> Dict[str, str]:
        """Get information about the database location and size."""
        info = {
            'path': str(self.db_path),
            'directory': str(self.app_data_dir),
            'exists': self.db_path.exists(),
            'size': '0 KB'
        }
        
        if info['exists']:
            size_bytes = self.db_path.stat().st_size
            if size_bytes < 1024:
                info['size'] = f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                info['size'] = f"{size_bytes / 1024:.1f} KB"
            else:
                info['size'] = f"{size_bytes / (1024 * 1024):.1f} MB"
        
        return info
    
    def get_photos(self, filters: Dict = None) -> List[Dict]:
        """Retrieve photos with optional filtering."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM photos"
            params = []
            
            if filters:
                conditions = []
                if filters.get('category_id'):
                    conditions.append('''
                        id IN (SELECT photo_id FROM photo_categories WHERE category_id = ?)
                    ''')
                    params.append(filters['category_id'])
                
                if filters.get('tag_id'):
                    conditions.append('''
                        id IN (SELECT photo_id FROM photo_tags WHERE tag_id = ?)
                    ''')
                    params.append(filters['tag_id'])
                
                if filters.get('search_term'):
                    conditions.append('filename LIKE ?')
                    params.append(f"%{filters['search_term']}%")
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY date_added DESC"
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def add_category(self, name: str, description: str = "", color: str = "#3498db") -> int:
        """Add a new category."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO categories (name, description, color) VALUES (?, ?, ?)",
                (name, description, color)
            )
            return cursor.lastrowid
    
    def add_tag(self, name: str, color: str = "#27ae60") -> int:
        """Add a new tag."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tags (name, color) VALUES (?, ?)",
                (name, color)
            )
            return cursor.lastrowid
    
    def get_categories(self) -> List[Dict]:
        """Get all categories."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM categories ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
    
    def get_tags(self) -> List[Dict]:
        """Get all tags."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tags ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
    
    def assign_photo_category(self, photo_id: int, category_id: int):
        """Assign a category to a photo."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO photo_categories (photo_id, category_id) VALUES (?, ?)",
                (photo_id, category_id)
            )
    
    def assign_photo_tag(self, photo_id: int, tag_id: int):
        """Assign a tag to a photo."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)",
                (photo_id, tag_id)
            )
    
    def delete_photo(self, photo_id: int) -> bool:
        """Delete a photo from the database."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Delete photo relationships first (due to foreign key constraints)
                cursor.execute("DELETE FROM photo_categories WHERE photo_id = ?", (photo_id,))
                cursor.execute("DELETE FROM photo_tags WHERE photo_id = ?", (photo_id,))
                
                # Delete the photo record
                cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
                
                # Check if deletion was successful
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting photo: {e}")
            return False
    
    def get_photo_by_id(self, photo_id: int) -> Optional[Dict]:
        """Get a specific photo by ID."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def delete_category(self, category_id: int) -> bool:
        """Delete a category and all its relationships."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Delete photo-category relationships first
                cursor.execute("DELETE FROM photo_categories WHERE category_id = ?", (category_id,))
                
                # Delete the category
                cursor.execute("DELETE FROM categories WHERE id = ?", (category_id,))
                
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting category: {e}")
            return False
    
    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag and all its relationships."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Delete photo-tag relationships first
                cursor.execute("DELETE FROM photo_tags WHERE tag_id = ?", (tag_id,))
                
                # Delete the tag
                cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
                
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error deleting tag: {e}")
            return False
    
    def get_category_by_id(self, category_id: int) -> Optional[Dict]:
        """Get a specific category by ID."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def get_tag_by_id(self, tag_id: int) -> Optional[Dict]:
        """Get a specific tag by ID."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tags WHERE id = ?", (tag_id,))
            result = cursor.fetchone()
            return dict(result) if result else None
    
    def count_photos_by_category(self, category_id: int) -> int:
        """Count how many photos are in a specific category."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM photo_categories WHERE category_id = ?", (category_id,))
            return cursor.fetchone()[0]
    
    def count_photos_by_tag(self, tag_id: int) -> int:
        """Count how many photos have a specific tag."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM photo_tags WHERE tag_id = ?", (tag_id,))
            return cursor.fetchone()[0]
    
    def get_photo_categories(self, photo_id: int) -> List[Dict]:
        """Get all categories assigned to a photo."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.* FROM categories c 
                JOIN photo_categories pc ON c.id = pc.category_id 
                WHERE pc.photo_id = ?
                ORDER BY c.name
            ''', (photo_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_photo_tags(self, photo_id: int) -> List[Dict]:
        """Get all tags assigned to a photo."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.* FROM tags t 
                JOIN photo_tags pt ON t.id = pt.tag_id 
                WHERE pt.photo_id = ?
                ORDER BY t.name
            ''', (photo_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def remove_photo_category(self, photo_id: int, category_id: int) -> bool:
        """Remove a category from a photo."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM photo_categories WHERE photo_id = ? AND category_id = ?",
                    (photo_id, category_id)
                )
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing category from photo: {e}")
            return False
    
    def remove_photo_tag(self, photo_id: int, tag_id: int) -> bool:
        """Remove a tag from a photo."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM photo_tags WHERE photo_id = ? AND tag_id = ?",
                    (photo_id, tag_id)
                )
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error removing tag from photo: {e}")
            return False


class MetadataExtractor:
    """Extracts metadata from image files."""
    
    @staticmethod
    def convert_exif_value(value):
        """Convert EXIF values to JSON-serializable types."""
        if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            # Handle tuples, lists, and other iterables
            try:
                return [MetadataExtractor.convert_exif_value(item) for item in value]
            except:
                return str(value)
        elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
            # Handle IFDRational and similar fraction types
            try:
                if value.denominator == 0:
                    return float('inf') if value.numerator > 0 else float('-inf')
                return float(value.numerator) / float(value.denominator)
            except:
                return str(value)
        elif isinstance(value, bytes):
            # Handle byte strings
            try:
                return value.decode('utf-8', errors='ignore')
            except:
                return str(value)
        elif isinstance(value, (int, float, str, bool, type(None))):
            # Already JSON serializable
            return value
        else:
            # Convert everything else to string
            return str(value)
    
    @staticmethod
    def convert_gps_coordinate(coord_tuple, ref):
        """Convert GPS coordinate from EXIF format to decimal degrees."""
        if not coord_tuple or len(coord_tuple) != 3:
            return None
        
        try:
            # coord_tuple contains (degrees, minutes, seconds) as fractions
            degrees = float(coord_tuple[0])
            minutes = float(coord_tuple[1])
            seconds = float(coord_tuple[2])
            
            # Convert to decimal degrees
            decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
            
            # Apply direction (negative for South/West)
            if ref in ['S', 'W']:
                decimal = -decimal
                
            return decimal
        except:
            return None
    
    @staticmethod
    def extract_gps_info(exif_data):
        """Extract GPS information from EXIF data."""
        gps_info = {}
        
        try:
            # Get GPS IFD (Image File Directory)
            gps_ifd = exif_data.get_ifd(0x8825)  # GPS IFD tag
            
            if gps_ifd:
                # Extract GPS coordinates
                gps_latitude = gps_ifd.get(2)  # GPSLatitude
                gps_latitude_ref = gps_ifd.get(1)  # GPSLatitudeRef
                gps_longitude = gps_ifd.get(4)  # GPSLongitude  
                gps_longitude_ref = gps_ifd.get(3)  # GPSLongitudeRef
                gps_altitude = gps_ifd.get(6)  # GPSAltitude
                gps_altitude_ref = gps_ifd.get(5)  # GPSAltitudeRef
                
                # Convert coordinates to decimal degrees
                if gps_latitude and gps_latitude_ref:
                    lat = MetadataExtractor.convert_gps_coordinate(gps_latitude, gps_latitude_ref)
                    if lat is not None:
                        gps_info['gps_latitude'] = lat
                
                if gps_longitude and gps_longitude_ref:
                    lon = MetadataExtractor.convert_gps_coordinate(gps_longitude, gps_longitude_ref)
                    if lon is not None:
                        gps_info['gps_longitude'] = lon
                
                # Convert altitude
                if gps_altitude:
                    try:
                        alt = float(gps_altitude)
                        # GPSAltitudeRef: 0 = above sea level, 1 = below sea level
                        if gps_altitude_ref == 1:
                            alt = -alt
                        gps_info['gps_altitude'] = alt
                    except:
                        pass
                
                # Try to get location name if available
                gps_area_info = gps_ifd.get(28)  # GPSAreaInformation
                if gps_area_info:
                    try:
                        location_name = str(gps_area_info)
                        if location_name and location_name != 'None':
                            gps_info['gps_location_name'] = location_name
                    except:
                        pass
                        
        except Exception as e:
            print(f"Error extracting GPS info: {e}")
        
        return gps_info
    
    @staticmethod
    def extract_metadata(file_path: str) -> Dict:
        """Extract comprehensive metadata from an image file."""
        metadata = {
            'filename': Path(file_path).name,
            'filepath': file_path,
            'file_size': Path(file_path).stat().st_size,
        }
        
        try:
            # Basic image info using Pillow
            with Image.open(file_path) as img:
                metadata.update({
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                })
                
                # Extract EXIF data using the newer method
                try:
                    exif_data = img.getexif()
                    if exif_data:
                        # Convert to dictionary for easier processing
                        exif_dict = {}
                        for tag_id, value in exif_data.items():
                            tag = TAGS.get(tag_id, str(tag_id))
                            
                            # Convert the value to a JSON-serializable type
                            converted_value = MetadataExtractor.convert_exif_value(value)
                            exif_dict[tag] = converted_value
                            
                            # Extract specific metadata fields
                            if tag == 'DateTime':
                                try:
                                    metadata['date_taken'] = datetime.strptime(
                                        str(converted_value), '%Y:%m:%d %H:%M:%S'
                                    ).isoformat()
                                except:
                                    pass
                            elif tag == 'Make':
                                metadata['camera_make'] = str(converted_value)
                            elif tag == 'Model':
                                metadata['camera_model'] = str(converted_value)
                            elif tag == 'LensModel':
                                metadata['lens_model'] = str(converted_value)
                            elif tag == 'FocalLength':
                                try:
                                    if isinstance(converted_value, (list, tuple)) and len(converted_value) >= 2:
                                        metadata['focal_length'] = float(converted_value[0]) / float(converted_value[1])
                                    else:
                                        metadata['focal_length'] = float(converted_value)
                                except:
                                    pass
                            elif tag == 'FNumber':
                                try:
                                    if isinstance(converted_value, (list, tuple)) and len(converted_value) >= 2:
                                        metadata['aperture'] = float(converted_value[0]) / float(converted_value[1])
                                    else:
                                        metadata['aperture'] = float(converted_value)
                                except:
                                    pass
                            elif tag == 'ExposureTime':
                                try:
                                    if isinstance(converted_value, (list, tuple)) and len(converted_value) >= 2:
                                        metadata['shutter_speed'] = f"{int(converted_value[0])}/{int(converted_value[1])}"
                                    else:
                                        metadata['shutter_speed'] = str(converted_value)
                                except:
                                    pass
                            elif tag == 'ISOSpeedRatings':
                                try:
                                    metadata['iso'] = int(converted_value)
                                except:
                                    pass
                            elif tag == 'Flash':
                                metadata['flash'] = str(converted_value)
                            elif tag == 'Orientation':
                                try:
                                    metadata['orientation'] = int(converted_value)
                                except:
                                    pass
                        
                        # Store complete metadata as JSON
                        metadata['metadata'] = exif_dict
                        
                        # Extract GPS information
                        gps_info = MetadataExtractor.extract_gps_info(exif_data)
                        metadata.update(gps_info)
                        
                    else:
                        metadata['metadata'] = {}
                        
                except AttributeError:
                    # Fallback to old method for older Pillow versions
                    try:
                        exif_data = img._getexif()
                        if exif_data:
                            exif_dict = {}
                            for tag_id, value in exif_data.items():
                                tag = TAGS.get(tag_id, str(tag_id))
                                
                                # Convert the value to a JSON-serializable type
                                converted_value = MetadataExtractor.convert_exif_value(value)
                                exif_dict[tag] = converted_value
                                
                                # Extract specific metadata fields (same logic as above)
                                if tag == 'DateTime':
                                    try:
                                        metadata['date_taken'] = datetime.strptime(
                                            str(converted_value), '%Y:%m:%d %H:%M:%S'
                                        ).isoformat()
                                    except:
                                        pass
                                elif tag == 'Make':
                                    metadata['camera_make'] = str(converted_value)
                                elif tag == 'Model':
                                    metadata['camera_model'] = str(converted_value)
                                elif tag == 'LensModel':
                                    metadata['lens_model'] = str(converted_value)
                                elif tag == 'FocalLength':
                                    try:
                                        if isinstance(converted_value, (list, tuple)) and len(converted_value) >= 2:
                                            metadata['focal_length'] = float(converted_value[0]) / float(converted_value[1])
                                        else:
                                            metadata['focal_length'] = float(converted_value)
                                    except:
                                        pass
                                elif tag == 'FNumber':
                                    try:
                                        if isinstance(converted_value, (list, tuple)) and len(converted_value) >= 2:
                                            metadata['aperture'] = float(converted_value[0]) / float(converted_value[1])
                                        else:
                                            metadata['aperture'] = float(converted_value)
                                    except:
                                        pass
                                elif tag == 'ExposureTime':
                                    try:
                                        if isinstance(converted_value, (list, tuple)) and len(converted_value) >= 2:
                                            metadata['shutter_speed'] = f"{int(converted_value[0])}/{int(converted_value[1])}"
                                        else:
                                            metadata['shutter_speed'] = str(converted_value)
                                    except:
                                        pass
                                elif tag == 'ISOSpeedRatings':
                                    try:
                                        metadata['iso'] = int(converted_value)
                                    except:
                                        pass
                                elif tag == 'Flash':
                                    metadata['flash'] = str(converted_value)
                                elif tag == 'Orientation':
                                    try:
                                        metadata['orientation'] = int(converted_value)
                                    except:
                                        pass
                            
                            metadata['metadata'] = exif_dict
                            
                            # For older method, try to extract GPS from the raw exif_data
                            # Note: This is more limited than the newer method
                            try:
                                # Try to find GPS data in the EXIF dictionary
                                for tag_id, value in exif_data.items():
                                    if tag_id == 34853:  # GPS IFD tag
                                        # This would contain GPS data but is complex to parse
                                        # For now, we'll skip GPS extraction in fallback mode
                                        pass
                            except:
                                pass
                                
                        else:
                            metadata['metadata'] = {}
                    except Exception as fallback_error:
                        print(f"Fallback EXIF extraction failed: {fallback_error}")
                        metadata['metadata'] = {}
                
        except Exception as e:
            print(f"Error extracting metadata from {file_path}: {e}")
            # Ensure we always return the basic metadata even if EXIF extraction fails
            metadata['metadata'] = {}
        
        return metadata


class ImageUtils:
    """Utility functions for image processing and display."""
    
    @staticmethod
    def apply_exif_orientation(pixmap: QPixmap, orientation: int) -> QPixmap:
        """Apply EXIF orientation to a pixmap for correct display."""
        if orientation is None or orientation == 1:
            return pixmap  # Normal orientation, no change needed
        
        transform = QTransform()
        
        if orientation == 2:
            # Flipped horizontally
            transform.scale(-1, 1)
        elif orientation == 3:
            # Rotated 180 degrees
            transform.rotate(180)
        elif orientation == 4:
            # Flipped vertically
            transform.scale(1, -1)
        elif orientation == 5:
            # Rotated 90 degrees counter-clockwise and flipped horizontally
            transform.rotate(-90)
            transform.scale(-1, 1)
        elif orientation == 6:
            # Rotated 90 degrees clockwise
            transform.rotate(90)
        elif orientation == 7:
            # Rotated 90 degrees clockwise and flipped horizontally
            transform.rotate(90)
            transform.scale(-1, 1)
        elif orientation == 8:
            # Rotated 90 degrees counter-clockwise
            transform.rotate(-90)
        
        return pixmap.transformed(transform, Qt.SmoothTransformation)
    
    @staticmethod
    def load_image_with_orientation(file_path: str, max_size: QSize = None) -> QPixmap:
        """Load an image and apply proper orientation based on EXIF data."""
        try:
            # Load the pixmap
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                return pixmap
            
            # Get orientation from EXIF data
            orientation = None
            try:
                with Image.open(file_path) as img:
                    exif_data = img.getexif()
                    if exif_data:
                        orientation = exif_data.get(274)  # 274 is the EXIF tag for Orientation
            except:
                pass
            
            # Apply orientation correction
            if orientation:
                pixmap = ImageUtils.apply_exif_orientation(pixmap, orientation)
            
            # Scale if max_size is provided
            if max_size and not pixmap.isNull():
                pixmap = pixmap.scaled(max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            return pixmap
            
        except Exception as e:
            print(f"Error loading image {file_path}: {e}")
            return QPixmap()


class PhotoImportWorker(QThread):
    """Worker thread for importing photos with metadata extraction."""
    
    progress_updated = Signal(int)
    photo_imported = Signal(dict)
    import_finished = Signal()
    error_occurred = Signal(str)
    
    def __init__(self, file_paths: List[str], db_manager: DatabaseManager):
        super().__init__()
        self.file_paths = file_paths
        self.db_manager = db_manager
    
    def run(self):
        total_files = len(self.file_paths)
        successfully_imported = 0
        
        for i, file_path in enumerate(self.file_paths):
            try:
                print(f"Importing: {file_path}")
                metadata = MetadataExtractor.extract_metadata(file_path)
                photo_id = self.db_manager.add_photo(metadata)
                metadata['id'] = photo_id
                self.photo_imported.emit(metadata)
                successfully_imported += 1
                print(f"Successfully imported: {file_path}")
            except Exception as e:
                error_msg = f"Error importing {Path(file_path).name}: {str(e)}"
                print(error_msg)
                self.error_occurred.emit(error_msg)
            
            progress = int((i + 1) / total_files * 100)
            self.progress_updated.emit(progress)
        
        print(f"Import completed: {successfully_imported}/{total_files} files imported successfully")
        self.import_finished.emit()


class PhotoListWidget(QListWidget):
    """Custom list widget for displaying photos with drag and drop support."""
    
    photo_delete_requested = Signal(int)  # Signal emitted when photo deletion is requested
    
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setIconSize(QSize(150, 150))
        self.setResizeMode(QListWidget.Adjust)
        self.setViewMode(QListWidget.IconMode)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position: QPoint):
        """Show context menu for photo operations."""
        item = self.itemAt(position)
        if item is None:
            return
        
        photo_data = item.data(Qt.UserRole)
        if photo_data is None:
            return
        
        menu = QMenu(self)
        
        delete_action = QAction("Delete Photo", self)
        delete_action.triggered.connect(lambda: self.photo_delete_requested.emit(photo_data['id']))
        menu.addAction(delete_action)
        
        menu.exec(self.mapToGlobal(position))
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if any(url.toLocalFile().lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif')) 
                   for url in urls):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            file_paths = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif')):
                    file_paths.append(file_path)
            
            if file_paths:
                self.parent().import_photos(file_paths)
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()


class CategoryTreeWidget(QTreeWidget):
    """Custom tree widget for categories with context menu support."""
    
    category_delete_requested = Signal(int)
    
    def __init__(self):
        super().__init__()
        self.setHeaderLabel("Categories")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position: QPoint):
        """Show context menu for category operations."""
        item = self.itemAt(position)
        if item is None:
            return
        
        category_id = item.data(0, Qt.UserRole)
        if category_id is None:
            return
        
        menu = QMenu(self)
        
        delete_action = QAction("Delete Category", self)
        delete_action.triggered.connect(lambda: self.category_delete_requested.emit(category_id))
        menu.addAction(delete_action)
        
        menu.exec(self.mapToGlobal(position))


class TagTreeWidget(QTreeWidget):
    """Custom tree widget for tags with context menu support."""
    
    tag_delete_requested = Signal(int)
    
    def __init__(self):
        super().__init__()
        self.setHeaderLabel("Tags")
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position: QPoint):
        """Show context menu for tag operations."""
        item = self.itemAt(position)
        if item is None:
            return
        
        tag_id = item.data(0, Qt.UserRole)
        if tag_id is None:
            return
        
        menu = QMenu(self)
        
        delete_action = QAction("Delete Tag", self)
        delete_action.triggered.connect(lambda: self.tag_delete_requested.emit(tag_id))
        menu.addAction(delete_action)
        
        menu.exec(self.mapToGlobal(position))


class DatabaseInfoDialog(QDialog):
    """Dialog for displaying database information."""
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Database Information")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        info = self.db_manager.get_database_info()
        
        # Create a table for the information
        table = QTableWidget(4, 2)
        table.setHorizontalHeaderLabels(["Property", "Value"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().hide()
        
        data = [
            ("Database File", Path(info['path']).name),
            ("Directory", info['directory']),
            ("Full Path", info['path']),
            ("Size", info['size'])
        ]
        
        for i, (prop, value) in enumerate(data):
            table.setItem(i, 0, QTableWidgetItem(prop))
            table.setItem(i, 1, QTableWidgetItem(value))
        
        table.resizeColumnsToContents()
        layout.addWidget(table)
        
        # Add buttons
        button_layout = QHBoxLayout()
        
        open_folder_btn = QPushButton("Open Database Folder")
        open_folder_btn.clicked.connect(self.open_database_folder)
        button_layout.addWidget(open_folder_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.resize(500, 200)
    
    def open_database_folder(self):
        """Open the database folder in the system file manager."""
        import subprocess
        import sys
        
        folder_path = self.db_manager.app_data_dir
        
        try:
            if sys.platform == "win32":
                os.startfile(folder_path)
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", folder_path])
            else:  # Linux and other Unix-like
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open folder: {e}")


class PhotoCategoriesTagsDialog(QDialog):
    """Dialog for managing categories and tags for a specific photo, plus overall category/tag management."""
    
    def __init__(self, photo_data: Dict, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.photo_data = photo_data
        self.db_manager = db_manager
        self.photo_id = photo_data.get('id')
        self.parent_window = parent
        self.setWindowTitle(f"Manage Categories & Tags - {photo_data.get('filename', 'Unknown')}")
        self.setModal(True)
        self.resize(800, 700)
        self.setup_ui()
        self.load_assignments()
        self.load_all_categories_tags()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create tab widget for different sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Tab 1: Assign to current photo
        self.create_photo_assignment_tab()
        
        # Tab 2: Manage all categories
        self.create_categories_management_tab()
        
        # Tab 3: Manage all tags
        self.create_tags_management_tab()
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
    
    def create_photo_assignment_tab(self):
        """Create the tab for assigning categories/tags to the current photo."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Photo info header
        header_layout = QHBoxLayout()
        
        # Photo thumbnail
        self.photo_thumbnail = QLabel()
        self.photo_thumbnail.setFixedSize(100, 100)
        self.photo_thumbnail.setStyleSheet("border: 1px solid gray")
        self.photo_thumbnail.setAlignment(Qt.AlignCenter)
        
        try:
            pixmap = ImageUtils.load_image_with_orientation(
                self.photo_data['filepath'], 
                QSize(100, 100)
            )
            if not pixmap.isNull():
                self.photo_thumbnail.setPixmap(pixmap)
            else:
                self.photo_thumbnail.setText("No preview")
        except:
            self.photo_thumbnail.setText("No preview")
        
        header_layout.addWidget(self.photo_thumbnail)
        
        # Photo details
        info_layout = QVBoxLayout()
        filename_label = QLabel(f"<b>{self.photo_data.get('filename', 'Unknown')}</b>")
        info_layout.addWidget(filename_label)
        
        if self.photo_data.get('date_taken'):
            date_label = QLabel(f"Date: {self.photo_data['date_taken']}")
            info_layout.addWidget(date_label)
        
        dimensions = self.photo_data.get('width'), self.photo_data.get('height')
        if dimensions[0] and dimensions[1]:
            size_label = QLabel(f"Size: {dimensions[0]} × {dimensions[1]}")
            info_layout.addWidget(size_label)
        
        info_layout.addStretch()
        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)
        
        # Categories section
        categories_group = QGroupBox("Categories")
        categories_layout = QVBoxLayout(categories_group)
        
        # Current categories
        current_categories_label = QLabel("Assigned Categories:")
        current_categories_label.setStyleSheet("font-weight: bold;")
        categories_layout.addWidget(current_categories_label)
        
        self.current_categories_layout = QHBoxLayout()
        self.current_categories_widget = QWidget()
        self.current_categories_widget.setLayout(self.current_categories_layout)
        self.current_categories_widget.setMinimumHeight(50)
        categories_layout.addWidget(self.current_categories_widget)
        
        # Add category section
        add_category_layout = QHBoxLayout()
        add_category_layout.addWidget(QLabel("Add Category:"))
        self.category_combo = QComboBox()
        self.category_combo.setMinimumWidth(200)
        add_category_btn = QPushButton("Add")
        add_category_btn.clicked.connect(self.add_category_to_photo)
        add_category_layout.addWidget(self.category_combo)
        add_category_layout.addWidget(add_category_btn)
        add_category_layout.addStretch()
        categories_layout.addLayout(add_category_layout)
        
        layout.addWidget(categories_group)
        
        # Tags section
        tags_group = QGroupBox("Tags")
        tags_layout = QVBoxLayout(tags_group)
        
        # Current tags
        current_tags_label = QLabel("Assigned Tags:")
        current_tags_label.setStyleSheet("font-weight: bold;")
        tags_layout.addWidget(current_tags_label)
        
        self.current_tags_layout = QHBoxLayout()
        self.current_tags_widget = QWidget()
        self.current_tags_widget.setLayout(self.current_tags_layout)
        self.current_tags_widget.setMinimumHeight(50)
        tags_layout.addWidget(self.current_tags_widget)
        
        # Add tag section
        add_tag_layout = QHBoxLayout()
        add_tag_layout.addWidget(QLabel("Add Tag:"))
        self.tag_combo = QComboBox()
        self.tag_combo.setMinimumWidth(200)
        add_tag_btn = QPushButton("Add")
        add_tag_btn.clicked.connect(self.add_tag_to_photo)
        add_tag_layout.addWidget(self.tag_combo)
        add_tag_layout.addWidget(add_tag_btn)
        add_tag_layout.addStretch()
        tags_layout.addLayout(add_tag_layout)
        
        layout.addWidget(tags_group)
        
        # Populate dropdowns
        self.populate_category_combo()
        self.populate_tag_combo()
        
        self.tab_widget.addTab(tab, "Assign to Photo")
    
    def create_categories_management_tab(self):
        """Create the tab for managing all categories."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Header
        header_label = QLabel("Manage Categories")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header_label)
        
        # Create new category section
        create_group = QGroupBox("Create New Category")
        create_layout = QVBoxLayout(create_group)
        
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Name:"))
        self.new_category_name = QLineEdit()
        self.new_category_name.setPlaceholderText("Enter category name...")
        form_layout.addWidget(self.new_category_name)
        
        form_layout.addWidget(QLabel("Description:"))
        self.new_category_desc = QLineEdit()
        self.new_category_desc.setPlaceholderText("Optional description...")
        form_layout.addWidget(self.new_category_desc)
        
        create_cat_btn = QPushButton("Create Category")
        create_cat_btn.clicked.connect(self.create_category_from_form)
        form_layout.addWidget(create_cat_btn)
        
        create_layout.addLayout(form_layout)
        layout.addWidget(create_group)
        
        # Existing categories section
        existing_group = QGroupBox("Existing Categories")
        existing_layout = QVBoxLayout(existing_group)
        
        self.categories_table = QTableWidget()
        self.categories_table.setColumnCount(4)
        self.categories_table.setHorizontalHeaderLabels(["Name", "Description", "Photos", "Actions"])
        self.categories_table.horizontalHeader().setStretchLastSection(False)
        self.categories_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.categories_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.categories_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.categories_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        existing_layout.addWidget(self.categories_table)
        
        layout.addWidget(existing_group)
        
        self.tab_widget.addTab(tab, "Manage Categories")
    
    def create_tags_management_tab(self):
        """Create the tab for managing all tags."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Header
        header_label = QLabel("Manage Tags")
        header_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(header_label)
        
        # Create new tag section
        create_group = QGroupBox("Create New Tag")
        create_layout = QVBoxLayout(create_group)
        
        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Name:"))
        self.new_tag_name = QLineEdit()
        self.new_tag_name.setPlaceholderText("Enter tag name...")
        form_layout.addWidget(self.new_tag_name)
        
        create_tag_btn = QPushButton("Create Tag")
        create_tag_btn.clicked.connect(self.create_tag_from_form)
        form_layout.addWidget(create_tag_btn)
        form_layout.addStretch()
        
        create_layout.addLayout(form_layout)
        layout.addWidget(create_group)
        
        # Existing tags section
        existing_group = QGroupBox("Existing Tags")
        existing_layout = QVBoxLayout(existing_group)
        
        self.tags_table = QTableWidget()
        self.tags_table.setColumnCount(3)
        self.tags_table.setHorizontalHeaderLabels(["Name", "Photos", "Actions"])
        self.tags_table.horizontalHeader().setStretchLastSection(False)
        self.tags_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tags_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tags_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        existing_layout.addWidget(self.tags_table)
        
        layout.addWidget(existing_group)
        
        self.tab_widget.addTab(tab, "Manage Tags")
    
    def populate_category_combo(self):
        """Populate the category combo box."""
        self.category_combo.clear()
        self.category_combo.addItem("Select a category...", None)
        categories = self.db_manager.get_categories()
        for category in categories:
            self.category_combo.addItem(category['name'], category['id'])
    
    def populate_tag_combo(self):
        """Populate the tag combo box."""
        self.tag_combo.clear()
        self.tag_combo.addItem("Select a tag...", None)
        tags = self.db_manager.get_tags()
        for tag in tags:
            self.tag_combo.addItem(tag['name'], tag['id'])
    
    def clear_layout(self, layout):
        """Clear all widgets from a layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
    def create_removable_chip(self, text: str, remove_callback):
        """Create a removable chip widget for categories/tags."""
        chip_widget = QWidget()
        chip_layout = QHBoxLayout(chip_widget)
        chip_layout.setContentsMargins(8, 4, 8, 4)
        chip_layout.setSpacing(4)
        
        # Style the chip with better contrast
        chip_widget.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                border: 1px solid #34495e;
                border-radius: 12px;
                margin: 2px;
            }
        """)
        
        # Label with white text for better contrast
        label = QLabel(text)
        label.setStyleSheet("border: none; background: transparent; font-size: 12px; color: white; font-weight: bold;")
        chip_layout.addWidget(label)
        
        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setFixedSize(16, 16)
        remove_btn.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                color: #ecf0f1;
                font-weight: bold;
                font-size: 14px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #e74c3c;
                color: white;
            }
        """)
        remove_btn.clicked.connect(remove_callback)
        chip_layout.addWidget(remove_btn)
        
        return chip_widget
    
    def load_assignments(self):
        """Load current category and tag assignments."""
        self.update_categories_display()
        self.update_tags_display()
    
    def update_categories_display(self):
        """Update the display of categories for the photo."""
        self.clear_layout(self.current_categories_layout)
        
        categories = self.db_manager.get_photo_categories(self.photo_id)
        
        if not categories:
            no_categories_label = QLabel("No categories assigned")
            no_categories_label.setStyleSheet("color: #666; font-style: italic;")
            self.current_categories_layout.addWidget(no_categories_label)
        else:
            for category in categories:
                # Create a proper closure by using a helper function
                chip = self.create_removable_chip(
                    category['name'],
                    self.make_remove_category_callback(category['id'])
                )
                self.current_categories_layout.addWidget(chip)
        
        self.current_categories_layout.addStretch()
    
    def update_tags_display(self):
        """Update the display of tags for the photo."""
        self.clear_layout(self.current_tags_layout)
        
        tags = self.db_manager.get_photo_tags(self.photo_id)
        
        if not tags:
            no_tags_label = QLabel("No tags assigned")
            no_tags_label.setStyleSheet("color: #666; font-style: italic;")
            self.current_tags_layout.addWidget(no_tags_label)
        else:
            for tag in tags:
                # Create a proper closure by using a helper function
                chip = self.create_removable_chip(
                    tag['name'],
                    self.make_remove_tag_callback(tag['id'])
                )
                self.current_tags_layout.addWidget(chip)
        
        self.current_tags_layout.addStretch()
    
    def make_remove_category_callback(self, category_id: int):
        """Create a proper callback function for removing a category."""
        return lambda: self.remove_category_from_photo(category_id)
    
    def make_remove_tag_callback(self, tag_id: int):
        """Create a proper callback function for removing a tag."""
        return lambda: self.remove_tag_from_photo(tag_id)
    
    def add_category_to_photo(self):
        """Add selected category to the photo."""
        category_id = self.category_combo.currentData()
        if category_id is None:
            QMessageBox.warning(self, "No Category Selected", "Please select a category to add.")
            return
        
        try:
            self.db_manager.assign_photo_category(self.photo_id, category_id)
            self.update_categories_display()
            category_name = self.category_combo.currentText()
            QMessageBox.information(self, "Success", f"Added category '{category_name}' to photo.")
            self.category_combo.setCurrentIndex(0)  # Reset selection
            
            # Refresh parent window to show updated categories
            if self.parent_window:
                current_items = self.parent_window.photo_list.selectedItems()
                if current_items:
                    photo_data = current_items[0].data(Qt.UserRole)
                    if photo_data and photo_data.get('id') == self.photo_id:
                        self.parent_window.show_photo_details(photo_data)
                        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to add category: {e}")
    
    def add_tag_to_photo(self):
        """Add selected tag to the photo."""
        tag_id = self.tag_combo.currentData()
        if tag_id is None:
            QMessageBox.warning(self, "No Tag Selected", "Please select a tag to add.")
            return
        
        try:
            self.db_manager.assign_photo_tag(self.photo_id, tag_id)
            self.update_tags_display()
            tag_name = self.tag_combo.currentText()
            QMessageBox.information(self, "Success", f"Added tag '{tag_name}' to photo.")
            self.tag_combo.setCurrentIndex(0)  # Reset selection
            
            # Refresh parent window to show updated tags
            if self.parent_window:
                current_items = self.parent_window.photo_list.selectedItems()
                if current_items:
                    photo_data = current_items[0].data(Qt.UserRole)
                    if photo_data and photo_data.get('id') == self.photo_id:
                        self.parent_window.show_photo_details(photo_data)
                        
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to add tag: {e}")
    
    def remove_category_from_photo(self, category_id: int):
        """Remove a category from the photo."""
        try:
            if self.db_manager.remove_photo_category(self.photo_id, category_id):
                self.update_categories_display()
                QMessageBox.information(self, "Success", "Category removed from photo.")
                
                # Refresh parent window to show updated categories
                if self.parent_window:
                    current_items = self.parent_window.photo_list.selectedItems()
                    if current_items:
                        photo_data = current_items[0].data(Qt.UserRole)
                        if photo_data and photo_data.get('id') == self.photo_id:
                            self.parent_window.show_photo_details(photo_data)
            else:
                QMessageBox.warning(self, "Error", "Failed to remove category from photo.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to remove category: {e}")
    
    def remove_tag_from_photo(self, tag_id: int):
        """Remove a tag from the photo."""
        try:
            if self.db_manager.remove_photo_tag(self.photo_id, tag_id):
                self.update_tags_display()
                QMessageBox.information(self, "Success", "Tag removed from photo.")
                
                # Refresh parent window to show updated tags
                if self.parent_window:
                    current_items = self.parent_window.photo_list.selectedItems()
                    if current_items:
                        photo_data = current_items[0].data(Qt.UserRole)
                        if photo_data and photo_data.get('id') == self.photo_id:
                            self.parent_window.show_photo_details(photo_data)
            else:
                QMessageBox.warning(self, "Error", "Failed to remove tag from photo.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to remove tag: {e}")
    
    def create_new_category(self):
        """Create a new category."""
        dialog = AddCategoryDialog(self)
        if dialog.exec() == QDialog.Accepted:
            name, description = dialog.get_data()
            if name:
                try:
                    self.db_manager.add_category(name, description)
                    self.populate_category_combo()
                    QMessageBox.information(self, "Success", f"Category '{name}' created successfully.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to create category: {e}")
    
    def create_new_tag(self):
        """Create a new tag."""
        dialog = AddTagDialog(self)
        if dialog.exec() == QDialog.Accepted:
            name = dialog.get_data()
            if name:
                try:
                    self.db_manager.add_tag(name)
                    self.populate_tag_combo()
                    QMessageBox.information(self, "Success", f"Tag '{name}' created successfully.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to create tag: {e}")
    
    def load_all_categories_tags(self):
        """Load all categories and tags into the management tables."""
        self.populate_categories_table()
        self.populate_tags_table()
    
    def populate_categories_table(self):
        """Populate the categories management table."""
        categories = self.db_manager.get_categories()
        self.categories_table.setRowCount(len(categories))
        
        for row, category in enumerate(categories):
            # Name
            name_item = QTableWidgetItem(category['name'])
            self.categories_table.setItem(row, 0, name_item)
            
            # Description
            desc_item = QTableWidgetItem(category.get('description', ''))
            self.categories_table.setItem(row, 1, desc_item)
            
            # Photo count
            photo_count = self.db_manager.count_photos_by_category(category['id'])
            count_item = QTableWidgetItem(str(photo_count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.categories_table.setItem(row, 2, count_item)
            
            # Actions (Delete button)
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
            delete_btn.clicked.connect(lambda checked, cat_id=category['id']: self.delete_category(cat_id))
            self.categories_table.setCellWidget(row, 3, delete_btn)
    
    def populate_tags_table(self):
        """Populate the tags management table."""
        tags = self.db_manager.get_tags()
        self.tags_table.setRowCount(len(tags))
        
        for row, tag in enumerate(tags):
            # Name
            name_item = QTableWidgetItem(tag['name'])
            self.tags_table.setItem(row, 0, name_item)
            
            # Photo count
            photo_count = self.db_manager.count_photos_by_tag(tag['id'])
            count_item = QTableWidgetItem(str(photo_count))
            count_item.setTextAlignment(Qt.AlignCenter)
            self.tags_table.setItem(row, 1, count_item)
            
            # Actions (Delete button)
            delete_btn = QPushButton("Delete")
            delete_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
            delete_btn.clicked.connect(lambda checked, tag_id=tag['id']: self.delete_tag(tag_id))
            self.tags_table.setCellWidget(row, 2, delete_btn)
    
    def create_category_from_form(self):
        """Create a new category from the form inputs."""
        name = self.new_category_name.text().strip()
        description = self.new_category_desc.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a category name.")
            return
        
        try:
            self.db_manager.add_category(name, description)
            self.new_category_name.clear()
            self.new_category_desc.clear()
            self.populate_categories_table()
            self.populate_category_combo()
            QMessageBox.information(self, "Success", f"Category '{name}' created successfully.")
            
            # Refresh parent window if available
            if self.parent_window:
                self.parent_window.load_photos()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create category: {e}")
    
    def create_tag_from_form(self):
        """Create a new tag from the form inputs."""
        name = self.new_tag_name.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Invalid Input", "Please enter a tag name.")
            return
        
        try:
            self.db_manager.add_tag(name)
            self.new_tag_name.clear()
            self.populate_tags_table()
            self.populate_tag_combo()
            QMessageBox.information(self, "Success", f"Tag '{name}' created successfully.")
            
            # Refresh parent window if available
            if self.parent_window:
                self.parent_window.load_photos()
                
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create tag: {e}")
    
    def delete_category(self, category_id: int):
        """Delete a category from the system."""
        try:
            # Get category details for confirmation
            category = self.db_manager.get_category_by_id(category_id)
            if not category:
                QMessageBox.warning(self, "Error", "Category not found.")
                return
            
            # Count photos in this category
            photo_count = self.db_manager.count_photos_by_category(category_id)
            
            # Create confirmation message
            message = f"Are you sure you want to delete the category '{category['name']}'?"
            if photo_count > 0:
                message += f"\n\nThis category is currently assigned to {photo_count} photo(s). "
                message += "Deleting the category will remove it from all photos, but the photos will remain in your catalog."
            
            # Ask for confirmation
            reply = QMessageBox.question(
                self,
                "Delete Category",
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Delete from database
                if self.db_manager.delete_category(category_id):
                    QMessageBox.information(self, "Success", f"Category '{category['name']}' deleted successfully.")
                    self.populate_categories_table()
                    self.populate_category_combo()
                    self.update_categories_display()  # Refresh current photo assignments
                    
                    # Refresh parent window if available
                    if self.parent_window:
                        self.parent_window.load_photos()
                else:
                    QMessageBox.warning(self, "Error", "Failed to delete category from database.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while deleting the category: {str(e)}")
    
    def delete_tag(self, tag_id: int):
        """Delete a tag from the system."""
        try:
            # Get tag details for confirmation
            tag = self.db_manager.get_tag_by_id(tag_id)
            if not tag:
                QMessageBox.warning(self, "Error", "Tag not found.")
                return
            
            # Count photos with this tag
            photo_count = self.db_manager.count_photos_by_tag(tag_id)
            
            # Create confirmation message
            message = f"Are you sure you want to delete the tag '{tag['name']}'?"
            if photo_count > 0:
                message += f"\n\nThis tag is currently assigned to {photo_count} photo(s). "
                message += "Deleting the tag will remove it from all photos, but the photos will remain in your catalog."
            
            # Ask for confirmation
            reply = QMessageBox.question(
                self,
                "Delete Tag",
                message,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Delete from database
                if self.db_manager.delete_tag(tag_id):
                    QMessageBox.information(self, "Success", f"Tag '{tag['name']}' deleted successfully.")
                    self.populate_tags_table()
                    self.populate_tag_combo()
                    self.update_tags_display()  # Refresh current photo assignments
                    
                    # Refresh parent window if available
                    if self.parent_window:
                        self.parent_window.load_photos()
                else:
                    QMessageBox.warning(self, "Error", "Failed to delete tag from database.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while deleting the tag: {str(e)}")


class AddCategoryDialog(QDialog):
    """Dialog for adding new categories."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Category")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_edit = QLineEdit()
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        
        layout.addRow("Name:", self.name_edit)
        layout.addRow("Description:", self.description_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_data(self) -> Tuple[str, str]:
        return self.name_edit.text(), self.description_edit.toPlainText()


class AddTagDialog(QDialog):
    """Dialog for adding new tags."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Tag")
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QFormLayout(self)
        
        self.name_edit = QLineEdit()
        layout.addRow("Name:", self.name_edit)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
    
    def get_data(self) -> str:
        return self.name_edit.text()


class PhotoSphereMainWindow(QMainWindow):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.current_photos = []
        self.setup_ui()
        self.load_data()
        
        # Show database location in status bar
        db_info = self.db_manager.get_database_info()
        self.status_bar.showMessage(f"Database: {db_info['directory']}")
        
        # Set up a timer to periodically update database size in status
        self.db_info_timer = QTimer()
        self.db_info_timer.timeout.connect(self.update_database_status)
        self.db_info_timer.start(30000)  # Update every 30 seconds
    
    def setup_ui(self):
        self.setWindowTitle("PhotoSphere")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panes
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Center panel (Photo grid) - no left panel needed now
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)
        
        # Right panel (Photo details)
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions (no left panel)
        splitter.setSizes([900, 400])
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Progress bar for imports
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def create_center_panel(self) -> QWidget:
        """Create the center panel with photo grid and search."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Toolbar with search and import
        toolbar_layout = QHBoxLayout()
        
        # Search section
        search_label = QLabel("Search:")
        toolbar_layout.addWidget(search_label)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search photos...")
        self.search_edit.setMaximumWidth(300)
        self.search_edit.textChanged.connect(self.filter_photos)
        toolbar_layout.addWidget(self.search_edit)
        
        # Spacer
        toolbar_layout.addStretch()
        
        # Import button
        import_btn = QPushButton("Import Photos")
        import_btn.clicked.connect(self.import_photos_dialog)
        toolbar_layout.addWidget(import_btn)
        
        # Photo count
        self.photo_count_label = QLabel("0 photos")
        toolbar_layout.addWidget(self.photo_count_label)
        
        layout.addLayout(toolbar_layout)
        
        # Photo list
        self.photo_list = PhotoListWidget()
        self.photo_list.itemClicked.connect(self.on_photo_selected)
        self.photo_list.photo_delete_requested.connect(self.delete_photo)
        layout.addWidget(self.photo_list)
        
        return panel
    
    def create_right_panel(self) -> QWidget:
        """Create the right panel with photo details."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Photo preview
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.photo_preview = QLabel()
        self.photo_preview.setAlignment(Qt.AlignCenter)
        self.photo_preview.setMinimumHeight(200)
        self.photo_preview.setStyleSheet("border: 1px solid gray")
        self.photo_preview.setText("Select a photo to view details")
        preview_layout.addWidget(self.photo_preview)
        
        layout.addWidget(preview_group)
        
        # Photo details
        details_group = QGroupBox("Details")
        details_layout = QVBoxLayout(details_group)
        
        self.details_table = QTableWidget()
        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.details_table.horizontalHeader().setStretchLastSection(True)
        self.details_table.verticalHeader().hide()
        self.details_table.setEditTriggers(QAbstractItemView.NoEditTriggers)  # Prevent editing
        self.details_table.setSelectionBehavior(QAbstractItemView.SelectRows)  # Select entire rows
        details_layout.addWidget(self.details_table)
        
        layout.addWidget(details_group)
        
        return panel
    
    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        import_action = QAction("Import Photos", self)
        import_action.triggered.connect(self.import_photos_dialog)
        file_menu.addAction(import_action)
        
        file_menu.addSeparator()
        
        db_info_action = QAction("Database Information", self)
        db_info_action.triggered.connect(self.show_database_info)
        file_menu.addAction(db_info_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        categories_tags_action = QAction("Manage Categories/Tags", self)
        categories_tags_action.triggered.connect(self.open_categories_tags_dialog)
        edit_menu.addAction(categories_tags_action)
    
    def update_database_status(self):
        """Update the database information in the status bar."""
        db_info = self.db_manager.get_database_info()
        self.status_bar.showMessage(f"Database: {db_info['directory']} ({db_info['size']})")
    
    def show_database_info(self):
        """Show the database information dialog."""
        dialog = DatabaseInfoDialog(self.db_manager, self)
        dialog.exec()
    
    def open_categories_tags_dialog(self):
        """Open the categories and tags management dialog for the current photo."""
        # Get currently selected photo
        current_items = self.photo_list.selectedItems()
        if not current_items:
            QMessageBox.information(
                self, 
                "No Photo Selected", 
                "Please select a photo first to manage its categories and tags.\n\n"
                "You can also use the 'Manage Categories' and 'Manage Tags' tabs "
                "to create and delete categories and tags."
            )
            return
        
        photo_data = current_items[0].data(Qt.UserRole)
        if not photo_data:
            QMessageBox.warning(self, "Error", "Could not get photo data.")
            return
        
        dialog = PhotoCategoriesTagsDialog(photo_data, self.db_manager, self)
        dialog.exec()
        
        # Refresh the photo list in case categories/tags changed and affect filtering
        self.load_photos()
    
    def load_data(self):
        """Load photos from database."""
        self.load_photos()
    
    def load_categories(self):
        """Load categories into the tree widget."""
        self.categories_tree.clear()
        categories = self.db_manager.get_categories()
        
        for category in categories:
            item = QTreeWidgetItem([category['name']])
            item.setData(0, Qt.UserRole, category['id'])
            self.categories_tree.addTopLevelItem(item)
    
    def load_tags(self):
        """Load tags into the tree widget."""
        self.tags_tree.clear()
        tags = self.db_manager.get_tags()
        
        for tag in tags:
            item = QTreeWidgetItem([tag['name']])
            item.setData(0, Qt.UserRole, tag['id'])
            self.tags_tree.addTopLevelItem(item)
    
    def load_photos(self, filters: Dict = None):
        """Load photos into the list widget."""
        self.photo_list.clear()
        self.current_photos = self.db_manager.get_photos(filters)
        
        for photo in self.current_photos:
            item = QListWidgetItem()
            item.setText(photo['filename'])
            item.setData(Qt.UserRole, photo)
            
            # Try to load thumbnail with proper orientation
            try:
                pixmap = ImageUtils.load_image_with_orientation(
                    photo['filepath'], 
                    QSize(150, 150)
                )
                if not pixmap.isNull():
                    item.setIcon(QIcon(pixmap))
            except Exception as e:
                print(f"Error loading thumbnail for {photo['filename']}: {e}")
            
            self.photo_list.addItem(item)
        
        self.photo_count_label.setText(f"{len(self.current_photos)} photos")
    
    def on_photo_selected(self, item: QListWidgetItem):
        """Handle photo selection to show details."""
        photo = item.data(Qt.UserRole)
        if photo:
            self.show_photo_details(photo)
    
    def format_gps_coordinate(self, lat: float, lon: float) -> str:
        """Format GPS coordinates for display."""
        if lat is None or lon is None:
            return ""
        
        # Format latitude
        lat_dir = "N" if lat >= 0 else "S"
        lat_abs = abs(lat)
        lat_deg = int(lat_abs)
        lat_min = (lat_abs - lat_deg) * 60
        
        # Format longitude  
        lon_dir = "E" if lon >= 0 else "W"
        lon_abs = abs(lon)
        lon_deg = int(lon_abs)
        lon_min = (lon_abs - lon_deg) * 60
        
        return f"{lat_deg}°{lat_min:.3f}'{lat_dir}, {lon_deg}°{lon_min:.3f}'{lon_dir}"
    
    def get_google_maps_link(self, lat: float, lon: float) -> str:
        """Generate a Google Maps link for the coordinates."""
        if lat is None or lon is None:
            return ""
        return f"https://www.google.com/maps?q={lat},{lon}"
    
    def show_photo_details(self, photo: Dict):
        """Display photo details in the right panel."""
        # Update preview with proper orientation
        try:
            pixmap = ImageUtils.load_image_with_orientation(
                photo['filepath'], 
                QSize(300, 300)
            )
            if not pixmap.isNull():
                self.photo_preview.setPixmap(pixmap)
            else:
                self.photo_preview.setText("No preview available")
        except Exception as e:
            print(f"Error loading preview for {photo['filename']}: {e}")
            self.photo_preview.setText("Preview error")
        
        # Get categories and tags for this photo
        photo_id = photo.get('id')
        categories_text = "None"
        tags_text = "None"
        
        if photo_id:
            try:
                categories = self.db_manager.get_photo_categories(photo_id)
                if categories:
                    categories_text = ", ".join([cat['name'] for cat in categories])
                
                tags = self.db_manager.get_photo_tags(photo_id)
                if tags:
                    tags_text = ", ".join([tag['name'] for tag in tags])
            except Exception as e:
                print(f"Error loading categories/tags: {e}")
        
        # Update details table
        details = [
            ("Filename", photo.get('filename', '')),
            ("Categories", categories_text),
            ("Tags", tags_text),
            ("File Size", f"{photo.get('file_size', 0) / 1024:.1f} KB" if photo.get('file_size') else ''),
            ("Dimensions", f"{photo.get('width', '')} × {photo.get('height', '')}" if photo.get('width') else ''),
            ("Date Added", photo.get('date_added', '')),
            ("Date Taken", photo.get('date_taken', '')),
            ("Camera", f"{photo.get('camera_make', '')} {photo.get('camera_model', '')}".strip()),
            ("Lens", photo.get('lens_model', '')),
            ("Focal Length", f"{photo.get('focal_length', '')}mm" if photo.get('focal_length') else ''),
            ("Aperture", f"f/{photo.get('aperture', '')}" if photo.get('aperture') else ''),
            ("Shutter Speed", photo.get('shutter_speed', '')),
            ("ISO", photo.get('iso', '')),
        ]
        
        # Add GPS information if available
        lat = photo.get('gps_latitude')
        lon = photo.get('gps_longitude')
        alt = photo.get('gps_altitude')
        location_name = photo.get('gps_location_name')
        
        if lat is not None and lon is not None:
            # Add formatted coordinates
            coords_formatted = self.format_gps_coordinate(lat, lon)
            details.append(("GPS Coordinates", coords_formatted))
            
            # Add decimal coordinates for reference
            details.append(("GPS (Decimal)", f"{lat:.6f}, {lon:.6f}"))
            
            # Add Google Maps link
            maps_link = self.get_google_maps_link(lat, lon)
            details.append(("Google Maps", maps_link))
        
        if alt is not None:
            alt_text = f"{alt:.1f}m" + (" above sea level" if alt >= 0 else " below sea level")
            details.append(("Altitude", alt_text))
            
        if location_name:
            details.append(("Location", location_name))
        
        self.details_table.setRowCount(len(details))
        for i, (prop, value) in enumerate(details):
            prop_item = QTableWidgetItem(prop)
            self.details_table.setItem(i, 0, prop_item)
            
            # Special styling for categories and tags
            if prop in ["Categories", "Tags"]:
                if value != "None":
                    # Use standard styling like other items
                    styled_item = QTableWidgetItem(value)
                    styled_item.setToolTip(f"Use 'Edit → Manage Categories/Tags' to modify")
                    self.details_table.setItem(i, 1, styled_item)
                else:
                    none_item = QTableWidgetItem(value)
                    none_item.setForeground(Qt.gray)
                    self.details_table.setItem(i, 1, none_item)
            # Special handling for Google Maps link
            elif prop == "Google Maps" and value:
                # Create a clickable link with standard styling
                link_item = QTableWidgetItem(f"View on Google Maps")
                link_item.setData(Qt.UserRole, value)  # Store the actual URL
                link_item.setToolTip(f"Double-click to open: {value}")
                self.details_table.setItem(i, 1, link_item)
            else:
                self.details_table.setItem(i, 1, QTableWidgetItem(str(value)))
        
        # Connect click handler for Google Maps links
        if not hasattr(self, '_details_click_connected'):
            self.details_table.itemDoubleClicked.connect(self.on_details_item_clicked)
            self._details_click_connected = True
    
    def on_details_item_clicked(self, item: QTableWidgetItem):
        """Handle clicks on detail items (for opening links)."""
        # Check if this is a Google Maps link
        prop_item = self.details_table.item(item.row(), 0)
        if prop_item and prop_item.text() == "Google Maps":
            url = item.data(Qt.UserRole)
            if url:
                try:
                    import webbrowser
                    webbrowser.open(url)
                except Exception as e:
                    QMessageBox.information(
                        self, 
                        "Google Maps", 
                        f"Could not open browser. You can manually visit:\n{url}"
                    )
    
    def filter_photos(self):
        """Filter photos based on search term."""
        search_term = self.search_edit.text()
        if search_term:
            self.load_photos({'search_term': search_term})
        else:
            self.load_photos()
    
    def delete_photo(self, photo_id: int):
        """Delete a photo from the catalog."""
        try:
            # Get photo details for confirmation
            photo = self.db_manager.get_photo_by_id(photo_id)
            if not photo:
                QMessageBox.warning(self, "Error", "Photo not found.")
                return
            
            # Ask for confirmation
            reply = QMessageBox.question(
                self,
                "Delete Photo",
                f"Are you sure you want to delete '{photo['filename']}' from the catalog?\n\n"
                "Note: This will only remove the photo from PhotoSphere catalog, "
                "not from your computer.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Delete from database
                if self.db_manager.delete_photo(photo_id):
                    self.status_bar.showMessage(f"Deleted: {photo['filename']}", 3000)
                    # Reload the photo list
                    self.load_photos()
                    # Clear the preview if this photo was selected
                    self.photo_preview.clear()
                    self.photo_preview.setText("Select a photo to view details")
                    self.details_table.setRowCount(0)
                else:
                    QMessageBox.warning(self, "Error", "Failed to delete photo from database.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while deleting the photo: {str(e)}")
    
    def import_photos_dialog(self):
        """Open file dialog to select photos for import."""
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(
            self,
            "Select Photos to Import",
            "",
            "Image Files (*.jpg *.jpeg *.png *.tiff *.bmp *.gif)"
        )
        
        print(f"Selected files: {file_paths}")
        
        if file_paths:
            self.import_photos(file_paths)
        else:
            print("No files selected for import")
    
    def import_photos(self, file_paths: List[str]):
        """Import photos with metadata extraction."""
        if not file_paths:
            return
            
        print(f"Starting import of {len(file_paths)} files...")
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        
        self.import_worker = PhotoImportWorker(file_paths, self.db_manager)
        self.import_worker.progress_updated.connect(self.progress_bar.setValue)
        self.import_worker.photo_imported.connect(self.on_photo_imported)
        self.import_worker.import_finished.connect(self.on_import_finished)
        self.import_worker.error_occurred.connect(self.on_import_error)
        self.import_worker.start()
    
    def on_photo_imported(self, photo_data: Dict):
        """Handle successful photo import."""
        self.status_bar.showMessage(f"Imported: {photo_data['filename']}", 1000)
    
    def on_import_error(self, error_message: str):
        """Handle import error."""
        print(f"Import error: {error_message}")
        # You can also show this in a message box if you want:
        # QMessageBox.warning(self, "Import Error", error_message)
    
    def on_import_finished(self):
        """Handle import completion."""
        self.progress_bar.hide()
        self.load_photos()
        self.status_bar.showMessage("Import completed successfully", 3000)
        print("Import process finished")


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("PhotoSphere")
    app.setApplicationVersion("1.0")
    
    # Show where the database will be stored
    app_data_dir = get_app_data_dir()
    print(f"Application data directory: {app_data_dir}")
    
    window = PhotoSphereMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()