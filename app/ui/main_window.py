"""Giao diện customtkinter chuyên nghiệp cho Batch Video Merger.

Bố cục 2 cột:
- Cột trái: phần cài đặt (cuộn được) — nguồn, cắt, tùy chọn, nhạc nền/GPU.
- Cột phải: khu vực chạy (luôn hiển thị) — nút Start/Stop, tiến trình, log.

Tầng GUI chỉ nhận input và hiển thị tiến trình. Toàn bộ xử lý nặng chạy trên
luồng nền (MergeEngine) và giao tiếp qua queue.Queue + threading.Event.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import time
from dataclasses import replace as _replace_cfg
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from app.engine.ffmpeg_check import check_tools, has_nvenc
from app.engine.merge_engine import MergeEngine, scan_folder
from app.engine.models import (
    MergeConfig,
    MergeOrder,
    MergeStatus,
    ProgressEvent,
    QualityPreset,
    ResizeMode,
    ResizeSubmode,
)
from app.engine.settings_store import load_settings, save_settings
from app.ui.template_designer import TemplateDesigner

try:
    from version import APP_NAME, APP_VERSION
except Exception:
    APP_NAME, APP_VERSION = "BQH Merger Video", "1.0.0"

POLL_INTERVAL_MS = 100
MIN_WIDTH = 1140
MIN_HEIGHT = 700

# Bảng màu
ACCENT = "#3B82F6"
ACCENT_HOVER = "#2563EB"
STOP_COLOR = "#374151"
STOP_HOVER = "#4B5563"
SUCCESS_COLOR = "#22C55E"
DANGER_COLOR = "#EF4444"
WARN_COLOR = "#F59E0B"
MUTED = "#9CA3AF"
CARD = ("#F3F4F6", "#1E2330")
PANEL = ("#FFFFFF", "#161A24")

NOT_SELECTED = "(chưa chọn)"

MERGE_ORDER_LABELS = {
    "Theo thứ tự tên file": MergeOrder.SORTED,
    "Ngẫu nhiên": MergeOrder.SHUFFLE,
}
RESIZE_MODE_LABELS = {
    "Giữ nguyên kích thước": ResizeMode.KEEP_SIZE,
    "9:16 (1080x1920)": ResizeMode.NINE_SIXTEEN,
}
SUBMODE_LABELS = {
    "Fit with padding (nền đen)": ResizeSubmode.FIT_PAD,
    "Fill crop (cắt cân giữa)": ResizeSubmode.FILL_CROP,
}
QUALITY_LABELS = {
    "Fast (CRF 28)": QualityPreset.FAST,
    "Balanced (CRF 23)": QualityPreset.BALANCED,
    "High Quality (CRF 18)": QualityPreset.HIGH,
}
WM_POS_LABELS = {
    "Trên trái": "top-left",
    "Trên phải": "top-right",
    "Dưới trái": "bottom-left",
    "Dưới phải": "bottom-right",
    "Giữa": "center",
}
CAPTION_POS_LABELS = {
    "Trên": "top",
    "Giữa": "center",
    "Dưới": "bottom",
}
CAPTION_SRC_LABELS = {
    "Chữ cố định (chung)": "fixed",
    "Theo tên video Folder 2": "f2_filename",
    "Từ file .txt cùng tên (Folder 2)": "f2_textfile",
}
CAPTION_SRC_HINTS = {
    "fixed": "Một dòng chữ chung cho tất cả video. Nhập vào ô bên dưới.",
    "f2_filename": "Mỗi video lấy chính TÊN FILE Folder 2 làm chữ. "
                   "Đổi tên video là đổi chữ. Luôn đúng sản phẩm.",
    "f2_textfile": "Mỗi video Folder 2 đọc file .txt CÙNG TÊN cạnh nó "
                   "(vd: ao.mp4 → ao.txt). Không có file txt thì video đó "
                   "không có chữ. Luôn đúng sản phẩm kể cả khi ghép ngẫu nhiên.",
}
CAPTION_SIZES = ["24", "28", "32", "36", "40", "48", "56", "64", "72", "84",
                 "96", "120"]
RES_LABELS = {
    "1080x1920 (9:16)": (1080, 1920),
    "720x1280 (9:16)": (720, 1280),
    "1080x1080 (1:1)": (1080, 1080),
    "1920x1080 (16:9)": (1920, 1080),
    "1280x720 (16:9)": (1280, 720),
}


class MainWindow(ctk.CTk):
    """Cửa sổ chính."""

    def __init__(self) -> None:
        super().__init__()

        self.title(APP_NAME)
        self.geometry(f"{MIN_WIDTH}x{MIN_HEIGHT}")
        self.minsize(MIN_WIDTH, MIN_HEIGHT)

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Trạng thái lựa chọn
        self.folder1: Path | None = None
        self.folder2: Path | None = None
        self.output_folder: Path | None = None
        self.music_file: Path | None = None
        self.watermark_file: Path | None = None
        self.template = None  # Template hoặc None

        # Trạng thái luồng
        self.event_queue: "queue.Queue[ProgressEvent]" = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self._total_pairs = 0
        self._last_output: Path | None = None
        self._start_time: float | None = None

        self._settings = load_settings()

        self._build_root_layout()
        self._build_header()
        self._build_left_panel()
        self._build_right_panel()

        self._on_resize_mode_change(self.resize_mode_var.get())
        self._apply_saved_settings()
        self._on_caption_source_change()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<F5>", self._on_refresh)

    # =====================================================================
    # LAYOUT KHUNG
    # =====================================================================
    def _build_root_layout(self) -> None:
        self.grid_columnconfigure(0, weight=3, uniform="cols")  # trái
        self.grid_columnconfigure(1, weight=2, uniform="cols")  # phải
        self.grid_rowconfigure(1, weight=1)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew",
                    padx=20, pady=(16, 6))
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header, text=APP_NAME,
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            header,
            text="Ghép video hàng loạt theo cặp — Folder 1 trước, Folder 2 sau",
            font=ctk.CTkFont(size=12), text_color=MUTED,
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Cụm bên phải: nút cập nhật + phiên bản + chế độ sáng
        right_box = ctk.CTkFrame(header, fg_color="transparent")
        right_box.grid(row=0, column=1, rowspan=2, sticky="e")

        self.update_btn = ctk.CTkButton(
            right_box, text="⭳ Cập nhật bản mới", width=150,
            fg_color=STOP_COLOR, hover_color=STOP_HOVER,
            command=self._on_check_update,
        )
        self.update_btn.grid(row=0, column=0, padx=(0, 10))

        self.theme_switch = ctk.CTkSwitch(
            right_box, text="Chế độ sáng", command=self._on_toggle_theme
        )
        self.theme_switch.grid(row=0, column=1)

        ctk.CTkLabel(
            right_box, text=f"v{APP_VERSION}",
            font=ctk.CTkFont(size=11), text_color=MUTED,
        ).grid(row=1, column=0, columnspan=2, sticky="e", pady=(2, 0))

    # =====================================================================
    # CỘT TRÁI — CÀI ĐẶT (DẠNG TAB)
    # =====================================================================
    def _build_left_panel(self) -> None:
        self.tabs = ctk.CTkTabview(
            self, corner_radius=12,
            segmented_button_selected_color=ACCENT,
            segmented_button_selected_hover_color=ACCENT_HOVER,
        )
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=(20, 10),
                       pady=(0, 16))

        self.tab_basic = self.tabs.add("  Cơ bản  ")
        self.tab_audio = self.tabs.add("  Âm thanh & Tốc độ  ")
        self.tab_adv = self.tabs.add("  Nâng cao  ")
        for t in (self.tab_basic, self.tab_audio, self.tab_adv):
            t.grid_columnconfigure(0, weight=1)

        # Tab Cơ bản: nguồn, cắt, tùy chọn xử lý
        self._current_tab = self.tab_basic
        self._build_sources_section()
        self._build_trim_section()
        self._build_output_options_section()

        # Tab Âm thanh & Tốc độ: nhạc nền, âm lượng, tốc độ, GPU
        self._current_tab = self.tab_audio
        self._build_advanced_section()

        # Tab Nâng cao: watermark, hiệu ứng, năng suất
        self._current_tab = self.tab_adv
        self._build_extra_section()

    def _card(self, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self._current_tab, corner_radius=12, fg_color=CARD)
        frame.grid(sticky="ew", pady=(0, 12), padx=2)
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            frame, text=title, font=ctk.CTkFont(size=15, weight="bold"),
            text_color=ACCENT,
        ).grid(row=0, column=0, columnspan=4, sticky="w", padx=16, pady=(12, 6))
        return frame

    # -------------------------------------------------------------- sources
    def _build_sources_section(self) -> None:
        frame = self._card("1. Nguồn & Đầu ra")

        self.folder1_label, self.folder1_count = self._folder_row(
            frame, 1, "Folder 1 (đầu):", self._on_select_folder1, True
        )
        self.folder2_label, self.folder2_count = self._folder_row(
            frame, 2, "Folder 2 (sau):", self._on_select_folder2, True
        )
        self.output_label, _ = self._folder_row(
            frame, 3, "Folder xuất:", self._on_select_output, False
        )

        self.preview_label = ctk.CTkLabel(
            frame, text="Chọn đủ 2 folder để xem số cặp sẽ ghép.",
            anchor="w", text_color=MUTED, font=ctk.CTkFont(size=12),
        )
        self.preview_label.grid(row=4, column=0, columnspan=3, sticky="w",
                                padx=16, pady=(2, 12))
        ctk.CTkButton(
            frame, text="🔄 Làm mới (F5)", width=110,
            fg_color=STOP_COLOR, hover_color=STOP_HOVER,
            command=self._on_refresh,
        ).grid(row=4, column=3, sticky="e", padx=(8, 16), pady=(2, 12))

    def _folder_row(self, frame, row, label_text, command, show_count):
        ctk.CTkLabel(frame, text=label_text, width=120, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(16, 8), pady=6
        )
        path_label = ctk.CTkLabel(
            frame, text=NOT_SELECTED, anchor="w", text_color=MUTED
        )
        path_label.grid(row=row, column=1, sticky="ew", padx=8, pady=6)

        count_label = None
        if show_count:
            count_label = ctk.CTkLabel(
                frame, text="", width=70, anchor="e", text_color=ACCENT,
                font=ctk.CTkFont(size=12, weight="bold"),
            )
            count_label.grid(row=row, column=2, sticky="e", padx=4, pady=6)
            btn_col = 3
        else:
            btn_col = 3

        ctk.CTkButton(frame, text="Chọn...", width=84, command=command).grid(
            row=row, column=btn_col, sticky="e", padx=(8, 16), pady=6
        )
        return path_label, count_label

    # ----------------------------------------------------------------- trim
    def _build_trim_section(self) -> None:
        frame = self._card("2. Cắt đầu / cuối (giây)")
        ctk.CTkLabel(frame, text="Cắt đầu", text_color=MUTED).grid(
            row=0, column=2, padx=8, pady=(12, 0)
        )
        ctk.CTkLabel(frame, text="Cắt cuối", text_color=MUTED).grid(
            row=0, column=3, padx=(8, 16), pady=(12, 0)
        )
        self.trim_head_1 = self._trim_row(frame, 1, "Folder 1:")
        self.trim_tail_1 = self._trim_cell(frame, 1, 3)
        self.trim_head_2 = self._trim_row(frame, 2, "Folder 2:")
        self.trim_tail_2 = self._trim_cell(frame, 2, 3)
        ctk.CTkLabel(frame, text="").grid(row=3, column=0, pady=(0, 6))

    def _trim_row(self, frame, row, label_text):
        ctk.CTkLabel(frame, text=label_text, width=120, anchor="w").grid(
            row=row, column=0, sticky="w", padx=(16, 8), pady=6
        )
        return self._trim_cell(frame, row, 2)

    def _trim_cell(self, frame, row, col, default="1"):
        entry = ctk.CTkEntry(frame, width=84, justify="center")
        entry.insert(0, default)
        padx = (8, 16) if col == 3 else 8
        entry.grid(row=row, column=col, padx=padx, pady=6, sticky="e")
        return entry

    # -------------------------------------------------------- output options
    def _build_output_options_section(self) -> None:
        frame = self._card("3. Tùy chọn xử lý")

        ctk.CTkLabel(frame, text="Thứ tự ghép:", width=120, anchor="w").grid(
            row=1, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.merge_order_var = ctk.StringVar(value="Theo thứ tự tên file")
        ctk.CTkOptionMenu(
            frame, values=list(MERGE_ORDER_LABELS.keys()),
            variable=self.merge_order_var,
        ).grid(row=1, column=1, columnspan=3, sticky="ew", padx=(8, 16), pady=6)

        ctk.CTkLabel(frame, text="Chất lượng:", width=120, anchor="w").grid(
            row=2, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.quality_var = ctk.StringVar(value="Balanced (CRF 23)")
        ctk.CTkOptionMenu(
            frame, values=list(QUALITY_LABELS.keys()),
            variable=self.quality_var,
        ).grid(row=2, column=1, columnspan=3, sticky="ew", padx=(8, 16), pady=6)

        ctk.CTkLabel(frame, text="Kích thước:", width=120, anchor="w").grid(
            row=3, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.resize_mode_var = ctk.StringVar(value="Giữ nguyên kích thước")
        ctk.CTkOptionMenu(
            frame, values=list(RESIZE_MODE_LABELS.keys()),
            variable=self.resize_mode_var, command=self._on_resize_mode_change,
        ).grid(row=3, column=1, columnspan=3, sticky="ew", padx=(8, 16), pady=6)

        ctk.CTkLabel(frame, text="Kiểu 9:16:", width=120, anchor="w").grid(
            row=4, column=0, sticky="w", padx=(16, 8), pady=(6, 14)
        )
        self.submode_var = ctk.StringVar(value="Fit with padding (nền đen)")
        self.submode_menu = ctk.CTkOptionMenu(
            frame, values=list(SUBMODE_LABELS.keys()), variable=self.submode_var,
        )
        self.submode_menu.grid(row=4, column=1, columnspan=3, sticky="ew",
                               padx=(8, 16), pady=(6, 14))

    # ------------------------------------------------------ advanced section
    def _build_advanced_section(self) -> None:
        frame = self._card("4. Nhạc nền & Tăng tốc")

        ctk.CTkLabel(frame, text="Nhạc nền:", width=120, anchor="w").grid(
            row=1, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.music_label = ctk.CTkLabel(
            frame, text="(không dùng)", anchor="w", text_color=MUTED
        )
        self.music_label.grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkButton(
            frame, text="Chọn nhạc", width=84, command=self._on_select_music
        ).grid(row=1, column=2, padx=4, pady=6)
        ctk.CTkButton(
            frame, text="Xoá", width=60, fg_color=STOP_COLOR,
            hover_color=STOP_HOVER, command=self._on_clear_music,
        ).grid(row=1, column=3, sticky="e", padx=(4, 16), pady=6)

        ctk.CTkLabel(frame, text="Âm lượng nhạc:", width=120, anchor="w").grid(
            row=2, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.volume_var = ctk.DoubleVar(value=1.0)
        self.volume_slider = ctk.CTkSlider(
            frame, from_=0.0, to=2.0, number_of_steps=20,
            variable=self.volume_var, command=self._on_volume_change,
        )
        self.volume_slider.grid(row=2, column=1, columnspan=2, sticky="ew",
                                padx=8, pady=6)
        self.volume_value_label = ctk.CTkLabel(
            frame, text="100%", width=56, text_color=ACCENT,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.volume_value_label.grid(row=2, column=3, padx=(4, 16), pady=6)

        self.mute_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame, text="Tắt tiếng gốc (chỉ nghe nhạc nền)",
            variable=self.mute_var,
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=16, pady=6)

        # ---- Tăng âm lượng video gốc ----
        ctk.CTkLabel(frame, text="Âm lượng video:", width=120, anchor="w").grid(
            row=4, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.boost_var = ctk.DoubleVar(value=1.0)
        ctk.CTkSlider(
            frame, from_=0.0, to=4.0, number_of_steps=40,
            variable=self.boost_var, command=self._on_boost_change,
        ).grid(row=4, column=1, columnspan=2, sticky="ew", padx=8, pady=6)
        self.boost_value_label = ctk.CTkLabel(
            frame, text="100%", width=56, text_color=ACCENT,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.boost_value_label.grid(row=4, column=3, padx=(4, 16), pady=6)

        # ---- Tốc độ phát ----
        ctk.CTkLabel(frame, text="Tốc độ video:", width=120, anchor="w").grid(
            row=5, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.speed_var = ctk.StringVar(value="1.0x (gốc)")
        speeds = [
            "0.5x (chậm)", "0.75x", "1.0x (gốc)",
            "1.25x", "1.5x", "1.75x", "2.0x (nhanh)", "2.5x", "3.0x",
        ]
        ctk.CTkOptionMenu(
            frame, values=speeds, variable=self.speed_var,
        ).grid(row=5, column=1, columnspan=3, sticky="ew",
               padx=(8, 16), pady=6)

        self.gpu_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame, text="Tăng tốc bằng GPU NVIDIA (NVENC)",
            variable=self.gpu_var,
        ).grid(row=6, column=0, columnspan=4, sticky="w",
               padx=16, pady=(6, 14))

    # -------------------------------------------------------- extra section
    def _build_extra_section(self) -> None:
        frame = self._card("5. Mẫu overlay, chữ & năng suất")

        # --- Trình thiết kế mẫu (chữ + sticker kéo-thả) ---
        ctk.CTkLabel(frame, text="Chọn mẫu:", width=120, anchor="w").grid(
            row=1, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.template_pick_var = ctk.StringVar(value="(không dùng mẫu)")
        self.template_menu = ctk.CTkOptionMenu(
            frame, values=self._template_choices(),
            variable=self.template_pick_var,
            command=self._on_pick_template,
        )
        self.template_menu.grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkButton(
            frame, text="🎨 Thiết kế / Thêm", width=130,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._open_template_designer,
        ).grid(row=1, column=2, padx=4, pady=6)
        ctk.CTkButton(
            frame, text="Xoá mẫu", width=70, fg_color=STOP_COLOR,
            hover_color=STOP_HOVER, command=self._on_delete_template,
        ).grid(row=1, column=3, sticky="e", padx=(4, 16), pady=6)

        self.template_label = ctk.CTkLabel(
            frame, text="Chưa chọn mẫu. Bấm 'Thiết kế / Thêm' để tạo mẫu mới.",
            anchor="w", text_color=MUTED, font=ctk.CTkFont(size=11),
        )
        self.template_label.grid(row=2, column=0, columnspan=4, sticky="w",
                                 padx=16, pady=(0, 6))

        # --- Chữ tự động theo từng video Folder 2 ---
        ctk.CTkLabel(frame, text="Chữ theo video:", width=120, anchor="w").grid(
            row=3, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.caption_source_var = ctk.StringVar(value="Chữ cố định (chung)")
        ctk.CTkOptionMenu(
            frame, values=list(CAPTION_SRC_LABELS.keys()),
            variable=self.caption_source_var,
            command=self._on_caption_source_change,
        ).grid(row=3, column=1, columnspan=3, sticky="ew", padx=(8, 16), pady=6)

        self.caption_entry = ctk.CTkEntry(
            frame, placeholder_text="Chữ chung (trống = không chèn)"
        )
        self.caption_entry.grid(row=4, column=1, columnspan=3, sticky="ew",
                                padx=(8, 16), pady=6)
        ctk.CTkLabel(frame, text="Nội dung:", width=120, anchor="w").grid(
            row=4, column=0, sticky="w", padx=(16, 8), pady=6
        )

        self.caption_hint = ctk.CTkLabel(
            frame, text="", anchor="w", text_color=MUTED,
            font=ctk.CTkFont(size=11), wraplength=420, justify="left",
        )
        self.caption_hint.grid(row=5, column=0, columnspan=4, sticky="w",
                               padx=16, pady=(0, 2))

        ctk.CTkLabel(frame, text="Vị trí chữ:", width=120, anchor="w").grid(
            row=6, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.caption_pos_var = ctk.StringVar(value="Dưới")
        ctk.CTkOptionMenu(
            frame, values=list(CAPTION_POS_LABELS.keys()),
            variable=self.caption_pos_var,
        ).grid(row=6, column=1, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(frame, text="Cỡ chữ:", anchor="e").grid(
            row=6, column=2, sticky="e", padx=8, pady=6
        )
        self.caption_size_var = ctk.StringVar(value="48")
        ctk.CTkOptionMenu(
            frame, values=CAPTION_SIZES,
            variable=self.caption_size_var, width=90,
        ).grid(row=6, column=3, sticky="e", padx=(8, 16), pady=(6, 12))

        # --- Hiệu ứng ---
        self.fade_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame, text="Fade in/out đầu & cuối video", variable=self.fade_var,
        ).grid(row=7, column=0, columnspan=2, sticky="w", padx=16, pady=6)

        self.strip_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            frame, text="Xoá metadata (chống trùng lặp)",
            variable=self.strip_var,
        ).grid(row=7, column=2, columnspan=2, sticky="w", padx=8, pady=6)

        # --- Độ phân giải & FPS ---
        ctk.CTkLabel(frame, text="Độ phân giải:", width=120, anchor="w").grid(
            row=8, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.res_var = ctk.StringVar(value="1080x1920 (9:16)")
        ctk.CTkOptionMenu(
            frame, values=list(RES_LABELS.keys()), variable=self.res_var,
        ).grid(row=8, column=1, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(frame, text="FPS:", anchor="e").grid(
            row=8, column=2, sticky="e", padx=8, pady=6
        )
        self.fps_var = ctk.StringVar(value="30")
        ctk.CTkOptionMenu(
            frame, values=["24", "30", "60"], variable=self.fps_var, width=90,
        ).grid(row=8, column=3, sticky="e", padx=(8, 16), pady=6)

        # --- Số luồng + seed ---
        ctk.CTkLabel(frame, text="Số luồng:", width=120, anchor="w").grid(
            row=9, column=0, sticky="w", padx=(16, 8), pady=6
        )
        self.workers_var = ctk.StringVar(value="1")
        ctk.CTkOptionMenu(
            frame, values=["1", "2", "3", "4"], variable=self.workers_var,
            width=90,
        ).grid(row=9, column=1, sticky="w", padx=8, pady=6)

        ctk.CTkLabel(frame, text="Seed (ngẫu nhiên):", anchor="e").grid(
            row=9, column=2, sticky="e", padx=8, pady=6
        )
        self.seed_entry = ctk.CTkEntry(frame, width=90, justify="center",
                                       placeholder_text="trống = tự do")
        self.seed_entry.grid(row=9, column=3, sticky="e", padx=(8, 16),
                             pady=(6, 14))

    # =====================================================================
    # CỘT PHẢI — KHU VỰC CHẠY (LUÔN HIỂN THỊ)
    # =====================================================================
    def _build_right_panel(self) -> None:
        panel = ctk.CTkFrame(self, corner_radius=12, fg_color=PANEL)
        panel.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=(0, 16))
        panel.grid_columnconfigure(0, weight=1)
        panel.grid_rowconfigure(5, weight=1)

        ctk.CTkLabel(
            panel, text="Bảng điều khiển",
            font=ctk.CTkFont(size=15, weight="bold"), text_color=ACCENT,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 8))

        # Nút Start/Stop
        btns = ctk.CTkFrame(panel, fg_color="transparent")
        btns.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        btns.grid_columnconfigure((0, 1), weight=1)

        self.start_btn = ctk.CTkButton(
            btns, text="▶  Bắt đầu ghép", height=46,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._on_start,
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.stop_btn = ctk.CTkButton(
            btns, text="■  Dừng", height=46,
            font=ctk.CTkFont(size=16), fg_color=STOP_COLOR,
            hover_color=STOP_HOVER, command=self._on_stop, state="disabled",
        )
        self.stop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

        self.open_btn = ctk.CTkButton(
            panel, text="📂  Mở thư mục kết quả", height=36,
            fg_color=STOP_COLOR, hover_color=STOP_HOVER,
            command=self._on_open_output, state="disabled",
        )
        self.open_btn.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 10))

        # Tiến trình
        prog = ctk.CTkFrame(panel, fg_color="transparent")
        prog.grid(row=3, column=0, sticky="ew", padx=16, pady=(0, 8))
        prog.grid_columnconfigure(0, weight=1)

        topline = ctk.CTkFrame(prog, fg_color="transparent")
        topline.grid(row=0, column=0, sticky="ew")
        topline.grid_columnconfigure(0, weight=1)
        self.percent_label = ctk.CTkLabel(
            topline, text="0%", font=ctk.CTkFont(size=18, weight="bold")
        )
        self.percent_label.grid(row=0, column=0, sticky="w")
        self.time_label = ctk.CTkLabel(
            topline, text="", font=ctk.CTkFont(size=12), text_color=MUTED
        )
        self.time_label.grid(row=0, column=1, sticky="e")

        self.progress = ctk.CTkProgressBar(prog, height=18)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.progress.set(0)

        # Panel tổng kết
        self.summary_frame = ctk.CTkFrame(panel, corner_radius=8, fg_color=CARD)
        self.summary_frame.grid(row=4, column=0, sticky="ew", padx=16, pady=8)
        self.summary_frame.grid_columnconfigure((0, 1, 2), weight=1)
        self.summary_done = self._summary_cell(0, "Thành công", SUCCESS_COLOR)
        self.summary_fail = self._summary_cell(1, "Lỗi", DANGER_COLOR)
        self.summary_unused = self._summary_cell(2, "Video thừa", MUTED)

        # Log
        loghead = ctk.CTkFrame(panel, fg_color="transparent")
        loghead.grid(row=5, column=0, sticky="new", padx=16, pady=(8, 2))
        loghead.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            loghead, text="Nhật ký xử lý",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        self.status_box = ctk.CTkTextbox(
            panel, font=ctk.CTkFont(size=12, family="Consolas"),
        )
        self.status_box.grid(row=6, column=0, sticky="nsew", padx=16,
                             pady=(0, 14))
        self.status_box.configure(state="disabled")
        panel.grid_rowconfigure(6, weight=3)
        panel.grid_rowconfigure(5, weight=0)

    def _summary_cell(self, col, label, color):
        cell = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        cell.grid(row=0, column=col, sticky="nsew", padx=6, pady=8)
        value = ctk.CTkLabel(
            cell, text="0", font=ctk.CTkFont(size=22, weight="bold"),
            text_color=color,
        )
        value.pack()
        ctk.CTkLabel(
            cell, text=label, font=ctk.CTkFont(size=11), text_color=MUTED
        ).pack()
        return value

    # =====================================================================
    # CALLBACK CHỌN FILE
    # =====================================================================
    def _on_select_folder1(self) -> None:
        path = filedialog.askdirectory(title="Chọn Folder 1")
        if path:
            self.folder1 = Path(path)
            self.folder1_label.configure(text=str(self.folder1.resolve()))
            self._refresh_counts()

    def _on_select_folder2(self) -> None:
        path = filedialog.askdirectory(title="Chọn Folder 2")
        if path:
            self.folder2 = Path(path)
            self.folder2_label.configure(text=str(self.folder2.resolve()))
            self._refresh_counts()

    def _on_select_output(self) -> None:
        path = filedialog.askdirectory(title="Chọn Folder xuất")
        if path:
            self.output_folder = Path(path)
            self.output_label.configure(text=str(self.output_folder.resolve()))

    def _on_select_music(self) -> None:
        path = filedialog.askopenfilename(
            title="Chọn file nhạc nền",
            filetypes=[
                ("Audio", "*.mp3 *.wav *.aac *.m4a *.ogg *.flac"),
                ("Tất cả", "*.*"),
            ],
        )
        if path:
            self.music_file = Path(path)
            self.music_label.configure(text=self.music_file.name,
                                       text_color=ACCENT)

    def _on_clear_music(self) -> None:
        self.music_file = None
        self.music_label.configure(text="(không dùng)", text_color=MUTED)

    def _template_choices(self) -> list[str]:
        from app.engine.template_store import list_templates
        names = list_templates()
        return ["(không dùng mẫu)"] + names

    def _refresh_template_menu(self, select: str | None = None) -> None:
        choices = self._template_choices()
        self.template_menu.configure(values=choices)
        if select is not None and select in choices:
            self.template_pick_var.set(select)

    def _open_template_designer(self) -> None:
        TemplateDesigner(self, template=self.template,
                         on_save=self._on_template_saved)

    def _on_template_saved(self, template) -> None:
        self.template = template if not template.is_empty() else None
        if self.template is not None:
            n_t = len(template.text_layers)
            n_s = len(template.sticker_layers)
            self.template_label.configure(
                text=f"Đang dùng: {template.name} "
                     f"({n_t} chữ, {n_s} sticker)",
                text_color=ACCENT,
            )
            # Mẫu vừa lưu vào thư viện -> làm mới danh sách và chọn nó
            self._refresh_template_menu(select=template.name)
        else:
            self.template_label.configure(
                text="Chưa chọn mẫu.", text_color=MUTED)
            self._refresh_template_menu(select="(không dùng mẫu)")

    def _on_pick_template(self, name: str) -> None:
        """Chọn một mẫu đã lưu từ dropdown."""
        if name == "(không dùng mẫu)":
            self.template = None
            self.template_label.configure(text="Chưa chọn mẫu.",
                                          text_color=MUTED)
            return
        from app.engine.template_store import load_template
        tpl = load_template(name)
        if tpl is None:
            self.template_label.configure(
                text=f"Không mở được mẫu '{name}'.", text_color=DANGER_COLOR)
            return
        self.template = tpl
        n_t = len(tpl.text_layers)
        n_s = len(tpl.sticker_layers)
        self.template_label.configure(
            text=f"Đang dùng: {tpl.name} ({n_t} chữ, {n_s} sticker)",
            text_color=ACCENT,
        )

    def _on_delete_template(self) -> None:
        name = self.template_pick_var.get()
        if name == "(không dùng mẫu)":
            return
        from app.engine.template_store import delete_template
        delete_template(name)
        self.template = None
        self._refresh_template_menu(select="(không dùng mẫu)")
        self.template_label.configure(
            text=f"Đã xoá mẫu '{name}'.", text_color=MUTED)

    def _on_caption_source_change(self, value=None) -> None:
        src = CAPTION_SRC_LABELS.get(self.caption_source_var.get(), "fixed")
        self.caption_hint.configure(text=CAPTION_SRC_HINTS.get(src, ""))
        # Ô nhập chữ chỉ dùng cho chế độ "cố định"
        if src == "fixed":
            self.caption_entry.configure(state="normal")
        else:
            self.caption_entry.configure(state="disabled")

    def _on_volume_change(self, value) -> None:
        self.volume_value_label.configure(text=f"{int(float(value) * 100)}%")

    def _on_boost_change(self, value) -> None:
        self.boost_value_label.configure(text=f"{int(float(value) * 100)}%")

    def _on_resize_mode_change(self, value: str) -> None:
        mode = RESIZE_MODE_LABELS.get(value, ResizeMode.KEEP_SIZE)
        state = "normal" if mode is ResizeMode.NINE_SIXTEEN else "disabled"
        self.submode_menu.configure(state=state)

    def _on_toggle_theme(self) -> None:
        ctk.set_appearance_mode("light" if self.theme_switch.get() else "dark")

    def _on_check_update(self) -> None:
        """Kiểm tra & tải bản mới từ GitHub (chạy trên luồng nền)."""
        from tkinter import messagebox
        from app.engine import updater

        self.update_btn.configure(state="disabled", text="Đang kiểm tra...")

        result_holder = {}

        def _work():
            chk = updater.check_for_update()
            if chk.ok and chk.changed:
                result_holder["res"] = updater.pull_update()
            else:
                result_holder["res"] = chk

        def _poll():
            if t.is_alive():
                self.after(200, _poll)
                return
            self.update_btn.configure(state="normal",
                                      text="⭳ Cập nhật bản mới")
            res = result_holder.get("res")
            if res is None:
                return
            if res.ok and res.changed:
                messagebox.showinfo("Cập nhật", res.message, parent=self)
            elif res.ok:
                messagebox.showinfo("Cập nhật", res.message, parent=self)
            else:
                messagebox.showerror("Cập nhật", res.message, parent=self)

        t = threading.Thread(target=_work, daemon=True)
        t.start()
        self.after(200, _poll)

    def _on_open_output(self) -> None:
        target = None
        if self._last_output is not None:
            merged = self._last_output / "merged"
            target = merged if merged.is_dir() else self._last_output
        elif self.output_folder is not None:
            target = self.output_folder
        if target is not None and Path(target).is_dir():
            _open_in_file_manager(Path(target))

    # =====================================================================
    # ĐẾM VIDEO & XEM TRƯỚC
    # =====================================================================
    def _on_refresh(self, event=None) -> None:
        """Quét lại folder và cập nhật số lượng (dùng khi tự xoá/thêm file)."""
        self._refresh_counts()

    def _count_videos(self, folder: Path | None) -> int:
        if folder is None or not folder.is_dir():
            return -1
        return len(scan_folder(folder))

    def _refresh_counts(self) -> None:
        n1 = self._count_videos(self.folder1)
        n2 = self._count_videos(self.folder2)
        self.folder1_count.configure(text=f"{n1} video" if n1 >= 0 else "")
        self.folder2_count.configure(text=f"{n2} video" if n2 >= 0 else "")

        if n1 < 0 or n2 < 0:
            self.preview_label.configure(
                text="Chọn đủ 2 folder để xem số cặp sẽ ghép.",
                text_color=MUTED,
            )
            return
        pairs = min(n1, n2)
        leftover = abs(n1 - n2)
        if pairs == 0:
            self.preview_label.configure(
                text="⚠  Không đủ video để tạo cặp nào.", text_color=DANGER_COLOR
            )
            return
        msg = f"➜  Sẽ ghép {pairs} cặp video."
        if leftover > 0:
            longer = "Folder 1" if n1 > n2 else "Folder 2"
            msg += f"  ({leftover} video thừa ở {longer} giữ nguyên)"
        self.preview_label.configure(text=msg, text_color=SUCCESS_COLOR)

    # =====================================================================
    # LOG
    # =====================================================================
    def _log(self, text: str) -> None:
        self.status_box.configure(state="normal")
        self.status_box.insert("end", text + "\n")
        self.status_box.see("end")
        self.status_box.configure(state="disabled")

    def _clear_log(self) -> None:
        self.status_box.configure(state="normal")
        self.status_box.delete("1.0", "end")
        self.status_box.configure(state="disabled")

    # =====================================================================
    # VALIDATION & BUILD CONFIG
    # =====================================================================
    def _parse_trim(self, entry, name, errors) -> float:
        raw = entry.get().strip().replace(",", ".")
        try:
            value = float(raw)
        except ValueError:
            errors.append(f"{name}: '{raw}' không phải số hợp lệ.")
            return 0.0
        if value < 0 or value > 3600:
            errors.append(f"{name}: phải trong khoảng 0 đến 3600 giây.")
        return value

    def _build_config(self) -> tuple[MergeConfig | None, list[str]]:
        errors: list[str] = []

        missing = []
        if self.folder1 is None:
            missing.append("Folder 1")
        if self.folder2 is None:
            missing.append("Folder 2")
        if self.output_folder is None:
            missing.append("Folder xuất")
        if missing:
            errors.append("Chưa chọn: " + ", ".join(missing) + ".")
            return None, errors

        f1 = self.folder1.resolve()
        f2 = self.folder2.resolve()
        out = self.output_folder.resolve()

        for label, p in (("Folder 1", f1), ("Folder 2", f2)):
            if not p.is_dir():
                errors.append(f"{label} không tồn tại hoặc không truy cập được.")
        if f1 == f2:
            errors.append("Folder 1 và Folder 2 không được trùng nhau.")
        if out == f1 or out == f2:
            errors.append("Folder xuất không được trùng Folder nguồn.")
        if _is_inside(out, f1) or _is_inside(out, f2):
            errors.append("Folder xuất không được nằm trong Folder nguồn.")

        th1 = self._parse_trim(self.trim_head_1, "Cắt đầu F1", errors)
        tt1 = self._parse_trim(self.trim_tail_1, "Cắt cuối F1", errors)
        th2 = self._parse_trim(self.trim_head_2, "Cắt đầu F2", errors)
        tt2 = self._parse_trim(self.trim_tail_2, "Cắt cuối F2", errors)

        if self.music_file is not None and not self.music_file.is_file():
            errors.append("File nhạc nền không tồn tại.")
        if self.mute_var.get() and self.music_file is None:
            errors.append(
                "Đã chọn 'Tắt tiếng gốc' nhưng chưa chọn nhạc nền — "
                "video sẽ không có âm thanh."
            )

        seed_raw = self.seed_entry.get().strip()
        seed_val: int | None = None
        if seed_raw:
            try:
                seed_val = int(seed_raw)
            except ValueError:
                errors.append("Seed phải là số nguyên hoặc để trống.")

        if errors:
            return None, errors

        res_w, res_h = RES_LABELS[self.res_var.get()]
        config = MergeConfig(
            folder1=f1, folder2=f2, output_folder=out,
            trim_head_1=th1, trim_tail_1=tt1, trim_head_2=th2, trim_tail_2=tt2,
            merge_order=MERGE_ORDER_LABELS[self.merge_order_var.get()],
            resize_mode=RESIZE_MODE_LABELS[self.resize_mode_var.get()],
            resize_submode=SUBMODE_LABELS[self.submode_var.get()],
            quality=QUALITY_LABELS[self.quality_var.get()],
            target_width=res_w,
            target_height=res_h,
            fps=int(self.fps_var.get()),
            background_music=self.music_file,
            music_volume=float(self.volume_var.get()),
            mute_original=bool(self.mute_var.get()),
            use_gpu=bool(self.gpu_var.get()),
            video_speed=_parse_speed(self.speed_var.get()),
            volume_boost=float(self.boost_var.get()),
            caption_text=self.caption_entry.get().strip(),
            caption_source=CAPTION_SRC_LABELS[self.caption_source_var.get()],
            caption_position=CAPTION_POS_LABELS[self.caption_pos_var.get()],
            caption_size=int(self.caption_size_var.get()),
            fade_in_out=bool(self.fade_var.get()),
            workers=int(self.workers_var.get()),
            seed=seed_val,
            strip_metadata=bool(self.strip_var.get()),
            template=self.template,
        )
        return config, []

    # =====================================================================
    # START / STOP
    # =====================================================================
    def _on_start(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            return

        self._clear_log()
        config, errors = self._build_config()
        if errors:
            for e in errors:
                self._log("⚠  " + e)
            return

        self._log("Đang kiểm tra ffmpeg/ffprobe...")
        self.update_idletasks()
        check = check_tools()
        if not check.all_ok:
            self._log("✖  " + check.message)
            return
        self._log("✔  ffmpeg và ffprobe sẵn sàng.")

        if self.gpu_var.get():
            if has_nvenc():
                self._log("✔  GPU NVENC khả dụng — tăng tốc bằng GPU.")
            else:
                self._log("⚠  Không có GPU NVENC, tự chuyển về CPU.")
                self.gpu_var.set(False)
                config = _replace_cfg(config, use_gpu=False)

        empty = []
        if not scan_folder(config.folder1):
            empty.append("Folder 1")
        if not scan_folder(config.folder2):
            empty.append("Folder 2")
        if empty:
            self._log("✖  Không có video hợp lệ trong: " + ", ".join(empty) + ".")
            return

        self.stop_event.clear()
        self.event_queue = queue.Queue()
        self.progress.set(0)
        self.percent_label.configure(text="0%")
        self._reset_summary()
        self._last_output = config.output_folder
        self._start_time = time.monotonic()
        self.time_label.configure(text="Đã chạy 00:00")

        save_settings(self._gather_settings())

        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.open_btn.configure(state="disabled")

        engine = MergeEngine(config, self.event_queue, self.stop_event)
        self.worker = threading.Thread(target=engine.run, daemon=True)
        self.worker.start()
        self.after(POLL_INTERVAL_MS, self._poll_queue)

    def _on_stop(self) -> None:
        if self.worker is not None and self.worker.is_alive():
            self.stop_event.set()
            self._log("… Đã yêu cầu dừng, đang hoàn tất cặp hiện tại...")
            self.stop_btn.configure(state="disabled")

    # =====================================================================
    # QUEUE POLL
    # =====================================================================
    def _poll_queue(self) -> None:
        try:
            while True:
                self._handle_event(self.event_queue.get_nowait())
        except queue.Empty:
            pass

        if self.worker is not None and self.worker.is_alive():
            self.after(POLL_INTERVAL_MS, self._poll_queue)
        else:
            try:
                while True:
                    self._handle_event(self.event_queue.get_nowait())
            except queue.Empty:
                pass

    def _handle_event(self, event: ProgressEvent) -> None:
        if event.kind == "init":
            self._total_pairs = event.total
            self._log(event.message)
            if event.total == 0:
                self._log("Không có cặp nào để ghép.")

        elif event.kind == "status":
            r = event.result
            if r is not None:
                name = r.file1.name if r.file1 else ""
                self._log(f"   • {r.status.value}: {name}")

        elif event.kind == "pair":
            r = event.result
            self._update_progress(event.processed, event.total)
            if r is not None:
                icon = _status_icon(r.status)
                f1 = r.file1.name if r.file1 else "?"
                f2 = r.file2.name if r.file2 else "?"
                line = f"[{r.stt}] {icon} {r.status.value}  |  {f1}  +  {f2}"
                if r.detail and r.status is not MergeStatus.DONE:
                    line += f"\n        ↳ {r.detail}"
                self._log(line)

        elif event.kind == "progress":
            # Tiến độ % theo từng video (chỉ khi chạy 1 luồng).
            try:
                pct = float(event.message)
            except (ValueError, TypeError):
                pct = 0.0
            done = max(0, event.processed - 1)
            total = event.total or 1
            overall = (done + pct) / total
            self.progress.set(max(0.0, min(1.0, overall)))
            self.percent_label.configure(text=f"{int(overall * 100)}%")
            self._update_time(done + pct, total)

        elif event.kind == "stopping":
            self._update_progress(event.processed, event.total)
            self._log(event.message)

        elif event.kind == "done":
            if event.summary is not None:
                self._apply_summary(event.summary)
            self.progress.set(1.0)
            self.percent_label.configure(text="100%")
            self._log("─" * 36)
            self._log(event.message)
            self.start_btn.configure(state="normal")
            self.stop_btn.configure(state="disabled")
            self.open_btn.configure(state="normal")
            if self._start_time is not None:
                elapsed = time.monotonic() - self._start_time
                self.time_label.configure(text=f"Tổng {_fmt_time(elapsed)}")
            self.bell()
            _notify_done(event.message)

    def _update_progress(self, processed: int, total: int) -> None:
        ratio = (processed / total) if total else 0.0
        self.progress.set(ratio)
        self.percent_label.configure(text=f"{int(ratio * 100)}%")
        self._update_time(processed, total)

    def _update_time(self, processed: int, total: int) -> None:
        if self._start_time is None:
            return
        elapsed = time.monotonic() - self._start_time
        text = f"Đã chạy {_fmt_time(elapsed)}"
        if 0 < processed < total:
            eta = (elapsed / processed) * (total - processed)
            text += f"  •  còn ~{_fmt_time(eta)}"
        self.time_label.configure(text=text)

    # =====================================================================
    # SUMMARY & SETTINGS
    # =====================================================================
    def _reset_summary(self) -> None:
        self.summary_done.configure(text="0")
        self.summary_fail.configure(text="0")
        self.summary_unused.configure(text="0")

    def _apply_summary(self, summary) -> None:
        self.summary_done.configure(text=str(summary.succeeded))
        self.summary_fail.configure(text=str(summary.failed))
        self.summary_unused.configure(text=str(summary.unused))

    def _apply_saved_settings(self) -> None:
        s = self._settings
        if not s:
            return
        for key, attr, label_attr in (
            ("folder1", "folder1", "folder1_label"),
            ("folder2", "folder2", "folder2_label"),
            ("output_folder", "output_folder", "output_label"),
        ):
            val = s.get(key)
            if val and Path(val).is_dir():
                p = Path(val)
                setattr(self, attr, p)
                getattr(self, label_attr).configure(text=str(p.resolve()))

        self._set_entry(self.trim_head_1, s.get("trim_head_1"))
        self._set_entry(self.trim_tail_1, s.get("trim_tail_1"))
        self._set_entry(self.trim_head_2, s.get("trim_head_2"))
        self._set_entry(self.trim_tail_2, s.get("trim_tail_2"))

        if s.get("merge_order") in MERGE_ORDER_LABELS:
            self.merge_order_var.set(s["merge_order"])
        if s.get("resize_mode") in RESIZE_MODE_LABELS:
            self.resize_mode_var.set(s["resize_mode"])
            self._on_resize_mode_change(s["resize_mode"])
        if s.get("submode") in SUBMODE_LABELS:
            self.submode_var.set(s["submode"])
        if s.get("quality") in QUALITY_LABELS:
            self.quality_var.set(s["quality"])
        if s.get("theme") == "light":
            self.theme_switch.select()
            ctk.set_appearance_mode("light")
        if s.get("music_volume") is not None:
            try:
                vol = float(s["music_volume"])
                self.volume_var.set(vol)
                self.volume_value_label.configure(text=f"{int(vol * 100)}%")
            except (ValueError, TypeError):
                pass
        if s.get("mute_original"):
            self.mute_var.set(True)
        if s.get("use_gpu"):
            self.gpu_var.set(True)
        if s.get("video_speed"):
            self.speed_var.set(s["video_speed"])
        if s.get("volume_boost") is not None:
            try:
                vb = float(s["volume_boost"])
                self.boost_var.set(vb)
                self.boost_value_label.configure(text=f"{int(vb * 100)}%")
            except (ValueError, TypeError):
                pass
        if s.get("fade"):
            self.fade_var.set(True)
        if s.get("strip"):
            self.strip_var.set(True)
        if s.get("res") in RES_LABELS:
            self.res_var.set(s["res"])
        if s.get("fps"):
            self.fps_var.set(s["fps"])
        if s.get("workers"):
            self.workers_var.set(s["workers"])
        if s.get("caption_pos") in CAPTION_POS_LABELS:
            self.caption_pos_var.set(s["caption_pos"])
        if s.get("caption_size"):
            self.caption_size_var.set(s["caption_size"])
        if s.get("caption_source") in CAPTION_SRC_LABELS:
            self.caption_source_var.set(s["caption_source"])

        self._refresh_counts()

    @staticmethod
    def _set_entry(entry, value) -> None:
        if value is None:
            return
        entry.delete(0, "end")
        entry.insert(0, str(value))

    def _gather_settings(self) -> dict:
        return {
            "folder1": str(self.folder1) if self.folder1 else None,
            "folder2": str(self.folder2) if self.folder2 else None,
            "output_folder": str(self.output_folder) if self.output_folder else None,
            "trim_head_1": self.trim_head_1.get(),
            "trim_tail_1": self.trim_tail_1.get(),
            "trim_head_2": self.trim_head_2.get(),
            "trim_tail_2": self.trim_tail_2.get(),
            "merge_order": self.merge_order_var.get(),
            "resize_mode": self.resize_mode_var.get(),
            "submode": self.submode_var.get(),
            "quality": self.quality_var.get(),
            "theme": "light" if self.theme_switch.get() else "dark",
            "music_volume": float(self.volume_var.get()),
            "mute_original": bool(self.mute_var.get()),
            "use_gpu": bool(self.gpu_var.get()),
            "video_speed": self.speed_var.get(),
            "volume_boost": float(self.boost_var.get()),
            "fade": bool(self.fade_var.get()),
            "strip": bool(self.strip_var.get()),
            "res": self.res_var.get(),
            "fps": self.fps_var.get(),
            "workers": self.workers_var.get(),
            "caption_pos": self.caption_pos_var.get(),
            "caption_size": self.caption_size_var.get(),
            "caption_source": self.caption_source_var.get(),
        }

    def _on_close(self) -> None:
        save_settings(self._gather_settings())
        self.destroy()


# ========================================================================
# HÀM TIỆN ÍCH MODULE
# ========================================================================
def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _parse_speed(label: str) -> float:
    """Tách giá trị tốc độ từ nhãn lựa chọn (ví dụ '1.5x' -> 1.5)."""
    try:
        return float(label.split("x")[0].strip())
    except (ValueError, AttributeError):
        return 1.0


def _fmt_time(seconds: float) -> str:
    seconds = int(max(0, seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _notify_done(message: str) -> None:
    """Phát tiếng báo hoàn tất trên Windows (nếu khả dụng)."""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.user32.MessageBeep(0)  # type: ignore[attr-defined]
    except Exception:
        pass


def _open_in_file_manager(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except OSError:
        pass


def _status_icon(status: MergeStatus) -> str:
    return {
        MergeStatus.DONE: "✔",
        MergeStatus.FAILED: "✖",
        MergeStatus.SKIPPED_TOO_SHORT: "⊘",
        MergeStatus.SKIPPED_UNREADABLE: "⊘",
        MergeStatus.UNUSED_NO_PAIR: "·",
    }.get(status, "•")
