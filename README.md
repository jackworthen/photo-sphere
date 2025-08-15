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

## 📋 Requirements

- Python 3.7 or higher
- PySide6 (Qt6 for Python)
- Pillow (Python Imaging Library)
- exifread

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/jackworthen/photo-sphere.git
   cd photo-sphere
   ```

2. **Install dependencies:**
   ```bash
   pip install PySide6 Pillow exifread
   ```

3. **Run the application:**
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

# Run application
python photosphere.py
```

## 🎯 Usage

### Getting Started

1. **Launch PhotoSphere** by running `python photosphere.py`
2. **Import Photos** using one of these methods:
   - Click "Import Photos" button and select files
   - Use the File menu → Import Photos
   - Drag and drop image files directly into the application

### Supported File Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- TIFF (.tiff)
- BMP (.bmp)
- GIF (.gif)

### Viewing Photo Details

- Click on any photo in the grid to view its details
- Photo details include:
  - Camera make and model
  - Lens information
  - Camera settings (aperture, shutter speed, ISO)
  - Date taken
  - File size and dimensions
  - GPS coordinates (if available)
  - Google Maps integration for location data

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
- Efficient thumbnail generation
- Support for various image formats
- Graceful handling of corrupted or unsupported files

## 🚧 Development

### Project Structure

```
photo-sphere/
├── photosphere.py          # Main application file
├── README.md              # This file
└── requirements.txt       # Python dependencies (optional)
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

---

Developed by [Jack Worthen](https://github.com/jackworthen)