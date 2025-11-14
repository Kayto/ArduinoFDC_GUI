# ArduinoFDC Firmware - Enhanced Version

## Overview

This is an **enhanced version** of the ArduinoFDC firmware with improvements to XModem file transfer functionality. It is based on the original ArduinoFDC firmware by David Hansel.

## Changes from Original

### XModem Enhancements

The main enhancement is improved handling of XModem file transfers with automatic padding removal:

1. **File Size Parameter Support**
   - The `WRITE` command now accepts an optional size parameter
   - Syntax: `write <filename> <size>`
   - Example: `write test.txt 1234`

2. **Automatic Padding Removal**
   - XModem protocol pads files to 128-byte blocks with 0x1A bytes
   - This firmware automatically detects and removes padding
   - Ensures files are stored at their exact original size
   - Reports how many padding bytes were trimmed

3. **Size Validation**
   - If size is specified, validates received bytes match expected size
   - Detects and reports size mismatches
   - Prevents corrupted transfers from being saved

### Technical Details

**New Variables:**
- `xmodem_expected_size` - Expected file size (if provided)
- `xmodem_bytes_written` - Actual bytes written to disk
- `xmodem_padding_discarded` - Number of padding bytes removed
- `xmodem_have_expected_size` - Flag indicating if size was specified

**Modified Functions:**
- `xmodem_write_callback()` - Enhanced to trim padding and validate size
- `do_write()` - Parses optional size parameter from WRITE command

**Benefits:**
- Files stored at exact size (no extra padding bytes)
- Automatic validation prevents corrupted transfers
- Compatible with original firmware for basic operations
- GUI can send file size for improved reliability

## Compatibility

### With Original Firmware
- ✅ All standard ArduDOS commands work identically
- ✅ Monitor mode commands unchanged
- ✅ Backward compatible - size parameter is optional
- ✅ Can be used interchangeably with original firmware

### With GUI
- ✅ GUI works with both original and enhanced firmware
- ✅ GUI automatically provides file size for WRITE operations
- ✅ Enhanced features activated automatically when available

## Installation

### Requirements
- Arduino Uno, Leonardo, Nano, Pro Mini, Micro, or Mega
- Arduino IDE 1.8.x or later
- Floppy disk drive connected as per ArduinoFDC wiring

### Upload Instructions

1. **Open in Arduino IDE**
   ```
   File → Open → ArduinoFDC-main.ino
   ```

2. **Select Your Board**
   ```
   Tools → Board → [Your Arduino Model]
   ```

3. **Select COM Port**
   ```
   Tools → Port → [Your Arduino's COM Port]
   ```

4. **Upload**
   ```
   Sketch → Upload (or press Ctrl+U)
   ```

5. **Verify Upload**
   - Open Serial Monitor (115200 baud)
   - You should see the ArduDOS prompt after reset

### Verification

After uploading, test with these commands:
```
help               # Should show all commands
dir                # Should list files (if disk formatted)
disktype 4         # Set disk type (example: 3.5" HD)
```

## Usage Examples

### Without Size Parameter (Original Behavior)
```
write myfile.txt
[Ready for XModem transfer]
[Send file via XModem]
```
File is saved, padding may be included.

### With Size Parameter (Enhanced)
```
write myfile.txt 1234
[Ready for XModem transfer]
[Send file via XModem]
Trimmed 108 padding bytes.
```
File is saved at exactly 1234 bytes, padding removed.

### Using with GUI

The GUI automatically provides the file size when sending files, so you get the enhanced behavior automatically:
1. Click "Send File" in XModem Transfers section
2. Select your file
3. GUI sends: `write filename.txt <actual_size>`
4. Transfer proceeds with automatic padding removal

## Technical Specifications

### XModem Protocol Details
- Block size: 128 bytes
- Padding character: 0x1A (Ctrl+Z)
- Error detection: Checksum or CRC-16
- Retry limit: Configurable

### File Size Handling
- Maximum file size: Limited by disk capacity
- Size parameter: Parsed as unsigned long (32-bit)
- Padding detection: Validates all padding bytes are 0x1A
- Error handling: Aborts if non-padding bytes found after expected size

## Troubleshooting

### "Size mismatch detected" Error
**Cause**: Received bytes don't match specified size
**Solution**: 
- Verify file size is correct
- Check for transmission errors
- Try resending the file

### Padding Not Removed
**Cause**: Size parameter not provided
**Solution**: 
- Use GUI for automatic size handling
- Manually specify size: `write filename.txt 1234`

### Upload Fails
**Cause**: Incorrect board or port selection
**Solution**:
- Verify board type in Tools → Board
- Check COM port in Device Manager
- Try pressing reset button during upload

## Source Code Attribution

This enhanced firmware is based on:
- **ArduinoFDC** by David Hansel
- Repository: https://github.com/dhansel/ArduinoFDC
- License: GNU GPL v3

### Modifications
- Enhanced XModem receive with padding removal
- File size parameter support
- Size validation and reporting
- All modifications are clearly documented in code comments

### License
GNU General Public License v3.0 (same as original ArduinoFDC)

## Credits

- **Original ArduinoFDC**: David Hansel
- **FatFS Library**: ChaN
- **XModem Implementation**: Integrated in original ArduinoFDC
- **Enhancements**: Community contributions

## Support

- **Original Firmware Issues**: https://github.com/dhansel/ArduinoFDC
- **Enhancement Issues**: Report in this repository
- **Hardware Setup**: See ArduinoFDC documentation

## Future Enhancements

Potential improvements for consideration:
- CRC-16 mode support
- Batch file operations
- Progress reporting during transfers
- Additional file size validation options

## Changelog

### Enhanced Version (2025-11-14)
- Added file size parameter to WRITE command
- Implemented automatic padding removal
- Added size validation and mismatch detection
- Added padding removal reporting
- Maintained full backward compatibility

### Original Version
- See https://github.com/dhansel/ArduinoFDC for original changelog
