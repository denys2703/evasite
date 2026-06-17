"""PySide6 desktop UI for the DXF to IMG renderer."""

from __future__ import annotations

from multiprocessing import freeze_support
from pathlib import Path
import json
import os
import threading
import subprocess
import sys

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .batch import BatchConfig, run_batch_detailed


APP_BG = "#f2f2f7"
CARD_BG = "#ffffff"
TEXT = "#1a1a1a"
MUTED = "#737373"
FIELD_BG = "rgba(0, 0, 0, 0.055)"
FIELD_BORDER = "rgba(0, 0, 0, 0.06)"
PRIMARY = "#0d6fff"
SECONDARY = "rgba(120, 120, 128, 0.20)"
FONT_FAMILY = "Segoe UI"
CONFIG_FILE = "gui_settings.json"
DEFAULT_SETTINGS = {
    "Workers": "4",
    "SuperSample": "3",
    "Border px": "10",
    "Stitch texture scale": "1.0",
    "Border texture scale": "1.0",
    "Padding": "100",
    "Gap": "50",
    "Stitch offset": "4",
    "Material texture scale": "1.0",
    "Corner smoothing px": "20",
    "Corner min angle deg": "30",
}

class RenderCancelled(Exception):
    """Raised inside the GUI worker when the user requests cancellation."""


