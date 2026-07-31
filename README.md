# Aurora Player

<p align="center">
  <img src="aurora_player/assets/logo.png" alt="Aurora Player logo" width="180">
</p>

<p align="center">
  A modern, all-in-one media player for Windows and Linux.<br>
  Play up to four videos in one adaptive window—without installing VLC or Python.
</p>

<p align="center">
  <a href="https://github.com/AlexKav47/AuroraPlayer/releases/latest"><strong>Download the latest release</strong></a>
</p>

Aurora Player combines broad format support, advanced playback tools, media
management, conversion, customization, and a distinctive multi-video workspace
in one desktop application. The Windows release includes its media engine and
runtime, so it is ready to use immediately after installation.

<p align="center">
<img width="2559" height="1439" alt="image" src="https://github.com/user-attachments/assets/37e320c6-0f56-4516-974b-4b30e5ad8169" />
</p>

## Highlights

- Play up to four independent videos in one window.
- Open common video and audio formats through the bundled libVLC engine.
- Drag files or entire folders directly onto a video pane.
- Manage playlists and a searchable media library.
- Control subtitles, tracks, playback speed, synchronization, and effects.
- Resume unfinished local media automatically.
- Customize every major keyboard shortcut and choose from nine themes.
- Check GitHub Releases automatically for new versions.
- Install normally or use the fully portable Windows package.

## Adaptive multi-video layout

Aurora Player automatically rearranges the workspace as videos are added:

| Open videos | Layout |
|---:|---|
| 1 | One video fills the available viewing area |
| 2 | Two videos appear side by side |
| 3 | Three videos are stacked in full-width rows |
| 4 | Four videos appear in a 2×2 grid |

Click any video to make it active. Playback controls, track selection, effects,
seeking, and volume changes apply to the active pane. Each pane also has its own
play/pause and close controls, while **Play/pause all panes** controls the whole
workspace at once.

New files opened from Explorer are sent to the existing Aurora Player window.
Available panes are filled first, and additional items remain in the playlist.

## Features

### Media playback

- Plays MP4, MKV, AVI, MOV, WebM, WMV, MPEG, MP3, FLAC, AAC, WAV, OGG, Opus,
  and many other formats supported by the bundled media engine.
- Opens local files, folders, playlists, command-line paths, and network URLs.
- Plays DVDs, Blu-rays, audio CDs, and VCDs through **File → Open disc**.
- Supports correctly tagged 360-degree video.
- Changes playback speed from 0.25× to 4×.
- Skips backward or forward by a configurable 5, 10, 25, or 50 seconds.
- Provides frame-by-frame playback and A–B looping.
- Remembers unfinished local media and resumes from the saved position.
- Seeks directly when the timeline is clicked and previews exact time on hover.

### Multi-video workspace

- Plays up to four videos simultaneously in one application window.
- Uses automatic full, side-by-side, stacked, and quarter-grid layouts.
- Supports click-to-select panes with a subtle active-pane highlight.
- Provides independent play/pause and close controls for every pane.
- Safely closes panes while their media is still playing.
- Opens dropped files in the pane under the pointer.
- Recursively finds supported media inside dropped folders.
- Offers a single command to play or pause every open pane.

### Subtitles and tracks

- Selects between embedded audio, video, and subtitle tracks.
- Loads external SRT, ASS, SSA, VTT, SUB, and IDX subtitle files.
- Adjusts subtitle delay and audio delay in milliseconds.
- Customizes subtitle size, position, margin, and bold styling.
- Supports closed captions exposed by the media engine.

### Audio and video controls

- Includes equalizer presets, compressor support, and spatial audio effects.
- Adjusts brightness, contrast, saturation, gamma, and hue.
- Applies sharpening and other libVLC-powered filters.
- Changes crop, zoom, scale, and aspect ratio.
- Synchronizes audio, video, and subtitles.
- Controls volume independently for the selected pane.
- Supports mouse gestures for seeking and volume.

### Playlists and media library

- Creates editable playlists in the sidebar.
- Imports and exports M3U and M3U8 playlists.
- Scans folders recursively into a persistent SQLite media library.
- Searches and categorizes library content.
- Removes files and folders from the library without deleting the originals.
- Keeps additional media queued when all four panes are occupied.

### Conversion and discs

