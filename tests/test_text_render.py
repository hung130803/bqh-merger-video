"""Test render lớp chữ thành PNG (chữ + nền bo góc)."""

from __future__ import annotations

from pathlib import Path

from app.engine.template_model import TextLayer
from app.engine.text_render import render_text_layer_png


def test_render_text_png(tmp_path: Path):
    layer = TextLayer(text="Xin chào", x=0.5, y=0.5, size_frac=0.08,
                      box=True, box_color="black", box_opacity=0.5,
                      box_radius=0.4)
    result = render_text_layer_png(layer, 1080, 1920, tmp_path)
    assert result is not None
    png, fx, fy = result
    assert Path(png).is_file()
    assert Path(png).stat().st_size > 0


def test_render_empty_text_returns_none(tmp_path: Path):
    layer = TextLayer(text="   ", x=0.5, y=0.5)
    assert render_text_layer_png(layer, 1080, 1920, tmp_path) is None
