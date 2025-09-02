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
    QHeaderView, QAbstractItemView, QComboBox, QLineEdit,
    QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QPoint
from PySide6.QtGui import QPixmap, QIcon, QDragEnterEvent, QDropEvent, QAction, QTransform

from PIL import Image
from PIL.ExifTags import TAGS
import exifread

# Add HEIC/HEIF support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTED = True
    print("HEIC/HEIF support enabled")
except ImportError:
    HEIC_SUPPORTED = False
    print("HEIC/HEIF support not available - install pillow-heif for HEIC support")


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


def get_resource_path(relative_path: str) -> Path:
    """Get the absolute path to a resource, works for both development and PyInstaller."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        # Development mode - resources are relative to this script
        base_path = Path(__file__).parent
    
    return base_path / relative_path


class DatabaseManager:
    """Handles all database operations for the PhotoSphere catalog."""
    
    def __init__(self, db_name: str = "photo_catalog.db"):
        # Get OS-specific application data directory
        self.app_data_dir = get_app_data_dir()
        
        # Create the directory if it doesn't exist
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Create thumbnail cache directory
        self.thumbnail_cache_dir = self.app_data_dir / "thumbnails"
        self.thumbnail_cache_dir.mkdir(exist_ok=True)
        
        # Set the full database path
        self.db_path = self.app_data_dir / db_name
        
        print(f"Database location: {self.db_path}")
        print(f"Thumbnail cache: {self.thumbnail_cache_dir}")
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables and indexes."""
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
            
            # Tags table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    color TEXT DEFAULT '#3498db',
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Photo-Tags junction table (many-to-many relationship)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS photo_tags (
                    photo_id INTEGER,
                    tag_id INTEGER,
                    assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (photo_id, tag_id),
                    FOREIGN KEY (photo_id) REFERENCES photos (id) ON DELETE CASCADE,
                    FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
                )
            ''')
            
            # Thumbnail cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS thumbnail_cache (
                    photo_id INTEGER PRIMARY KEY,
                    thumbnail_path TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_modified_date TIMESTAMP,
                    FOREIGN KEY (photo_id) REFERENCES photos (id) ON DELETE CASCADE
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
            
            # Create indexes for better performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_photos_date_added ON photos(date_added)",
                "CREATE INDEX IF NOT EXISTS idx_photos_date_taken ON photos(date_taken)",
                "CREATE INDEX IF NOT EXISTS idx_photos_filename ON photos(filename)",
                "CREATE INDEX IF NOT EXISTS idx_photos_filepath ON photos(filepath)",
                "CREATE INDEX IF NOT EXISTS idx_thumbnail_cache_photo_id ON thumbnail_cache(photo_id)",
                "CREATE INDEX IF NOT EXISTS idx_photo_tags_photo_id ON photo_tags(photo_id)",
                "CREATE INDEX IF NOT EXISTS idx_photo_tags_tag_id ON photo_tags(tag_id)",
                "CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name)"
            ]
            
            for index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                except Exception as e:
                    print(f"Error creating index: {e}")
            
            conn.commit()
            print("Database initialization completed")
    
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
    
    def get_thumbnail_path(self, photo_id: int, file_path: str) -> Optional[str]:
        """Get cached thumbnail path if it exists and is current."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT thumbnail_path, file_modified_date FROM thumbnail_cache WHERE photo_id = ?",
                (photo_id,)
            )
            result = cursor.fetchone()
            
            if result:
                thumb_path, cached_modified = result
                
                # Check if files exist and are current
                if thumb_path and os.path.exists(thumb_path) and os.path.exists(file_path):
                    try:
                        current_modified = datetime.fromtimestamp(
                            os.path.getmtime(file_path)
                        ).isoformat()
                        
                        if cached_modified == current_modified:
                            return thumb_path
                    except Exception as e:
                        print(f"Error checking file modification time: {e}")
            
        return None
    
    def cache_thumbnail(self, photo_id: int, file_path: str, thumbnail_pixmap: QPixmap) -> Optional[str]:
        """Cache a thumbnail for future use."""
        try:
            # Generate thumbnail filename
            thumb_filename = f"thumb_{photo_id}.jpg"
            thumb_path = self.thumbnail_cache_dir / thumb_filename
            
            # Save thumbnail
            if thumbnail_pixmap.save(str(thumb_path), "JPEG", 85):
                # Get file modification time
                file_modified = datetime.fromtimestamp(
                    os.path.getmtime(file_path)
                ).isoformat()
                
                # Update database
                with sqlite3.connect(str(self.db_path)) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT OR REPLACE INTO thumbnail_cache 
                        (photo_id, thumbnail_path, file_modified_date)
                        VALUES (?, ?, ?)
                    ''', (photo_id, str(thumb_path), file_modified))
                    conn.commit()
                
                return str(thumb_path)
            
        except Exception as e:
            print(f"Error caching thumbnail for photo {photo_id}: {e}")
        
        return None
    
    def cleanup_orphaned_thumbnails(self):
        """Clean up thumbnail files for deleted photos."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Get thumbnail paths for photos that no longer exist
                cursor.execute('''
                    SELECT tc.thumbnail_path 
                    FROM thumbnail_cache tc 
                    LEFT JOIN photos p ON tc.photo_id = p.id 
                    WHERE p.id IS NULL
                ''')
                
                orphaned_paths = cursor.fetchall()
                
                # Delete orphaned thumbnail files
                deleted_count = 0
                for (thumb_path,) in orphaned_paths:
                    try:
                        if thumb_path and os.path.exists(thumb_path):
                            os.remove(thumb_path)
                            deleted_count += 1
                    except Exception as e:
                        print(f"Error deleting thumbnail {thumb_path}: {e}")
                
                # Remove orphaned records from database
                cursor.execute('''
                    DELETE FROM thumbnail_cache 
                    WHERE photo_id NOT IN (SELECT id FROM photos)
                ''')
                
                conn.commit()
                
                if deleted_count > 0:
                    print(f"Cleaned up {deleted_count} orphaned thumbnails")
                    
        except Exception as e:
            print(f"Error cleaning up thumbnails: {e}")
    
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
        
        # Add thumbnail cache info
        cache_size = 0
        cache_count = 0
        try:
            for thumb_file in self.thumbnail_cache_dir.glob("thumb_*.jpg"):
                cache_size += thumb_file.stat().st_size
                cache_count += 1
            
            if cache_size < 1024 * 1024:
                cache_size_str = f"{cache_size / 1024:.1f} KB"
            else:
                cache_size_str = f"{cache_size / (1024 * 1024):.1f} MB"
            
            info['thumbnail_cache_size'] = cache_size_str
            info['thumbnail_count'] = str(cache_count)
        except:
            info['thumbnail_cache_size'] = "Unknown"
            info['thumbnail_count'] = "0"
        
        return info
    
    def get_photos(self, limit: Optional[int] = None, offset: int = 0, tag_filter: str = None) -> List[Dict]:
        """Retrieve photos with optional pagination and tag filtering."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            base_query = "SELECT DISTINCT p.* FROM photos p"
            where_clause = ""
            params = []
            
            if tag_filter == "Untagged":
                # Show photos with no tags
                base_query += " LEFT JOIN photo_tags pt ON p.id = pt.photo_id"
                where_clause = " WHERE pt.photo_id IS NULL"
            elif tag_filter and tag_filter != "All":
                # Show photos with specific tag
                base_query += " INNER JOIN photo_tags pt ON p.id = pt.photo_id INNER JOIN tags t ON pt.tag_id = t.id"
                where_clause = " WHERE t.name = ?"
                params.append(tag_filter)
            
            order_clause = " ORDER BY p.date_added DESC"
            
            if limit:
                limit_clause = " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
                query = base_query + where_clause + order_clause + limit_clause
            else:
                query = base_query + where_clause + order_clause
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_total_photo_count(self, tag_filter: str = None) -> int:
        """Get total number of photos with optional tag filtering."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            
            if tag_filter == "Untagged":
                cursor.execute('''
                    SELECT COUNT(DISTINCT p.id) 
                    FROM photos p 
                    LEFT JOIN photo_tags pt ON p.id = pt.photo_id 
                    WHERE pt.photo_id IS NULL
                ''')
            elif tag_filter and tag_filter != "All":
                cursor.execute('''
                    SELECT COUNT(DISTINCT p.id) 
                    FROM photos p 
                    INNER JOIN photo_tags pt ON p.id = pt.photo_id 
                    INNER JOIN tags t ON pt.tag_id = t.id 
                    WHERE t.name = ?
                ''', (tag_filter,))
            else:
                cursor.execute("SELECT COUNT(*) FROM photos")
            
            return cursor.fetchone()[0]
    
    def delete_photo(self, photo_id: int) -> bool:
        """Delete a photo from the database and its cached thumbnail."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                
                # Get thumbnail path before deleting
                cursor.execute("SELECT thumbnail_path FROM thumbnail_cache WHERE photo_id = ?", (photo_id,))
                result = cursor.fetchone()
                if result and result[0]:
                    thumb_path = result[0]
                    try:
                        if os.path.exists(thumb_path):
                            os.remove(thumb_path)
                    except Exception as e:
                        print(f"Error deleting thumbnail file: {e}")
                
                # Delete from photos table (thumbnail_cache and photo_tags will cascade delete)
                cursor.execute("DELETE FROM photos WHERE id = ?", (photo_id,))
                success = cursor.rowcount > 0
                
                conn.commit()
                return success
                
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
    
    # Tag management methods
    def create_tag(self, name: str, color: str = '#3498db') -> int:
        """Create a new tag."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO tags (name, color) VALUES (?, ?)", (name, color))
            return cursor.lastrowid
    
    def get_all_tags(self) -> List[Dict]:
        """Get all tags."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tags ORDER BY name")
            return [dict(row) for row in cursor.fetchall()]
    
    def update_tag(self, tag_id: int, name: str, color: str) -> bool:
        """Update a tag."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tags SET name = ?, color = ? WHERE id = ?", (name, color, tag_id))
            return cursor.rowcount > 0
    
    def delete_tag(self, tag_id: int) -> bool:
        """Delete a tag and all its associations."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
            return cursor.rowcount > 0
    
    def get_photo_tags(self, photo_id: int) -> List[Dict]:
        """Get all tags for a specific photo."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.* FROM tags t 
                INNER JOIN photo_tags pt ON t.id = pt.tag_id 
                WHERE pt.photo_id = ? 
                ORDER BY t.name
            ''', (photo_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def assign_tag_to_photo(self, photo_id: int, tag_id: int) -> bool:
        """Assign a tag to a photo."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)", (photo_id, tag_id))
                return True
        except:
            return False
    
    def remove_tag_from_photo(self, photo_id: int, tag_id: int) -> bool:
        """Remove a tag from a photo."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM photo_tags WHERE photo_id = ? AND tag_id = ?", (photo_id, tag_id))
                return cursor.rowcount > 0
        except:
            return False
    
    def set_photo_tags(self, photo_id: int, tag_ids: List[int]) -> bool:
        """Set all tags for a photo (replaces existing tags)."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                # Remove existing tags
                cursor.execute("DELETE FROM photo_tags WHERE photo_id = ?", (photo_id,))
                # Add new tags
                for tag_id in tag_ids:
                    cursor.execute("INSERT INTO photo_tags (photo_id, tag_id) VALUES (?, ?)", (photo_id, tag_id))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error setting photo tags: {e}")
            return False
    
    def batch_assign_tags_to_photos(self, photo_ids: List[int], tag_ids: List[int]) -> bool:
        """Assign tags to multiple photos at once."""
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                # Insert tags for each photo
                for photo_id in photo_ids:
                    for tag_id in tag_ids:
                        cursor.execute(
                            "INSERT OR IGNORE INTO photo_tags (photo_id, tag_id) VALUES (?, ?)", 
                            (photo_id, tag_id)
                        )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error batch assigning tags: {e}")
            return False
    
    def get_common_tags_for_photos(self, photo_ids: List[int]) -> List[Dict]:
        """Get tags that are common to all specified photos."""
        if not photo_ids:
            return []
            
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Get tags that appear in all photos
                placeholders = ','.join(['?' for _ in photo_ids])
                cursor.execute(f'''
                    SELECT t.*, COUNT(pt.photo_id) as photo_count
                    FROM tags t 
                    INNER JOIN photo_tags pt ON t.id = pt.tag_id 
                    WHERE pt.photo_id IN ({placeholders})
                    GROUP BY t.id, t.name, t.color, t.created_date
                    HAVING COUNT(pt.photo_id) = ?
                    ORDER BY t.name
                ''', photo_ids + [len(photo_ids)])
                
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error getting common tags: {e}")
            return []


