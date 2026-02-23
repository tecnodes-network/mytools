# SSH Tunnel Manager Pro

A modern, user-friendly desktop application for managing multiple SSH tunnels on Windows. Built with Python and CustomTkinter.

## Overview

SSH Tunnel Manager Pro allows users to create, manage, and monitor multiple SSH tunnel connections through an intuitive GUI. It supports multiple port forwards per profile, real-time connection status monitoring, and persistent configuration storage.

## Features

- **Multiple Profiles**: Create unlimited SSH tunnel configurations
- **Multi-Port Forwarding**: Each profile supports multiple local→remote port mappings
- **Real-time Monitoring**: Live status indicators and activity logging
- **System Validation**: Verifies actual port binding before marking as "Connected"
- **Resizable Interface**: Draggable sash to resize log window
- **Portable Configuration**: JSON-based config with customizable storage location
- **Threaded Operations**: Non-blocking UI during connection attempts

## Tech Stack

### Core Technologies
- **Python 3.8+**: Core language
- **CustomTkinter 5.x**: Modern UI framework (tkinter extension with Material Design)
- **PyInstaller**: Executable compilation
- **Windows API**: `subprocess.CREATE_NO_WINDOW` for background processes

### Dependencies

```txt
customtkinter>=5.2.0
pystray>=0.19.0
Pillow>=9.0.0
pyinstaller>=5.0
```

### System Requirements
- **OS**: Windows 10/11 (64-bit)
- **SSH Client**: OpenSSH (built into Windows 10/11) or PuTTY/plink
- **Privileges**: Standard user (no admin required for ports > 1024)

## Installation

### Method 1: Pre-built Executable
1. Download TunnelManager.exe from releases
2. Place in desired directory (e.g., C:\Tools\TunnelManager\)
3. Run TunnelManager.exe
4. First Run: Creates tunnel_profiles.json in same directory

### Method 2: From Source
```bash
# Clone repository
git clone <repo-url>
cd ssh-tunnel-manager

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python tunnel_manager.py
```

## Building Executable
```bash
# Build script (build.bat)
pyinstaller --noconfirm --onefile --windowed --name "TunnelManager" --clean tunnel_manager.py

# Output: dist/TunnelManager.exe
```
Run TunnelManager.exe
First Run: Creates tunnel_profiles.json in same directory
Method 2: From Source
bash
Copy
# Clone repository
git clone <repo-url>
cd ssh-tunnel-manager

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run application
python tunnel_manager.py
Building Executable
bash
Copy
# Build script (build.bat)
pyinstaller --noconfirm --onefile --windowed --name "TunnelManager" --clean tunnel_manager.py

