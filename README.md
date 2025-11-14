# ArduinoFDC GUI

A graphical user interface for controlling the [ArduinoFDC](https://github.com/dhansel/ArduinoFDC) floppy disk controller by David Hansel.

## Overview

This GUI provides an easy-to-use interface for interacting with ArduinoFDC, allowing you to:

- **Browse and manage files** on floppy disks using the ArduDOS file system
- **Read and write files** via XModem protocol
- **Format disks** with MS-DOS FAT file system
- **Low-level disk operations** through Monitor mode
- **Transfer complete disk images** for archival and restoration
- **Support multiple disk types**: 5.25" DD/HD and 3.5" DD/HD

## Requirements

### Hardware
- Arduino Uno, Leonardo, Nano, Pro Mini, Micro, or Mega
- Floppy disk drive (5.25" or 3.5", DD or HD)
- ArduinoFDC firmware installed on Arduino

**Firmware Options:**
- **Enhanced firmware** (included in `firmware/` folder) - Recommended
  - Includes automatic XModem padding removal
  - Better file size handling
  - Full backward compatibility
- **Original firmware** from [David Hansel's repository](https://github.com/dhansel/ArduinoFDC)
  - Standard ArduinoFDC functionality
  - Also fully supported by this GUI

See `firmware/README.md` for details on the enhancements.

### Software
- Windows 10 or later
- Serial COM port driver for Arduino

## Quick Start

### Using Pre-built Executable (Recommended)

1. Download `ArduinoFDC_GUI.exe` from the `dist` folder
2. Connect your Arduino with ArduinoFDC firmware
3. Run `ArduinoFDC_GUI.exe`
4. Select your COM port (default: COM4)
5. Click "Connect"

### Building from Source

#### Prerequisites
- Python 3.12 or later
- pip package manager

#### Installation

1. Clone or download this repository
2. Install required packages:
```bash
pip install pyserial xmodem pyinstaller
```

3. Run the application:
```bash
python src/arduino_fdc_gui.py
```

#### Building Executable

To build your own executable:
```bash
cd src
pyinstaller ArduinoFDC_GUI.spec
```

The executable will be created in `src/dist/ArduinoFDC_GUI.exe`

## Features

### ArduDOS Mode
- **File Browser**: Navigate directories, view file listings
- **File Operations**: TYPE (view text), DUMP (hex view), DELETE, WRITE new files
- **Directory Operations**: MKDIR, RMDIR, navigate subdirectories
- **Drive Selection**: Switch between Drive A: and Drive B:
- **Disk Formatting**: High-level MS-DOS format with FAT file system
- **XModem Transfers**: Send and receive individual files
- **Disk Type Selection**: Configure for different floppy formats

### Monitor Mode
- **Low-level Operations**: Direct sector access
- **Drive Control**: Motor on/off, drive selection
- **Disk Type Settings**: 5.25" DD/HD, 3.5" DD/HD configurations
- **Low-level Format**: Physical disk formatting
- **Disk Image Transfers**: Upload/download complete disk images via XModem
- **Advanced Operations**: Write all sectors, format tracks

### Interface Features
- **Maximized Window**: Full-screen workspace on startup
- **Real-time Status Bar**: Shows current mode, drive, and disk type
- **Activity Log**: Optional collapsible log window for debugging
- **XModem Progress**: Live transfer status with block counts and percentages
- **Intuitive Layout**: Organized panels for easy access to all functions

## Usage Guide

### Connecting

1. Ensure Arduino is connected via USB
2. Select the correct COM port (check Device Manager if unsure)
3. Baud rate is preset to 115200 (standard for ArduinoFDC)
4. Click "Connect"

### Working with Files (ArduDOS Mode)

1. Click "Refresh" to load the current directory
2. Double-click directories to navigate
3. Select a file and use TYPE to view text or DUMP for hex view
4. Use "Send File" to transfer files to the floppy via XModem
5. Use "Receive File" to download files from the floppy

### Formatting a Disk

**Important**: Formatting erases all data on the disk!

1. Set the correct disk type using the Disk Type Selection buttons
2. In ArduDOS mode, click "FORMAT (MS-DOS)" for high-level formatting
3. Or use Monitor mode "Format" button for low-level formatting
4. Follow the prompts in the terminal

### Transferring Disk Images (Monitor Mode)

1. Switch to Monitor Commands tab
2. Set the correct disk type
3. Click "Download Disk (S)" to save a disk image
4. Click "Upload Disk (R)" to restore a disk image
5. Monitor the progress in the status bar

### Using the Activity Log

1. Click "Show Log" button in the connection bar
2. View timestamped activity messages for debugging
3. Click "Clear Log" to reset the log
4. Click "Hide Log" to collapse the window

## Disk Type Reference

| Type | Description | Capacity | Tracks | Sectors/Track |
|------|-------------|----------|--------|---------------|
| 5.25" DD | Double Density | 360 KB | 40 | 9 |
| 5.25" DD in HD | DD disk in HD drive | 360 KB | 40 | 9 |
| 5.25" HD | High Density | 1.2 MB | 80 | 15 |
| 3.5" DD | Double Density | 720 KB | 80 | 9 |
| 3.5" HD | High Density | 1.44 MB | 80 | 18 |

## Troubleshooting

### Connection Issues
- Verify the correct COM port is selected
- Ensure Arduino has ArduinoFDC firmware installed
- Check that no other program is using the serial port
- Try disconnecting and reconnecting

### Disk Read/Write Errors
- Verify the correct disk type is selected
- Ensure the disk is properly inserted
- Check that the disk is not write-protected (if writing)
- Clean the drive heads if experiencing consistent errors

### XModem Transfer Problems
- Ensure stable connection (no disconnects during transfer)
- Verify sufficient disk space for received files
- Check disk type matches the actual disk format
- Monitor the activity log for detailed error messages

## Command Reference

### ArduDOS Commands
- `dir` - List directory contents
- `cd <dirname>` - Change directory
- `type <filename>` - Display file contents (text)
- `dump <filename>` - Display file contents (hex)
- `del <filename>` - Delete a file
- `mkdir <dirname>` - Create directory
- `rmdir <dirname>` - Remove directory
- `a:` or `b:` - Switch drives
- `format` - Format disk with FAT file system
- `disktype <0-4>` - Set disk type
- `help` - Show available commands

### Monitor Commands
- `h` or `?` - Show help
- `m 0/1` - Motor off/on
- `s 0/1` - Select drive A/B
- `t 0-4` - Set disk type
- `f` - Format disk (low-level)
- `r <filename>` - Receive disk image via XModem
- `s <filename>` - Send disk image via XModem
- `x` - Exit to ArduDOS mode

## Technical Details

### Serial Communication
- Baud Rate: 115200
- Data Bits: 8
- Parity: None
- Stop Bits: 1
- Flow Control: None
- Line Termination: CR (\\r)

### Dependencies
- **pyserial**: Serial port communication
- **xmodem**: File transfer protocol implementation
- **tkinter**: GUI framework (included with Python)

### File Structure
```
ArduinoFDC_GUI_Release/
├── README.md           # This file
├── LICENSE            # GNU GPL v3
├── src/
│   ├── arduino_fdc_gui.py      # Main GUI application
│   └── ArduinoFDC_GUI.spec     # PyInstaller build specification
├── dist/
│   └── ArduinoFDC_GUI.exe      # Pre-built executable
└── docs/
    └── (additional documentation)
```

## Credits

- **ArduinoFDC Firmware**: Created by [David Hansel](https://github.com/dhansel/ArduinoFDC)
- **Enhanced Firmware**: XModem padding removal and size validation improvements (included in this package)
- **GUI Application**: Community contribution for ease of use
- **FatFS Library**: By ChaN, integrated into ArduinoFDC
- **XModem Protocol**: Standard file transfer implementation

## License

This GUI application is released under the GNU General Public License v3.0, same as the ArduinoFDC project.

See [LICENSE](LICENSE) file for details.

## Support

For issues with:
- **ArduinoFDC Firmware**: Visit the [original ArduinoFDC repository](https://github.com/dhansel/ArduinoFDC)
- **GUI Application**: Open an issue in this repository
- **Hardware Setup**: Refer to the ArduinoFDC documentation

## Version History

### Version 1.0 (November 2025)
- Initial release
- Full ArduDOS and Monitor mode support
- XModem file and disk image transfers
- Maximized window with status bar
- Optional activity log window
- Support for all standard disk formats
- Automatic status tracking (drive, disk type, mode)

## Contributing

Contributions are welcome! Please ensure any changes maintain compatibility with the original ArduinoFDC firmware.

## Disclaimer

Use this software at your own risk. Always backup important data before formatting or writing to floppy disks. The authors are not responsible for data loss or hardware damage.