class RenderWorker(QObject):
    """Run the real batch renderer away from the Qt UI thread."""

    status = Signal(str)
    finished = Signal(int, int)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, config: BatchConfig, cancel_event: threading.Event) -> None:
        super().__init__()
        self.config = config
        self.cancel_event = cancel_event

    def run(self) -> None:
        try:
            def status_callback(message: str) -> None:
                if self.cancel_event.is_set():
                    raise RenderCancelled()
                self.status.emit(message)

            results = run_batch_detailed(self.config, status_callback=status_callback)
            if self.cancel_event.is_set():
                self.cancelled.emit()
                return
            ok_count = sum(1 for result in results if result.ok)
            self.finished.emit(ok_count, len(results))
        except RenderCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class DXFToIMGWindow(QMainWindow):
    """Compact macOS-like DXF to IMG utility window built with PySide6."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("DXF to IMG")
        self.resize(800, 840)
        self.setMinimumSize(680, 640)
        self.path_fields: dict[str, QLineEdit] = {}
        self.setting_fields: dict[str, QLineEdit] = {}
        self.combo_fields: dict[str, QComboBox] = {}
        self.status_edit: QTextEdit | None = None
        self.progress_bar: QProgressBar | None = None
        self.start_button: QPushButton | None = None
        self.stop_button: QPushButton | None = None
        self.config_path = _config_path()
        self._loading_config = False
        self.total_jobs = 0
        self.render_thread: QThread | None = None
        self.render_worker: RenderWorker | None = None
        self.cancel_event = threading.Event()
        self._stopping_render = False
        self._build_ui()
        self._load_config()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("root")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(10)
        root_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        content = QWidget(root)
        content.setObjectName("content")
        content.setMaximumWidth(820)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        content_layout.addWidget(self.create_files_section())
        content_layout.addWidget(self.create_render_settings_section())
        content_layout.addWidget(self.create_status_section())
        root_layout.addWidget(content, 1, Qt.AlignmentFlag.AlignHCenter)
        self.setCentralWidget(root)
        self._apply_styles()

    def create_card(self) -> QFrame:
        card = QFrame(self)
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(0)
        return card

    def create_title(self, text: str) -> QLabel:
        title = QLabel(text)
        title.setObjectName("sectionTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFixedHeight(24)
        return title

    def create_path_row(self, label_text: str, button_text: str, *, file_dialog: bool = False) -> tuple[QWidget, QLineEdit]:
        row = QWidget(self)
        row.setObjectName("row")
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(0)
        layout.setColumnMinimumWidth(0, 106)
        layout.setColumnStretch(1, 1)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedWidth(106)

        field = QLineEdit()
        field.setObjectName("pathField")
        field.setPlaceholderText("")
        field.setMinimumWidth(80)
        field.setFixedHeight(24)

        button = QPushButton(button_text)
        button.setObjectName("primaryButton")
        button.setCursor(Qt.CursorShape.ArrowCursor)
        button.clicked.connect(lambda _checked=False, target=field, is_file=file_dialog: self._choose_path(target, is_file))

        layout.addWidget(label, 0, 0)
        layout.addWidget(field, 0, 1)
        layout.addWidget(button, 0, 2)
        return row, field

    def create_setting_row(self, label_text: str) -> tuple[QWidget, QLineEdit]:
        row, layout = self._create_setting_row_base(label_text)
        field = QLineEdit()
        field.setObjectName("settingField")
        field.setFixedHeight(24)
        field.setMinimumWidth(120)
        layout.addWidget(field, 0, 1)
        return row, field

    def create_setting_combo_row(self, label_text: str, values: list[str]) -> tuple[QWidget, QComboBox]:
        row, layout = self._create_setting_row_base(label_text)
        combo = QComboBox()
        combo.setObjectName("settingField")
        combo.addItems(values)
        combo.setFixedHeight(24)
        combo.setMinimumWidth(120)
        layout.addWidget(combo, 0, 1)
        return row, combo

    def _create_setting_row_base(self, label_text: str) -> tuple[QWidget, QGridLayout]:
        row = QWidget(self)
        row.setObjectName("settingRow")
        layout = QGridLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(0)
        layout.setColumnMinimumWidth(0, 128)
        layout.setColumnStretch(1, 1)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumWidth(128)
        layout.addWidget(label, 0, 0)
        return row, layout

    def create_files_section(self) -> QFrame:
        card = self.create_card()
        layout = card.layout()
        assert isinstance(layout, QVBoxLayout)

        layout.addWidget(self.create_title("Templates folder"))
        layout.setContentsMargins(8, 8, 8, 8)
        self._add_path_row(layout, "templates", "Templates folder", "Choose", row_spacing=2)
        self._add_path_row(layout, "only_folder", "Only folder", "Choose", row_spacing=2)
        self._add_path_row(layout, "dxf_folder", "Front DXF folder", "Choose", default="2", row_spacing=2)
        self._add_path_row(layout, "rear_dxf_folder", "Rear DXF folder", "Choose", default="7", row_spacing=2)
        self._add_path_row(layout, "tunnel_dxf_folder", "Tunnel DXF folder", "Choose", default="8", row_spacing=2)
        self._add_path_row(layout, "trunk_dxf_folders", "Trunk folders", "Choose", default="12,13,14", row_spacing=2)
        self._add_path_row(layout, "second_row_dxf_folder", "2nd row folder", "Choose", default="17", row_spacing=2)
        self._add_path_row(layout, "third_row_dxf_folder", "3rd row folder", "Choose", default="18", row_spacing=2)
        self._add_path_row(layout, "extra_dxf_folders", "Extra folders", "Choose", row_spacing=2)
        self._add_path_row(layout, "output", "Output folder", "Choose", row_spacing=2)

        texture_title = self.create_title("Textures files")
        texture_title.setContentsMargins(0, 6, 0, 0)
        layout.addWidget(texture_title)
        self._add_path_row(layout, "material", "Material texture", "Choose file", file_dialog=True, row_spacing=2)
        self._add_path_row(layout, "border", "Border texture", "Choose file", file_dialog=True, row_spacing=2)
        self._add_path_row(layout, "stitches", "Stitches texture", "Choose file", file_dialog=True, row_spacing=0)
        return card

    def create_render_settings_section(self) -> QFrame:
        card = self.create_card()
        layout = card.layout()
        assert isinstance(layout, QVBoxLayout)
        layout.addWidget(self.create_title("Render Settings"))

        settings = QWidget(card)
        settings_layout = QGridLayout(settings)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.setHorizontalSpacing(26)
        settings_layout.setVerticalSpacing(6)
        settings_layout.setColumnStretch(0, 1)
        settings_layout.setColumnStretch(1, 1)

        left_column = self._create_settings_column(
            [
                "Workers",
                "SuperSample",
                "Border px",
                "Stitch texture scale",
                "Border texture scale",
            ]
        )
        right_column = self._create_settings_column(
            [
                "Padding",
                "Gap",
                "Stitch offset",
                "Material texture scale",
                "Corner smoothing px",
                "Corner min angle deg",
                "Axis align",
            ]
        )
        settings_layout.addWidget(left_column, 0, 0)
        settings_layout.addWidget(right_column, 0, 1)

        actions = QWidget(settings)
        actions_layout = QHBoxLayout(actions)
        actions_layout.setContentsMargins(0, 2, 0, 0)
        actions_layout.setSpacing(8)
        actions_layout.addStretch(1)

        self.start_button = QPushButton("Start Render")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self.start_render)
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("secondaryButton")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_render)
        output_button = QPushButton("Open output")
        output_button.setObjectName("secondaryButton")
        output_button.clicked.connect(self.open_output)
        logs_button = QPushButton("Open logs")
        logs_button.setObjectName("secondaryButton")
        logs_button.clicked.connect(self.open_logs)

        actions_layout.addWidget(self.start_button)
        actions_layout.addWidget(self.stop_button)
        actions_layout.addWidget(output_button)
        actions_layout.addWidget(logs_button)
        settings_layout.addWidget(actions, 1, 0, 1, 2)

        self.progress_bar = QProgressBar(settings)
        self.progress_bar.setObjectName("progressBar")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        settings_layout.addWidget(self.progress_bar, 2, 0, 1, 2)
        layout.addWidget(settings)
        return card

    def create_status_section(self) -> QFrame:
        card = self.create_card()
        card.setObjectName("statusCard")
        card.setMinimumHeight(118)
        card.setMaximumHeight(145)
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = card.layout()
        assert isinstance(layout, QVBoxLayout)
        layout.addWidget(self.create_title("Live status"))

        self.status_edit = QTextEdit(card)
        self.status_edit.setObjectName("statusEdit")
        self.status_edit.setReadOnly(True)
        self.status_edit.setPlaceholderText("")
        self.status_edit.setMinimumHeight(72)
        self.status_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.status_edit, 1)
        return card

    def _add_path_row(
        self,
        layout: QVBoxLayout,
        key: str,
        label: str,
        button_text: str,
        *,
        file_dialog: bool = False,
        default: str = "",
        row_spacing: int = 10,
    ) -> None:
        row, field = self.create_path_row(label, button_text, file_dialog=file_dialog)
        if default:
            field.setText(default)
        self.path_fields[key] = field
        field.textChanged.connect(lambda _text: self._save_config())
        layout.addWidget(row)
        if row_spacing > 0:
            layout.addSpacing(row_spacing)

    def _create_settings_column(self, labels: list[str]) -> QWidget:
        column = QWidget(self)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(6)
        for label in labels:
            if label == "Axis align":
                row, combo = self.create_setting_combo_row(label, ["top", "center", "bottom"])
                self.combo_fields[label] = combo
                combo.currentTextChanged.connect(lambda _text: self._save_config())
                column_layout.addWidget(row)
                continue
            row, field = self.create_setting_row(label)
            field.setText(DEFAULT_SETTINGS.get(label, ""))
            self.setting_fields[label] = field
            field.textChanged.connect(lambda _text: self._save_config())
            column_layout.addWidget(row)
        return column

    def _choose_path(self, target: QLineEdit, file_dialog: bool) -> None:
        if file_dialog:
            selected, _filter = QFileDialog.getOpenFileName(self, "Choose file", "", "PNG textures (*.png);;All files (*.*)")
        else:
            selected = QFileDialog.getExistingDirectory(self, "Choose folder")
        if selected:
            target.setText(selected)

    def start_render(self) -> None:
        if self.status_edit is None or self.progress_bar is None:
            return
        if self.render_thread is not None and self.render_thread.isRunning():
            self.status_edit.append("Render is already running.")
            return

        try:
            config = self._build_batch_config()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid settings", str(exc))
            return

        self._save_config()
        self.total_jobs = 0
        self._stopping_render = False
        self.cancel_event.clear()
        self.progress_bar.setValue(0)
        self.status_edit.append("Starting render…")

        self.render_thread = QThread(self)
        self.render_worker = RenderWorker(config, self.cancel_event)
        self.render_worker.moveToThread(self.render_thread)
        self.render_thread.started.connect(self.render_worker.run)
        self.render_worker.status.connect(self._handle_render_status)
        self.render_worker.finished.connect(self._render_finished)
        self.render_worker.failed.connect(self._render_failed)
        self.render_worker.cancelled.connect(self._render_cancelled)
        self.render_worker.finished.connect(self.render_thread.quit)
        self.render_worker.failed.connect(self.render_thread.quit)
        self.render_worker.cancelled.connect(self.render_thread.quit)
        self.render_thread.finished.connect(self.render_worker.deleteLater)
        self.render_thread.finished.connect(self._render_thread_finished)
        self._set_running_state(True)
        self.render_thread.start()

    def stop_render(self) -> None:
        if self.render_thread is None or not self.render_thread.isRunning():
            return
        self._stopping_render = True
        self.cancel_event.set()
        if self.stop_button is not None:
            self.stop_button.setEnabled(False)
        if self.status_edit is not None:
            self.status_edit.append("Stopping render after current task…")

    def _build_batch_config(self) -> BatchConfig:
        templates = Path(self._field_text("templates") or "Templates")
        output = Path(self._field_text("output") or "output")
        folder_text = self._field_text("only_folder")
        folder = Path(folder_text) if folder_text else None
        dxf_folder_text = self._field_text("dxf_folder") or "2"
        dxf_folder = Path(dxf_folder_text)
        set_folder_name = dxf_folder.name if dxf_folder.exists() else dxf_folder_text.strip()
        rear_folder_text = self._field_text("rear_dxf_folder") or "7"
        tunnel_folder_text = self._field_text("tunnel_dxf_folder") or "8"
        trunk_folder_text = self._field_text("trunk_dxf_folders") or "12,13,14"
        second_row_folder_text = self._field_text("second_row_dxf_folder") or "17"
        third_row_folder_text = self._field_text("third_row_dxf_folder") or "18"
        extra_folder_text = self._field_text("extra_dxf_folders")
        if folder:
            render_dir = folder if folder.exists() else templates / folder
        elif dxf_folder.exists():
            render_dir = dxf_folder
        else:
            render_dir = None
        return BatchConfig(
            templates_dir=templates,
            output_dir=output,
            render_dir=render_dir,
            set_folder_name=set_folder_name,
            rear_set_folder_name=_folder_name_or_text(rear_folder_text),
            tunnel_set_folder_name=_folder_name_or_text(tunnel_folder_text),
            trunk_set_folder_names=_folder_names_or_csv(trunk_folder_text),
            second_row_set_folder_name=_folder_name_or_text(second_row_folder_text),
            third_row_set_folder_name=_folder_name_or_text(third_row_folder_text),
            extra_set_folder_names=_folder_names_or_csv(extra_folder_text) if extra_folder_text else (),
            log_file=output / "render.log",
            material_texture=_optional_path(self._field_text("material")),
            border_texture=_optional_path(self._field_text("border")),
            stitch_texture=_optional_path(self._field_text("stitches")),
            padding=self._setting_int("Padding"),
            gap=self._setting_int("Gap"),
            border_px=self._setting_int("Border px"),
            corner_smoothing_px=self._setting_int("Corner smoothing px"),
            corner_min_angle_deg=self._setting_float("Corner min angle deg"),
            material_texture_scale=self._setting_float("Material texture scale"),
            border_texture_scale=self._setting_float("Border texture scale"),
            stitch_texture_scale=self._setting_float("Stitch texture scale"),
            stitch_offset_px=self._setting_int("Stitch offset"),
            supersample=self._setting_int("SuperSample"),
            axis_align=self._combo_text("Axis align", "top"),
            workers=self._setting_int("Workers"),
        )

    def _setting_int(self, label: str) -> int:
        value = self._setting_text(label)
        try:
            return int(float(value))
        except ValueError as exc:
            raise ValueError(f"{label} must be a number") from exc

    def _setting_float(self, label: str) -> float:
        value = self._setting_text(label)
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"{label} must be a number") from exc

    def _setting_text(self, label: str) -> str:
        field = self.setting_fields.get(label)
        return field.text().strip() if field is not None and field.text().strip() else DEFAULT_SETTINGS[label]

    def _combo_text(self, key: str, default: str) -> str:
        combo = self.combo_fields.get(key)
        return combo.currentText().strip() if combo is not None and combo.currentText().strip() else default

    def _field_text(self, key: str) -> str:
        field = self.path_fields.get(key)
        return field.text().strip() if field is not None else ""

    def _handle_render_status(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        if self.status_edit is not None:
            self.status_edit.append(line)
        self._update_progress_from_line(line)

    def _update_progress_from_line(self, line: str) -> None:
        if self.progress_bar is None:
            return
        if line.startswith("Discovered "):
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                self.total_jobs = int(parts[1])
                self.progress_bar.setValue(0)
            return
        if line.startswith("[") and "/" in line and "]" in line:
            head = line.split("]", 1)[0].strip("[")
            completed_text, total_text = head.split("/", 1)
            if completed_text.isdigit() and total_text.isdigit():
                completed = int(completed_text)
                total = int(total_text)
                self.total_jobs = total
                self.progress_bar.setValue(round(completed / total * 100) if total else 0)
            return
        if line.startswith("Done:") or line.startswith("Rendered "):
            if self.total_jobs:
                self.progress_bar.setValue(100)

    def _render_finished(self, ok_count: int, total: int) -> None:
        self._set_running_state(False)
        if self.progress_bar is not None and total:
            self.progress_bar.setValue(100)
        if self.status_edit is not None:
            self.status_edit.append(f"Render finished: {ok_count}/{total} image(s).")
        self._stopping_render = False

    def _render_failed(self, message: str) -> None:
        self._set_running_state(False)
        if self.status_edit is not None:
            self.status_edit.append(f"Render failed: {message}")
        self._stopping_render = False

    def _render_cancelled(self) -> None:
        self._set_running_state(False)
        if self.status_edit is not None:
            self.status_edit.append("Render stopped by user.")
        self._stopping_render = False

    def _render_thread_finished(self) -> None:
        if self.render_thread is not None:
            self.render_thread.deleteLater()
        self.render_thread = None
        self.render_worker = None

    def _set_running_state(self, running: bool) -> None:
        if self.start_button is not None:
            self.start_button.setEnabled(not running)
        if self.stop_button is not None:
            self.stop_button.setEnabled(running)

    def open_output(self) -> None:
        output = self.path_fields.get("output")
        output_path = output.text().strip() if output is not None else ""
        if output_path:
            _open_path(Path(output_path))
        else:
            QMessageBox.information(self, "Open output", "Choose an output folder first.")

    def open_logs(self) -> None:
        output = self.path_fields.get("output")
        output_path = output.text().strip() if output is not None else ""
        if output_path:
            _open_path(Path(output_path) / "render.log")
        else:
            QMessageBox.information(self, "Open logs", "Choose an output folder first.")

    def _load_config(self) -> None:
        if not self.config_path.exists():
            return
        self._loading_config = True
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            for key, value in data.get("paths", {}).items():
                field = self.path_fields.get(key)
                if field is not None:
                    field.setText(str(value))
            for key, value in data.get("settings", {}).items():
                field = self.setting_fields.get(key)
                if field is not None:
                    field.setText(str(value))
            for key, value in data.get("combos", {}).items():
                combo = self.combo_fields.get(key)
                if combo is not None:
                    index = combo.findText(str(value))
                    if index >= 0:
                        combo.setCurrentIndex(index)
        except (OSError, json.JSONDecodeError, TypeError):
            if self.status_edit is not None:
                self.status_edit.append("Could not load saved GUI settings; using defaults.")
        finally:
            self._loading_config = False

    def _save_config(self) -> None:
        if self._loading_config:
            return
        data = {
            "paths": {key: field.text() for key, field in self.path_fields.items()},
            "settings": {key: field.text() for key, field in self.setting_fields.items()},
            "combos": {key: combo.currentText() for key, combo in self.combo_fields.items()},
        }
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.render_thread is not None and self.render_thread.isRunning():
            self.stop_render()
            self.render_thread.quit()
            self.render_thread.wait(1500)
        self._save_config()
        super().closeEvent(event)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            f"""
            QWidget#root {{
                background: {APP_BG};
                color: {TEXT};
                font-family: "{FONT_FAMILY}";
                font-size: 13px;
            }}
            QWidget#content {{
                background: transparent;
            }}
            QFrame#card, QFrame#statusCard {{
                background: {CARD_BG};
                border-radius: 20px;
            }}
            QLabel#sectionTitle {{
                color: {TEXT};
                font-size: 13px;
                font-weight: 510;
                letter-spacing: -0.01em;
                background: transparent;
            }}
            QLabel#fieldLabel {{
                color: {TEXT};
                font-size: 13px;
                font-weight: 510;
                letter-spacing: -0.01em;
                background: transparent;
            }}
            QLineEdit#pathField, QLineEdit#settingField, QComboBox#settingField {{
                background: {FIELD_BG};
                color: {MUTED};
                border: 1px solid {FIELD_BORDER};
                border-radius: 10px;
                padding: 0 10px;
                selection-background-color: {PRIMARY};
                min-height: 24px;
                max-height: 24px;
            }}
            QComboBox#settingField::drop-down {{
                border: none;
                width: 18px;
            }}
            QPushButton#primaryButton, QPushButton#secondaryButton {{
                border: none;
                border-radius: 10px;
                min-height: 24px;
                max-height: 24px;
                padding: 0 17px;
                font-size: 13px;
                font-weight: 510;
                letter-spacing: -0.01em;
            }}
            QPushButton#primaryButton {{
                background: {PRIMARY};
                color: white;
            }}
            QPushButton#primaryButton:pressed {{
                background: #0b63e5;
            }}
            QPushButton#secondaryButton {{
                background: {SECONDARY};
                color: {TEXT};
            }}
            QPushButton#secondaryButton:pressed {{
                background: rgba(120, 120, 128, 0.30);
            }}
            QPushButton#primaryButton:disabled, QPushButton#secondaryButton:disabled {{
                background: rgba(120, 120, 128, 0.12);
                color: rgba(26, 26, 26, 0.42);
            }}
            QProgressBar#progressBar {{
                background: rgba(0, 0, 0, 0.055);
                border: none;
                border-radius: 4px;
            }}
            QProgressBar#progressBar::chunk {{
                background: {PRIMARY};
                border-radius: 4px;
            }}
            QTextEdit#statusEdit {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(0,0,0,0.018), stop:1 rgba(0,0,0,0));
                color: {MUTED};
                border: none;
                border-radius: 14px;
                padding: 12px;
                font-size: 13px;
            }}
            QScrollBar:vertical {{
                width: 0px;
                background: transparent;
            }}
            """
        )


def _folder_name_or_text(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    path = Path(text)
    return path.name if path.exists() else text


def _folder_names_or_csv(value: str) -> tuple[str, ...]:
    names: list[str] = []
    for part in value.split(","):
        text = part.strip()
        if text:
            names.append(_folder_name_or_text(text))
    return tuple(names) or ("12", "13", "14")


def _optional_path(value: str) -> Path | None:
    value = value.strip()
    return Path(value) if value else None


def _config_path() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "eva-dxf-renderer" / CONFIG_FILE


def _open_path(path: Path) -> None:
    if path.suffix:
        path.parent.mkdir(parents=True, exist_ok=True)
    else:
        path.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


def main() -> int:
    freeze_support()
    app = QApplication(sys.argv)
    app.setApplicationName("DXF to IMG")
    app.setFont(QFont(FONT_FAMILY, 13))
    window = DXFToIMGWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