- Converts media to MP4, WebM, MP3, or FLAC using built-in presets.
- Opens DVD, Blu-ray, audio CD, and VCD sources.
- Includes the VLC conversion executable and required modules in Windows
  releases.

### Personalization and convenience

- Includes Graphite, Pearl, Midnight, Forest, Rose, Sunset, Pixie, Retro, and
  Space themes.
- Imports custom Qt stylesheet (`.qss`) skins.
- Allows keyboard shortcuts to be changed, cleared, or restored to defaults.
- Hides or restores the playlist and library sidebar.
- Enters fullscreen by shortcut or by double-clicking a video.
- Uses a video-only fullscreen view; mouse or keyboard activity slides the
  playback controls back into view temporarily.
- Always provides `Esc` as a fullscreen exit action by default.
- Supports trusted Python extensions through a documented entry point.
- Checks GitHub Releases for updates at most once every 24 hours.

## Download and install

### Windows installer — recommended

Download `AuroraPlayer-v1.3.0-Setup.exe` from the
[latest release](https://github.com/AlexKav47/AuroraPlayer/releases/latest),
then run it.

The installer:

- installs Aurora Player under `C:\Program Files\Aurora Player`;
- creates a Start Menu shortcut;
- registers supported media formats with Windows Default Apps;
- includes the complete Python, Qt, and libVLC runtime;
- adds Aurora Player to **Settings → Apps → Installed apps**; and
- provides a normal uninstaller.

The application is not currently code-signed, so Windows may show an
**Unknown publisher** or SmartScreen message. If you downloaded the installer
from this repository, choose **More info → Run anyway** to continue.

### Windows portable

Download `AuroraPlayer-v1.3.0-Portable.zip`, extract the entire archive, and
run:

```text
AuroraPlayer\AuroraPlayer.exe
```

Keep `AuroraPlayer.exe` beside its `runtime` folder. Portable settings are
stored in the current Windows user's application-data area, so preferences are
retained between launches without modifying the extracted runtime.

### Verify a download

Each release includes `SHA256-v1.3.0.txt`. Compare its values with the
downloaded files using PowerShell:

```powershell
Get-FileHash .\AuroraPlayer-v1.3.0-Setup.exe -Algorithm SHA256
Get-FileHash .\AuroraPlayer-v1.3.0-Portable.zip -Algorithm SHA256
```

### Linux

Linux binaries must be built on Linux because the application uses native Qt
and libVLC components. Install Python, VLC/libVLC, and Python's venv package,
then run:

```sh
chmod +x run.sh
./run.sh
```

On Debian or Ubuntu, the native packages are commonly named `vlc`, `libvlc5`,
and `python3-venv`. Package names vary by distribution.

## Quick start

1. Launch Aurora Player.
2. Open media with **File → Open file(s)**, press `Ctrl+O`, or drag media into
   the viewing area.
3. Add more videos by opening or dropping additional files.
4. Click a pane to select it.
5. Use the bottom controls for seeking, configurable skipping, playback speed,
   volume, and navigation.
6. Open the sidebar to manage the playlist or media library.

Dropping a folder scans it recursively. The first supported item opens in the
target pane, other available panes are filled, and remaining items are added to
the playlist.

## Keyboard and mouse controls

| Input | Default action |
|---|---|
| `Space` | Play or pause the active pane |
| `Ctrl+Space` | Play or pause all panes |
| `Left` / `Right` | Skip backward or forward by the selected amount |
| `Shift+Left` / `Shift+Right` | Seek backward or forward 30 seconds |
| `Up` / `Down` | Raise or lower volume |
| `M` | Mute |
| `S` | Stop |
| `E` | Advance one frame |
| `[` / `]` | Set the A and B loop points |
| `\` | Clear the A–B loop |
| `F11` or video double-click | Enter or leave fullscreen |
| `Esc` | Leave fullscreen |
| `Ctrl+N` | Add another video |
| `Ctrl+B` | Show or hide the sidebar |
| `Ctrl+O` | Open files |
| `Ctrl+Shift+O` | Open a folder |
| Right-drag horizontally | Seek backward or forward |
| Right-drag vertically | Lower or raise volume |
| Click a pane | Make that pane active |
| Drop files or folders on a pane | Open media in that pane |
| `Delete` in the library | Remove selected entries without deleting files |

Change or disable shortcuts under
**View → Customize keyboard shortcuts**. Choose **Restore defaults** in the
shortcut editor to return to the original controls.

The backward and forward skip buttons use 10 seconds by default. Select
**Settings → Playback skip amount** to change both buttons, the `Left` / `Right`
shortcuts, and horizontal mouse gestures to 5, 10, 25, or 50 seconds.

## Automatic update checks

Automatic checks are enabled by default and run at most once every 24 hours.
Aurora Player reads the latest published release from this repository and
notifies you when its version is newer than the installed version.

- Toggle automatic checks under **Help → Check for updates automatically**.
- Run a manual check with **Help → Check for updates**.
- On Windows, accepting an update downloads the correctly versioned installer
  from the official Aurora Player GitHub release and launches it automatically.
- GitHub's SHA-256 asset digest is verified when the release provides one.
- Aurora Player always asks before downloading or installing an update.
- Other platforms open the GitHub release page for manual installation.
- Draft releases and tags without a published GitHub Release are not offered.

## Default application settings

The installer registers Aurora Player with Windows, but Windows requires the
user to approve default-app changes:

1. Open **Settings → Apps → Default apps**.
2. Search for **Aurora Player**.
3. Select the video and audio extensions you want Aurora Player to open.

Opening an associated file while Aurora Player is already running sends it to
the same window instead of starting a second instance.

## Data and uninstalling

The installed application stores its settings, resume history, media-library
database, custom themes, and extensions in the user's application-data area.
The portable build uses the same per-user storage by default.

During uninstall, Aurora Player asks whether this application data should also
be removed. Your original video and audio files are never deleted by the
uninstaller. Removing an entry from the Aurora Player library also leaves the
original file untouched.

Use **Playback → Clear saved playback positions** at any time to erase resume
history.

## Disc playback notes

- Commercial Blu-ray playback may require separately available AACS/BD+
  components and lawful keys. Aurora Player does not bypass copy protection.
- Disc support depends on the optical drive, operating-system permissions, and
  available decoding components.
- A Windows disc device is usually a drive letter such as `D:`.
- A typical Linux optical-drive path is `/dev/sr0`.

## Themes and extensions

Choose a built-in theme under **View → Skin**, or import a custom Qt stylesheet
(`.qss`).

User extensions are trusted Python files placed in Aurora Player's
application-data `extensions` folder. An extension exposes a `register`
function:

```python
def register(application):
    # application.new_window(path=None)
    # application.windows
    pass
```

Extensions run with the same permissions as the application. Only install
extension files from sources you trust.

## Build from source

### Windows

Install Python and VLC on the development computer, then run:

```powershell
.\build.ps1
.\build-installer.ps1
```

`build.ps1` creates the portable folder and ZIP. `build-installer.ps1` uses
Inno Setup 7 to create the Windows installer. VLC and Python are needed only on
the build computer; they are bundled for end users.

### Linux

Build on Linux with:

```sh
chmod +x build.sh
./build.sh
```

## Testing

After installing the project requirements and `pytest`, run:

```powershell
python -m pytest
```

The automated suite covers the media library, playlists, recursive media-path
expansion, resume storage, portable settings, and release-version comparison.
The packaged application also supports an internal four-pane playback smoke
test used during release validation.

## Project structure

| Path | Purpose |
|---|---|
| `aurora_player/app.py` | Application lifecycle, single-instance handoff, themes, extensions, and update checks |
| `aurora_player/player.py` | Playback window, panes, menus, controls, playlists, and media-engine binding |
| `aurora_player/dialogs.py` | Disc, synchronization, effects, subtitle, conversion, and shortcut dialogs |
| `aurora_player/library.py` | Persistent media library, resume positions, media discovery, and playlists |
| `aurora_player/settings.py` | Installed and portable settings storage |
| `aurora_player/updates.py` | GitHub release version comparison |
| `aurora_player/vlc_runtime.py` | Bundled and system libVLC discovery |
| `installer/AuroraPlayer.iss` | Windows installer and file-association configuration |

## Technology

Aurora Player is built with:

- [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/)
- [libVLC](https://www.videolan.org/vlc/libvlc.html)
- [python-vlc](https://pypi.org/project/python-vlc/)
- [SQLite](https://www.sqlite.org/)
- [Inno Setup](https://jrsoftware.org/isinfo.php) for Windows installation

Third-party licensing information is provided in
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

Aurora Player is an independent project and is not affiliated with or endorsed
by VideoLAN.
