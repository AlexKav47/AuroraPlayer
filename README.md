# Aurora Player

<img src="aurora_player/assets/logo.png" alt="Aurora Player logo" width="180">

Aurora Player is a Windows and Linux desktop media player built with Qt and an
embedded libVLC media engine. One window can hold up to four independent video
panes in an adaptive layout: one full-area video, two side-by-side videos,
three stacked rows, or four quarter-size panes.

The Windows release is a fast portable folder. Python, Qt, the media engine,
codecs, filters, disc modules, and conversion tools are bundled beside the
executable. The target computer does not need VLC or Python installed.

## Run it

### Windows

For a normal installation, double-click:

```text
release\AuroraPlayer-Setup.exe
```

The setup installs Aurora Player under Program Files, creates a Start Menu
entry, registers supported media formats with Windows Default Apps, and adds an
uninstaller under **Settings → Apps → Installed apps**. Windows requires the
user to confirm default-app changes, so setup offers to open the Default Apps
page when it finishes.

During uninstall, Aurora asks whether to remove its settings, library database,
custom themes, and extensions. Original video and audio files are never
deleted.

For portable use instead, extract `release\AuroraPlayer-Portable.zip` once,
then double-click:

```text
release\AuroraPlayer\AuroraPlayer.exe
```

There is no installation or first-run setup. The executable can be copied to
another Windows 10/11 x64 computer together with its `runtime` folder and
launched directly. Keeping the runtime unpacked avoids the long extraction delay
that affected the earlier single-file build.

The `run.ps1` script is only for source-code development.

### Linux

Linux binaries must be built on Linux because native binaries cannot be
cross-compiled by the Windows packaging tool. For source development, install
VLC/libVLC and Python's venv package, then run:

```sh
chmod +x run.sh
./run.sh
```

Package names differ by distribution. On Debian/Ubuntu the required native
packages are normally `vlc`, `libvlc5`, and `python3-venv`.

## Current feature coverage

| Requested capability | Current implementation |
|---|---|
| MP4, MKV, AVI, MOV, MP3, FLAC, AAC and other formats | Decoded by the media engine embedded in the executable |
| DVD, Blu-ray, audio CD and VCD | **File → Open disc** with disc type and device selection |
| Open files | Dialog, drag-and-drop, folder opening, command line, and network URL |
| Playlists | Editable sidebar, M3U/M3U8 import/export, previous/next controls |
| Media library | Persistent SQLite library, recursive folder scan, search, categorization, and safe file/folder removal |
| Subtitles and closed captions | Embedded subtitle-track menu plus external SRT/ASS/SSA/VTT/SUB loading |
| Subtitle timing and appearance | Live delay plus persistent size, position, margin, and bold settings |
| Multiple audio/video tracks | Dynamic Audio, Video, and Subtitle track menus |
| Playback speed | 0.25× through 4× |
| Frame-by-frame and A–B loop | `E`/Frame button and `[`, `]`, `\` loop controls |
| Equalizer, compressor, spatial effects | libVLC equalizer presets; compressor/spatializer reload filters |
| Video filters and colour | Live brightness, contrast, saturation, gamma, hue, and reload-based sharpen |
| Crop, zoom and aspect ratio | Video menu controls |
| Audio/video/subtitle synchronization | Millisecond audio and subtitle delays |
| Convert/transcode | VLC-powered MP4, WebM, MP3 and FLAC presets |
| 360° video | libVLC projection support for correctly tagged 360° files |
| Shortcuts and mouse gestures | Keyboard seek/volume/play/frame/fullscreen; right-drag seek/volume |
| Extensions | Trusted Python extensions with a documented `register(application)` entry point |
| Custom skins | Six built-in colour themes plus user-imported Qt `.qss` stylesheets |
| Windows and Linux | Native Qt window and platform-specific VLC video surface |
| Multiple simultaneous videos | One window, up to four independent panes, adaptive layouts, click-to-select controls, and play/pause-all |

## Important disc notes

- Commercial Blu-ray playback can require separately available AACS/BD+
  components and lawful keys. The application does not
  bypass copy protection.
- DVD and Blu-ray support also depends on the optical drive and operating-system
  permissions.
- On Linux, the usual optical-drive path is `/dev/sr0`; on Windows it is a drive
  letter such as `D:`.

## Opening files in the same window

Aurora Player uses a single-instance handoff. Once the executable is associated
with video extensions, later Explorer or file-manager launches send their files
to the existing window. Available panes are filled up to the four-video limit;
additional files remain accessible in the playlist.

To rebuild the executable on a development computer:

```powershell
.\build.ps1
```

The Windows executable appears at:

```text
release\AuroraPlayer\AuroraPlayer.exe
```

Then use **Settings → Apps → Default apps** to associate the formats you want
with that executable. Target computers do not need VLC or Python.

On Linux, run `./build.sh`, install the resulting application somewhere on
`PATH`, and create a normal desktop entry with the media MIME types you want.

## Controls

| Input | Action |
|---|---|
| `Space` | Play/pause |
| `Left` / `Right` | Seek 5 seconds |
| `Shift+Left` / `Shift+Right` | Seek 30 seconds |
| `Up` / `Down` | Volume |
| `M` | Mute |
| `E` | Next frame |
| `[` / `]` | Set A/B loop points |
| `\` | Clear A/B loop |
| `F11` or video double-click | Fullscreen |
| Right-drag horizontally | Seek backward/forward |
| Right-drag vertically | Volume down/up |
| `Ctrl+N` | Select another video to add |
| `Ctrl+Space` | Play/pause all panes |
| Click a pane | Make that pane active |
| Per-pane play button | Pause or resume only that video |
| `Ctrl+B` or Sidebar button | Show or hide the sidebar |
| `Delete` in the library | Remove selected files/folders from the library without deleting them from disk |

## Extensions and skins

User extensions live in Aurora Player's application-data `extensions` folder.
An extension is a trusted Python file:

```python
def register(application):
    # application.new_window(path=None)
    # application.windows
    pass
```

Extensions execute as normal Python code with the user's permissions. Do not
install an extension unless you trust its source.

Skins are Qt stylesheets (`.qss`) and can be loaded from **View → Skin**.

## Development

Run the automated tests after installing the requirements:

```powershell
.\.venv\Scripts\python.exe -m pip install pytest
.\.venv\Scripts\python.exe -m pytest
```

The code is intentionally split into:

- `app.py` — lifecycle, single-instance handoff, skins, and extension loading
- `player.py` — playback UI, library/playlist views, controls, and VLC binding
- `dialogs.py` — discs, synchronization, effects, subtitles, and conversion
- `library.py` — persistent media library and M3U handling
- `vlc_runtime.py` — Windows/Linux libVLC discovery

## Production follow-ups

Useful follow-up work for later releases:

- code-signing the installer and application binaries;
- thumbnail and metadata extraction in a background worker;
- thumbnail previews while seeking;
- per-file resume positions and play history;
- GPU/backend diagnostics and crash reporting;
- sandboxed or declarative extensions instead of unrestricted Python;
- CI builds and playback tests on both Windows and Linux.
