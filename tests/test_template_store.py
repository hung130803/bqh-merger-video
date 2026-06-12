"""Test thư viện mẫu (lưu/liệt kê/nạp/xoá)."""

from __future__ import annotations

import app.engine.template_store as store
from app.engine.template_model import Template, TextLayer


def test_save_list_load_delete(tmp_path, monkeypatch):
    # Chuyển thư mục thư viện sang tmp để không đụng dữ liệu thật
    monkeypatch.setattr(store, "LIBRARY_DIR", tmp_path / "tpl")

    tpl = Template(name="Mau Test")
    tpl.text_layers.append(TextLayer(text="Hello"))
    store.save_template(tpl)

    names = store.list_templates()
    assert "Mau Test" in names

    loaded = store.load_template("Mau Test")
    assert loaded is not None
    assert loaded.text_layers[0].text == "Hello"

    assert store.delete_template("Mau Test") is True
    assert "Mau Test" not in store.list_templates()


def test_load_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LIBRARY_DIR", tmp_path / "tpl2")
    assert store.load_template("khong_co") is None
