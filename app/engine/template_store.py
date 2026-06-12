"""Thư viện mẫu (template) — lưu/nạp nhiều mẫu để tái sử dụng.

Mỗi mẫu lưu thành một file JSON trong thư mục thư viện ở home. Người dùng
đặt tên mẫu; tên file lấy theo tên mẫu (đã làm sạch ký tự không hợp lệ).
"""

from __future__ import annotations

import re
from pathlib import Path

from .template_model import Template

LIBRARY_DIR = Path.home() / ".batch_video_merger_templates"


def _safe_name(name: str) -> str:
    name = (name or "mau").strip() or "mau"
    # bỏ ký tự không hợp lệ cho tên file
    return re.sub(r'[<>:"/\\|?*]', "_", name)[:80]


def ensure_dir() -> Path:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    return LIBRARY_DIR


def list_templates() -> list[str]:
    """Trả về danh sách TÊN mẫu đã lưu (theo tên file, bỏ .json)."""
    if not LIBRARY_DIR.is_dir():
        return []
    names = []
    for p in sorted(LIBRARY_DIR.glob("*.json")):
        names.append(p.stem)
    return names


def save_template(template: Template) -> Path:
    """Lưu mẫu vào thư viện (ghi đè nếu trùng tên). Trả về đường dẫn file."""
    ensure_dir()
    fname = _safe_name(template.name) + ".json"
    path = LIBRARY_DIR / fname
    template.save(path)
    return path


def load_template(name: str) -> Template | None:
    """Nạp mẫu theo tên; trả None nếu không tồn tại/đọc lỗi."""
    path = LIBRARY_DIR / (_safe_name(name) + ".json")
    if not path.is_file():
        # thử khớp trực tiếp theo stem
        for p in LIBRARY_DIR.glob("*.json"):
            if p.stem == name:
                path = p
                break
        else:
            return None
    try:
        return Template.load(path)
    except (OSError, ValueError):
        return None


def delete_template(name: str) -> bool:
    """Xoá mẫu theo tên. Trả True nếu xoá được."""
    path = LIBRARY_DIR / (_safe_name(name) + ".json")
    if not path.is_file():
        for p in LIBRARY_DIR.glob("*.json"):
            if p.stem == name:
                path = p
                break
        else:
            return False
    try:
        path.unlink()
        return True
    except OSError:
        return False
