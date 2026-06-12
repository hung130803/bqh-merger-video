"""Dọn dẹp file tạm sót lại từ các lần chạy trước (nếu app bị tắt đột ngột).

Gọi một lần khi mở app. An toàn: chỉ xoá đúng các file/thư mục tạm do chính
ứng dụng tạo ra, bỏ qua mọi lỗi.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
import time
from pathlib import Path


def cleanup_stale_temp() -> None:
    """Xoá thư mục tạm 'bvm_txt_*' cũ và file cập nhật .exe sót lại."""
    # 1. Thư mục tạm render chữ (bvm_txt_*) trong thư mục temp hệ thống
    try:
        tmp_root = Path(tempfile.gettempdir())
        now = time.time()
        for d in tmp_root.glob("bvm_txt_*"):
            try:
                # chỉ xoá thư mục cũ hơn 1 giờ để tránh đụng lần chạy hiện tại
                if d.is_dir() and (now - d.stat().st_mtime) > 3600:
                    shutil.rmtree(d, ignore_errors=True)
            except OSError:
                pass
    except OSError:
        pass

    # 2. File .exe cũ/mới sót lại cạnh ứng dụng sau khi tự cập nhật
    try:
        if getattr(sys, "frozen", False):
            exe = Path(sys.executable)
            for leftover in (
                exe.with_name(exe.stem + "_old.exe"),
                exe.with_name(exe.stem + "_new.exe"),
                exe.with_name("_bqh_update.bat"),
            ):
                try:
                    if leftover.is_file():
                        leftover.unlink()
                except OSError:
                    pass
    except OSError:
        pass
