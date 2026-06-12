"""Render lớp chữ (kèm nền bo góc, độ mờ) thành ảnh PNG bằng Pillow.

ffmpeg drawtext chỉ vẽ nền vuông góc, nên để có nền bo góc tròn + độ mờ thật,
ta vẽ chữ thành ảnh trong suốt rồi overlay lên video. Toạ độ/cỡ theo tỉ lệ
khung (0..1) giống Template.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .fonts import resolve_font_file

_COLOR_RGB = {
    "white": (255, 255, 255), "black": (0, 0, 0), "red": (220, 38, 38),
    "yellow": (250, 204, 21), "blue": (37, 99, 235), "green": (34, 197, 94),
    "orange": (249, 115, 22), "pink": (236, 72, 153), "purple": (147, 51, 234),
    "gray": (107, 114, 128),
}


def _rgb(name: str) -> tuple[int, int, int]:
    return _COLOR_RGB.get(name, (255, 255, 255))


def wrap_text(text: str, font, draw, max_width: float) -> str:
    """Tự động xuống dòng để mỗi dòng không vượt quá max_width pixel.

    Giữ nguyên các lần xuống dòng thủ công (\\n) của người dùng, đồng thời
    chia nhỏ những dòng quá dài theo từ. Trả về chuỗi đã chèn \\n.
    """
    out_lines: list[str] = []
    for raw_line in text.split("\n"):
        words = raw_line.split(" ")
        cur = ""
        for w in words:
            trial = w if not cur else cur + " " + w
            width = draw.textlength(trial, font=font)
            if width <= max_width or not cur:
                cur = trial
            else:
                out_lines.append(cur)
                cur = w
        out_lines.append(cur)
    return "\n".join(out_lines)


def render_text_layer_png(
    layer, frame_w: int, frame_h: int, out_dir: Path
) -> tuple[Path, float, float] | None:
    """Vẽ một TextLayer thành PNG trong suốt cỡ khung (frame_w x frame_h).

    Trả về (đường dẫn PNG, x_frac, y_frac) — png đã đặt sẵn chữ đúng vị trí
    trên một canvas bằng kích thước khung, nên chỉ cần overlay tại (0,0).
    Trả None nếu không có nội dung.
    """
    text = (layer.text or "").strip()
    if not text:
        return None

    fontsize = max(8, int(layer.size_frac * frame_h))
    fontfile = resolve_font_file(getattr(layer, "font", "Arial"),
                                 getattr(layer, "bold", True))
    try:
        font = (ImageFont.truetype(fontfile, fontsize) if fontfile
                else ImageFont.load_default())
    except OSError:
        font = ImageFont.load_default()

    # Ảnh trong suốt bằng kích thước khung
    img = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Tự động xuống dòng cho vừa ~90% chiều rộng khung
    max_text_w = frame_w * 0.9
    text = wrap_text(text, font, draw, max_text_w)

    # Đo chữ (hỗ trợ nhiều dòng)
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center",
                                   spacing=int(fontsize * 0.2))
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # Tâm theo tỉ lệ
    cx = layer.x * frame_w
    cy = layer.y * frame_h
    pad = int(fontsize * 0.35)

    # Vẽ nền bo góc nếu bật
    if getattr(layer, "box", True):
        bx1 = cx - tw / 2 - pad
        by1 = cy - th / 2 - pad
        bx2 = cx + tw / 2 + pad
        by2 = cy + th / 2 + pad
        opacity = int(max(0.0, min(1.0, layer.box_opacity)) * 255)
        radius = int(getattr(layer, "box_radius", 0.25) * min(
            bx2 - bx1, by2 - by1) / 2)
        fill = _rgb(layer.box_color) + (opacity,)
        if radius > 0:
            draw.rounded_rectangle([bx1, by1, bx2, by2], radius=radius,
                                   fill=fill)
        else:
            draw.rectangle([bx1, by1, bx2, by2], fill=fill)

    # Vẽ chữ nhiều dòng (căn giữa tại tâm).
    tx = cx - tw / 2 - bbox[0]
    ty = cy - th / 2 - bbox[1]
    draw.multiline_text((tx, ty), text, font=font, align="center",
                        spacing=int(fontsize * 0.2),
                        fill=_rgb(layer.color) + (255,))

    # Lưu PNG tạm
    fd, name = tempfile.mkstemp(suffix=".png", dir=str(out_dir))
    import os
    os.close(fd)
    path = Path(name)
    img.save(path)
    return path, 0.0, 0.0
