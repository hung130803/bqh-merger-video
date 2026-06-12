"""Cửa sổ thiết kế Template: kéo-thả chữ & sticker trên khung xem trước.

Người dùng thêm lớp chữ/sticker, kéo tới vị trí mong muốn trên canvas đúng
tỉ lệ khung video, chỉnh thuộc tính, rồi lưu lại. Toạ độ lưu theo tỉ lệ
(0..1) trong Template để áp đúng lên mọi độ phân giải.
"""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from app.engine.template_model import StickerLayer, Template, TextLayer

ACCENT = "#3B82F6"
ACCENT_HOVER = "#2563EB"
MUTED = "#9CA3AF"
DANGER = "#EF4444"
CANVAS_BG = "#0B0E14"

# Bảng màu tên -> RGB để pha độ mờ trong khung xem trước.
_COLOR_RGB = {
    "white": (255, 255, 255), "black": (0, 0, 0), "red": (220, 38, 38),
    "yellow": (250, 204, 21), "blue": (37, 99, 235), "green": (34, 197, 94),
    "orange": (249, 115, 22), "pink": (236, 72, 153), "purple": (147, 51, 234),
    "gray": (107, 114, 128),
}


def _round_rect(canvas, x1, y1, x2, y2, r, fill):
    """Vẽ hình chữ nhật bo góc mượt bằng 2 hình chữ nhật + 4 cung tròn góc.

    Trả về một tag (chuỗi) gom tất cả phần tử để có thể xoá/đưa xuống dưới
    như một đối tượng duy nhất.
    """
    import uuid
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    tag = f"rr_{uuid.uuid4().hex[:8]}"
    if r <= 1:
        canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline="",
                                tags=tag)
        return tag
    # Thân: hình chữ nhật ngang + dọc tạo hình chữ thập
    canvas.create_rectangle(x1 + r, y1, x2 - r, y2, fill=fill, outline="",
                            tags=tag)
    canvas.create_rectangle(x1, y1 + r, x2, y2 - r, fill=fill, outline="",
                            tags=tag)
    # 4 cung tròn lấp góc (pieslice)
    d = 2 * r
    canvas.create_arc(x1, y1, x1 + d, y1 + d, start=90, extent=90,
                      fill=fill, outline="", style="pieslice", tags=tag)
    canvas.create_arc(x2 - d, y1, x2, y1 + d, start=0, extent=90,
                      fill=fill, outline="", style="pieslice", tags=tag)
    canvas.create_arc(x1, y2 - d, x1 + d, y2, start=180, extent=90,
                      fill=fill, outline="", style="pieslice", tags=tag)
    canvas.create_arc(x2 - d, y2 - d, x2, y2, start=270, extent=90,
                      fill=fill, outline="", style="pieslice", tags=tag)
    return tag


def _rgb_tuple(name: str) -> tuple[int, int, int]:
    return _COLOR_RGB.get(name, (255, 255, 255))


def _blend_to_bg(color: str, opacity: float, bg_hex: str) -> str:
    """Pha màu nền với nền canvas theo độ mờ để mô phỏng opacity (tkinter
    không hỗ trợ alpha). Trả về mã màu hex."""
    fg = _COLOR_RGB.get(color, (0, 0, 0))
    bh = bg_hex.lstrip("#")
    bg = (int(bh[0:2], 16), int(bh[2:4], 16), int(bh[4:6], 16))
    op = max(0.0, min(1.0, opacity))
    r = round(fg[0] * op + bg[0] * (1 - op))
    g = round(fg[1] * op + bg[1] * (1 - op))
    b = round(fg[2] * op + bg[2] * (1 - op))
    return f"#{r:02x}{g:02x}{b:02x}"

# Canvas hiển thị thu nhỏ; tỉ lệ giữ đúng theo khung tham chiếu.
CANVAS_H = 560


