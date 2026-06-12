"""Test caption tự động theo từng video Folder 2."""

from __future__ import annotations

import queue
import threading
from pathlib import Path

from app.engine.merge_engine import MergeEngine
from app.engine.models import (
    MergeConfig,
    MergeOrder,
    QualityPreset,
    ResizeMode,
    ResizeSubmode,
)


def _engine(tmp_path: Path, source: str) -> MergeEngine:
    cfg = MergeConfig(
        folder1=tmp_path,
        folder2=tmp_path,
        output_folder=tmp_path,
        trim_head_1=1, trim_tail_1=1, trim_head_2=1, trim_tail_2=1,
        merge_order=MergeOrder.SORTED,
        resize_mode=ResizeMode.KEEP_SIZE,
        resize_submode=ResizeSubmode.FIT_PAD,
        quality=QualityPreset.BALANCED,
        caption_source=source,
    )
    return MergeEngine(cfg, queue.Queue(), threading.Event())


def test_caption_fixed_returns_none(tmp_path):
    eng = _engine(tmp_path, "fixed")
    assert eng._resolve_caption(tmp_path / "sanpham_A.mp4") is None


def test_caption_from_filename(tmp_path):
    eng = _engine(tmp_path, "f2_filename")
    assert eng._resolve_caption(tmp_path / "Ao thun 199k.mp4") == "Ao thun 199k"


def test_caption_from_textfile(tmp_path):
    eng = _engine(tmp_path, "f2_textfile")
    video = tmp_path / "sp.mp4"
    (tmp_path / "sp.txt").write_text("Quần jean cao cấp 350k", encoding="utf-8")
    assert eng._resolve_caption(video) == "Quần jean cao cấp 350k"


def test_caption_textfile_missing_returns_empty(tmp_path):
    eng = _engine(tmp_path, "f2_textfile")
    # không có file txt -> không chèn chữ
    assert eng._resolve_caption(tmp_path / "khong_co.mp4") == ""


def test_template_first_layer_gets_video_name(tmp_path):
    """Chế độ f2_filename: lớp chữ đầu tiên của mẫu nhận tên video F2."""
    from app.engine.merge_engine import _template_with_name
    from app.engine.models import MergeConfig, MergeOrder, QualityPreset, \
        ResizeMode, ResizeSubmode
    from app.engine.template_model import Template, TextLayer

    tpl = Template()
    tpl.text_layers.append(TextLayer(text="Nội dung mới", x=0.5, y=0.15,
                                     size_frac=0.06))
    cfg = MergeConfig(
        tmp_path, tmp_path, tmp_path, 1, 1, 1, 1,
        MergeOrder.SORTED, ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD,
        QualityPreset.BALANCED, caption_source="f2_filename",
    )
    new_tpl = _template_with_name(tpl, "San pham A", cfg)
    assert new_tpl.text_layers[0].text == "San pham A"
    # template gốc không bị đổi
    assert tpl.text_layers[0].text == "Nội dung mới"


def test_template_token_replacement(tmp_path):
    """Token {ten} được thay bằng tên video."""
    from app.engine.merge_engine import _template_with_name
    from app.engine.models import MergeConfig, MergeOrder, QualityPreset, \
        ResizeMode, ResizeSubmode
    from app.engine.template_model import Template, TextLayer

    tpl = Template()
    tpl.text_layers.append(TextLayer(text="Mua ngay: {ten}", x=0.5, y=0.5))
    cfg = MergeConfig(
        tmp_path, tmp_path, tmp_path, 1, 1, 1, 1,
        MergeOrder.SORTED, ResizeMode.KEEP_SIZE, ResizeSubmode.FIT_PAD,
        QualityPreset.BALANCED, caption_source="fixed",
    )
    new_tpl = _template_with_name(tpl, "Ghe Sofa", cfg)
    assert new_tpl.text_layers[0].text == "Mua ngay: Ghe Sofa"
