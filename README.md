# PhotoSphere

A robust desktop application for organizing and cataloging your photography collection with automatic metadata extraction and GPS support.

## 🚀 Features

- **📸 Photo Import**: Import photos with automatic metadata extraction
- **🗃️ Smart Cataloging**: Organize your photo collection in a searchable database
- **📊 EXIF Data Parsing**: Extract comprehensive camera settings and technical details
- **🌍 GPS Support**: View location data and open coordinates in Google Maps
- **🖼️ Image Preview**: High-quality photo preview with proper EXIF orientation handling
- **🖱️ Drag & Drop**: Easy photo import by dragging files into the application
- **💾 Cross-Platform Database**: SQLite database with OS-specific storage locations
- **🔄 Orientation Correction**: Automatic image rotation based on EXIF orientation data
- **📱 HEIC Support**: Modern iPhone/iPad HEIC format support with optional dependency
- **👆 Quick Access**: Double-click photos to open in your default image viewer

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

### Viewing Photo Details

- **Single-click** on any photo in the grid to view its details
- **Double-click** on any photo to open it in your system's default image viewer
- Photo details include:
  - Camera make and model
  - Lens information
  - Camera settings (aperture, shutter speed, ISO)
  - Date taken
  - File size and dimensions
  - GPS coordinates (if available)
  - Google Maps integration for location data

### Working with HEIC Files

- **With HEIC support enabled**: Full thumbnails, previews, and metadata extraction
- **Without HEIC support**: Files are cataloged with placeholder thumbnails and basic metadata
- **Double-click**: Opens HEIC files in your default viewer regardless of PhotoSphere's HEIC support
- **Status indicator**: Check the status bar to see if HEIC support is enabled

### Database Management

- **Database Location**: PhotoSphere stores its database in OS-specific locations:
  - **Windows**: `%APPDATA%\PhotoSphere\`
  - **macOS**: `~/Library/Application Support/PhotoSphere/`
  - **Linux**: `~/.local/share/PhotoSphere/`
- **Database Info**: Access via File → Database Information
- **Backup**: The database file `photo_catalog.db` can be backed up from the database directory

## 🗂️ Database Schema

PhotoSphere uses SQLite with the following structure:

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
- Efficient thumbnail generation for all supported formats
- HEIC/HEIF format support with automatic conversion for display
- Graceful handling of corrupted or unsupported files
- Placeholder generation for unsupported formats
- Cross-platform file opening in default image viewers

## 📸 Screenshots

*Add screenshots of your application here*

## 🚧 Development

### Project Structure

```
photo-sphere/
├── photosphere.py          # Main application file
├── README.md              # This file
└── requirements.txt       # Python dependencies (optional)
```

### requirements.txt (suggested content)

```
PySide6>=6.0.0
Pillow>=8.0.0
exifread>=2.3.0
pillow-heif>=0.10.0  # Optional: for HEIC/HEIF support
```

### Key Classes

- `PhotoSphereMainWindow`: Main application window
- `DatabaseManager`: SQLite database operations
- `MetadataExtractor`: EXIF and image metadata extraction
- `ImageUtils`: Image processing and orientation handling
- `PhotoImportWorker`: Background thread for photo importing

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

## 🔮 Future Enhancements

- [ ] Batch photo operations
- [ ] Advanced search and filtering
- [ ] Photo rating system
- [ ] Export functionality
- [ ] Duplicate photo detection
- [ ] Photo editing integration
- [ ] Cloud storage integration
- [ ] RAW format support
- [ ] Video file support
- [ ] Advanced HEIC metadata extraction

## 🔧 Troubleshooting

### HEIC Files Not Displaying

If HEIC files show as gray placeholders:

1. **Check HEIC support status**: Look at the status bar or About dialog
2. **Install pillow-heif**: Run `pip install pillow-heif`
3. **Restart PhotoSphere**: Close and reopen the application
4. **Verify installation**: You should see "HEIC/HEIF support enabled" in the console

### Performance Issues

- Large collections: Consider importing photos in smaller batches
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