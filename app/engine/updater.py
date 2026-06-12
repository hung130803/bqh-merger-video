"""Tự cập nhật ứng dụng qua GitHub Releases.

Hai chế độ:
  - Bản .exe (đóng gói PyInstaller): tải file .exe mới từ Release mới nhất,
    thay thế file đang chạy và khởi động lại. Người dùng KHÔNG cần git.
  - Bản chạy từ mã nguồn (python main.py): hướng dẫn dùng git pull
    (vẫn hỗ trợ, nhưng ưu tiên luồng .exe ở trên).

Dùng GitHub API công khai (không cần token cho repo public).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

try:
    from version import (
        APP_VERSION, GITHUB_OWNER, GITHUB_REPO, EXE_ASSET_NAME,
    )
except Exception:  # pragma: no cover
    APP_VERSION = "0.0.0"
    GITHUB_OWNER = ""
    GITHUB_REPO = ""
    EXE_ASSET_NAME = "BQH_Merger_Video.exe"

API_LATEST = "https://api.github.com/repos/{owner}/{repo}/releases/latest"


@dataclass
class UpdateInfo:
    ok: bool
    message: str
    has_update: bool = False
    latest_version: str = ""
    download_url: str = ""


def is_frozen() -> bool:
    """True nếu đang chạy dưới dạng .exe đóng gói (PyInstaller)."""
    return getattr(sys, "frozen", False)


def _norm_version(v: str) -> tuple:
    """Chuyển '1.2.3' / 'v1.2.3' -> (1, 2, 3) để so sánh."""
    v = (v or "").strip().lstrip("vV")
    parts = []
    for chunk in v.split("."):
        num = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(num) if num else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def _fetch_latest_release(timeout: float = 15) -> dict | None:
    if not GITHUB_OWNER or not GITHUB_REPO:
        return None
    url = API_LATEST.format(owner=GITHUB_OWNER, repo=GITHUB_REPO)
    req = urllib.request.Request(
        url, headers={"Accept": "application/vnd.github+json",
                      "User-Agent": "BQH-Merger-Video"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def check_for_update() -> UpdateInfo:
    """Kiểm tra Release mới nhất trên GitHub, so với phiên bản hiện tại."""
    data = _fetch_latest_release()
    if data is None:
        return UpdateInfo(
            False,
            "Không kết nối được GitHub hoặc chưa có bản phát hành nào.",
        )
    tag = data.get("tag_name", "")
    latest = _norm_version(tag)
    current = _norm_version(APP_VERSION)

    # Tìm file .exe trong assets
    download_url = ""
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name == EXE_ASSET_NAME or name.lower().endswith(".exe"):
            download_url = asset.get("browser_download_url", "")
            if name == EXE_ASSET_NAME:
                break

    if latest <= current:
        return UpdateInfo(
            True, f"Bạn đang dùng bản mới nhất (v{APP_VERSION}).",
            has_update=False, latest_version=tag,
        )
    return UpdateInfo(
        True,
        f"Có bản mới: {tag} (bạn đang dùng v{APP_VERSION}).",
        has_update=True, latest_version=tag, download_url=download_url,
    )


def download_and_apply(download_url: str, progress_cb=None) -> UpdateInfo:
    """Tải .exe mới về và thay thế file đang chạy, rồi khởi động lại.

    Chỉ áp dụng khi đang chạy dạng .exe (is_frozen). Trả UpdateInfo.
    """
    if not is_frozen():
        return UpdateInfo(
            False,
            "Đang chạy từ mã nguồn. Hãy dùng 'git pull' để cập nhật, "
            "hoặc tải bản .exe mới từ trang Releases trên GitHub.",
        )
    if not download_url:
        return UpdateInfo(
            False, "Bản phát hành không kèm file .exe để tải."
        )

    cur_exe = Path(sys.executable)
    new_exe = cur_exe.with_name(cur_exe.stem + "_new.exe")

    # Tải file .exe mới
    try:
        req = urllib.request.Request(
            download_url, headers={"User-Agent": "BQH-Merger-Video"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(new_exe, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total:
                        try:
                            progress_cb(downloaded / total)
                        except Exception:
                            pass
    except Exception as exc:
        try:
            if new_exe.exists():
                new_exe.unlink()
        except OSError:
            pass
        return UpdateInfo(False, f"Tải bản mới thất bại: {exc}")

    if not new_exe.exists() or new_exe.stat().st_size == 0:
        return UpdateInfo(False, "File tải về không hợp lệ.")

    # Tạo script .bat để thay thế file exe sau khi app thoát, rồi mở lại.
    bat = cur_exe.with_name("_bqh_update.bat")
    old_exe = cur_exe.with_name(cur_exe.stem + "_old.exe")
    script = f"""@echo off
chcp 65001 >nul
echo Dang cap nhat BQH Merger Video...
ping 127.0.0.1 -n 3 >nul
if exist "{old_exe.name}" del /f /q "{old_exe.name}"
move /y "{cur_exe.name}" "{old_exe.name}" >nul
move /y "{new_exe.name}" "{cur_exe.name}" >nul
start "" "{cur_exe.name}"
del /f /q "{old_exe.name}" >nul 2>&1
del /f /q "%~f0" >nul 2>&1
"""
    try:
        bat.write_text(script, encoding="utf-8")
    except OSError as exc:
        return UpdateInfo(False, f"Không tạo được script cập nhật: {exc}")

    # Chạy bat (ẩn cửa sổ) rồi để app tự thoát.
    try:
        subprocess.Popen(
            ["cmd", "/c", str(bat)],
            cwd=str(cur_exe.parent),
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError as exc:
        return UpdateInfo(False, f"Không chạy được script cập nhật: {exc}")

    return UpdateInfo(
        True,
        "Đã tải bản mới. Ứng dụng sẽ tự đóng và mở lại bản mới sau giây lát.",
        has_update=True,
    )


def exit_app() -> None:
    """Thoát ứng dụng ngay (để script .bat thay thế file exe)."""
    os._exit(0)
