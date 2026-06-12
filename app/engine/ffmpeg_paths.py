"""Phân giải đường dẫn tới ffmpeg/ffprobe.

Thứ tự ưu tiên:
  1. ffmpeg/ffprobe được đóng gói kèm trong .exe (PyInstaller _MEIPASS).
  2. ffmpeg/ffprobe nằm cùng thư mục với file .exe.
  3. ffmpeg/ffprobe trên PATH hệ thống (gõ 'ffmpeg').

Nhờ vậy bản .exe có kèm ffmpeg sẽ chạy được ngay, không cần cài riêng.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _candidates(name: str) -> list[Path]:
    paths: list[Path] = []
    # 1. Thư mục _MEIPASS (file bundle khi chạy .exe onefile)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        paths.append(Path(meipass) / f"{name}.exe")
    # 2. Cùng thư mục với file thực thi
    if getattr(sys, "frozen", False):
        paths.append(Path(sys.executable).parent / f"{name}.exe")
    return paths


def resolve_tool(name: str) -> str:
    """Trả về đường dẫn ffmpeg/ffprobe nếu tìm thấy bản bundle/cạnh exe,
    ngược lại trả về tên lệnh ('ffmpeg'/'ffprobe') để dùng từ PATH."""
    for p in _candidates(name):
        if p.is_file():
            return str(p)
    return name


def ffmpeg_path() -> str:
    return resolve_tool("ffmpeg")


def ffprobe_path() -> str:
    return resolve_tool("ffprobe")
