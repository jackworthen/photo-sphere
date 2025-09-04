# PhotoSphere

A robust desktop application for organizing and cataloging your photography collection with automatic metadata extraction, GPS support, and comprehensive tagging system.

## 🚀 Features

- **📸 Photo Import**: Import photos with automatic metadata extraction
- **🏷️ Tag Management**: Create, assign, and filter photos by custom tags
- **🗃️ Smart Cataloging**: Organize your photo collection in a searchable database
- **📊 EXIF Data Parsing**: Extract comprehensive camera settings and technical details
- **🌍 GPS Support**: View location data and open coordinates in Google Maps
- **🖼️ Image Preview**: High-quality photo preview with proper EXIF orientation handling
- **🔍 Advanced Filtering**: Filter photos by tags, including untagged photos
- **📂 Multiple Sorting**: Sort by date, filename, file size, camera, ISO, or dimensions
- **⚡ Batch Operations**: Assign tags or remove multiple photos at once
- **🖱️ Drag & Drop**: Easy photo import by dragging files into the application
- **💾 Cross-Platform Database**: SQLite database with OS-specific storage locations
- **📄 Orientation Correction**: Automatic image rotation based on EXIF orientation data
- **📱 HEIC Support**: Modern iPhone/iPad HEIC format support with optional dependency
- **👆 Quick Access**: Double-click photos to open in your default image viewer
- **💿 Save Copy**: Save copies of photos to custom locations
- **🚀 Optimized Loading**: Fast startup with lazy thumbnail loading and caching

## 📋 Requirements

- Python 3.7 or higher
- PySide6 (Qt6 for Python)
- Pillow (Python Imaging Library)
- exifread
- pillow-heif (optional, for HEIC/HEIF support)

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jackworthen/photo-sphere.git
   cd photo-sphere
   ```

2. **Install basic dependencies:**
   ```bash
   pip install PySide6 Pillow exifread
   ```

3. **Install HEIC support (optional but recommended):**
   ```bash
   pip install pillow-heif
   ```

4. **Run the application:**
   ```bash
   python photosphere.py
   ```

### Alternative Installation with Virtual Environment

```bash
# Create virtual environment
python -m venv photosphere-env

# Activate virtual environment
# On Windows:
photosphere-env\Scripts\activate
# On macOS/Linux:
source photosphere-env/bin/activate

# Install dependencies
pip install PySide6 Pillow exifread

# Install HEIC support (optional)
pip install pillow-heif

