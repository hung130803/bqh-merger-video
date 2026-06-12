"""Quy ước đặt tên file kết quả và file gốc đã dùng.

Các hàm ở đây là hàm thuần (pure) để dễ kiểm thử bằng property-based testing.
"""

from __future__ import annotations

from pathlib import Path


def format_stt(index: int) -> str:
    """Định dạng số thứ tự cặp.

    index bắt đầu từ 1. Trả về chuỗi ba chữ số có số 0 ở đầu (001, 002, ...).
    Khi index > 999, dùng đủ số chữ số cần thiết mà không cắt bớt giá trị,
    do đó luôn đảm bảo int(format_stt(n)) == n.
    """
    if index < 1:
        raise ValueError("index phải >= 1")
    return f"{index:03d}"


def merged_name(stt: str, name1: str, name2: str) -> str:
    """Tên file kết quả: merged_<STT>__<ten-f1>__<ten-f2>.mp4.

    name1, name2 là tên file gốc đã loại bỏ phần mở rộng.
    """
    return f"merged_{stt}__{name1}__{name2}.mp4"


def used_name(stt: str, side: str, name: str) -> str:
    """Tên file gốc đã dùng: <STT>_<side>_<ten>.mp4.

    side phải là "F1" hoặc "F2". name là tên gốc đã bỏ phần mở rộng.
    """
    if side not in ("F1", "F2"):
        raise ValueError('side phải là "F1" hoặc "F2"')
    return f"{stt}_{side}_{name}.mp4"


def resolve_collision(target: Path) -> Path:
    """Trả về một đường dẫn chưa tồn tại trong thư mục đích.

    Nếu target chưa tồn tại, trả về chính nó. Nếu đã tồn tại, chèn hậu tố
    _<n> (n bắt đầu từ 1, tăng dần) ngay trước phần mở rộng cho tới khi
    tạo được tên chưa tồn tại.
    """
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    parent = target.parent

    n = 1
    while True:
        candidate = parent / f"{stem}_{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1
