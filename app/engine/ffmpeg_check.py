"""Kiểm tra sự hiện diện của ffmpeg và ffprobe."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

# Hướng dẫn cài đặt hiển thị khi thiếu công cụ.
INSTALL_HINT = (
    "Chưa tìm thấy ffmpeg/ffprobe trên máy.\n"
    "Cách cài trên Windows:\n"
    "  1. Tải bản build từ https://www.gyan.dev/ffmpeg/builds/ "
    "(gói 'release full').\n"
    "  2. Giải nén, ví dụ vào C:\\ffmpeg.\n"
    "  3. Thêm C:\\ffmpeg\\bin vào biến môi trường PATH.\n"
    "  4. Mở lại cửa sổ dòng lệnh và chạy 'ffmpeg -version' để kiểm tra."
)


@dataclass
class ToolCheckResult:
    """Kết quả kiểm tra công cụ."""

    ffmpeg_ok: bool
    ffprobe_ok: bool
    message: str = ""

    @property
    def all_ok(self) -> bool:
        return self.ffmpeg_ok and self.ffprobe_ok


def _probe_tool(path: str, timeout: float) -> bool:
    """Chạy `<tool> -version`; trả True nếu chạy được và exit code == 0."""
    try:
        result = subprocess.run(
            [path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            creationflags=_no_window_flag(),
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _no_window_flag() -> int:
    """Cờ ẩn cửa sổ console khi chạy subprocess trên Windows."""
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _default_ffmpeg() -> str:
    try:
        from .ffmpeg_paths import ffmpeg_path
        return ffmpeg_path()
    except Exception:
        return "ffmpeg"


def _default_ffprobe() -> str:
    try:
        from .ffmpeg_paths import ffprobe_path
        return ffprobe_path()
    except Exception:
        return "ffprobe"


def check_tools(
    ffmpeg_path: str | None = None,
    ffprobe_path: str | None = None,
    timeout: float = 10.0,
) -> ToolCheckResult:
    """Kiểm tra ffmpeg và ffprobe có khả dụng không.

    Hoàn tất trong giới hạn `timeout` giây cho mỗi công cụ. Khi thiếu một
    trong hai, message nêu rõ công cụ còn thiếu kèm hướng dẫn cài đặt.
    """
    ffmpeg_path = ffmpeg_path or _default_ffmpeg()
    ffprobe_path = ffprobe_path or _default_ffprobe()
    ffmpeg_ok = _probe_tool(ffmpeg_path, timeout)
    ffprobe_ok = _probe_tool(ffprobe_path, timeout)

    message = ""
    if not (ffmpeg_ok and ffprobe_ok):
        missing = []
        if not ffmpeg_ok:
            missing.append("ffmpeg")
        if not ffprobe_ok:
            missing.append("ffprobe")
        message = f"Thiếu công cụ: {', '.join(missing)}.\n\n{INSTALL_HINT}"

    return ToolCheckResult(
        ffmpeg_ok=ffmpeg_ok, ffprobe_ok=ffprobe_ok, message=message
    )


def has_nvenc(ffmpeg_path: str | None = None, timeout: float = 10.0) -> bool:
    """Trả True nếu ffmpeg hỗ trợ encoder h264_nvenc (GPU NVIDIA).

    Chỉ kiểm tra sự hiện diện của encoder trong danh sách; không đảm bảo
    encode thành công nếu driver/GPU có vấn đề. Engine vẫn tự fallback về
    CPU khi NVENC chạy lỗi.
    """
    ffmpeg_path = ffmpeg_path or _default_ffmpeg()
    try:
        result = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            creationflags=_no_window_flag(),
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    output = result.stdout.decode("utf-8", "replace")
    return "h264_nvenc" in output
