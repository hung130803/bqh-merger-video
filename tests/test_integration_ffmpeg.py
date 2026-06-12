"""Integration tests dùng ffmpeg thật với video mẫu nhỏ."""

from __future__ import annotations

import queue
import threading
from pathlib import Path

import pytest

from app.engine.ffmpeg_check import check_tools
from app.engine.ffmpeg_runner import FfmpegRunner
from app.engine.merge_engine import MergeEngine
from app.engine.models import (
    MergeConfig,
    MergeOrder,
    MergeStatus,
    QualityPreset,
    ResizeMode,
    ResizeSubmode,
)
from tests.conftest import ffmpeg_required


@ffmpeg_required
def test_check_tools_ok():
    result = check_tools()
    assert result.all_ok


def test_check_tools_missing():
    result = check_tools(ffmpeg_path="ffmpeg_nope_xyz", ffprobe_path="ffprobe_nope_xyz")
    assert not result.all_ok
    assert "ffmpeg" in result.message


@ffmpeg_required
def test_probe_duration_and_resolution(sample_factory):
    runner = FfmpegRunner()
    v = sample_factory("v.mp4", seconds=2, width=320, height=240)
    dur = runner.probe_duration(v)
    assert 1.5 < dur < 2.6
    assert runner.probe_resolution(v) == (320, 240)
    assert runner.probe_has_audio(v) is True


def _config(folder1: Path, folder2: Path, out: Path, mode, submode):
    return MergeConfig(
        folder1=folder1,
        folder2=folder2,
        output_folder=out,
        trim_head_1=0.5,
        trim_tail_1=0.5,
        trim_head_2=0.5,
        trim_tail_2=0.5,
        merge_order=MergeOrder.SORTED,
        resize_mode=mode,
        resize_submode=submode,
        quality=QualityPreset.FAST,
    )


@ffmpeg_required
@pytest.mark.parametrize(
    "mode,submode",
    [
        (ResizeMode.NINE_SIXTEEN, ResizeSubmode.FIT_PAD),
        (ResizeMode.NINE_SIXTEEN, ResizeSubmode.FILL_CROP),
        (ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD),
    ],
)
def test_run_concat_modes(tmp_path, mode, submode):
    runner = FfmpegRunner()
    from tests.conftest import make_sample_video

    f1 = make_sample_video(tmp_path / "a.mp4", seconds=2, width=320, height=240)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=2, width=640, height=360)
    out = tmp_path / "merged.mp4"

    f1_res = runner.probe_resolution(f1) if mode is ResizeMode.KEEP_SIZE else None
    runner.run_concat(
        f1, f2, out, 0.5, 1.0, 0.5, 1.0,
        _config(tmp_path, tmp_path, tmp_path, mode, submode), f1_res,
    )

    assert out.exists() and out.stat().st_size > 0
    # xác minh chuẩn hóa: 30fps, yuv420p, audio 44100
    assert _probe_field(runner, out, "stream=r_frame_rate", "v") == "30/1"
    assert _probe_field(runner, out, "stream=pix_fmt", "v") == "yuv420p"
    assert _probe_field(runner, out, "stream=sample_rate", "a") == "44100"


