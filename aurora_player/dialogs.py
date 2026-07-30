from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import vlc
from PySide6.QtCore import QProcess, QSettings, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
)


class DiscDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Open disc")
        layout = QFormLayout(self)
        self.disc_type = QComboBox()
        self.disc_type.addItems(["DVD", "Blu-ray", "Audio CD", "VCD"])
        self.device = QLineEdit("D:" if sys.platform == "win32" else "/dev/sr0")
        layout.addRow("Disc type", self.disc_type)
        layout.addRow("Device", self.device)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def media_location(self) -> str:
        schemes = {
            "DVD": "dvd",
            "Blu-ray": "bluray",
            "Audio CD": "cdda",
            "VCD": "vcd",
        }
        return f"{schemes[self.disc_type.currentText()]}:///{self.device.text().strip()}"


class SyncDialog(QDialog):
    values_changed = Signal(int, int)

    def __init__(
        self, audio_delay_ms: int, subtitle_delay_ms: int, parent=None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Audio and subtitle synchronization")
        layout = QFormLayout(self)
        self.audio_delay = QSpinBox()
        self.audio_delay.setRange(-10_000, 10_000)
        self.audio_delay.setSuffix(" ms")
        self.audio_delay.setValue(audio_delay_ms)
        self.subtitle_delay = QSpinBox()
        self.subtitle_delay.setRange(-10_000, 10_000)
        self.subtitle_delay.setSuffix(" ms")
        self.subtitle_delay.setValue(subtitle_delay_ms)
        layout.addRow("Audio delay", self.audio_delay)
        layout.addRow("Subtitle delay", self.subtitle_delay)
        note = QLabel("Positive values make that track play later.")
        note.setWordWrap(True)
        layout.addRow(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self._emit_values
        )
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _emit_values(self) -> None:
        self.values_changed.emit(self.audio_delay.value(), self.subtitle_delay.value())


class SubtitleStyleDialog(QDialog):
    style_changed = Signal(dict)

    def __init__(self, settings: QSettings, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Subtitle appearance")
        layout = QFormLayout(self)
        self.size = QSpinBox()
        self.size.setRange(10, 72)
        self.size.setValue(int(settings.value("subtitles/font_size", 24)))
        self.position = QComboBox()
        self.position.addItems(["Bottom", "Top", "Center"])
        self.position.setCurrentText(
            str(settings.value("subtitles/position", "Bottom"))
        )
        self.margin = QSpinBox()
        self.margin.setRange(0, 400)
        self.margin.setSuffix(" px")
        self.margin.setValue(int(settings.value("subtitles/margin", 30)))
        self.bold = QCheckBox()
        self.bold.setChecked(
            str(settings.value("subtitles/bold", "false")).lower() == "true"
        )
        layout.addRow("Font size", self.size)
        layout.addRow("Position", self.position)
        layout.addRow("Margin", self.margin)
        layout.addRow("Bold", self.bold)
        note = QLabel(
            "Appearance changes apply when the current item is reloaded or the next "
            "item is opened. Timing changes are available under Playback → Synchronize."
        )
        note.setWordWrap(True)
        layout.addRow(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Close
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.apply
        )
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def apply(self) -> None:
        values = {
            "font_size": self.size.value(),
            "position": self.position.currentText(),
            "margin": self.margin.value(),
            "bold": self.bold.isChecked(),
        }
        for key, value in values.items():
            self.settings.setValue(f"subtitles/{key}", value)
        self.style_changed.emit(values)


class VideoEffectsDialog(QDialog):
    sharpen_changed = Signal(float)

    def __init__(
        self, player: vlc.MediaPlayer, sharpen_amount: float = 0.0, parent=None
    ) -> None:
        super().__init__(parent)
        self.player = player
        self.setWindowTitle("Video effects")
        layout = QVBoxLayout(self)
        self.enabled = QCheckBox("Enable image adjustment")
        self.enabled.setChecked(True)
        layout.addWidget(self.enabled)
        form = QFormLayout()
        self.controls: dict[vlc.VideoAdjustOption, tuple[QSlider, float]] = {}
        specs = [
            ("Brightness", vlc.VideoAdjustOption.Brightness, 0, 200, 100.0),
            ("Contrast", vlc.VideoAdjustOption.Contrast, 0, 200, 100.0),
            ("Saturation", vlc.VideoAdjustOption.Saturation, 0, 300, 100.0),
            ("Gamma", vlc.VideoAdjustOption.Gamma, 10, 300, 100.0),
            ("Hue", vlc.VideoAdjustOption.Hue, 0, 360, 1.0),
        ]
        for label, option, minimum, maximum, divisor in specs:
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(minimum, maximum)
            slider.setValue(0 if option == vlc.VideoAdjustOption.Hue else 100)
            slider.valueChanged.connect(self.apply)
            form.addRow(label, slider)
            self.controls[option] = (slider, divisor)
        layout.addLayout(form)
        sharpen_group = QGroupBox("Sharpen filter (reload required)")
        sharpen_layout = QFormLayout(sharpen_group)
        self.sharpen = QSlider(Qt.Orientation.Horizontal)
        self.sharpen.setRange(0, 200)
        self.sharpen.setValue(round(sharpen_amount * 100))
        self.apply_sharpen = QPushButton("Apply sharpen and reload")
        self.apply_sharpen.clicked.connect(
            lambda: self.sharpen_changed.emit(self.sharpen.value() / 100.0)
        )
        sharpen_layout.addRow("Strength", self.sharpen)
        sharpen_layout.addRow(self.apply_sharpen)
        layout.addWidget(sharpen_group)
        reset = QPushButton("Reset")
        reset.clicked.connect(self.reset)
        layout.addWidget(reset)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addWidget(close)
        self.enabled.toggled.connect(self.apply)

    def apply(self) -> None:
        self.player.video_set_adjust_int(
            vlc.VideoAdjustOption.Enable, int(self.enabled.isChecked())
        )
        if not self.enabled.isChecked():
            return
        for option, (slider, divisor) in self.controls.items():
            value = float(slider.value() / divisor)
            self.player.video_set_adjust_float(option, value)

    def reset(self) -> None:
        for option, (slider, _) in self.controls.items():
            slider.setValue(0 if option == vlc.VideoAdjustOption.Hue else 100)
        self.sharpen.setValue(0)
        self.apply()


class AudioEffectsDialog(QDialog):
    equalizer_selected = Signal(object)
    filters_changed = Signal(bool, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Audio effects")
        layout = QFormLayout(self)
        self.preset = QComboBox()
        count = vlc.libvlc_audio_equalizer_get_preset_count()
        for index in range(count):
            raw = vlc.libvlc_audio_equalizer_get_preset_name(index)
            name = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
            self.preset.addItem(name, index)
        self.preset.insertItem(0, "Off", -1)
        self.compressor = QCheckBox("Enable compressor on reload")
        self.spatializer = QCheckBox("Enable spatializer on reload")
        layout.addRow("Equalizer preset", self.preset)
        layout.addRow(self.compressor)
        layout.addRow(self.spatializer)
        note = QLabel(
            "The equalizer is immediate. Compressor and spatializer are libVLC audio "
            "filters and take effect when the media is reloaded."
        )
        note.setWordWrap(True)
        layout.addRow(note)
        self.preset.currentIndexChanged.connect(self._select_equalizer)
        self.compressor.toggled.connect(self._emit_filters)
        self.spatializer.toggled.connect(self._emit_filters)
        close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close.rejected.connect(self.reject)
        layout.addRow(close)

    def _select_equalizer(self) -> None:
        index = int(self.preset.currentData())
        equalizer = (
            None
            if index < 0
            else vlc.libvlc_audio_equalizer_new_from_preset(index)
        )
        self.equalizer_selected.emit(equalizer)

    def _emit_filters(self) -> None:
        self.filters_changed.emit(
            self.compressor.isChecked(), self.spatializer.isChecked()
        )


class ConverterDialog(QDialog):
    def __init__(
        self, vlc_executable: str | None, input_path: str | None = None, parent=None
    ) -> None:
        super().__init__(parent)
        self.vlc_executable = vlc_executable
        self.process = QProcess(self)
        self.setWindowTitle("Convert media")
        layout = QFormLayout(self)
        input_row = QHBoxLayout()
        self.input_path = QLineEdit(input_path or "")
        input_button = QPushButton("Browse…")
        input_button.clicked.connect(self.choose_input)
        input_row.addWidget(self.input_path)
        input_row.addWidget(input_button)
        layout.addRow("Input", input_row)
        output_row = QHBoxLayout()
        self.output_path = QLineEdit()
        output_button = QPushButton("Browse…")
        output_button.clicked.connect(self.choose_output)
        output_row.addWidget(self.output_path)
        output_row.addWidget(output_button)
        layout.addRow("Output", output_row)
        self.preset = QComboBox()
        self.preset.addItem(
            "MP4 — H.264 + AAC",
            (
                "vcodec=h264,acodec=mp4a,ab=192,channels=2,samplerate=48000",
                "mp4",
                ".mp4",
            ),
        )
        self.preset.addItem(
            "WebM — VP9 + Opus",
            ("vcodec=VP90,acodec=opus,ab=160,channels=2", "webm", ".webm"),
        )
        self.preset.addItem(
            "MP3 audio", ("acodec=mp3,ab=192,channels=2", "raw", ".mp3")
        )
        self.preset.addItem(
            "FLAC audio", ("acodec=flac,channels=2", "raw", ".flac")
        )
        self.preset.currentIndexChanged.connect(self._suggest_extension)
        layout.addRow("Preset", self.preset)
        self.status = QLabel("Ready")
        layout.addRow(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.start_button = buttons.addButton(
            "Start conversion", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.start_button.clicked.connect(self.start)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.process.finished.connect(self._conversion_finished)

    def choose_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose input")
        if path:
            self.input_path.setText(path)
            self._suggest_extension()

    def choose_output(self) -> None:
        extension = self.preset.currentData()[2]
        path, _ = QFileDialog.getSaveFileName(
            self, "Choose output", f"converted{extension}"
        )
        if path:
            self.output_path.setText(path)

    def _suggest_extension(self) -> None:
        if not self.input_path.text():
            return
        extension = self.preset.currentData()[2]
        current = self.output_path.text()
        if not current:
            self.output_path.setText(
                str(Path(self.input_path.text()).with_suffix(extension))
            )

    def start(self) -> None:
        if not self.vlc_executable:
            QMessageBox.critical(
                self,
                "VLC executable not found",
                "Install VLC and ensure vlc/cvlc is available.",
            )
            return
        source = self.input_path.text().strip()
        target = self.output_path.text().strip()
        if not source or not target:
            QMessageBox.warning(self, "Missing path", "Choose input and output files.")
            return
        transcode, mux, _ = self.preset.currentData()
        safe_target = target.replace("'", "\\'")
        sout = (
            f"#transcode{{{transcode}}}:"
            f"std{{access=file,mux={mux},dst='{safe_target}'}}"
        )
        arguments = [
            "-I",
            "dummy",
            "--quiet",
            source,
            "--sout",
            sout,
            "vlc://quit",
        ]
        self.start_button.setEnabled(False)
        self.status.setText("Converting…")
        self.process.start(self.vlc_executable, arguments)

    def _conversion_finished(
        self, exit_code: int, _status: QProcess.ExitStatus
    ) -> None:
        self.start_button.setEnabled(True)
        if exit_code == 0:
            self.status.setText("Conversion complete")
        else:
            self.status.setText(f"Conversion failed (exit code {exit_code})")
