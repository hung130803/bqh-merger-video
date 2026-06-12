"""Mô hình dữ liệu cho Template (mẫu overlay áp lên video).

Một Template gồm nhiều lớp (layer): lớp chữ (TextLayer) và lớp sticker/ảnh
(StickerLayer). Toạ độ và kích thước lưu dưới dạng TỈ LỆ (0.0 - 1.0) so với
khung hình, nhờ vậy mẫu áp đúng lên mọi độ phân giải.

Toạ độ (x, y) là tâm của lớp, tính theo tỉ lệ chiều rộng/chiều cao khung.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class TextLayer:
    """Lớp chữ trên video."""

    text: str = "Nội dung"
    x: float = 0.5          # tâm theo chiều rộng (0..1)
    y: float = 0.85         # tâm theo chiều cao (0..1)
    size_frac: float = 0.05  # cỡ chữ theo tỉ lệ chiều cao khung
    color: str = "black"
    font: str = "Arial"      # tên kiểu chữ
    bold: bool = True
    box: bool = True         # nền phía sau chữ
    box_color: str = "white"
    box_opacity: float = 1.0
    box_radius: float = 0.25  # bo góc nền: 0 = vuông, 1 = bo tối đa
    kind: str = "text"


@dataclass
class StickerLayer:
    """Lớp sticker/ảnh (PNG) trên video."""

    path: str = ""
    x: float = 0.5          # tâm theo chiều rộng (0..1)
    y: float = 0.15         # tâm theo chiều cao (0..1)
    scale_frac: float = 0.2  # chiều rộng sticker theo tỉ lệ chiều rộng khung
    opacity: float = 1.0
    kind: str = "sticker"


@dataclass
class Template:
    """Mẫu gồm danh sách lớp, theo tỉ lệ khung tham chiếu."""

    name: str = "Mẫu mới"
    ref_width: int = 1080
    ref_height: int = 1920
    text_layers: list[TextLayer] = field(default_factory=list)
    sticker_layers: list[StickerLayer] = field(default_factory=list)

    # ----------------------------------------------------------- serialize
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ref_width": self.ref_width,
            "ref_height": self.ref_height,
            "text_layers": [asdict(t) for t in self.text_layers],
            "sticker_layers": [asdict(s) for s in self.sticker_layers],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Template":
        t = cls(
            name=data.get("name", "Mẫu"),
            ref_width=int(data.get("ref_width", 1080)),
            ref_height=int(data.get("ref_height", 1920)),
        )
        for td in data.get("text_layers", []):
            t.text_layers.append(TextLayer(**_filter_fields(TextLayer, td)))
        for sd in data.get("sticker_layers", []):
            t.sticker_layers.append(
                StickerLayer(**_filter_fields(StickerLayer, sd))
            )
        return t

    def save(self, path: Path) -> None:
        with Path(path).open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: Path) -> "Template":
        with Path(path).open("r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def is_empty(self) -> bool:
        return not self.text_layers and not self.sticker_layers


def _filter_fields(cls, data: dict) -> dict:
    """Lọc chỉ giữ các khóa hợp lệ của dataclass (bỏ qua khóa lạ)."""
    valid = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
    return {k: v for k, v in data.items() if k in valid}
