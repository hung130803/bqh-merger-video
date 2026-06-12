"""Fixtures dùng chung cho test, gồm sinh video mẫu nhỏ bằng ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")

ffmpeg_required = pytest.mark.skipif(
    FFMPEG is None or FFPROBE is None,
    reason="Cần ffmpeg/ffprobe trên PATH cho integration test",
)


def make_sample_video(
    path: Path, seconds: int = 3, width: int = 320, height: int = 240
) -> Path:
    """Sinh một video mẫu testsrc + sine bằng ffmpeg."""
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"testsrc=size={width}x{height}:rate=25:duration={seconds}",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        str(path),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return path


@pytest.fixture
def sample_factory(tmp_path):
    """Trả về hàm tạo video mẫu trong tmp_path."""
    def _factory(name: str, seconds: int = 3, width: int = 320, height: int = 240):
        return make_sample_video(tmp_path / name, seconds, width, height)
    return _factory