# Output: dist/TunnelManager.exe
Architecture
Class Structure
```
App (Main Application)
├── Settings (Configuration management)
├── TunnelManager (Profile management)
│   └── SSHTunnel (Individual connection handler)
└── ProfileDialog (UI for add/edit)
```
Key Components
1. SSHTunnel Class
Handles individual SSH connections:
Process Management: Uses subprocess.Popen with CREATE_NO_WINDOW
Validation: Socket-based port checking (is_port_open())
Monitoring: Background thread (_monitor()) for disconnect detection
Error Handling: Captures stderr for connection failures
2. TunnelManager Class
Manages profile persistence:
Storage: JSON file (default: portable, configurable via Settings)
Caching: Maintains SSHTunnel instances to prevent duplicate processes
Path Resolution: Supports both portable and AppData storage modes
3. Settings Class
Manages application settings:
Auto-path Detection: Uses sys.frozen to detect exe vs script mode
Migration: Handles config file relocation
Configuration File Format
Location: tunnel_profiles.json (or user-defined path)
#### Example JSON
```json
[
  {
    "name": "Production MySQL",
    "host": "167.235.33.106",
    "ssh_port": 1221,
    "user": "akhan",
    "key": "C:/Users/akhan/.ssh/id_tunnel",
    "forwards": [
      {
        "local": "3306",
        "remote": "3306",
        "remote_host": "localhost"
      },
      {
        "local": "8080",
        "remote": "80",
        "remote_host": "localhost"
      }
    ]
  }
]
```
UI Layout Structure
```
Root Window
├── Sidebar (250px fixed)
│   ├── Title
│   ├── Action Buttons (Add, Start All, Stop All)
│   └── Settings
└── Main Content (flexible)
  ├── Stats Header (3 cards)
  ├── Scrollable Profile List
  ├── Draggable Sash (6px height)
  └── Activity Log (resizable)
```
# Usage Guide
- Creating a Profile
- Click "+ Add Profile"
- Fill in connection details:
- Profile Name: Display name (e.g., "Production DB")
- Host: SSH server IP/hostname
- SSH Port: Usually 22 (or custom like 1221)
- Username: SSH login user
- SSH Key: Path to private key file
- Add port forwards:
- Local Port: Port on your machine (e.g., 3306)
- Remote Host: Usually "localhost" (from server's perspective)
- Remote Port: Port on remote server (e.g., 3306 for MySQL)
- Click Save
Starting/Stopping Tunnels
- Individual: Click Start/Stop button on profile card
- Batch: Use Start All or Stop All in sidebar
-  Status Indicators:
- 🟢 Green: Connected and verified
- 🟠 Orange: Connection failed/error
-🔴 Red: Disconnected
- Resizing Log Window
- Drag the gray horizontal bar between the profile list and activity log up or down.
- Changing Config Location
- Click Settings
- Browse to new location for tunnel_profiles.json
- Existing config will be copied if new location is empty
# Troubleshooting
"Access Denied" During Build
Cause: TunnelManager.exe is running
Fix:
```cmd
taskkill /F /IM TunnelManager.exe
# Or check system tray for minimized app
```
Connection Shows "Connected" But Port Not Working
Possible Causes:
Key Authentication Failed: Check SSH key path and permissions
Port Already in Use: Local port may be occupied by another service
Firewall: Windows Defender may be blocking local port
Debug Steps:
Check Activity Log for error messages
Test manually: ssh -p PORT -L LOCAL:REMOTE USER@HOST -N
Check Windows Event Viewer for SSH errors
UI Freezes on Connection
Cause: SSH hanging on authentication
Fix:
Ensure SSH key has no passphrase (or use ssh-agent)
Add ConnectTimeout=10 to SSH options (already in code)
"SSH Tunnel object has no attribute is_running"
Cause: Outdated compiled version
Fix: Clean rebuild
```cmd
rmdir /s /q dist build
del TunnelManager.spec
pyinstaller --noconfirm --onefile --windowed --name "TunnelManager" tunnel_manager.py
```
Profile Data Lost
Check:
Config file path in Settings
File permissions in target directory
JSON syntax validity (if hand-edited)
Development Guide
Adding New Features
1. Adding SSH Options
Edit SSHTunnel.start() method:
```python
cmd = [
  'ssh',
  '-p', str(self.profile.get('ssh_port', 22)),
  '-i', os.path.expanduser(self.profile['key']),
  '-o', 'NewOption=value',  # Add here
  # ...
]
```
2. Adding UI Elements
Use ctk.CTkFrame for containers
Use grid() or pack() consistently (current code uses mixed)
Update grid_rowconfigure/grid_columnconfigure for resizing
3. Adding New Profile Fields
Update ProfileDialog.__init__() to add input field
Update ProfileDialog.save() to include in profile dict
Update SSHTunnel to use the new field
Migration: Handle missing keys in existing profiles:
```python
value = profile.get('new_field', 'default_value')
```
Threading Considerations
SSH Operations: Run in daemon threads to prevent UI freeze
UI Updates: Must use self.root.after() for thread-safe GUI updates
Process Killing: Safe from any thread, but check self._stop_check flag
Cross-Platform Notes
Current implementation is Windows-specific due to:
subprocess.CREATE_NO_WINDOW
taskkill usage
os.environ['APPDATA']
For Linux/Mac ports:
Remove creationflags parameter
Use os.kill() instead of taskkill
Use os.path.expanduser('~/.config') instead of APPDATA
File Structure
```
project/
├── tunnel_manager.py      # Main application (single file)
├── build.bat              # Windows build script
├── requirements.txt       # Python dependencies
├── tunnel_profiles.json   # User data (generated)
├── settings.json          # App settings (in APPDATA)
└── dist/
  └── TunnelManager.exe  # Compiled executable
```
Security Considerations
SSH Keys: Store keys with restricted permissions (600)
Config File: tunnel_profiles.json contains connection details (no passwords, but host info)
StrictHostKeyChecking: Currently disabled (-o StrictHostKeyChecking=no) for ease of use. Enable for production:
```python
# Remove this line from cmd in SSHTunnel.start()
'-o', 'StrictHostKeyChecking=no',
```
Known Limitations
No Password Authentication: Only SSH key-based auth supported
Windows Only: Uses Windows-specific subprocess flags
No Auto-Reconnect: Tunnels don't auto-restart on disconnect (could be added in _monitor())
Single Instance: Running multiple copies may cause port conflicts
Future Enhancements
Potential improvements for new developers:
* [ ] Auto-reconnect with exponential backoff
* [ ] Password authentication support (with secure storage)
* [ ] Import/export profiles
* [ ] System tray minimization (pystray integration stub exists)
* [ ] Connection statistics (bytes transferred)
* [ ] Linux/Mac support
* [ ] Dark/Light theme toggle
License
[Your License Here]
Support
For issues or feature requests:
Check Troubleshooting section above
Review Activity Log for specific error messages
Test SSH connection manually using command line first
plain
Copy

## Quick Start Checklist for New Developers

1. **Environment**: Install Python 3.8+, create venv
2. **Dependencies**: `pip install customtkinter pystray pillow pyinstaller`
3. **Test Run**: `python tunnel_manager.py` (creates sample config)
4. **Add Profile**: Use UI to create test connection
5. **Verify**: Check that `ssh.exe` appears in Task Manager when connected
6. **Build**: Run `build.bat` to create distributable

**Key Debugging Tip**: If tunnels fail silently, temporarily modify `SSHTunnel.start()` to remove `creationflags=subprocess.CREATE_NO_WINDOW` to see SSH error messages in console.