class TagManagementDialog(QDialog):
    """Dialog for managing tags (create, edit, delete)."""
    
    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setWindowTitle("Manage Tags")
        self.setModal(True)
        self.setup_ui()
        self.load_tags()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Create new tag section
        new_tag_group = QGroupBox("Create New Tag")
        new_tag_layout = QHBoxLayout(new_tag_group)
        
        self.tag_name_input = QLineEdit()
        self.tag_name_input.setPlaceholderText("Enter tag name...")
        new_tag_layout.addWidget(QLabel("Name:"))
        new_tag_layout.addWidget(self.tag_name_input)
        
        create_button = QPushButton("Create Tag")
        create_button.clicked.connect(self.create_tag)
        new_tag_layout.addWidget(create_button)
        
        layout.addWidget(new_tag_group)
        
        # Existing tags section
        existing_tags_group = QGroupBox("Existing Tags")
        existing_layout = QVBoxLayout(existing_tags_group)
        
        self.tags_table = QTableWidget()
        self.tags_table.setColumnCount(3)
        self.tags_table.setHorizontalHeaderLabels(["Name", "Edit", "Delete"])
        self.tags_table.horizontalHeader().setStretchLastSection(True)
        self.tags_table.verticalHeader().hide()
        existing_layout.addWidget(self.tags_table)
        
        layout.addWidget(existing_tags_group)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)
        
        self.resize(500, 400)
    
    def create_tag(self):
        """Create a new tag."""
        name = self.tag_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Error", "Please enter a tag name.")
            return
        
        try:
            self.db_manager.create_tag(name)
            self.tag_name_input.clear()
            self.load_tags()
            QMessageBox.information(self, "Success", f"Tag '{name}' created successfully.")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create tag: {str(e)}")
    
    def load_tags(self):
        """Load existing tags into the table."""
        tags = self.db_manager.get_all_tags()
        self.tags_table.setRowCount(len(tags))
        
        for i, tag in enumerate(tags):
            # Name
            self.tags_table.setItem(i, 0, QTableWidgetItem(tag['name']))
            
            # Edit button
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(lambda checked, tag_id=tag['id']: self.edit_tag(tag_id))
            self.tags_table.setCellWidget(i, 1, edit_button)
            
            # Delete button
            delete_button = QPushButton("Delete")
            delete_button.clicked.connect(lambda checked, tag_id=tag['id'], tag_name=tag['name']: self.delete_tag(tag_id, tag_name))
            self.tags_table.setCellWidget(i, 2, delete_button)
    
    def edit_tag(self, tag_id: int):
        """Edit an existing tag."""
        # Find the tag in the current list
        tags = self.db_manager.get_all_tags()
        tag = next((t for t in tags if t['id'] == tag_id), None)
        if not tag:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Tag")
        layout = QVBoxLayout(dialog)
        
        form_layout = QFormLayout()
        name_input = QLineEdit(tag['name'])
        form_layout.addRow("Name:", name_input)
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            new_name = name_input.text().strip()
            if new_name:
                try:
                    # Use existing color or default
                    existing_color = tag.get('color', '#3498db')
                    self.db_manager.update_tag(tag_id, new_name, existing_color)
                    self.load_tags()
                    QMessageBox.information(self, "Success", f"Tag updated successfully.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to update tag: {str(e)}")
    
    def delete_tag(self, tag_id: int, tag_name: str):
        """Delete a tag."""
        reply = QMessageBox.question(
            self,
            "Delete Tag",
            f"Are you sure you want to delete the tag '{tag_name}'?\n\n"
            "This will remove the tag from all photos.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.delete_tag(tag_id)
                self.load_tags()
                QMessageBox.information(self, "Success", f"Tag '{tag_name}' deleted successfully.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to delete tag: {str(e)}")


class BatchTagAssignmentDialog(QDialog):
    """Dialog for assigning tags to multiple photos at once."""
    
    def __init__(self, db_manager: DatabaseManager, photo_ids: List[int], parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.photo_ids = photo_ids
        self.setWindowTitle(f"Batch Assign Tags - {len(photo_ids)} Photos")
        self.setModal(True)
        self.setup_ui()
        self.load_tags()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Info section
        info_label = QLabel(f"Assign tags to {len(self.photo_ids)} selected photos:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Instructions
        instructions = QLabel("✓ Checked tags will be added to ALL selected photos\n"
                             "○ Unchecked tags will be removed from ALL selected photos\n"
                             "◐ Partially checked tags are only on some photos")
        instructions.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 10px;")
        layout.addWidget(instructions)
        
        # Tags list with checkboxes
        self.tags_widget = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_widget)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.tags_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(300)
        layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        create_tag_button = QPushButton("Create New Tag")
        create_tag_button.clicked.connect(self.create_new_tag)
        button_layout.addWidget(create_tag_button)
        
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        apply_button = QPushButton("Apply Changes")
        apply_button.clicked.connect(self.apply_changes)
        apply_button.setStyleSheet("QPushButton { font-weight: bold; }")
        button_layout.addWidget(apply_button)
        
        layout.addLayout(button_layout)
        
        self.resize(500, 400)
    
    def load_tags(self):
        """Load all tags and show current assignments."""
        # Clear existing checkboxes
        for i in reversed(range(self.tags_layout.count())):
            self.tags_layout.itemAt(i).widget().setParent(None)
        
        all_tags = self.db_manager.get_all_tags()
        common_tags = self.db_manager.get_common_tags_for_photos(self.photo_ids)
        common_tag_ids = [tag['id'] for tag in common_tags]
        
        self.tag_checkboxes = {}
        
        # Get tags that exist on some but not all photos
        partially_assigned_tags = set()
        for photo_id in self.photo_ids:
            photo_tags = self.db_manager.get_photo_tags(photo_id)
            photo_tag_ids = [tag['id'] for tag in photo_tags]
            for tag_id in photo_tag_ids:
                if tag_id not in common_tag_ids:
                    partially_assigned_tags.add(tag_id)
        
        for tag in all_tags:
            checkbox = QCheckBox(tag['name'])
            
            if tag['id'] in common_tag_ids:
                # Tag is on all photos
                checkbox.setChecked(True)
                checkbox.setToolTip("This tag is assigned to all selected photos")
            elif tag['id'] in partially_assigned_tags:
                # Tag is on some but not all photos
                checkbox.setCheckState(Qt.PartiallyChecked)
                checkbox.setToolTip("This tag is assigned to some selected photos")
            else:
                # Tag is not on any photos
                checkbox.setChecked(False)
                checkbox.setToolTip("This tag is not assigned to any selected photos")
            
            self.tag_checkboxes[tag['id']] = checkbox
            self.tags_layout.addWidget(checkbox)
        
        if not all_tags:
            no_tags_label = QLabel("No tags available. Create some tags first.")
            no_tags_label.setStyleSheet("color: gray; font-style: italic;")
            self.tags_layout.addWidget(no_tags_label)
    
    def create_new_tag(self):
        """Open tag creation dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Tag")
        layout = QVBoxLayout(dialog)
        
        form_layout = QFormLayout()
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter tag name...")
        form_layout.addRow("Name:", name_input)
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            if name:
                try:
                    self.db_manager.create_tag(name)
                    self.load_tags()  # Refresh the tag list
                    QMessageBox.information(self, "Success", f"Tag '{name}' created successfully.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to create tag: {str(e)}")
    
class TagAssignmentDialog(QDialog):
    """Dialog for assigning tags to a single photo."""
    
    def __init__(self, db_manager: DatabaseManager, photo_id: int, photo_name: str, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.photo_id = photo_id
        self.setWindowTitle(f"Assign Tags - {photo_name}")
        self.setModal(True)
        self.setup_ui()
        self.load_tags()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Select tags to assign to this photo:")
        layout.addWidget(info_label)
        
        # Tags list with checkboxes
        self.tags_widget = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_widget)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.tags_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(300)
        layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        create_tag_button = QPushButton("Create New Tag")
        create_tag_button.clicked.connect(self.create_new_tag)
        button_layout.addWidget(create_tag_button)
        
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_tags)
        button_layout.addWidget(save_button)
        
        layout.addLayout(button_layout)
        
        self.resize(400, 350)
    
    def load_tags(self):
        """Load all tags and show current assignments."""
        # Clear existing checkboxes
        for i in reversed(range(self.tags_layout.count())):
            self.tags_layout.itemAt(i).widget().setParent(None)
        
        all_tags = self.db_manager.get_all_tags()
        photo_tags = self.db_manager.get_photo_tags(self.photo_id)
        photo_tag_ids = [tag['id'] for tag in photo_tags]
        
        self.tag_checkboxes = {}
        
        for tag in all_tags:
            checkbox = QCheckBox(tag['name'])
            checkbox.setChecked(tag['id'] in photo_tag_ids)
            
            self.tag_checkboxes[tag['id']] = checkbox
            self.tags_layout.addWidget(checkbox)
        
        if not all_tags:
            no_tags_label = QLabel("No tags available. Create some tags first.")
            no_tags_label.setStyleSheet("color: gray; font-style: italic;")
            self.tags_layout.addWidget(no_tags_label)
    
    def create_new_tag(self):
        """Open tag creation dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Tag")
        layout = QVBoxLayout(dialog)
        
        form_layout = QFormLayout()
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter tag name...")
        form_layout.addRow("Name:", name_input)
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            if name:
                try:
                    self.db_manager.create_tag(name)
                    self.load_tags()  # Refresh the tag list
                    QMessageBox.information(self, "Success", f"Tag '{name}' created successfully.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to create tag: {str(e)}")
    
    def save_tags(self):
        """Save tag assignments."""
        selected_tag_ids = []
        for tag_id, checkbox in self.tag_checkboxes.items():
            if checkbox.isChecked():
                selected_tag_ids.append(tag_id)
        
        if self.db_manager.set_photo_tags(self.photo_id, selected_tag_ids):
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to save tag assignments.")
    """Dialog for assigning tags to a photo."""
    
    def __init__(self, db_manager: DatabaseManager, photo_id: int, photo_name: str, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.photo_id = photo_id
        self.setWindowTitle(f"Assign Tags - {photo_name}")
        self.setModal(True)
        self.setup_ui()
        self.load_tags()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        info_label = QLabel("Select tags to assign to this photo:")
        layout.addWidget(info_label)
        
        # Tags list with checkboxes
        self.tags_widget = QWidget()
        self.tags_layout = QVBoxLayout(self.tags_widget)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.tags_widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(300)
        layout.addWidget(scroll_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        create_tag_button = QPushButton("Create New Tag")
        create_tag_button.clicked.connect(self.create_new_tag)
        button_layout.addWidget(create_tag_button)
        
        button_layout.addStretch()
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_tags)
        button_layout.addWidget(save_button)
        
        layout.addLayout(button_layout)
        
        self.resize(400, 350)
    
    def load_tags(self):
        """Load all tags and show current assignments."""
        # Clear existing checkboxes
        for i in reversed(range(self.tags_layout.count())):
            self.tags_layout.itemAt(i).widget().setParent(None)
        
        all_tags = self.db_manager.get_all_tags()
        photo_tags = self.db_manager.get_photo_tags(self.photo_id)
        photo_tag_ids = [tag['id'] for tag in photo_tags]
        
        self.tag_checkboxes = {}
        
        for tag in all_tags:
            checkbox = QCheckBox(tag['name'])
            checkbox.setChecked(tag['id'] in photo_tag_ids)
            
            self.tag_checkboxes[tag['id']] = checkbox
            self.tags_layout.addWidget(checkbox)
        
        if not all_tags:
            no_tags_label = QLabel("No tags available. Create some tags first.")
            no_tags_label.setStyleSheet("color: gray; font-style: italic;")
            self.tags_layout.addWidget(no_tags_label)
    
    def create_new_tag(self):
        """Open tag creation dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Create New Tag")
        layout = QVBoxLayout(dialog)
        
        form_layout = QFormLayout()
        name_input = QLineEdit()
        name_input.setPlaceholderText("Enter tag name...")
        form_layout.addRow("Name:", name_input)
        layout.addLayout(form_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec() == QDialog.Accepted:
            name = name_input.text().strip()
            if name:
                try:
                    self.db_manager.create_tag(name)
                    self.load_tags()  # Refresh the tag list
                    QMessageBox.information(self, "Success", f"Tag '{name}' created successfully.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to create tag: {str(e)}")
    
    def save_tags(self):
        """Save tag assignments."""
        selected_tag_ids = []
        for tag_id, checkbox in self.tag_checkboxes.items():
            if checkbox.isChecked():
                selected_tag_ids.append(tag_id)
        
        if self.db_manager.set_photo_tags(self.photo_id, selected_tag_ids):
            self.accept()
        else:
            QMessageBox.warning(self, "Error", "Failed to save tag assignments.")


class ThumbnailWorker(QThread):
    """Worker thread for generating thumbnails in the background."""
    
    thumbnail_ready = Signal(int, QPixmap)  # photo_id, pixmap
    thumbnail_failed = Signal(int, str)     # photo_id, error_message
    
    def __init__(self, photo_id: int, file_path: str, db_manager: DatabaseManager):
        super().__init__()
        self.photo_id = photo_id
        self.file_path = file_path
        self.db_manager = db_manager
    
    def run(self):
        """Generate thumbnail in background thread."""
        try:
            # Check cache first
            cached_thumb = self.db_manager.get_thumbnail_path(self.photo_id, self.file_path)
            if cached_thumb:
                pixmap = QPixmap(cached_thumb)
                if not pixmap.isNull():
                    self.thumbnail_ready.emit(self.photo_id, pixmap)
                    return
            
            # Check if original file still exists
            if not os.path.exists(self.file_path):
                self.thumbnail_failed.emit(self.photo_id, "File not found")
                return
            
            # Generate new thumbnail
            pixmap = ImageUtils.load_image_with_orientation(
                self.file_path, 
                QSize(120, 120)
            )
            
            if not pixmap.isNull():
                # Cache the thumbnail
                self.db_manager.cache_thumbnail(self.photo_id, self.file_path, pixmap)
                self.thumbnail_ready.emit(self.photo_id, pixmap)
            else:
                self.thumbnail_failed.emit(self.photo_id, "Failed to load image")
                
        except Exception as e:
            error_msg = f"Error generating thumbnail: {str(e)}"
            print(f"Thumbnail worker error for {self.file_path}: {error_msg}")
            self.thumbnail_failed.emit(self.photo_id, error_msg)


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
            # Method 1: Try the get_ifd method (works for most formats)
            try:
                gps_ifd = exif_data.get_ifd(0x8825)  # GPS IFD tag
                
                if gps_ifd:
                    print("GPS IFD found using get_ifd method")
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
                            print(f"GPS Latitude: {lat}")
                    
                    if gps_longitude and gps_longitude_ref:
                        lon = MetadataExtractor.convert_gps_coordinate(gps_longitude, gps_longitude_ref)
                        if lon is not None:
                            gps_info['gps_longitude'] = lon
                            print(f"GPS Longitude: {lon}")
                    
                    # Convert altitude
                    if gps_altitude:
                        try:
                            alt = float(gps_altitude)
                            # GPSAltitudeRef: 0 = above sea level, 1 = below sea level
                            if gps_altitude_ref == 1:
                                alt = -alt
                            gps_info['gps_altitude'] = alt
                            print(f"GPS Altitude: {alt}")
                        except:
                            pass
                    
                    # Try to get location name if available
                    gps_area_info = gps_ifd.get(28)  # GPSAreaInformation
                    if gps_area_info:
                        try:
                            location_name = str(gps_area_info)
                            if location_name and location_name != 'None':
                                gps_info['gps_location_name'] = location_name
                                print(f"GPS Location: {location_name}")
                        except:
                            pass
                
            except (AttributeError, TypeError) as e:
                print(f"get_ifd method failed: {e}, trying alternative method")
            
            # Method 2: Alternative method for HEIC and other formats
            if not gps_info:  # If no GPS data found with method 1
                print("Trying alternative GPS extraction method")
                
                # Look for GPS tags directly in EXIF data
                gps_tags = {
                    1: 'GPSLatitudeRef',
                    2: 'GPSLatitude', 
                    3: 'GPSLongitudeRef',
                    4: 'GPSLongitude',
                    5: 'GPSAltitudeRef',
                    6: 'GPSAltitude',
                    28: 'GPSAreaInformation'
                }
                
                gps_data = {}
                for tag_id, tag_name in gps_tags.items():
                    # Try to find GPS tags in the main EXIF data
                    if hasattr(exif_data, 'get'):
                        value = exif_data.get(tag_id + 0x8000)  # GPS tags are offset
                        if value is not None:
                            gps_data[tag_name] = value
                            print(f"Found GPS tag {tag_name}: {value}")
                
                # Process found GPS data
                if 'GPSLatitude' in gps_data and 'GPSLatitudeRef' in gps_data:
                    lat = MetadataExtractor.convert_gps_coordinate(
                        gps_data['GPSLatitude'], 
                        gps_data['GPSLatitudeRef']
                    )
                    if lat is not None:
                        gps_info['gps_latitude'] = lat
                        print(f"Alternative method - GPS Latitude: {lat}")
                
                if 'GPSLongitude' in gps_data and 'GPSLongitudeRef' in gps_data:
                    lon = MetadataExtractor.convert_gps_coordinate(
                        gps_data['GPSLongitude'], 
                        gps_data['GPSLongitudeRef']
                    )
                    if lon is not None:
                        gps_info['gps_longitude'] = lon
                        print(f"Alternative method - GPS Longitude: {lon}")
                
                if 'GPSAltitude' in gps_data:
                    try:
                        alt = float(gps_data['GPSAltitude'])
                        if 'GPSAltitudeRef' in gps_data and gps_data['GPSAltitudeRef'] == 1:
                            alt = -alt
                        gps_info['gps_altitude'] = alt
                        print(f"Alternative method - GPS Altitude: {alt}")
                    except:
                        pass
                        
        except Exception as e:
            print(f"Error extracting GPS info: {e}")
        
        if gps_info:
            print(f"Successfully extracted GPS info: {gps_info}")
        else:
            print("No GPS information found in EXIF data")
        
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
                
                print(f"Processing {metadata.get('format', 'unknown')} file: {file_path}")
                
                # Extract EXIF data using the newer method
                try:
                    exif_data = img.getexif()
                    if exif_data:
                        print(f"Found EXIF data with {len(exif_data)} tags")
                        
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
                        print("Attempting GPS extraction...")
                        gps_info = MetadataExtractor.extract_gps_info(exif_data)
                        metadata.update(gps_info)
                        
                    else:
                        print("No EXIF data found")
                        metadata['metadata'] = {}
                        
                except AttributeError:
                    # Fallback to old method for older Pillow versions
                    print("Using fallback EXIF extraction method")
                    metadata['metadata'] = {}
                
        except Exception as e:
            error_msg = f"Error extracting metadata from {file_path}: {e}"
            print(error_msg)
            metadata['metadata'] = {'error': str(e)}
        
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
    def is_heic_file(file_path: str) -> bool:
        """Check if a file is a HEIC/HEIF file."""
        return file_path.lower().endswith(('.heic', '.heif'))
    
    @staticmethod
    def load_image_with_orientation(file_path: str, max_size: QSize = None) -> QPixmap:
        """Load an image and apply proper orientation based on EXIF data."""
        try:
            # Check if it's a HEIC file and handle differently
            if ImageUtils.is_heic_file(file_path):
                if HEIC_SUPPORTED:
                    return ImageUtils.load_heic_image(file_path, max_size)
                else:
                    # HEIC file but no support - return a placeholder
                    print(f"HEIC file detected but support not available: {file_path}")
                    return ImageUtils.create_heic_placeholder(max_size)
            
            # Standard image loading for non-HEIC files
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
    
    @staticmethod
    def load_heic_image(file_path: str, max_size: QSize = None) -> QPixmap:
        """Load a HEIC/HEIF image and convert it to QPixmap."""
        try:
            print(f"Loading HEIC image: {file_path}")
            
            # Open HEIC image using Pillow with HEIF support
            with Image.open(file_path) as img:
                # Convert to RGB if not already (HEIC might be in different color space)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Get orientation from EXIF data
                orientation = None
                try:
                    exif_data = img.getexif()
                    if exif_data:
                        orientation = exif_data.get(274)  # 274 is the EXIF tag for Orientation
                except:
                    pass
                
                # Resize if max_size is specified
                if max_size:
                    # Calculate the size to fit within max_size while keeping aspect ratio
                    img.thumbnail((max_size.width(), max_size.height()), Image.Resampling.LANCZOS)
                
                # Convert PIL Image to QPixmap
                # First convert to bytes
                import io
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                
                # Create QPixmap from bytes
                pixmap = QPixmap()
                pixmap.loadFromData(img_byte_arr.getvalue())
                
                # Apply orientation correction if needed
                if orientation and not pixmap.isNull():
                    pixmap = ImageUtils.apply_exif_orientation(pixmap, orientation)
                
                print(f"Successfully loaded HEIC image: {file_path}")
                return pixmap
                
        except Exception as e:
            print(f"Error loading HEIC image {file_path}: {e}")
            # Try fallback method
            try:
                # Simple fallback - try to load as regular image (might work in some cases)
                pixmap = QPixmap(file_path)
                if not pixmap.isNull():
                    print(f"HEIC image loaded using fallback method: {file_path}")
                    if max_size:
                        pixmap = pixmap.scaled(max_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    return pixmap
            except:
                pass
            
            return QPixmap()
    
    @staticmethod
    def create_heic_placeholder(max_size: QSize = None) -> QPixmap:
        """Create a placeholder image for HEIC files when support is not available."""
        try:
            from PySide6.QtCore import Qt
            from PySide6.QtGui import QPainter, QFont, QColor
            
            # Create default size if not specified
            if max_size is None:
                width, height = 150, 150
            else:
                width, height = max_size.width(), max_size.height()
            
            # Create a pixmap with gray background
            pixmap = QPixmap(width, height)
            pixmap.fill(QColor(200, 200, 200))  # Light gray
            
            # Draw text on the pixmap
            painter = QPainter(pixmap)
            painter.setFont(QFont("Arial", max(8, width // 15)))
            painter.setPen(QColor(100, 100, 100))  # Dark gray text
            
            # Draw "HEIC" text
            text_rect = pixmap.rect()
            painter.drawText(text_rect, Qt.AlignCenter, "HEIC\nFile")
            
            # Draw smaller help text
            painter.setFont(QFont("Arial", max(6, width // 20)))
            help_rect = text_rect.adjusted(5, height//2, -5, -5)
            painter.drawText(help_rect, Qt.AlignCenter | Qt.TextWordWrap, "Install\npillow-heif\nfor support")
            
            painter.end()
            return pixmap
            
        except Exception as e:
            print(f"Error creating HEIC placeholder: {e}")
            # Return empty pixmap as fallback
            return QPixmap()


class PhotoImportWorker(QThread):
    """Worker thread for importing photos with metadata extraction."""
    
    progress_updated = Signal(int)
    photo_imported = Signal(dict)
    import_finished = Signal()
    error_occurred = Signal(str)
    heic_warning = Signal(str)  # New signal for HEIC warnings
    
    def __init__(self, file_paths: List[str], db_manager: DatabaseManager):
        super().__init__()
        self.file_paths = file_paths
        self.db_manager = db_manager
    
    def run(self):
        total_files = len(self.file_paths)
        successfully_imported = 0
        heic_files_found = []
        
        for i, file_path in enumerate(self.file_paths):
            try:
                print(f"Importing: {file_path}")
                
                # Check if it's a HEIC file without support
                if file_path.lower().endswith(('.heic', '.heif')) and not HEIC_SUPPORTED:
                    heic_files_found.append(Path(file_path).name)
                    print(f"HEIC file detected but support not available: {file_path}")
                
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
        
        # Emit HEIC warning if HEIC files were found but support is not available
        if heic_files_found and not HEIC_SUPPORTED:
            warning_msg = f"HEIC files detected but cannot be displayed:\n\n"
            warning_msg += "\n".join(heic_files_found)
            warning_msg += f"\n\nTo enable HEIC support, install pillow-heif:\npip install pillow-heif\n\nThen restart PhotoSphere."
            self.heic_warning.emit(warning_msg)
        
        print(f"Import completed: {successfully_imported}/{total_files} files imported successfully")
        self.import_finished.emit()


class PhotoListWidget(QListWidget):
    """Custom list widget for displaying photos with drag and drop support and lazy loading."""
    
    photo_delete_requested = Signal(int)  # Signal emitted when photo deletion is requested
    photo_open_requested = Signal(str)    # Signal emitted when photo should be opened in default viewer
    photo_save_copy_requested = Signal(str)  # Signal emitted when photo copy is requested (filepath)
    photo_assign_tags_requested = Signal(int, str)  # Signal emitted when tag assignment is requested (photo_id, photo_name)
    batch_assign_tags_requested = Signal(list)  # Signal emitted when batch tag assignment is requested (list of photo_ids)
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db_manager = db_manager
        self.thumbnail_workers = {}  # Track active thumbnail workers
        self.loaded_thumbnails = set()  # Track which thumbnails have been loaded
        self.pending_updates = []  # Track pending thumbnail updates
        
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setDefaultDropAction(Qt.CopyAction)
        self.setIconSize(QSize(120, 120))
        self.setResizeMode(QListWidget.Adjust)
        self.setViewMode(QListWidget.IconMode)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # Enable multi-selection
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # Set uniform item sizes to prevent layout issues
        self.setUniformItemSizes(True)
        self.setGridSize(QSize(130, 150))  # Slightly larger than icon for proper spacing
        
        # Connect to scroll changes for lazy loading
        self.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        self.itemEntered.connect(self.on_item_entered)
        
        # Timer for delayed loading to avoid loading during rapid scrolling
        self.load_timer = QTimer()
        self.load_timer.setSingleShot(True)
        self.load_timer.timeout.connect(self.load_visible_thumbnails)
        
        # Timer for batch thumbnail updates to prevent layout issues
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.process_pending_updates)
    
    def on_scroll_changed(self):
        """Handle scroll changes with delayed loading."""
        self.load_timer.stop()
        self.load_timer.start(150)  # 150ms delay
    
    def on_item_entered(self, item):
        """Load thumbnail when mouse hovers over item."""
        if item:
            self.load_thumbnail_for_item(item)
    
    def load_visible_thumbnails(self):
        """Load thumbnails only for currently visible items plus buffer."""
        try:
            viewport_rect = self.viewport().rect()
            
            # Find visible items
            visible_items = []
            for i in range(self.count()):
                item = self.item(i)
                if item:
                    item_rect = self.visualItemRect(item)
                    if item_rect.intersects(viewport_rect):
                        visible_items.append(item)
            
            # Add buffer items (items just outside visible area)
            buffer = 5  # Load 5 extra items above and below
            if visible_items:
                first_visible_row = self.row(visible_items[0])
                last_visible_row = self.row(visible_items[-1])
                
                # Add buffer items
                start_row = max(0, first_visible_row - buffer)
                end_row = min(self.count() - 1, last_visible_row + buffer)
                
                for row in range(start_row, end_row + 1):
                    item = self.item(row)
                    if item and item not in visible_items:
                        visible_items.append(item)
            
            # Load thumbnails for visible items
            for item in visible_items:
                self.load_thumbnail_for_item(item)
                
        except Exception as e:
            print(f"Error loading visible thumbnails: {e}")
    
    def load_thumbnail_for_item(self, item: QListWidgetItem):
        """Load thumbnail for a specific item if not already loaded."""
        if not item:
            return
            
        photo_data = item.data(Qt.UserRole)
        if not photo_data:
            return
            
        photo_id = photo_data.get('id')
        if not photo_id or photo_id in self.loaded_thumbnails:
            return
            
        # Don't start a new worker if one is already running for this photo
        if photo_id in self.thumbnail_workers:
            return
        
        file_path = photo_data.get('filepath')
        if not file_path:
            return
        
        # Start thumbnail worker
        worker = ThumbnailWorker(photo_id, file_path, self.db_manager)
        worker.thumbnail_ready.connect(self.on_thumbnail_ready)
        worker.thumbnail_failed.connect(self.on_thumbnail_failed)
        worker.finished.connect(lambda: self.cleanup_worker(photo_id))
        
        self.thumbnail_workers[photo_id] = worker
        worker.start()
    
    def on_thumbnail_ready(self, photo_id: int, pixmap: QPixmap):
        """Handle successful thumbnail generation with batch updates."""
        self.loaded_thumbnails.add(photo_id)
        
        # Add to pending updates instead of updating immediately
        self.pending_updates.append((photo_id, pixmap))
        
        # Start or restart the update timer to batch updates
        self.update_timer.stop()
        self.update_timer.start(50)  # 50ms delay to batch multiple updates
    
    def process_pending_updates(self):
        """Process all pending thumbnail updates in batch."""
        if not self.pending_updates:
            return
        
        # Temporarily disable updates to prevent flicker
        self.setUpdatesEnabled(False)
        
        try:
            # Process all pending updates
            for photo_id, pixmap in self.pending_updates:
                # Find the item with this photo_id and set its icon
                for i in range(self.count()):
                    item = self.item(i)
                    if item:
                        photo_data = item.data(Qt.UserRole)
                        if photo_data and photo_data.get('id') == photo_id:
                            item.setIcon(QIcon(pixmap))
                            break
            
            # Clear pending updates
            self.pending_updates.clear()
            
            # Force a complete layout recalculation
            self.doItemsLayout()
            
        finally:
            # Re-enable updates
            self.setUpdatesEnabled(True)
            # Force a repaint
            self.viewport().update()
    
    def on_thumbnail_failed(self, photo_id: int, error_message: str):
        """Handle thumbnail generation failure."""
        self.loaded_thumbnails.add(photo_id)  # Don't try again
        print(f"Thumbnail failed for photo {photo_id}: {error_message}")
    
    def cleanup_worker(self, photo_id: int):
        """Clean up completed worker threads."""
        if photo_id in self.thumbnail_workers:
            worker = self.thumbnail_workers[photo_id]
            worker.deleteLater()
            del self.thumbnail_workers[photo_id]
    
    def clear_thumbnails(self):
        """Clear all thumbnails and loaded state."""
        # Stop all running workers
        for worker in self.thumbnail_workers.values():
            worker.quit()
            worker.wait()
        self.thumbnail_workers.clear()
        self.loaded_thumbnails.clear()
        self.pending_updates.clear()
        self.update_timer.stop()
    
    def show_context_menu(self, position: QPoint):
        """Show context menu for photo operations."""
        item = self.itemAt(position)
        selected_items = self.selectedItems()
        
        if not selected_items:
            return
        
        menu = QMenu(self)
        
        if len(selected_items) == 1:
            # Single photo selected - show all options
            photo_data = selected_items[0].data(Qt.UserRole)
            if photo_data is None:
                return
            
            open_action = QAction("Open in Default Viewer", self)
            open_action.triggered.connect(lambda: self.photo_open_requested.emit(photo_data['filepath']))
            menu.addAction(open_action)
            
            save_copy_action = QAction("Save Copy", self)
            save_copy_action.triggered.connect(lambda: self.photo_save_copy_requested.emit(photo_data['filepath']))
            menu.addAction(save_copy_action)
            
            menu.addSeparator()
            
            assign_tags_action = QAction("Assign Tags", self)
            assign_tags_action.triggered.connect(
                lambda: self.photo_assign_tags_requested.emit(photo_data['id'], photo_data['filename'])
            )
            menu.addAction(assign_tags_action)
            
            menu.addSeparator()
            
            delete_action = QAction("Remove Photo", self)
            delete_action.triggered.connect(lambda: self.photo_delete_requested.emit(photo_data['id']))
            menu.addAction(delete_action)
            
        else:
            # Multiple photos selected - show batch operations only
            photo_ids = []
            photo_names = []
            for selected_item in selected_items:
                photo_data = selected_item.data(Qt.UserRole)
                if photo_data:
                    photo_ids.append(photo_data['id'])
                    photo_names.append(photo_data['filename'])
            
            if photo_ids:
                batch_assign_action = QAction(f"Assign Tags to {len(photo_ids)} Photos", self)
                batch_assign_action.triggered.connect(lambda: self.batch_assign_tags_requested.emit(photo_ids))
                menu.addAction(batch_assign_action)
                
                menu.addSeparator()
                
                # For now, we'll skip batch delete to avoid accidents
                # Could add it later with additional confirmation
                batch_info_action = QAction(f"{len(photo_ids)} photos selected", self)
                batch_info_action.setEnabled(False)
                menu.addAction(batch_info_action)
        
        menu.exec(self.mapToGlobal(position))
    
    def on_item_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on photo items."""
        photo_data = item.data(Qt.UserRole)
        if photo_data and photo_data.get('filepath'):
            self.photo_open_requested.emit(photo_data['filepath'])
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            supported_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif']
            if HEIC_SUPPORTED:
                supported_extensions.extend(['.heic', '.heif'])
            
            if any(url.toLocalFile().lower().endswith(tuple(supported_extensions)) 
                   for url in urls):
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            file_paths = []
            supported_extensions = ['.jpg', '.jpeg', '.png', '.tiff', '.bmp', '.gif']
            if HEIC_SUPPORTED:
                supported_extensions.extend(['.heic', '.heif'])
            
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(tuple(supported_extensions)):
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
        table = QTableWidget(6, 2)
        table.setHorizontalHeaderLabels(["Property", "Value"])
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().hide()
        
        data = [
            ("Database File", Path(info['path']).name),
            ("Directory", info['directory']),
            ("Full Path", info['path']),
            ("Database Size", info['size']),
            ("Thumbnail Cache Size", info.get('thumbnail_cache_size', 'Unknown')),
            ("Cached Thumbnails", info.get('thumbnail_count', '0'))
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
        
        cleanup_btn = QPushButton("Cleanup Thumbnails")
        cleanup_btn.clicked.connect(self.cleanup_thumbnails)
        button_layout.addWidget(cleanup_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        self.resize(500, 250)
    
    def cleanup_thumbnails(self):
        """Clean up orphaned thumbnails."""
        reply = QMessageBox.question(
            self,
            "Cleanup Thumbnails",
            "This will remove thumbnail files for photos that no longer exist in the catalog.\n\n"
            "Do you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.db_manager.cleanup_orphaned_thumbnails()
                QMessageBox.information(self, "Cleanup Complete", "Orphaned thumbnails have been cleaned up.")
                # Refresh the dialog
                self.accept()
                new_dialog = DatabaseInfoDialog(self.db_manager, self.parent())
                new_dialog.exec()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to cleanup thumbnails: {str(e)}")
    
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
    """Main application window with optimized loading."""
    
    def __init__(self):
        super().__init__()
        self.db_manager = DatabaseManager()
        self.current_photos = []
        self.current_tag_filter = "All"
        self.setup_ui()
        
        # Show window immediately, load data afterward
        QTimer.singleShot(0, self.load_data_async)
        
        # Show database location in status bar
        db_info = self.db_manager.get_database_info()
        heic_status = " | HEIC Support: Enabled" if HEIC_SUPPORTED else " | HEIC Support: Disabled"
        self.status_bar.showMessage(f"Database: {db_info['directory']}{heic_status}")
        
        # Set up a timer to periodically update database size in status
        self.db_info_timer = QTimer()
        self.db_info_timer.timeout.connect(self.update_database_status)
        self.db_info_timer.start(30000)  # Update every 30 seconds
    
    def setup_ui(self):
        self.setWindowTitle("PhotoSphere")
        self.setGeometry(100, 100, 1200, 900)
        
        # Set application icon
        try:
            icon_path = get_resource_path("ps_icon.ico")
            if icon_path.exists():
                icon = QIcon(str(icon_path))
                self.setWindowIcon(icon)
                print(f"Application icon loaded from: {icon_path}")
            else:
                print(f"Icon file not found at: {icon_path}")
        except Exception as e:
            print(f"Error loading application icon: {e}")
        
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
        
        # Toolbar with import button, tag filter, and photo count
        toolbar_layout = QHBoxLayout()
        
        # Import button
        import_btn = QPushButton("Import Photos")
        import_btn.clicked.connect(self.import_photos_dialog)
        toolbar_layout.addWidget(import_btn)
        
        # Tag filter dropdown
        filter_label = QLabel("Filter by Tag:")
        toolbar_layout.addWidget(filter_label)
        
        self.tag_filter_combo = QComboBox()
        self.tag_filter_combo.currentTextChanged.connect(self.on_tag_filter_changed)
        toolbar_layout.addWidget(self.tag_filter_combo)
        
        # Spacer
        toolbar_layout.addStretch()
        
        # Selection info (hidden by default)
        self.selection_info_label = QLabel("")
        self.selection_info_label.setStyleSheet("color: #0066cc; font-weight: bold;")
        self.selection_info_label.hide()
        toolbar_layout.addWidget(self.selection_info_label)
        
        # Photo count
        self.photo_count_label = QLabel("Loading photos...")
        toolbar_layout.addWidget(self.photo_count_label)
        
        layout.addLayout(toolbar_layout)
        
        # Photo list with db_manager reference
        self.photo_list = PhotoListWidget(self.db_manager)
        self.photo_list.itemClicked.connect(self.on_photo_selected)
        self.photo_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.photo_list.photo_delete_requested.connect(self.delete_photo)
        self.photo_list.photo_open_requested.connect(self.open_photo_in_default_viewer)
        self.photo_list.photo_save_copy_requested.connect(self.save_photo_copy)
        self.photo_list.photo_assign_tags_requested.connect(self.assign_tags_to_photo)
        self.photo_list.batch_assign_tags_requested.connect(self.batch_assign_tags_to_photos)
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
        self.photo_preview.setMinimumHeight(350)
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
        
        # Tags menu
        tags_menu = menubar.addMenu("Tags")
        
        manage_tags_action = QAction("Manage Tags", self)
        manage_tags_action.triggered.connect(self.manage_tags)
        tags_menu.addAction(manage_tags_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        documentation_action = QAction("Documentation", self)
        documentation_action.triggered.connect(self.open_documentation)
        help_menu.addAction(documentation_action)
        
        help_menu.addSeparator()
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def load_data_async(self):
        """Load data asynchronously after UI is shown."""
        # Clean up orphaned thumbnails on startup (in background)
        QTimer.singleShot(1000, self.db_manager.cleanup_orphaned_thumbnails)
        
        # Load tag filter options
        self.load_tag_filter_options()
        
        # Load photo metadata without thumbnails for fast startup
        self.load_photos_metadata_only()
        
        # Start loading visible thumbnails after a short delay
        QTimer.singleShot(200, self.photo_list.load_visible_thumbnails)
    
    def load_tag_filter_options(self):
        """Load tag filter dropdown options."""
        try:
            # Clear existing items
            self.tag_filter_combo.clear()
            
            # Add standard options
            self.tag_filter_combo.addItem("All")
            self.tag_filter_combo.addItem("Untagged")
            
            # Add separator
            self.tag_filter_combo.insertSeparator(2)
            
            # Add all tags
            tags = self.db_manager.get_all_tags()
            for tag in tags:
                self.tag_filter_combo.addItem(tag['name'])
            
            # Set default selection
            self.tag_filter_combo.setCurrentText("All")
            
        except Exception as e:
            print(f"Error loading tag filter options: {e}")
    
    def on_tag_filter_changed(self, tag_name: str):
        """Handle tag filter change."""
        if tag_name == "":  # Ignore empty selections
            return
            
        self.current_tag_filter = tag_name
        self.load_photos_metadata_only()
        # Start loading visible thumbnails after a short delay
        QTimer.singleShot(100, self.photo_list.load_visible_thumbnails)
    
    def load_photos_metadata_only(self):
        """Load photo metadata without thumbnails for fast startup."""
        try:
            self.photo_list.clear_thumbnails()
            self.photo_list.clear()
            
            # Apply current tag filter
            tag_filter = None if self.current_tag_filter == "All" else self.current_tag_filter
            self.current_photos = self.db_manager.get_photos(tag_filter=tag_filter)
            
            for photo in self.current_photos:
                item = QListWidgetItem()
                item.setText(photo['filename'])
                item.setData(Qt.UserRole, photo)
                
                # Don't set any placeholder icon - let thumbnails appear as they load
                # This should prevent layout conflicts
                
                self.photo_list.addItem(item)
            
            # Update photo count with filter info
            total_count = len(self.current_photos)
            if self.current_tag_filter == "All":
                self.photo_count_label.setText(f"{total_count} photos")
            else:
                self.photo_count_label.setText(f"{total_count} photos ({self.current_tag_filter})")
            
            # Update status
            if len(self.current_photos) > 0:
                filter_status = f" (filtered by '{self.current_tag_filter}')" if self.current_tag_filter != "All" else ""
                self.status_bar.showMessage(f"Photos loaded{filter_status} - thumbnails loading in background", 3000)
            else:
                filter_status = f" matching '{self.current_tag_filter}'" if self.current_tag_filter != "All" else ""
                self.status_bar.showMessage(f"No photos{filter_status} in catalog", 3000)
                
        except Exception as e:
            print(f"Error loading photos: {e}")
            self.photo_count_label.setText("Error loading photos")
            QMessageBox.warning(self, "Error", f"Failed to load photos: {str(e)}")
    
    def update_database_status(self):
        """Update the database information in the status bar."""
        db_info = self.db_manager.get_database_info()
        heic_status = " | HEIC Support: Enabled" if HEIC_SUPPORTED else " | HEIC Support: Disabled"
        self.status_bar.showMessage(f"Database: {db_info['directory']} ({db_info['size']}){heic_status}")
    
    def show_database_info(self):
        """Show the database information dialog."""
        dialog = DatabaseInfoDialog(self.db_manager, self)
        dialog.exec()
    
    def manage_tags(self):
        """Show the tag management dialog."""
        dialog = TagManagementDialog(self.db_manager, self)
        dialog.exec()
        
        # Always refresh tag filter options after tag management dialog closes
        # (user might have created/edited/deleted tags)
        self.load_tag_filter_options()
        
        # Refresh photo list if we're viewing details (tags might have changed)
        if hasattr(self, 'current_selected_photo'):
            self.show_photo_details(self.current_selected_photo)
    
    def assign_tags_to_photo(self, photo_id: int, photo_name: str):
        """Show tag assignment dialog for a photo."""
        dialog = TagAssignmentDialog(self.db_manager, photo_id, photo_name, self)
        if dialog.exec() == QDialog.Accepted:
            # Always refresh tag filter options (user might have created new tags)
            self.load_tag_filter_options()
            
            # Refresh the current view if needed
            if self.current_tag_filter != "All":
                self.load_photos_metadata_only()
                QTimer.singleShot(100, self.photo_list.load_visible_thumbnails)
            
            # Refresh photo details if this photo is currently selected
            if hasattr(self, 'current_selected_photo') and self.current_selected_photo.get('id') == photo_id:
                updated_photo = self.db_manager.get_photo_by_id(photo_id)
                if updated_photo:
                    self.current_selected_photo = updated_photo
                    self.show_photo_details(updated_photo)
    
    def batch_assign_tags_to_photos(self, photo_ids: List[int]):
        """Show batch tag assignment dialog for multiple photos."""
        if not photo_ids:
            return
            
        dialog = BatchTagAssignmentDialog(self.db_manager, photo_ids, self)
        if dialog.exec() == QDialog.Accepted:
            # Always refresh tag filter options (user might have created new tags)
            self.load_tag_filter_options()
            
            # Refresh the current view if we're filtering by tags
            if self.current_tag_filter != "All":
                self.load_photos_metadata_only()
                QTimer.singleShot(100, self.photo_list.load_visible_thumbnails)
            
            # Refresh photo details if one of the batch photos is currently selected
            if hasattr(self, 'current_selected_photo'):
                current_id = self.current_selected_photo.get('id')
                if current_id and current_id in photo_ids:
                    updated_photo = self.db_manager.get_photo_by_id(current_id)
                    if updated_photo:
                        self.current_selected_photo = updated_photo
                        self.show_photo_details(updated_photo)
            
            self.status_bar.showMessage(f"Updated tags for {len(photo_ids)} photos", 3000)
    
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
        heic_status = "✓ Enabled" if HEIC_SUPPORTED else "✗ Not Available"
        heic_instructions = "" if HEIC_SUPPORTED else "<br><b>To enable HEIC support:</b><br>1. Run: <code>pip install pillow-heif</code><br>2. Restart PhotoSphere"
        
        about_text = f"""
        <h3>PhotoSphere</h3>
        <p><b>Version:</b> 1.2 (Tag System)</p>
        <p><b>Description:</b> A robust application for organizing and cataloging photography with metadata extraction and tagging system.</p>
        
        <p><b>Features:</b></p>
        <ul>
        <li>Import photos with automatic metadata extraction</li>
        <li>EXIF data parsing including GPS coordinates</li>
        <li>Tag management and photo categorization</li>
        <li>Filter photos by tags</li>
        <li>Cross-platform database storage</li>
        <li>Drag & drop photo import</li>
        <li>Photo preview with proper orientation handling</li>
        <li>Double-click to open photos in default viewer</li>
        <li>Save copies of photos to custom locations</li>
        <li>Optimized lazy loading for fast startup</li>
        <li>Thumbnail caching system</li>
        </ul>
        
        <p><b>Supported Formats:</b></p>
        <ul>
        <li>JPEG, PNG, TIFF, BMP, GIF</li>
        <li>HEIC/HEIF: {heic_status}</li>
        </ul>
        {heic_instructions}
        
        <p><b>Requirements:</b></p>
        <p>PySide6, Pillow, exifread<br>
        <i>Optional:</i> pillow-heif (for HEIC/HEIF support)</p>
        
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
        """Load photos from database (kept for compatibility)."""
        self.load_photos_metadata_only()
    
    def on_photo_selected(self, item: QListWidgetItem):
        """Handle photo selection to show details."""
        # Only show details if exactly one photo is selected
        selected_items = self.photo_list.selectedItems()
        if len(selected_items) == 1:
            photo = item.data(Qt.UserRole)
            if photo:
                self.current_selected_photo = photo  # Store for refresh purposes
                self.show_photo_details(photo)
                # Ensure thumbnail is loaded for selected photo
                self.photo_list.load_thumbnail_for_item(item)
        else:
            # Multiple photos selected or none selected
            self.photo_preview.clear()
            self.photo_preview.setText("Select a single photo to view details")
            self.details_table.setRowCount(0)
    
    def on_selection_changed(self):
        """Handle changes in photo selection."""
        selected_items = self.photo_list.selectedItems()
        count = len(selected_items)
        
        if count > 1:
            # Multiple photos selected
            self.selection_info_label.setText(f"{count} photos selected")
            self.selection_info_label.show()
            
            # Clear details panel
            self.photo_preview.clear()
            self.photo_preview.setText(f"{count} photos selected\nRight-click to assign tags to all")
            self.details_table.setRowCount(0)
            
        elif count == 1:
            # Single photo selected
            self.selection_info_label.hide()
            # Details will be shown by on_photo_selected
            
        else:
            # No photos selected
            self.selection_info_label.hide()
            self.photo_preview.clear()
            self.photo_preview.setText("Select a photo to view details")
            self.details_table.setRowCount(0)
    
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
                QSize(400, 400)
            )
            if not pixmap.isNull():
                self.photo_preview.setPixmap(pixmap)
            else:
                self.photo_preview.setText("No preview available")
        except Exception as e:
            print(f"Error loading preview for {photo['filename']}: {e}")
            self.photo_preview.setText("Preview error")
        
        # Helper function to check if value should be displayed
        def should_show_value(value):
            if value is None:
                return False
            if isinstance(value, str):
                return value.strip() != "" and value.strip().lower() != "none"
            return True
        
        # Get tags for this photo
        photo_tags = self.db_manager.get_photo_tags(photo['id'])
        
        # Build details list starting with tags
        details = []
        
        # Add tags at the top if they exist
        if photo_tags:
            tag_names = [tag['name'] for tag in photo_tags]
            tag_display = ", ".join(tag_names)
            details.append(("Tags", tag_display))
        
        # Add other photo details
        details.extend([
            ("Filename", photo.get('filename', '')),
            ("File Size", f"{photo.get('file_size', 0) / (1024 * 1024):.2f} MB" if photo.get('file_size') else ''),
            ("Dimensions", f"{photo.get('width', '')} × {photo.get('height', '')}" if photo.get('width') else ''),
            ("Date Added", photo.get('date_added', '')),
            ("Date Taken", photo.get('date_taken', '')),
            ("Camera", f"{photo.get('camera_make', '')} {photo.get('camera_model', '')}".strip()),
            ("Lens", photo.get('lens_model', '')),
            ("Focal Length", f"{photo.get('focal_length', '')}mm" if photo.get('focal_length') else ''),
            ("Aperture", f"f/{photo.get('aperture', '')}" if photo.get('aperture') else ''),
            ("Shutter Speed", photo.get('shutter_speed', '')),
            ("ISO", photo.get('iso', '')),
        ])
        
        # Filter out empty values
        details = [(prop, value) for prop, value in details if should_show_value(value)]
        
        # Add GPS information if available
        lat = photo.get('gps_latitude')
        lon = photo.get('gps_longitude')
        alt = photo.get('gps_altitude')
        location_name = photo.get('gps_location_name')
        
        if lat is not None and lon is not None:
            # Add formatted coordinates
            coords_formatted = self.format_gps_coordinate(lat, lon)
            if should_show_value(coords_formatted):
                details.append(("GPS Coordinates", coords_formatted))
            
            # Add decimal coordinates for reference
            decimal_coords = f"{lat:.6f}, {lon:.6f}"
            if should_show_value(decimal_coords):
                details.append(("GPS (Decimal)", decimal_coords))
            
            # Add Google Maps link
            maps_link = self.get_google_maps_link(lat, lon)
            if should_show_value(maps_link):
                details.append(("Google Maps", maps_link))
        
        if alt is not None:
            alt_text = f"{alt:.1f}m" + (" above sea level" if alt >= 0 else " below sea level")
            if should_show_value(alt_text):
                details.append(("Altitude", alt_text))
            
        if should_show_value(location_name):
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
    
    def save_photo_copy(self, file_path: str):
        """Save a copy of the photo to a user-selected location."""
        try:
            # Check if source file exists
            if not os.path.exists(file_path):
                QMessageBox.warning(
                    self,
                    "File Not Found",
                    f"The source photo file could not be found:\n{file_path}\n\n"
                    "The file may have been moved or deleted."
                )
                return
            
            # Get the original filename and extension
            source_path = Path(file_path)
            original_filename = source_path.name
            file_extension = source_path.suffix.lower()
            
            # Set up file filter based on the original file type
            file_filters = []
            
            if file_extension in ['.jpg', '.jpeg']:
                file_filters.append("JPEG Images (*.jpg *.jpeg)")
            elif file_extension == '.png':
                file_filters.append("PNG Images (*.png)")
            elif file_extension in ['.tiff', '.tif']:
                file_filters.append("TIFF Images (*.tiff *.tif)")
            elif file_extension == '.bmp':
                file_filters.append("BMP Images (*.bmp)")
            elif file_extension == '.gif':
                file_filters.append("GIF Images (*.gif)")
            elif file_extension in ['.heic', '.heif']:
                file_filters.append("HEIC/HEIF Images (*.heic *.heif)")
            
            # Add common image formats
            file_filters.extend([
                "JPEG Images (*.jpg *.jpeg)",
                "PNG Images (*.png)",
                "TIFF Images (*.tiff *.tif)",
                "BMP Images (*.bmp)",
                "GIF Images (*.gif)"
            ])
            
            if HEIC_SUPPORTED:
                file_filters.append("HEIC/HEIF Images (*.heic *.heif)")
            
            file_filters.append("All Files (*)")
            
            # Create save dialog
            save_dialog = QFileDialog(self)
            save_dialog.setAcceptMode(QFileDialog.AcceptSave)
            save_dialog.setFileMode(QFileDialog.AnyFile)
            save_dialog.setNameFilters(file_filters)
            save_dialog.setDefaultSuffix(file_extension.lstrip('.'))
            
            # Set default filename
            save_dialog.selectFile(original_filename)
            
            # Set dialog title
            save_dialog.setWindowTitle(f"Save Copy of {original_filename}")
            
            # Show dialog and get result
            if save_dialog.exec() == QDialog.Accepted:
                selected_files = save_dialog.selectedFiles()
                if selected_files:
                    destination_path = selected_files[0]
                    
                    # Check if destination already exists
                    if os.path.exists(destination_path):
                        reply = QMessageBox.question(
                            self,
                            "File Exists",
                            f"A file already exists at:\n{destination_path}\n\n"
                            "Do you want to overwrite it?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        
                        if reply != QMessageBox.Yes:
                            return
                    
                    # Copy the file
                    try:
                        shutil.copy2(file_path, destination_path)
                        self.status_bar.showMessage(
                            f"Copy saved: {Path(destination_path).name}", 
                            5000
                        )
                        
                        # Show success message
                        QMessageBox.information(
                            self,
                            "Copy Saved",
                            f"Photo copy successfully saved to:\n{destination_path}"
                        )
                        
                    except Exception as copy_error:
                        QMessageBox.critical(
                            self,
                            "Copy Failed",
                            f"Failed to copy the photo.\n\n"
                            f"Source: {file_path}\n"
                            f"Destination: {destination_path}\n\n"
                            f"Error: {str(copy_error)}"
                        )
        
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while preparing to save the photo copy:\n\n{str(e)}"
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
                "Remove Photo",
                f"Are you sure you want to remove '{photo['filename']}' from the catalog?\n\n"
                "Note: This will only remove the photo from PhotoSphere catalog, "
                "not from your computer.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Delete from database
                if self.db_manager.delete_photo(photo_id):
                    self.status_bar.showMessage(f"Removed: {photo['filename']}", 3000)
                    # Reload the photo list
                    self.load_photos_metadata_only()
                    # Start loading visible thumbnails
                    QTimer.singleShot(100, self.photo_list.load_visible_thumbnails)
                    # Clear the preview if this photo was selected
                    self.photo_preview.clear()
                    self.photo_preview.setText("Select a photo to view details")
                    self.details_table.setRowCount(0)
                else:
                    QMessageBox.warning(self, "Error", "Failed to remove photo from database.")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred while removing the photo: {str(e)}")
    
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
        
        # Build comprehensive file filters
        filters = []
        
        # All supported images filter
        all_extensions = "*.jpg *.jpeg *.png *.tiff *.tif *.bmp *.gif"
        if HEIC_SUPPORTED:
            all_extensions += " *.heic *.heif"
        filters.append(f"All Supported Images ({all_extensions})")
        
        # Individual format filters
        filters.append("JPEG Images (*.jpg *.jpeg)")
        filters.append("PNG Images (*.png)")
        filters.append("TIFF Images (*.tiff *.tif)")
        filters.append("BMP Images (*.bmp)")
        filters.append("GIF Images (*.gif)")
        
        # Add HEIC filter if supported
        if HEIC_SUPPORTED:
            filters.append("HEIC/HEIF Images (*.heic *.heif)")
        
        # All files fallback
        filters.append("All Files (*)")
        
        # Join all filters
        file_filter = ";;".join(filters)
        
        print(f"HEIC Support: {HEIC_SUPPORTED}")
        print(f"File filter: {file_filter}")
        
        file_paths, _ = file_dialog.getOpenFileNames(
            self,
            "Select Photos to Import",
            "",
            file_filter
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
        self.import_worker.heic_warning.connect(self.on_heic_warning)
        self.import_worker.start()
    
    def on_photo_imported(self, photo_data: Dict):
        """Handle successful photo import."""
        self.status_bar.showMessage(f"Imported: {photo_data['filename']}", 1000)
    
    def on_import_error(self, error_message: str):
        """Handle import error."""
        print(f"Import error: {error_message}")
    
    def on_heic_warning(self, warning_message: str):
        """Handle HEIC support warning."""
        QMessageBox.warning(
            self,
            "HEIC Support Required",
            warning_message
        )
    
    def on_import_finished(self):
        """Handle import completion."""
        self.progress_bar.hide()
        # Refresh tag filter options (in case we need to update counts)
        self.load_tag_filter_options()
        # Reload photos
        self.load_photos_metadata_only()
        # Start loading visible thumbnails
        QTimer.singleShot(100, self.photo_list.load_visible_thumbnails)
        self.status_bar.showMessage("Import completed successfully", 3000)
        print("Import process finished")


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("PhotoSphere")
    app.setApplicationVersion("1.2")
    
    # Set application icon for taskbar, alt-tab, etc.
    try:
        icon_path = get_resource_path("ps_icon.ico")
        if icon_path.exists():
            app_icon = QIcon(str(icon_path))
            app.setWindowIcon(app_icon)
            print(f"Application icon set from: {icon_path}")
        else:
            print(f"Icon file not found at: {icon_path}")
    except Exception as e:
        print(f"Error setting application icon: {e}")
    
    # Show where the database will be stored
    app_data_dir = get_app_data_dir()
    print(f"Application data directory: {app_data_dir}")
    
    window = PhotoSphereMainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()