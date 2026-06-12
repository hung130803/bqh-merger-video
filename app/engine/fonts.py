"""Danh mục kiểu chữ phổ biến và ánh xạ tới file font trên Windows.

ffmpeg drawtext cần đường dẫn fontfile cụ thể. Module này dò các font có
sẵn trong thư mục Windows\\Fonts và trả về danh sách kiểu chữ dùng được,
kèm hàm phân giải tên -> đường dẫn file.
"""

from __future__ import annotations

import os
from pathlib import Path

# Tên hiển thị -> (tên file thường, tên file bold)
# Đây là các font phổ biến hay dùng cho video/caption.
FONT_FILES: dict[str, tuple[str, str]] = {
    "Arial": ("arial.ttf", "arialbd.ttf"),
    "Arial Black": ("ariblk.ttf", "ariblk.ttf"),
    "Tahoma": ("tahoma.ttf", "tahomabd.ttf"),
    "Verdana": ("verdana.ttf", "verdanab.ttf"),
    "Segoe UI": ("segoeui.ttf", "segoeuib.ttf"),
    "Times New Roman": ("times.ttf", "timesbd.ttf"),
    "Georgia": ("georgia.ttf", "georgiab.ttf"),
    "Calibri": ("calibri.ttf", "calibrib.ttf"),
    "Comic Sans MS": ("comic.ttf", "comicbd.ttf"),
    "Impact": ("impact.ttf", "impact.ttf"),
    "Courier New": ("cour.ttf", "courbd.ttf"),
    "Trebuchet MS": ("trebuc.ttf", "trebucbd.ttf"),
}


def _fonts_dir() -> Path:
    win = os.environ.get("WINDIR", r"C:\Windows")
    return Path(win) / "Fonts"


def available_fonts() -> list[str]:
    """Trả về danh sách tên kiểu chữ có file thực sự tồn tại trên máy."""
    fdir = _fonts_dir()
    found = []
    for name, (regular, _bold) in FONT_FILES.items():
        if (fdir / regular).is_file():
            found.append(name)
    return found or ["Arial"]


def resolve_font_file(name: str, bold: bool = True) -> str | None:
    """Trả về đường dẫn file font cho tên kiểu chữ (ưu tiên bold nếu chọn).

    Trả None nếu không tìm thấy file phù hợp.
    """
    fdir = _fonts_dir()
    entry = FONT_FILES.get(name)
    if entry is None:
        return None
    regular, bold_file = entry
    target = bold_file if bold else regular
    path = fdir / target
    if path.is_file():
        return str(path)
    # fallback: thử bản thường
    path2 = fdir / regular
    if path2.is_file():
        return str(path2)
    return None
