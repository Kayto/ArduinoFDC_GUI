# Changelog

All notable changes to the ArduinoFDC GUI project will be documented in this file.

## [1.0.1] - 2026-02-17

### Added
- Per-drive disk type tracking - disk type settings are now remembered separately for Drive A: and Drive B:

### Fixed
- Disk type now correctly restored when switching drives in ArduDOS mode (a:, b:)
- Disk type now correctly restored when switching drives in Monitor mode (s 0, s 1)

---

## [1.0.0] - 2025-11-14

### Added
- Initial release of ArduinoFDC GUI
- Full ArduDOS mode support
  - File browser with directory navigation
  - File operations (TYPE, DUMP, DELETE, WRITE)
  - Directory operations (MKDIR, RMDIR)
  - Drive switching (A: and B:)
  - MS-DOS high-level disk formatting
  - XModem file transfers (send and receive)
  - Disk type selection for all standard formats

- Complete Monitor mode support
  - Low-level disk operations
  - Drive control (motor on/off, drive selection)
  - Disk type configuration
  - Physical disk formatting
  - Complete disk image transfers via XModem
  - Advanced operations (write all sectors)

- User Interface Features
  - Maximized window on startup for better visibility
  - Real-time status bar showing mode, drive, and disk type
  - Optional collapsible activity log window
  - Enhanced XModem progress display with block counts and percentages
  - Intuitive tab-based layout for ArduDOS and Monitor modes
  - Credit to original ArduinoFDC author (David Hansel)

- Technical Features
  - Automatic command completion tracking
  - Drive and disk type detection from terminal commands
  - Status bar updates on connect/disconnect
  - Thread-based serial communication for non-blocking I/O
  - Comprehensive error handling
  - Logging system with timestamps

### Changed
- Replaced all DEBUG print statements with proper logging mechanism
- Improved status bar to show real-time updates
- Enhanced XModem progress messages with emoji indicators (🔼 upload, 🔽 download)
- Renamed format button to "FORMAT (MS-DOS)" for clarity
- Removed quick format button (low-level format available in Monitor mode)

### Fixed
- Status bar now updates when typing drive commands directly in terminal
- Drive and disk type status reset to defaults on connect/disconnect
- Command completion timeout reduced from 10s to 3s for better responsiveness
- Atomic flag clearing to prevent race conditions in command completion
- Forced flag clear on timeout prevents cascading failures

### Technical Details
- Python 3.12.5
- PyInstaller 6.16.0
- Dependencies: pyserial 3.5, xmodem 0.4.7
- Source code: 2389 lines
- Build target: Windows 10/11

### Known Issues
- None at this time

### Future Considerations
- Additional disk format support (if needed)
- Batch file operations
- Disk image format conversion tools
- Configuration file for persistent settings
- Multiple language support

---

## Version Format

This project follows [Semantic Versioning](https://semver.org/):
- MAJOR version for incompatible API changes
- MINOR version for added functionality in a backwards compatible manner
- PATCH version for backwards compatible bug fixes

## Links
- [ArduinoFDC Original Project](https://github.com/dhansel/ArduinoFDC)
- [GNU General Public License v3.0](LICENSE)
