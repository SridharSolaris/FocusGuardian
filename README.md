# FocusGuardian

A focus distraction preventor for **Windows 10/11**. Blocks distracting websites and desktop apps during Pomodoro focus sessions, with usage tracking and break reminders.

![License](https://img.shields.io/badge/license-MIT-blue)
![Platform](https://img.shields.io/badge/platform-Windows-0078D4)
![Python](https://img.shields.io/badge/python-3.12-3776AB)
![Version](https://img.shields.io/badge/version-1.0.0-success)

## Features

- **Website blocking** — Redirects distracting sites to a motivational "stay focused" page during focus sessions
- **Desktop app blocking** — Kills distracting processes (games, social apps, etc.) while you work
- **Pomodoro timer** — Customizable work/break cycles with an elegant circular progress ring
- **Focus profiles** — Create multiple blocklists for different scenarios (Social Media, Deep Work, Games Only)
- **Schedules** — Automatically activate profiles at specific times on specific days
- **Usage tracking** — Visual statistics with focus time, break time, sessions, and a 7-day bar chart
- **Break & eye-rest reminders** — Periodic notifications to rest your eyes and stretch
- **Windows 11 Dark Theme** — Native Fluent Design dark UI with dark title bar, rounded corners, and enterprise-grade polish

## Requirements

- **Windows 10 (2004+) or Windows 11**
- Administrator privileges (required for hosts-file editing and process blocking)
- Python 3.8+ with `psutil` (if running from source)
- No Python needed if using the installer — it bundles its own runtime

## Installation

### Option 1: Download the installer (recommended)

1. Go to the [Releases page](../../releases)
2. Download `FocusGuardian_Setup_v1.0.0.exe`
3. Run the installer (requires administrator privileges)
4. If Windows SmartScreen shows "Unknown publisher", click **More info** → **Run anyway** (the app is unsigned but safe)

### Option 2: Run from source

```bash
git clone https://github.com/SridharSolaris/FocusGuardian.git
cd FocusGuardian
pip install psutil
python focus_guardian.py
```

Run as administrator for hosts-file editing and process blocking.

## Usage

### Quick Start

1. Launch FocusGuardian (runs as administrator)
2. Select a **Focus Profile** on the Timer page (e.g., "Social Media" blocks YouTube, Facebook, Twitter, etc.)
3. Click **Start** to begin a Pomodoro session
4. Websites and apps in the profile are now blocked
5. When the work timer ends, blocking pauses for your break
6. After the break, the next work session begins automatically

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Start / Pause timer |
| `Esc` | Stop timer |

### Customizing Profiles

Go to **Profiles** to create your own blocklists:

- **Websites** — Add domains like `reddit.com`, `youtube.com` (with or without `www.`)
- **Desktop Apps** — Add process names like `discord.exe`, `steam.exe`
- Click **Pick from Running Processes** on the Desktop Apps page to select from currently running programs

### Schedules

Go to **Schedules** to auto-activate profiles at set times (e.g., "Deep Work" every weekday at 9 AM). Schedules work independently of the Pomodoro timer.

## Configuration

Settings are stored in `%APPDATA%\\FocusGuardian\\config.json`:

| Setting | Default | Description |
|---------|---------|-------------|
| Work duration | 25 min | Length of each focus session |
| Short break | 5 min | Break between work sessions |
| Long break | 15 min | Break after every 4 sessions |
| Sessions before long break | 4 | Work sessions before a long break |
| Eye-rest reminder | 20 min | Interval for eye-rest notifications |
| Block page server port | 80 | Port for the "stay focused" redirect page |
| App scan interval | 3 sec | How often to check for blocked processes |
| Sound | On | Play a sound when sessions complete |
| Strict mode | Off | Makes it harder to stop mid-session |

## How It Works

- **Website blocking**: Modifies the Windows `hosts` file to redirect blocked domains to `127.0.0.1`, where FocusGuardian runs a local HTTP server serving a motivational page.
- **App blocking**: Uses `psutil` to scan running processes at a configurable interval and terminates any that match the blocklist.
- **Timer**: A Pomodoro-style timer that activates blocking during work sessions and deactivates it during breaks.
- **Statistics**: Session data is stored in a local SQLite database for tracking focus time and streaks.

## SmartScreen Warning

The installer is **unsigned** (no code signing certificate). Windows SmartScreen will show "Unknown publisher" — this is expected for open-source software without a paid code signing certificate.

To run the installer:
1. Click **More info**
2. Click **Run anyway**

This is normal for open-source projects like OBS Studio, Audacity, and many GitHub releases.

## Building the Installer

### Prerequisites

- Python 3.12 (standalone build for Windows)
- [psutil](https://pypi.org/project/psutil/)
- [NSIS 3.05](https://nsis.sourceforge.io/)

```bash
pip download psutil --only-binary=:all: --platform win_amd64 --python-version 312 --no-deps
makensis focus_guardian.nsi
```

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with Python and Tkinter
- Uses [psutil](https://github.com/giampaolo/psutil) for process management
- Inspired by the Windows 11 Settings app design language
