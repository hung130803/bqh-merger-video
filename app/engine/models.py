"""Data models và enums cho Batch Video Merger.

Toàn bộ kiểu dữ liệu dùng chung giữa engine và GUI được định nghĩa ở đây.
Module này KHÔNG phụ thuộc vào customtkinter để engine có thể test độc lập.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# --- Định dạng video được hỗ trợ (so khớp không phân biệt hoa thường) ---
SUPPORTED_FORMATS: frozenset[str] = frozenset(
    {".mp4", ".mov", ".mkv", ".avi", ".webm"}
)


class MergeOrder(Enum):
    """Chế độ sắp xếp cặp video."""

    SORTED = "sorted"    # theo thứ tự tên file
    SHUFFLE = "shuffle"  # ngẫu nhiên


class ResizeMode(Enum):
    """Chế độ xử lý kích thước đầu ra."""

    NINE_SIXTEEN = "9:16"    # 1080x1920
    KEEP_SIZE = "keep_size"  # giữ nguyên kích thước


class ResizeSubmode(Enum):
    """Chế độ con khi resize 9:16."""

    FIT_PAD = "fit_pad"      # Fit with padding (nền đen)
    FILL_CROP = "fill_crop"  # Fill crop (cắt cân giữa)


class QualityPreset(Enum):
    """Mức chất lượng đầu ra, giá trị là CRF tương ứng."""

    FAST = 28
    BALANCED = 23
    HIGH = 18


class MergeStatus(Enum):
    """Tập trạng thái có kiểm soát hiển thị trên giao diện."""

    DONE = "Done"
    FAILED = "Failed"
    SKIPPED_TOO_SHORT = "Skipped because video too short"
    SKIPPED_UNREADABLE = "Skipped because unreadable"
    UNUSED_NO_PAIR = "Unused because no pair"


@dataclass(frozen=True)
class MergeConfig:
    """Toàn bộ tham số cho một lần chạy ghép video."""

    folder1: Path
    folder2: Path
    output_folder: Path
    trim_head_1: float
    trim_tail_1: float
    trim_head_2: float
    trim_tail_2: float
    merge_order: MergeOrder
    resize_mode: ResizeMode
    resize_submode: ResizeSubmode  # bỏ qua khi resize_mode == KEEP_SIZE
    quality: QualityPreset
    target_width: int = 1080       # dùng cho 9:16
    target_height: int = 1920
    fps: int = 30
    audio_rate: int = 44100
    # --- Nhạc nền ---
    background_music: Path | None = None  # None nghĩa là không dùng nhạc nền
    music_volume: float = 1.0             # hệ số âm lượng nhạc nền (0.0 - 2.0)
    mute_original: bool = False           # True = tắt tiếng gốc, chỉ nghe nhạc
    # --- Tăng tốc encode ---
    use_gpu: bool = False                 # True = dùng NVENC nếu khả dụng
    # --- Tốc độ phát & âm lượng video ---
    video_speed: float = 1.0              # 0.25 - 4.0, 1.0 = bình thường
    volume_boost: float = 1.0             # 0.0 - 4.0, hệ số âm lượng video gốc
    # --- Watermark / logo ---
    watermark: Path | None = None         # ảnh logo chèn vào video
    watermark_position: str = "top-right"  # top-left/top-right/bottom-left/bottom-right/center
    watermark_scale: float = 0.15         # tỉ lệ chiều rộng logo so với video
    watermark_opacity: float = 1.0        # 0.0 - 1.0
    # --- Caption / text cố định ---
    caption_text: str = ""                # chữ chèn lên video (rỗng = không dùng)
    caption_source: str = "fixed"         # fixed / f2_filename / f2_textfile
    caption_position: str = "bottom"      # top/center/bottom
    caption_size: int = 48                # cỡ chữ (px)
    caption_color: str = "white"          # màu chữ
    # --- Hiệu ứng ---
    fade_in_out: bool = False             # fade đầu/cuối video
    fade_duration: float = 0.5            # giây
    # --- Đầu ra & năng suất ---
    workers: int = 1                      # số luồng xử lý song song
    seed: int | None = None               # seed cho chế độ ngẫu nhiên
    strip_metadata: bool = False          # xoá metadata để chống trùng lặp
    # --- Template overlay (mẫu chữ + sticker) ---
    template: object | None = None        # Template hoặc None


@dataclass
class PairResult:
    """Kết quả xử lý một cặp (hoặc một video thừa)."""

    index: int
    stt: str
    file1: Path | None
    file2: Path | None
    status: MergeStatus
    detail: str = ""               # lý do lỗi/bỏ qua nếu có
    output_path: Path | None = None


@dataclass
class ProgressEvent:
    """Sự kiện engine đẩy vào queue để GUI cập nhật.

    kind:
      - "init":     bắt đầu, có total và leftovers
      - "pair":     một cặp đã xử lý xong, cập nhật processed/total
      - "status":   thông điệp trạng thái kèm result (tuỳ chọn)
      - "stopping": đã ghi nhận Stop_Request, đang chờ dừng
      - "done":     kết thúc toàn bộ, kèm summary trong message/result
    """

    kind: str
    processed: int = 0
    total: int = 0
    leftovers: int = 0
    message: str = ""
    result: PairResult | None = None
    summary: "RunSummary | None" = None


@dataclass
class RunSummary:
    """Tổng kết một lần chạy."""

    succeeded: int = 0
    failed: int = 0
    unused: int = 0
    not_processed: int = 0  # số cặp chưa xử lý khi dừng do Stop_Request
    stopped: bool = False
    results: list[PairResult] = field(default_factory=list)