def _probe_field(runner, path, entries, stream):
    raw = runner._run_probe([
        runner.ffprobe_path,
        "-v", "error",
        "-select_streams", f"{stream}:0",
        "-show_entries", entries,
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return raw.strip()


@ffmpeg_required
def test_full_run_moves_originals(tmp_path):
    f1_dir = tmp_path / "f1"
    f2_dir = tmp_path / "f2"
    out_dir = tmp_path / "out"
    f1_dir.mkdir()
    f2_dir.mkdir()
    out_dir.mkdir()

    from tests.conftest import make_sample_video

    make_sample_video(f1_dir / "001.mp4", seconds=2)
    make_sample_video(f1_dir / "002.mp4", seconds=2)
    make_sample_video(f2_dir / "a.mp4", seconds=2)
    make_sample_video(f2_dir / "b.mp4", seconds=2)
    # video thừa ở f1
    make_sample_video(f1_dir / "003.mp4", seconds=2)

    config = _config(
        f1_dir, f2_dir, out_dir, ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD
    )
    engine = MergeEngine(config, queue.Queue(), threading.Event())
    summary = engine.run()

    assert summary.succeeded == 2
    assert summary.failed == 0
    assert summary.unused == 1

    # 2 file merged
    merged = list((out_dir / "merged").glob("*.mp4"))
    assert len(merged) == 2
    # gốc đã move
    assert len(list((out_dir / "used_folder_1").glob("*.mp4"))) == 2
    assert len(list((out_dir / "used_folder_2").glob("*.mp4"))) == 2
    # video thừa còn lại trong f1
    assert (f1_dir / "003.mp4").exists()


@ffmpeg_required
def test_background_music_mix(tmp_path):
    """Ghép với nhạc nền trộn cùng tiếng gốc."""
    from tests.conftest import make_sample_video
    import subprocess as sp

    runner = FfmpegRunner()
    f1 = make_sample_video(tmp_path / "a.mp4", seconds=2)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=2)
    music = tmp_path / "music.mp3"
    # tạo file nhạc 5 giây
    import shutil as _sh
    ff = _sh.which("ffmpeg")
    sp.run(
        [ff, "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=5",
         str(music)],
        check=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL,
    )

    out = tmp_path / "merged_music.mp4"
    cfg = _config(tmp_path, tmp_path, tmp_path, ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    from dataclasses import replace
    cfg = replace(cfg, background_music=music, music_volume=0.5)

    runner.run_concat(
        f1, f2, out, 0.5, 1.0, 0.5, 1.0, cfg,
        runner.probe_resolution(f1),
    )
    assert out.exists() and out.stat().st_size > 0
    assert _probe_field(runner, out, "stream=sample_rate", "a") == "44100"


@ffmpeg_required
def test_background_music_mute_original(tmp_path):
    """Ghép với nhạc nền và tắt tiếng gốc."""
    from tests.conftest import make_sample_video
    import subprocess as sp
    import shutil as _sh

    runner = FfmpegRunner()
    f1 = make_sample_video(tmp_path / "a.mp4", seconds=2)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=2)
    music = tmp_path / "music.mp3"
    ff = _sh.which("ffmpeg")
    sp.run(
        [ff, "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=5",
         str(music)],
        check=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL,
    )

    out = tmp_path / "merged_mute.mp4"
    cfg = _config(tmp_path, tmp_path, tmp_path, ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    from dataclasses import replace
    cfg = replace(cfg, background_music=music, music_volume=1.0, mute_original=True)

    runner.run_concat(
        f1, f2, out, 0.5, 1.0, 0.5, 1.0, cfg,
        runner.probe_resolution(f1),
    )
    assert out.exists() and out.stat().st_size > 0


@ffmpeg_required
def test_video_speed_and_volume_boost(tmp_path):
    """Ghép với tốc độ video x2 và tăng âm lượng x1.5."""
    from tests.conftest import make_sample_video
    from dataclasses import replace

    runner = FfmpegRunner()
    f1 = make_sample_video(tmp_path / "a.mp4", seconds=2)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=2)
    out = tmp_path / "merged_speed.mp4"

    cfg = _config(tmp_path, tmp_path, tmp_path,
                  ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    cfg = replace(cfg, video_speed=2.0, volume_boost=1.5)

    runner.run_concat(
        f1, f2, out, 0.5, 1.0, 0.5, 1.0, cfg,
        runner.probe_resolution(f1),
    )
    assert out.exists() and out.stat().st_size > 0
    # Tốc độ x2: tổng (1+1=2 giây) phải còn ~1 giây.
    dur = runner.probe_duration(out)
    assert 0.7 < dur < 1.4


@ffmpeg_required
def test_watermark_overlay(tmp_path):
    """Ghép kèm watermark (logo PNG nhỏ)."""
    from tests.conftest import make_sample_video
    from dataclasses import replace
    import subprocess as sp
    import shutil as _sh

    runner = FfmpegRunner()
    f1 = make_sample_video(tmp_path / "a.mp4", seconds=2)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=2)
    logo = tmp_path / "logo.png"
    ff = _sh.which("ffmpeg")
    sp.run(
        [ff, "-y", "-f", "lavfi", "-i", "color=c=red:s=80x80:d=1",
         "-frames:v", "1", str(logo)],
        check=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL,
    )

    out = tmp_path / "merged_wm.mp4"
    cfg = _config(tmp_path, tmp_path, tmp_path,
                  ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    cfg = replace(cfg, watermark=logo, watermark_position="bottom-right",
                  watermark_scale=0.2)
    runner.run_concat(
        f1, f2, out, 0.5, 1.0, 0.5, 1.0, cfg, runner.probe_resolution(f1)
    )
    assert out.exists() and out.stat().st_size > 0


@ffmpeg_required
def test_fade_and_strip_metadata(tmp_path):
    """Ghép với fade in/out và xoá metadata."""
    from tests.conftest import make_sample_video
    from dataclasses import replace

    runner = FfmpegRunner()
    f1 = make_sample_video(tmp_path / "a.mp4", seconds=3)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=3)
    out = tmp_path / "merged_fade.mp4"
    cfg = _config(tmp_path, tmp_path, tmp_path,
                  ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    cfg = replace(cfg, fade_in_out=True, fade_duration=0.5,
                  strip_metadata=True)
    runner.run_concat(
        f1, f2, out, 0.3, 2.0, 0.3, 2.0, cfg, runner.probe_resolution(f1)
    )
    assert out.exists() and out.stat().st_size > 0


@ffmpeg_required
def test_parallel_workers_full_run(tmp_path):
    """Chạy với 2 luồng song song, kiểm tra tất cả cặp được ghép."""
    f1_dir = tmp_path / "f1"
    f2_dir = tmp_path / "f2"
    out_dir = tmp_path / "out"
    f1_dir.mkdir()
    f2_dir.mkdir()
    out_dir.mkdir()
    from tests.conftest import make_sample_video
    from dataclasses import replace

    for i in range(3):
        make_sample_video(f1_dir / f"{i}.mp4", seconds=2)
        make_sample_video(f2_dir / f"x{i}.mp4", seconds=2)

    cfg = _config(f1_dir, f2_dir, out_dir,
                  ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    cfg = replace(cfg, workers=2)
    import queue
    import threading
    engine = MergeEngine(cfg, queue.Queue(), threading.Event())
    summary = engine.run()
    assert summary.succeeded == 3
    assert len(list((out_dir / "merged").glob("*.mp4"))) == 3


@ffmpeg_required
def test_caption_text(tmp_path):
    """Ghép kèm caption chữ cố định."""
    from tests.conftest import make_sample_video
    from dataclasses import replace

    runner = FfmpegRunner()
    f1 = make_sample_video(tmp_path / "a.mp4", seconds=2)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=2)
    out = tmp_path / "merged_caption.mp4"
    cfg = _config(tmp_path, tmp_path, tmp_path,
                  ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    cfg = replace(cfg, caption_text="@tenkenh #viral",
                  caption_position="bottom", caption_size=40)
    runner.run_concat(
        f1, f2, out, 0.5, 1.0, 0.5, 1.0, cfg, runner.probe_resolution(f1)
    )
    assert out.exists() and out.stat().st_size > 0


@ffmpeg_required
def test_progress_callback(tmp_path):
    """run_concat gọi progress_cb với giá trị tăng dần tới 1.0."""
    from tests.conftest import make_sample_video

    runner = FfmpegRunner()
    f1 = make_sample_video(tmp_path / "a.mp4", seconds=2)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=2)
    out = tmp_path / "merged_prog.mp4"
    cfg = _config(tmp_path, tmp_path, tmp_path,
                  ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)

    values = []
    runner.run_concat(
        f1, f2, out, 0.3, 1.2, 0.3, 1.2, cfg, runner.probe_resolution(f1),
        progress_cb=values.append,
    )
    assert out.exists() and out.stat().st_size > 0
    assert values  # có ít nhất một lần báo tiến độ
    assert values[-1] == 1.0
    assert all(0.0 <= v <= 1.0 for v in values)


@ffmpeg_required
def test_template_overlay(tmp_path):
    """Ghép kèm template gồm 1 lớp chữ + 1 sticker."""
    from tests.conftest import make_sample_video
    from dataclasses import replace
    from app.engine.template_model import Template, TextLayer, StickerLayer
    import subprocess as sp
    import shutil as _sh

    runner = FfmpegRunner()
    f1 = make_sample_video(tmp_path / "a.mp4", seconds=2)
    f2 = make_sample_video(tmp_path / "b.mp4", seconds=2)
    logo = tmp_path / "logo.png"
    ff = _sh.which("ffmpeg")
    sp.run(
        [ff, "-y", "-f", "lavfi", "-i", "color=c=blue:s=60x60:d=1",
         "-frames:v", "1", str(logo)],
        check=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL,
    )

    tpl = Template(name="Test")
    tpl.text_layers.append(TextLayer(text="SALE 50%", x=0.5, y=0.9,
                                     size_frac=0.06))
    tpl.sticker_layers.append(StickerLayer(path=str(logo), x=0.2, y=0.1,
                                           scale_frac=0.15))

    out = tmp_path / "merged_tpl.mp4"
    cfg = _config(tmp_path, tmp_path, tmp_path,
                  ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    cfg = replace(cfg, template=tpl)
    runner.run_concat(
        f1, f2, out, 0.5, 1.0, 0.5, 1.0, cfg, runner.probe_resolution(f1)
    )
    assert out.exists() and out.stat().st_size > 0


@ffmpeg_required
def test_used_folder_keeps_original_names(tmp_path):
    """Video gốc đã dùng phải giữ NGUYÊN tên khi chuyển vào used_folder."""
    f1_dir = tmp_path / "f1"
    f2_dir = tmp_path / "f2"
    out_dir = tmp_path / "out"
    f1_dir.mkdir()
    f2_dir.mkdir()
    out_dir.mkdir()
    from tests.conftest import make_sample_video

    make_sample_video(f1_dir / "san_pham_dau.mp4", seconds=2)
    make_sample_video(f2_dir / "video_sau.mp4", seconds=2)

    config = _config(f1_dir, f2_dir, out_dir,
                     ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD)
    engine = MergeEngine(config, queue.Queue(), threading.Event())
    engine.run()

    assert (out_dir / "used_folder_1" / "san_pham_dau.mp4").exists()
    assert (out_dir / "used_folder_2" / "video_sau.mp4").exists()


@ffmpeg_required
def test_stop_event_halts_before_next_pair(tmp_path):
    f1_dir = tmp_path / "f1"
    f2_dir = tmp_path / "f2"
    out_dir = tmp_path / "out"
    f1_dir.mkdir()
    f2_dir.mkdir()
    out_dir.mkdir()

    from tests.conftest import make_sample_video

    for i in range(3):
        make_sample_video(f1_dir / f"{i}.mp4", seconds=2)
        make_sample_video(f2_dir / f"x{i}.mp4", seconds=2)

    config = _config(
        f1_dir, f2_dir, out_dir, ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD
    )
    stop = threading.Event()
    stop.set()  # dừng ngay từ đầu
    engine = MergeEngine(config, queue.Queue(), stop)
    summary = engine.run()

    assert summary.stopped is True
    assert summary.succeeded == 0
    # không cặp nào được xử lý -> gốc còn nguyên
    assert len(list(f1_dir.glob("*.mp4"))) == 3