class TemplateDesigner(ctk.CTkToplevel):
    """Cửa sổ con thiết kế template."""

    def __init__(self, master, template: Template | None = None,
                 on_save=None) -> None:
        super().__init__(master)
        self.title("Thiết kế mẫu (Template)")
        self.geometry("980x680")
        self.minsize(900, 620)

        self.on_save = on_save
        self.template = template if template is not None else Template()

        # Tỉ lệ khung
        self.ref_w = self.template.ref_width
        self.ref_h = self.template.ref_height
        self.canvas_h = CANVAS_H
        self.canvas_w = int(self.canvas_h * self.ref_w / self.ref_h)

        # Danh sách item trên canvas: mỗi phần tử là dict
        # {kind, layer, cid, type}
        self.items: list[dict] = []
        self.selected: dict | None = None
        self._sel_rect = None  # khung chọn (viền trắng)
        self._handles: list = []        # 4 tay cầm góc
        self._handle_pts: dict = {}      # toạ độ tay cầm
        self._guides: list = []          # đường căn
        self._mode = "move"              # "move" hoặc "resize"
        self._resize_start_dist = 1.0    # khoảng cách góc lúc bắt đầu resize
        self._resize_start_size = 0.05   # cỡ lúc bắt đầu resize
        self._drag_dx = 0
        self._drag_dy = 0

        self._build_ui()
        self._load_template_items()
        self.after(100, self.lift)
        self.grab_set()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Canvas khung xem trước (trái) ---
        import tkinter as tk
        left = ctk.CTkFrame(self, corner_radius=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(16, 8), pady=16)
        ctk.CTkLabel(
            left, text="Khung xem trước (kéo để di chuyển)",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(padx=12, pady=(12, 6))

        self.canvas = tk.Canvas(
            left, width=self.canvas_w, height=self.canvas_h,
            bg=CANVAS_BG, highlightthickness=1, highlightbackground="#333",
        )
        self.canvas.pack(padx=12, pady=12)
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        # Cuộn chuột để phóng to/thu nhỏ lớp đang chọn
        self.canvas.bind("<MouseWheel>", self._on_canvas_wheel)
        self.canvas.bind("<Button-4>", self._on_canvas_wheel)
        self.canvas.bind("<Button-5>", self._on_canvas_wheel)

        ctk.CTkLabel(
            left, text=f"Tỉ lệ khung: {self.ref_w}x{self.ref_h}",
            text_color=MUTED, font=ctk.CTkFont(size=11),
        ).pack(pady=(0, 4))
        ctk.CTkLabel(
            left,
            text="Kéo ô góc trắng để phóng to/thu nhỏ • "
                 "Đường hồng hiện khi căn giữa / trên / dưới",
            text_color=MUTED, font=ctk.CTkFont(size=10),
            wraplength=self.canvas_w,
        ).pack(pady=(0, 12))

        # --- Bảng điều khiển (phải) ---
        right = ctk.CTkScrollableFrame(self, corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
        right.grid_columnconfigure(0, weight=1)

        # Tên mẫu
        ctk.CTkLabel(right, text="Tên mẫu:", anchor="w").grid(
            row=0, column=0, sticky="w", padx=12, pady=(12, 2)
        )
        self.name_entry = ctk.CTkEntry(right)
        self.name_entry.insert(0, self.template.name)
        self.name_entry.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 10))

        # Khung tham chiếu
        ctk.CTkLabel(right, text="Khung mẫu:", anchor="w").grid(
            row=2, column=0, sticky="w", padx=12, pady=(0, 2)
        )
        self.ref_var = ctk.StringVar(value=f"{self.ref_w}x{self.ref_h}")
        ctk.CTkOptionMenu(
            right, values=["1080x1920", "1080x1080", "1920x1080"],
            variable=self.ref_var, command=self._on_ref_change,
        ).grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

        # Nút thêm lớp
        addbar = ctk.CTkFrame(right, fg_color="transparent")
        addbar.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 8))
        addbar.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            addbar, text="+ Thêm chữ", command=self._add_text,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            addbar, text="+ Thêm sticker", command=self._add_sticker,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ctk.CTkLabel(
            right,
            text="Khi chọn 'Chữ theo video Folder 2' ở ngoài: lớp chữ đầu "
                 "tiên sẽ TỰ thành tên video (giữ nguyên kiểu/vị trí bạn "
                 "chỉnh). Hoặc gõ {ten} để đặt tên vào chỗ bất kỳ.",
            text_color=MUTED, font=ctk.CTkFont(size=11),
            wraplength=300, justify="left",
        ).grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 4))

        # Khu vực thuộc tính lớp đang chọn
        self.props = ctk.CTkFrame(right, corner_radius=8)
        self.props.grid(row=6, column=0, sticky="ew", padx=12, pady=8)
        self.props.grid_columnconfigure(1, weight=1)
        self._prop_placeholder = ctk.CTkLabel(
            self.props, text="Chọn một lớp để chỉnh thuộc tính.",
            text_color=MUTED,
        )
        self._prop_placeholder.grid(row=0, column=0, columnspan=2,
                                    padx=12, pady=12)

        # Nút lưu / huỷ
        bottom = ctk.CTkFrame(right, fg_color="transparent")
        bottom.grid(row=6, column=0, sticky="ew", padx=12, pady=(8, 12))
        bottom.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkButton(
            bottom, text="Xoá lớp đang chọn", fg_color=DANGER,
            hover_color="#B91C1C", command=self._delete_selected,
        ).grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ctk.CTkButton(
            bottom, text="💾 Lưu mẫu ra file", command=self._save_to_file,
        ).grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ctk.CTkButton(
            bottom, text="📂 Mở mẫu từ file", command=self._load_from_file,
        ).grid(row=1, column=1, sticky="ew", padx=(4, 0))
        ctk.CTkButton(
            bottom, text="✔ Dùng mẫu này", height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#22C55E", hover_color="#16A34A",
            command=self._apply_and_close,
        ).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

    # ---------------------------------------------------- toạ độ chuyển đổi
    def _to_px(self, fx: float, fy: float) -> tuple[int, int]:
        return int(fx * self.canvas_w), int(fy * self.canvas_h)

    def _to_frac(self, px: float, py: float) -> tuple[float, float]:
        return (
            max(0.0, min(1.0, px / self.canvas_w)),
            max(0.0, min(1.0, py / self.canvas_h)),
        )

    # ------------------------------------------------------- vẽ các lớp
    def _load_template_items(self) -> None:
        self.canvas.delete("all")
        self.items.clear()
        for tl in self.template.text_layers:
            self._draw_text_item(tl)
        for sl in self.template.sticker_layers:
            self._draw_sticker_item(sl)

    def _render_text_photo(self, layer):
        """Render lớp chữ (chữ + nền bo góc) thành ảnh mượt bằng Pillow.

        Trả về (PhotoImage, w, h) ở kích thước hiển thị trên canvas.
        """
        from PIL import Image, ImageDraw, ImageFont, ImageTk
        from app.engine.fonts import resolve_font_file

        text = layer.text or "(chữ)"
        fontsize = max(8, int(layer.size_frac * self.canvas_h))
        fontfile = resolve_font_file(getattr(layer, "font", "Arial"),
                                     getattr(layer, "bold", True))
        try:
            font = (ImageFont.truetype(fontfile, fontsize) if fontfile
                    else ImageFont.load_default())
        except OSError:
            font = ImageFont.load_default()

        # Đo chữ (hỗ trợ nhiều dòng + tự xuống dòng cho vừa khung)
        tmp = Image.new("RGBA", (10, 10))
        td = ImageDraw.Draw(tmp)
        from app.engine.text_render import wrap_text
        text = wrap_text(text, font, td, self.canvas_w * 0.9)
        bbox = td.multiline_textbbox((0, 0), text, font=font,
                                     align="center", spacing=4)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        pad = int(fontsize * 0.35)
        W = int(tw + pad * 2 + 4)
        H = int(th + pad * 2 + 4)

        img = Image.new("RGBA", (max(4, W), max(4, H)), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if getattr(layer, "box", True):
            opacity = int(max(0.0, min(1.0, layer.box_opacity)) * 255)
            radius = int(getattr(layer, "box_radius", 0.25) * min(W, H) / 2)
            fill = _rgb_tuple(layer.box_color) + (opacity,)
            if radius > 0:
                draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=radius,
                                       fill=fill)
            else:
                draw.rectangle([0, 0, W - 1, H - 1], fill=fill)

        tx = (W - tw) / 2 - bbox[0]
        ty = (H - th) / 2 - bbox[1]
        draw.multiline_text((tx, ty), text, font=font, align="center",
                            spacing=4, fill=_rgb_tuple(layer.color) + (255,))

        photo = ImageTk.PhotoImage(img)
        return photo, W, H

    def _draw_text_item(self, layer: TextLayer) -> dict:
        px, py = self._to_px(layer.x, layer.y)
        photo, w, h = self._render_text_photo(layer)
        cid = self.canvas.create_image(px, py, image=photo, anchor="center")
        item = {"kind": "text", "layer": layer, "cid": cid, "photo": photo}
        self.items.append(item)
        return item

    def _draw_sticker_item(self, layer: StickerLayer) -> dict:
        px, py = self._to_px(layer.x, layer.y)
        w = max(20, int(layer.scale_frac * self.canvas_w))
        cid = self.canvas.create_rectangle(
            px - w // 2, py - w // 2, px + w // 2, py + w // 2,
            outline=ACCENT, width=2, dash=(4, 2),
        )
        label = Path(layer.path).name if layer.path else "sticker"
        tid = self.canvas.create_text(
            px, py, text=f"🖼 {label}", fill=ACCENT, font=("Arial", 10),
        )
        item = {"kind": "sticker", "layer": layer, "cid": cid, "tid": tid}
        self.items.append(item)
        return item

    def _redraw_item(self, item: dict) -> None:
        layer = item["layer"]
        px, py = self._to_px(layer.x, layer.y)
        if item["kind"] == "text":
            photo, w, h = self._render_text_photo(layer)
            item["photo"] = photo  # giữ tham chiếu tránh bị thu gom
            self.canvas.itemconfigure(item["cid"], image=photo)
            self.canvas.coords(item["cid"], px, py)
        else:
            w = max(20, int(layer.scale_frac * self.canvas_w))
            self.canvas.coords(
                item["cid"], px - w // 2, py - w // 2, px + w // 2, py + w // 2
            )
            self.canvas.coords(item["tid"], px, py)
            label = Path(layer.path).name if layer.path else "sticker"
            self.canvas.itemconfigure(item["tid"], text=f"🖼 {label}")

    # ------------------------------------------------------- tương tác canvas
    def _handle_at(self, x, y):
        """Trả về tên handle góc nếu (x,y) gần một tay cầm, ngược lại None."""
        for name, (hx, hy) in self._handle_pts.items():
            if abs(x - hx) <= 9 and abs(y - hy) <= 9:
                return name
        return None

    def _on_canvas_click(self, event) -> None:
        # Ưu tiên: bấm vào tay cầm góc của lớp đang chọn -> chế độ resize
        if self.selected is not None and self._handle_at(event.x, event.y):
            self._mode = "resize"
            layer = self.selected["layer"]
            cx, cy = self._to_px(layer.x, layer.y)
            # Ghi lại khoảng cách & cỡ ban đầu để kéo tương đối (không nhảy)
            self._resize_start_dist = max(
                8.0, ((event.x - cx) ** 2 + (event.y - cy) ** 2) ** 0.5
            )
            if self.selected["kind"] == "text":
                self._resize_start_size = layer.size_frac
            else:
                self._resize_start_size = layer.scale_frac
            return
        # Ngược lại: chọn item gần tâm nhất rồi vào chế độ move
        nearest = None
        best = 1e9
        for it in self.items:
            px, py = self._to_px(it["layer"].x, it["layer"].y)
            d = (px - event.x) ** 2 + (py - event.y) ** 2
            if d < best:
                best = d
                nearest = it
        if nearest is not None:
            self.selected = nearest
            px, py = self._to_px(nearest["layer"].x, nearest["layer"].y)
            self._drag_dx = px - event.x
            self._drag_dy = py - event.y
            self._mode = "move"
            self._show_props()
            self._highlight_selection()

    def _on_canvas_drag(self, event) -> None:
        if self.selected is None:
            return
        if self._mode == "resize":
            self._resize_drag(event)
            return
        nx = event.x + self._drag_dx
        ny = event.y + self._drag_dy
        fx, fy = self._to_frac(nx, ny)
        fx, fy = self._apply_snap(fx, fy)
        self.selected["layer"].x = fx
        self.selected["layer"].y = fy
        self._redraw_item(self.selected)
        self._highlight_selection()

    def _on_canvas_release(self, event) -> None:
        self._mode = "move"
        self._clear_guides()

    def _resize_drag(self, event) -> None:
        """Kéo tay cầm góc theo tỉ lệ tương đối: kéo ra to, kéo vào nhỏ."""
        layer = self.selected["layer"]
        cx, cy = self._to_px(layer.x, layer.y)
        dist = max(4.0, ((event.x - cx) ** 2 + (event.y - cy) ** 2) ** 0.5)
        ratio = dist / self._resize_start_dist
        new_size = self._resize_start_size * ratio
        if self.selected["kind"] == "text":
            layer.size_frac = max(0.02, min(0.40, new_size))
        else:
            layer.scale_frac = max(0.05, min(0.95, new_size))
        self._redraw_item(self.selected)
        self._highlight_selection()
        self._show_props()

    def _on_canvas_wheel(self, event) -> None:
        """Lăn chuột để phóng to/thu nhỏ lớp đang chọn."""
        if self.selected is None:
            return
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            factor = 1.08
        else:
            factor = 0.92
        layer = self.selected["layer"]
        if self.selected["kind"] == "text":
            layer.size_frac = max(0.02, min(0.40, layer.size_frac * factor))
        else:
            layer.scale_frac = max(0.05, min(0.95, layer.scale_frac * factor))
        self._redraw_item(self.selected)
        self._highlight_selection()
        self._show_props()

    # ----------------------------------------------------- đường căn (snap)
    SNAP_TOL = 0.025
    SNAP_X = [0.5]
    SNAP_Y = [0.1, 0.5, 0.9]

    def _apply_snap(self, fx: float, fy: float) -> tuple[float, float]:
        """Hít toạ độ vào mốc căn và vẽ đường căn (giữa, trên, dưới)."""
        self._clear_guides()
        sx_out, sy_out = fx, fy
        for sx in self.SNAP_X:
            if abs(fx - sx) <= self.SNAP_TOL:
                sx_out = sx
                gx = int(sx * self.canvas_w)
                self._guides.append(self.canvas.create_line(
                    gx, 0, gx, self.canvas_h, fill="#FF4D8D", width=1,
                    dash=(4, 3),
                ))
                break
        for sy in self.SNAP_Y:
            if abs(fy - sy) <= self.SNAP_TOL:
                sy_out = sy
                gy = int(sy * self.canvas_h)
                self._guides.append(self.canvas.create_line(
                    0, gy, self.canvas_w, gy, fill="#FF4D8D", width=1,
                    dash=(4, 3),
                ))
                break
        return sx_out, sy_out

    def _clear_guides(self) -> None:
        for g in self._guides:
            self.canvas.delete(g)
        self._guides.clear()

    def _highlight_selection(self) -> None:
        """Vẽ khung viền trắng + 4 tay cầm góc quanh lớp đang chọn."""
        if self._sel_rect is not None:
            self.canvas.delete(self._sel_rect)
            self._sel_rect = None
        for h in self._handles:
            self.canvas.delete(h)
        self._handles.clear()
        self._handle_pts.clear()
        if self.selected is None:
            return
        cid = self.selected["cid"]
        try:
            bbox = self.canvas.bbox(cid)
        except Exception:
            bbox = None
        if not bbox:
            return
        x1, y1, x2, y2 = bbox
        pad = 6
        x1 -= pad
        y1 -= pad
        x2 += pad
        y2 += pad
        self._sel_rect = self.canvas.create_rectangle(
            x1, y1, x2, y2, outline="white", width=2, dash=(5, 3),
        )
        corners = {
            "tl": (x1, y1), "tr": (x2, y1),
            "bl": (x1, y2), "br": (x2, y2),
        }
        s = 5
        for name, (hx, hy) in corners.items():
            self._handle_pts[name] = (hx, hy)
            self._handles.append(self.canvas.create_rectangle(
                hx - s, hy - s, hx + s, hy + s, fill="white", outline=ACCENT,
            ))

    # ------------------------------------------------------------- thêm lớp
    def _add_text(self) -> None:
        layer = TextLayer(text="Nội dung mới", x=0.5, y=0.5)
        self.template.text_layers.append(layer)
        item = self._draw_text_item(layer)
        self.selected = item
        self._show_props()
        self._highlight_selection()


    def _add_sticker(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Chọn ảnh sticker (PNG nền trong là đẹp nhất)",
            filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.webp"), ("Tất cả", "*.*")],
        )
        if not path:
            return
        layer = StickerLayer(path=path, x=0.5, y=0.3, scale_frac=0.25)
        self.template.sticker_layers.append(layer)
        item = self._draw_sticker_item(layer)
        self.selected = item
        self._show_props()
        self._highlight_selection()

    def _delete_selected(self) -> None:
        if self.selected is None:
            return
        layer = self.selected["layer"]
        if self.selected["kind"] == "text":
            self.template.text_layers.remove(layer)
            self.canvas.delete(self.selected["cid"])
        else:
            self.template.sticker_layers.remove(layer)
            self.canvas.delete(self.selected["cid"])
            self.canvas.delete(self.selected["tid"])
        self.items.remove(self.selected)
        self.selected = None
        if self._sel_rect is not None:
            self.canvas.delete(self._sel_rect)
            self._sel_rect = None
        for h in self._handles:
            self.canvas.delete(h)
        self._handles.clear()
        self._handle_pts.clear()
        self._show_props()

    # ------------------------------------------------------- bảng thuộc tính
    def _clear_props(self) -> None:
        for w in self.props.winfo_children():
            w.destroy()

    def _show_props(self) -> None:
        self._clear_props()
        if self.selected is None:
            ctk.CTkLabel(
                self.props, text="Chọn một lớp để chỉnh thuộc tính.",
                text_color=MUTED,
            ).grid(row=0, column=0, columnspan=2, padx=12, pady=12)
            return

        layer = self.selected["layer"]
        if self.selected["kind"] == "text":
            self._text_props(layer)
        else:
            self._sticker_props(layer)

    def _text_props(self, layer: TextLayer) -> None:
        ctk.CTkLabel(self.props, text="Lớp CHỮ", font=ctk.CTkFont(weight="bold"),
                     text_color=ACCENT).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6)
        )

        ctk.CTkLabel(self.props, text="Nội dung:").grid(
            row=1, column=0, sticky="nw", padx=12, pady=4
        )
        e = ctk.CTkTextbox(self.props, height=70, wrap="word")
        e.insert("1.0", layer.text)
        e.grid(row=1, column=1, sticky="ew", padx=12, pady=4)

        def _upd_text(_=None):
            layer.text = e.get("1.0", "end").rstrip("\n")
            self._redraw_item(self.selected)
            self._highlight_selection()
        e.bind("<KeyRelease>", _upd_text)

        # Cỡ chữ
        ctk.CTkLabel(self.props, text="Cỡ chữ:").grid(
            row=2, column=0, sticky="w", padx=12, pady=4
        )
        size_var = ctk.DoubleVar(value=layer.size_frac)
        sl = ctk.CTkSlider(self.props, from_=0.02, to=0.15,
                           variable=size_var)
        sl.grid(row=2, column=1, sticky="ew", padx=12, pady=4)

        def _upd_size(_=None):
            layer.size_frac = float(size_var.get())
            self._redraw_item(self.selected)
            self._highlight_selection()
        sl.configure(command=_upd_size)

        # Màu chữ
        ctk.CTkLabel(self.props, text="Màu chữ:").grid(
            row=3, column=0, sticky="w", padx=12, pady=4
        )
        color_var = ctk.StringVar(value=layer.color)
        cm = ctk.CTkOptionMenu(
            self.props,
            values=["white", "black", "red", "yellow", "blue", "green",
                    "orange", "pink"],
            variable=color_var,
        )
        cm.grid(row=3, column=1, sticky="ew", padx=12, pady=4)

        def _upd_color(_=None):
            layer.color = color_var.get()
            self._redraw_item(self.selected)
        cm.configure(command=_upd_color)

        # Kiểu chữ (font)
        ctk.CTkLabel(self.props, text="Kiểu chữ:").grid(
            row=4, column=0, sticky="w", padx=12, pady=4
        )
        from app.engine.fonts import available_fonts
        fonts = available_fonts()
        if layer.font not in fonts:
            fonts = [layer.font] + fonts
        font_var = ctk.StringVar(value=layer.font)
        fm = ctk.CTkOptionMenu(self.props, values=fonts, variable=font_var)
        fm.grid(row=4, column=1, sticky="ew", padx=12, pady=4)

        def _upd_font(_=None):
            layer.font = font_var.get()
            self._redraw_item(self.selected)
        fm.configure(command=_upd_font)

        # Đậm
        bold_var = ctk.BooleanVar(value=getattr(layer, "bold", True))

        def _upd_bold():
            layer.bold = bool(bold_var.get())
            self._redraw_item(self.selected)
        ctk.CTkCheckBox(self.props, text="Chữ đậm (bold)",
                        variable=bold_var, command=_upd_bold).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=12, pady=4
        )

        # Nền chữ
        box_var = ctk.BooleanVar(value=layer.box)

        def _upd_box():
            layer.box = bool(box_var.get())
            self._redraw_item(self.selected)
            self._highlight_selection()
        ctk.CTkCheckBox(self.props, text="Bật nền chữ",
                        variable=box_var, command=_upd_box).grid(
            row=6, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 2)
        )

        # Màu nền chữ
        ctk.CTkLabel(self.props, text="Màu nền:").grid(
            row=7, column=0, sticky="w", padx=12, pady=4
        )
        boxcolor_var = ctk.StringVar(value=layer.box_color)
        bcm = ctk.CTkOptionMenu(
            self.props,
            values=["black", "white", "red", "yellow", "blue", "green",
                    "orange", "pink", "purple", "gray"],
            variable=boxcolor_var,
        )
        bcm.grid(row=7, column=1, sticky="ew", padx=12, pady=4)

        def _upd_boxcolor(_=None):
            layer.box_color = boxcolor_var.get()
            self._redraw_item(self.selected)
        bcm.configure(command=_upd_boxcolor)

        # Độ đậm nền
        ctk.CTkLabel(self.props, text="Độ đậm nền:").grid(
            row=8, column=0, sticky="w", padx=12, pady=(4, 10)
        )
        boxop_var = ctk.DoubleVar(value=layer.box_opacity)
        bsl = ctk.CTkSlider(self.props, from_=0.0, to=1.0, variable=boxop_var)
        bsl.grid(row=8, column=1, sticky="ew", padx=12, pady=(4, 10))

        def _upd_boxop(_=None):
            layer.box_opacity = float(boxop_var.get())
            self._redraw_item(self.selected)
        bsl.configure(command=_upd_boxop)

        # Bo góc nền
        ctk.CTkLabel(self.props, text="Bo góc nền:").grid(
            row=9, column=0, sticky="w", padx=12, pady=(4, 10)
        )
        radius_var = ctk.DoubleVar(value=getattr(layer, "box_radius", 0.25))
        rsl = ctk.CTkSlider(self.props, from_=0.0, to=1.0, variable=radius_var)
        rsl.grid(row=9, column=1, sticky="ew", padx=12, pady=(4, 10))

        def _upd_radius(_=None):
            layer.box_radius = float(radius_var.get())
            self._redraw_item(self.selected)
        rsl.configure(command=_upd_radius)

    def _sticker_props(self, layer: StickerLayer) -> None:
        ctk.CTkLabel(self.props, text="Lớp STICKER",
                     font=ctk.CTkFont(weight="bold"), text_color=ACCENT).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 6)
        )
        ctk.CTkLabel(
            self.props, text=Path(layer.path).name if layer.path else "(chưa có)",
            text_color=MUTED,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=12, pady=4)

        # Cỡ
        ctk.CTkLabel(self.props, text="Kích thước:").grid(
            row=2, column=0, sticky="w", padx=12, pady=4
        )
        scale_var = ctk.DoubleVar(value=layer.scale_frac)
        sl = ctk.CTkSlider(self.props, from_=0.05, to=0.6, variable=scale_var)
        sl.grid(row=2, column=1, sticky="ew", padx=12, pady=4)

        def _upd_scale(_=None):
            layer.scale_frac = float(scale_var.get())
            self._redraw_item(self.selected)
            self._highlight_selection()
        sl.configure(command=_upd_scale)

        # Độ mờ
        ctk.CTkLabel(self.props, text="Độ mờ:").grid(
            row=3, column=0, sticky="w", padx=12, pady=(4, 10)
        )
        op_var = ctk.DoubleVar(value=layer.opacity)
        sl2 = ctk.CTkSlider(self.props, from_=0.1, to=1.0, variable=op_var)
        sl2.grid(row=3, column=1, sticky="ew", padx=12, pady=(4, 10))

        def _upd_op(_=None):
            layer.opacity = float(op_var.get())
        sl2.configure(command=_upd_op)

    # ------------------------------------------------------------- ref change
    def _on_ref_change(self, value: str) -> None:
        try:
            w, h = value.lower().split("x")
            self.ref_w = int(w)
            self.ref_h = int(h)
        except ValueError:
            return
        self.template.ref_width = self.ref_w
        self.template.ref_height = self.ref_h
        self.canvas_w = int(self.canvas_h * self.ref_w / self.ref_h)
        self.canvas.configure(width=self.canvas_w)
        self._load_template_items()

    # ----------------------------------------------------------- lưu / mở
    def _sync_name(self) -> None:
        self.template.name = self.name_entry.get().strip() or "Mẫu"

    def _save_to_file(self) -> None:
        self._sync_name()
        path = filedialog.asksaveasfilename(
            parent=self, title="Lưu mẫu", defaultextension=".json",
            initialfile=f"{self.template.name}.json",
            filetypes=[("Template JSON", "*.json")],
        )
        if path:
            self.template.save(Path(path))
            messagebox.showinfo("Đã lưu", f"Đã lưu mẫu vào:\n{path}",
                                parent=self)

    def _load_from_file(self) -> None:
        path = filedialog.askopenfilename(
            parent=self, title="Mở mẫu",
            filetypes=[("Template JSON", "*.json"), ("Tất cả", "*.*")],
        )
        if not path:
            return
        try:
            self.template = Template.load(Path(path))
        except (OSError, ValueError) as exc:
            messagebox.showerror("Lỗi", f"Không mở được mẫu:\n{exc}",
                                 parent=self)
            return
        self.ref_w = self.template.ref_width
        self.ref_h = self.template.ref_height
        self.canvas_w = int(self.canvas_h * self.ref_w / self.ref_h)
        self.canvas.configure(width=self.canvas_w)
        self.ref_var.set(f"{self.ref_w}x{self.ref_h}")
        self.name_entry.delete(0, "end")
        self.name_entry.insert(0, self.template.name)
        self.selected = None
        self._load_template_items()
        self._show_props()

    def _apply_and_close(self) -> None:
        self._sync_name()
        # Tự lưu vào thư viện mẫu để tái sử dụng (nếu có nội dung)
        if not self.template.is_empty():
            try:
                from app.engine.template_store import save_template
                save_template(self.template)
            except Exception:
                pass
        if self.on_save is not None:
            self.on_save(self.template)
        self.grab_release()
        self.destroy()
