"""Property test cho an toàn di chuyển video gốc (Property 9).

Dùng FfmpegRunner giả lập để điều khiển kết quả output mà không cần ffmpeg.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.engine.merge_engine import MergeEngine
from app.engine.models import (
    MergeConfig,
    MergeOrder,
    MergeStatus,
    QualityPreset,
    ResizeMode,
    ResizeSubmode,
)


class FakeRunner:
    """Runner giả: điều khiển việc tạo output thành công/thất bại."""

    def __init__(self, produce_output: bool, output_size: int = 10):
        self.produce_output = produce_output
        self.output_size = output_size

    def probe_duration(self, path: Path) -> float:
        return 10.0

    def probe_resolution(self, path: Path) -> tuple[int, int]:
        return (640, 480)

    def probe_has_audio(self, path: Path) -> bool:
        return True

    def run_concat(self, f1, f2, output, *args, **kwargs) -> None:
        if self.produce_output:
            Path(output).write_bytes(b"x" * self.output_size)
        # nếu không produce_output: không tạo file -> verify sẽ fail


def _make_config(tmp: Path) -> MergeConfig:
    f1 = tmp / "f1"
    f2 = tmp / "f2"
    out = tmp / "out"
    f1.mkdir()
    f2.mkdir()
    out.mkdir()
    return MergeConfig(
        folder1=f1,
        folder2=f2,
        output_folder=out,
        trim_head_1=1,
        trim_tail_1=1,
        trim_head_2=1,
        trim_tail_2=1,
        merge_order=MergeOrder.SORTED,
        resize_mode=ResizeMode.NINE_SIXTEEN,
        resize_submode=ResizeSubmode.FIT_PAD,
        quality=QualityPreset.BALANCED,
    )


# Feature: batch-video-merger, Property 9: Gốc chỉ được di chuyển khi output đã xác minh
@settings(max_examples=60, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(success=st.booleans())
def test_property_originals_moved_only_when_verified(success):
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        config = _make_config(tmp)

        src1 = config.folder1 / "a.mp4"
        src2 = config.folder2 / "b.mp4"
        src1.write_bytes(b"orig1")
        src2.write_bytes(b"orig2")

        engine = MergeEngine(
            config,
            queue.Queue(),
            threading.Event(),
            runner=FakeRunner(produce_output=success),
        )
        engine._ensure_dirs()
        result = engine.process_pair(1, src1, src2)

        if result.status is MergeStatus.DONE:
            # output phải tồn tại và > 0 byte
            assert result.output_path is not None
            assert result.output_path.exists()
            assert result.output_path.stat().st_size > 0
            # gốc đã được di chuyển khỏi thư mục nguồn
            assert not src1.exists()
            assert not src2.exists()
        else:
            # thất bại: cả hai gốc vẫn còn nguyên tại thư mục nguồn
            assert src1.exists()
            assert src2.exists()
