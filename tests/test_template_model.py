"""Test lưu/nạp Template."""

from __future__ import annotations

from app.engine.template_model import StickerLayer, Template, TextLayer


def test_template_roundtrip(tmp_path):
    tpl = Template(name="Mẫu A", ref_width=1080, ref_height=1920)
    tpl.text_layers.append(TextLayer(text="Xin chào", x=0.5, y=0.8))
    tpl.sticker_layers.append(StickerLayer(path="logo.png", x=0.1, y=0.1))

    path = tmp_path / "tpl.json"
    tpl.save(path)
    loaded = Template.load(path)

    assert loaded.name == "Mẫu A"
    assert len(loaded.text_layers) == 1
    assert loaded.text_layers[0].text == "Xin chào"
    assert len(loaded.sticker_layers) == 1
    assert loaded.sticker_layers[0].path == "logo.png"


def test_template_empty():
    assert Template().is_empty()
    t = Template()
    t.text_layers.append(TextLayer())
    assert not t.is_empty()


def test_from_dict_ignores_unknown_keys():
    data = {
        "name": "X",
        "text_layers": [{"text": "hi", "bogus": 123}],
        "sticker_layers": [],
    }
    t = Template.from_dict(data)
    assert t.text_layers[0].text == "hi"


def test_text_layer_has_font_fields():
    t = TextLayer()
    assert hasattr(t, "font")
    assert hasattr(t, "bold")


def test_available_fonts_nonempty():
    from app.engine.fonts import available_fonts
    fonts = available_fonts()
    assert isinstance(fonts, list)
    assert len(fonts) >= 1
