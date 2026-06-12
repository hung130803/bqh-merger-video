"""Lưu và nạp lại các lựa chọn gần nhất của người dùng.

Lưu dưới dạng JSON trong thư mục home để lần chạy sau tự điền lại.
Mọi lỗi đọc/ghi đều bỏ qua an toàn (không làm hỏng trải nghiệm).
"""

from __future__ import annotations

import json
from pathlib import Path

SETTINGS_PATH = Path.home() / ".batch_video_merger.json"


def load_settings() -> dict:
    """Đọc cài đặt đã lưu; trả về dict rỗng nếu không có/lỗi."""
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(data: dict) -> None:
    """Ghi cài đặt; bỏ qua mọi lỗi ghi."""
    try:
        with SETTINGS_PATH.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
