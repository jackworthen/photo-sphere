"""
PhotoSphere Application - Simplified Version
A robust application for organizing and cataloging photography with metadata extraction.

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
    QSplitter, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QScrollArea, QFrame,
    QDialog, QDialogButtonBox, QFormLayout, QMessageBox,
    QProgressBar, QStatusBar, QMenuBar, QMenu, QFileDialog,
    QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QPoint
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
    
    def get_photos(self) -> List[Dict]:
        """Retrieve all photos."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM photos ORDER BY date_added DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def delete_photo(self, photo_id: int) -> bool:
        """Delete a photo from the database."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
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
    photo_open_requested = Signal(str)    # Signal emitted when photo should be opened in default viewer
    
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
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
    
    def show_context_menu(self, position: QPoint):
        """Show context menu for photo operations."""
        item = self.itemAt(position)
        if item is None:
            return
        
        photo_data = item.data(Qt.UserRole)
        if photo_data is None:
            return
        
        menu = QMenu(self)
        
        open_action = QAction("Open in Default Viewer", self)
        open_action.triggered.connect(lambda: self.photo_open_requested.emit(photo_data['filepath']))
        menu.addAction(open_action)
        
        menu.addSeparator()
        
        delete_action = QAction("Delete Photo", self)
        delete_action.triggered.connect(lambda: self.photo_delete_requested.emit(photo_data['id']))
        menu.addAction(delete_action)
        
        menu.exec(self.mapToGlobal(position))
    
    def on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on photo items."""
        photo_data = item.data(Qt.UserRole)
        if photo_data and photo_data.get('filepath'):
            self.photo_open_requested.emit(photo_data['filepath'])
    
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
        self.setGeometry(100, 100, 1200, 900)
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Create splitter for resizable panes
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Center panel (Photo grid)
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)
        
        # Right panel (Photo details)
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([800, 400])
        
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
        """Create the center panel with photo grid."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Toolbar with import button and photo count
        toolbar_layout = QHBoxLayout()
        
        # Import button
        import_btn = QPushButton("Import Photos")
        import_btn.clicked.connect(self.import_photos_dialog)
        toolbar_layout.addWidget(import_btn)
        
        # Spacer
        toolbar_layout.addStretch()
        
        # Photo count
        self.photo_count_label = QLabel("0 photos")
        toolbar_layout.addWidget(self.photo_count_label)
        
        layout.addLayout(toolbar_layout)
        
        # Photo list
        self.photo_list = PhotoListWidget()
        self.photo_list.itemClicked.connect(self.on_photo_selected)
        self.photo_list.photo_delete_requested.connect(self.delete_photo)
        self.photo_list.photo_open_requested.connect(self.open_photo_in_default_viewer)
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
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        documentation_action = QAction("Documentation", self)
        documentation_action.triggered.connect(self.open_documentation)
        help_menu.addAction(documentation_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def update_database_status(self):
        """Update the database information in the status bar."""
        db_info = self.db_manager.get_database_info()
        self.status_bar.showMessage(f"Database: {db_info['directory']} ({db_info['size']})")
    
    def show_database_info(self):
        """Show the database information dialog."""
        dialog = DatabaseInfoDialog(self.db_manager, self)
        dialog.exec()
    
    def open_documentation(self):
        """Open the documentation URL in the default browser."""
        import webbrowser
        url = "https://github.com/jackworthen/photo-sphere"
        try:
            webbrowser.open(url)
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error",
                f"Could not open browser. Please visit manually:\n{url}\n\nError: {e}"
            )
    
    def show_about(self):
        """Show the About dialog."""
        about_text = """
        <h3>PhotoSphere</h3>
        <p><b>Version:</b> 1.0</p>
        <p><b>Description:</b> A robust application for organizing and cataloging photography with metadata extraction.</p>
        
        <p><b>Features:</b></p>
        <ul>
        <li>Import photos with automatic metadata extraction</li>
        <li>EXIF data parsing including GPS coordinates</li>
        <li>Cross-platform database storage</li>
        <li>Drag & drop photo import</li>
        <li>Photo preview with proper orientation handling</li>
        <li>Double-click to open photos in default viewer</li>
        </ul>
        
        <p><b>Requirements:</b></p>
        <p>PySide6, Pillow, exifread</p>
        
        <p><b>Documentation:</b><br>
        <a href="https://github.com/jackworthen/photo-sphere">https://github.com/jackworthen/photo-sphere</a></p>
        
        <p><i>PhotoSphere - Your personal photo catalog solution</i></p>
        """
        
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("About PhotoSphere")
        msg_box.setTextFormat(Qt.RichText)
        msg_box.setText(about_text)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.exec()
    
    def load_data(self):
        """Load photos from database."""
        self.load_photos()
    
    def load_photos(self):
        """Load photos into the list widget."""
        self.photo_list.clear()
        self.current_photos = self.db_manager.get_photos()
        
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
        
        # Update details table
        details = [
            ("Filename", photo.get('filename', '')),
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
            
            # Special handling for Google Maps link
            if prop == "Google Maps" and value:
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
    
    def open_photo_in_default_viewer(self, file_path: str):
        """Open a photo in the system's default image viewer."""
        import subprocess
        import sys
        
        # Check if file exists
        if not os.path.exists(file_path):
            QMessageBox.warning(
                self,
                "File Not Found",
                f"The photo file could not be found:\n{file_path}\n\n"
                "The file may have been moved or deleted."
            )
            return
        
        try:
            if sys.platform == "win32":
                # Windows
                os.startfile(file_path)
            elif sys.platform == "darwin":
                # macOS
                subprocess.run(["open", file_path])
            else:
                # Linux and other Unix-like systems
                subprocess.run(["xdg-open", file_path])
            
            self.status_bar.showMessage(f"Opened: {os.path.basename(file_path)}", 2000)
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Error Opening Photo",
                f"Could not open the photo in the default viewer.\n\n"
                f"File: {file_path}\n"
                f"Error: {str(e)}\n\n"
                "Please check that you have an image viewer installed."
            )
    
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