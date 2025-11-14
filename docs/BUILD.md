# Building ArduinoFDC GUI

This document provides detailed instructions for building the ArduinoFDC GUI application from source.

## Prerequisites

### Required Software
- Python 3.12 or later
- pip (Python package manager)
- Git (optional, for cloning the repository)

### Required Python Packages
```bash
pip install pyserial==3.5
pip install xmodem==0.4.7
pip install pyinstaller==6.16.0
```

## Development Setup

### 1. Clone or Download the Repository
```bash
git clone <repository-url>
cd ArduinoFDC_GUI_Release
```

Or download and extract the ZIP file.

### 2. Create Virtual Environment (Recommended)
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

If `requirements.txt` doesn't exist, install manually:
```bash
pip install pyserial xmodem pyinstaller
```

### 4. Run from Source
```bash
cd src
python arduino_fdc_gui.py
```

## Building the Executable

### Using PyInstaller Spec File (Recommended)

The included `ArduinoFDC_GUI.spec` file contains optimized build settings:

```bash
cd src
pyinstaller ArduinoFDC_GUI.spec
```

The executable will be created in `src/dist/ArduinoFDC_GUI.exe`

### Manual PyInstaller Build

If you need to customize the build:

```bash
cd src
pyinstaller --onefile --windowed --name ArduinoFDC_GUI arduino_fdc_gui.py
```

Options explained:
- `--onefile`: Creates a single executable
- `--windowed`: No console window (GUI only)
- `--name`: Output filename

### Build Output

After building, you'll find:
- `build/` - Temporary build files (can be deleted)
- `dist/` - Contains the final executable
- `*.spec` - Build specification file

## Testing

### Before Release
1. Test all major functions:
   - Serial connection/disconnection
   - File browsing and operations
   - XModem transfers (send/receive)
   - Disk formatting
   - Mode switching (ArduDOS ↔ Monitor)
   - Status bar updates
   - Log window functionality

2. Test with different disk types:
   - 5.25" DD
   - 5.25" HD
   - 3.5" DD
   - 3.5" HD

3. Verify error handling:
   - Disconnect during operations
   - Invalid commands
   - File not found scenarios
   - Disk full conditions

## Project Structure

```
src/
├── arduino_fdc_gui.py       # Main application (2400+ lines)
│   ├── ArduinoFDCGUI class
│   ├── UI setup methods
│   ├── Serial communication
│   ├── XModem implementation
│   ├── File operations
│   └── Event handlers
└── ArduinoFDC_GUI.spec      # PyInstaller configuration
```

## Key Components

### GUI Framework
- **tkinter**: Standard Python GUI library
- **ttk**: Themed widgets for modern appearance
- **scrolledtext**: Terminal and log displays

### Serial Communication
- **pyserial**: Cross-platform serial port access
- Thread-based TX/RX queues for non-blocking I/O
- Configurable baud rate (default: 115200)

### File Transfer
- **xmodem**: Industry-standard protocol implementation
- Progress callbacks for UI updates
- Error detection and retry logic
- Support for both files and disk images

### Features Implemented
- Maximized window on startup
- Real-time status bar (mode, drive, disk type)
- Optional collapsible activity log
- Automatic command completion tracking
- Drive/disk type detection from terminal commands
- Enhanced XModem progress display

## Troubleshooting Build Issues

### Missing Dependencies
```bash
pip install --upgrade pyserial xmodem pyinstaller
```

### PyInstaller Warnings
- Warnings about missing modules are usually safe to ignore
- Only actual errors prevent executable creation

### Executable Too Large
The executable includes Python runtime and all dependencies (~15-20 MB is normal)

### Antivirus False Positives
Some antivirus software may flag PyInstaller executables. This is a known issue with packed executables. You may need to:
- Add an exception in your antivirus
- Use code signing (requires a certificate)
- Provide VirusTotal scan results

## Optimization Tips

### Reduce Executable Size
```bash
pyinstaller --onefile --windowed --strip --noupx arduino_fdc_gui.py
```

### Include Icon
```bash
pyinstaller --onefile --windowed --icon=icon.ico arduino_fdc_gui.py
```

### Debug Build
For troubleshooting, create a console version:
```bash
pyinstaller --onefile --name ArduinoFDC_GUI_Debug arduino_fdc_gui.py
```

## Development Workflow

1. Make changes to `arduino_fdc_gui.py`
2. Test with `python arduino_fdc_gui.py`
3. Check for syntax errors with linter
4. Build executable with PyInstaller
5. Test executable thoroughly
6. Update version number and changelog
7. Create release package

## Packaging for Distribution

### Create Release Package
```bash
# Create directory structure
mkdir release
mkdir release\src
mkdir release\dist
mkdir release\docs

# Copy files
copy arduino_fdc_gui.py release\src\
copy ArduinoFDC_GUI.spec release\src\
copy dist\ArduinoFDC_GUI.exe release\dist\
copy ..\LICENSE release\
copy README.md release\

# Create ZIP
tar -a -c -f ArduinoFDC_GUI_v1.0.zip release
```

### What to Include
- ✅ Source code (`arduino_fdc_gui.py`)
- ✅ Build spec (`ArduinoFDC_GUI.spec`)
- ✅ Executable (`ArduinoFDC_GUI.exe`)
- ✅ License (GNU GPL v3)
- ✅ README with usage instructions
- ✅ This BUILD document
- ❌ Virtual environment files
- ❌ Build artifacts (`build/` folder)
- ❌ Python cache (`__pycache__/`)
- ❌ Development backup folders

## Platform Support

### Windows
- Fully tested on Windows 10/11
- Executable works without Python installation

### macOS
- Build with: `pyinstaller --onefile --windowed arduino_fdc_gui.py`
- Requires manual testing (not officially supported)

### Linux
- Build with: `pyinstaller --onefile arduino_fdc_gui.py`
- May require `python3-tk` package
- Serial port permissions may need configuration

## Continuous Integration (Optional)

For automated builds, consider:
- GitHub Actions for Windows builds
- Automatic version tagging
- Release asset uploads

Example `.github/workflows/build.yml`:
```yaml
name: Build
on: [push]
jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      - run: pip install pyserial xmodem pyinstaller
      - run: cd src && pyinstaller ArduinoFDC_GUI.spec
      - uses: actions/upload-artifact@v2
        with:
          name: ArduinoFDC_GUI
          path: src/dist/ArduinoFDC_GUI.exe
```

## Support

For build issues, check:
1. Python version compatibility (3.12+ recommended)
2. All dependencies installed correctly
3. PyInstaller is latest version
4. No syntax errors in source code
5. Sufficient disk space for build artifacts

## License

This build documentation is part of the ArduinoFDC GUI project and is released under GNU GPL v3.