# Run application
python photosphere.py
```

### HEIC/HEIF Support

PhotoSphere supports modern HEIC and HEIF image formats used by Apple devices (iPhone, iPad) and some Android phones. This support requires the optional `pillow-heif` library.

**To enable HEIC support:**
1. Install pillow-heif: `pip install pillow-heif`
2. Restart PhotoSphere

**Without HEIC support:**
- HEIC files can still be imported and cataloged
- Placeholder thumbnails will be shown
- All metadata except image dimensions will be extracted
- Double-click still opens files in your default viewer

## 🎯 Usage

### Getting Started

1. **Launch PhotoSphere** by running `python photosphere.py`
2. **Import Photos** using one of these methods:
   - Click "Import Photos" button and select files
   - Use the File menu → Import Photos
   - Drag and drop image files directly into the application

### Tag Management

- **Create Tags**: Use Tags → Manage Tags or create tags during assignment
- **Assign Tags**: Right-click photos to assign tags individually or in batches
- **Filter by Tags**: Use the tag filter dropdown to view photos by specific tags
- **Untagged Filter**: Quickly find photos without any tags assigned
- **Batch Operations**: Select multiple photos for batch tag assignment or removal

### Supported File Formats

**Standard Formats:**
- JPEG (.jpg, .jpeg)
- PNG (.png)
- TIFF (.tiff, .tif)
- BMP (.bmp)
- GIF (.gif)

**Modern Formats (with optional pillow-heif):**
- HEIC (.heic) - Apple's High Efficiency Image Container
- HEIF (.heif) - High Efficiency Image Format

> **Note:** HEIC/HEIF support requires installing `pillow-heif`. Without it, HEIC files can still be imported but will show placeholder thumbnails.

### Photo Operations

- **Single-click** to view photo details
- **Double-click** to open in your system's default image viewer
- **Right-click** for context menu with options:
  - Open in Default Viewer
  - Save Copy to custom location
  - Assign Tags
  - Remove from catalog
- **Multi-select** photos for batch operations
- **Drag & Drop** new photos to import

### Viewing and Sorting

- **Sort Options**: Date added/taken, filename, file size, camera, ISO, dimensions
- **Tag Filtering**: View all photos, untagged photos, or photos with specific tags
- **Photo Details**: View comprehensive EXIF data, GPS coordinates, and assigned tags
- **Filename Toggle**: Show or hide filenames below thumbnails

### Database Management

- **Database Location**: PhotoSphere stores its database in OS-specific locations:
  - **Windows**: `%APPDATA%\PhotoSphere\`
  - **macOS**: `~/Library/Application Support/PhotoSphere/`
  - **Linux**: `~/.local/share/PhotoSphere/`
- **Database Info**: Access via File → Database Information
- **Thumbnail Cleanup**: Remove orphaned thumbnail files
- **Backup**: The database file `photo_catalog.db` can be backed up from the database directory

## 🗂️ Database Schema

PhotoSphere uses SQLite with comprehensive photo and tag management:

```sql
photos (
    id INTEGER PRIMARY KEY,
    filename TEXT,
    filepath TEXT UNIQUE,
    file_size INTEGER,
    date_added TIMESTAMP,
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

tags (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    color TEXT,
    created_date TIMESTAMP
)

photo_tags (
    photo_id INTEGER,
    tag_id INTEGER,
    assigned_date TIMESTAMP
)
```

## 🔧 Technical Details

### Metadata Extraction

PhotoSphere extracts comprehensive metadata from photos including:

- **Basic Info**: Filename, file size, dimensions
- **Camera Data**: Make, model, lens model
- **Exposure Settings**: Aperture, shutter speed, ISO, focal length
- **GPS Data**: Latitude, longitude, altitude, location names
- **Technical**: Orientation, flash settings, date taken

### GPS Features

- Automatic GPS coordinate extraction from EXIF data
- Coordinate format conversion (degrees/minutes/seconds to decimal)
- Google Maps integration for viewing photo locations
- Support for altitude data

### Image Handling

- Proper EXIF orientation handling for correct image display
- Efficient thumbnail generation with caching for fast loading
- HEIC/HEIF format support with automatic conversion for display
- Lazy loading system for optimal performance with large collections
- Graceful handling of corrupted or unsupported files
- Cross-platform file opening in default image viewers

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes, please open an issue first to discuss what you would like to change.

### Development Setup

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🐛 Known Issues

- GPS extraction may not work with all camera models
- Very large photo collections may experience slower performance
- Some EXIF data might not be extracted from certain camera manufacturers
- HEIC files require the optional `pillow-heif` library for full support
- HEIC thumbnail generation may be slower than standard formats

## 🔧 Troubleshooting

### HEIC Files Not Displaying

If HEIC files show as gray placeholders:

1. **Check HEIC support status**: Look at the status bar or About dialog
2. **Install pillow-heif**: Run `pip install pillow-heif`
3. **Restart PhotoSphere**: Close and reopen the application
4. **Verify installation**: You should see "HEIC/HEIF support enabled" in the console

### Performance Issues

- Large collections: The lazy loading system should handle most cases efficiently
- Slow HEIC thumbnails: This is normal due to format conversion
- Memory usage: Restart the application if importing many large files

### Database Issues

- **Backup regularly**: Copy the database file from the application data directory
- **Location**: Use File → Database Information to find your database
- **Corruption**: Delete the database file to start fresh (imports will be lost)

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/jackworthen/photo-sphere/issues) page
2. Create a new issue if your problem isn't already reported
3. Provide detailed information about your system and the issue

---

Developed by [Jack Worthen](https://github.com/jackworthen)