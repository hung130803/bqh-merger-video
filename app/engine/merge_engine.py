"""Engine điều phối toàn bộ một lần chạy ghép video.

Không import customtkinter — engine chạy độc lập trên luồng nền và giao tiếp
với GUI qua queue.Queue (ProgressEvent) và threading.Event (stop).
"""

from __future__ import annotations

import queue
import random
import shutil
import threading
from dataclasses import replace
from pathlib import Path

from . import naming
from .ffmpeg_runner import FfmpegError, FfmpegRunner, FfprobeError
from .models import (
    SUPPORTED_FORMATS,
    MergeConfig,
    MergeOrder,
    MergeStatus,
    PairResult,
    ProgressEvent,
    ResizeMode,
    RunSummary,
)


# ---------------------------------------------------------------- pure helpers
def compute_keep_window(
    duration: float, trim_head: float, trim_tail: float
) -> float | None:
    """Tính thời lượng giữ lại sau khi cắt đầu/cuối.

    Trả None khi duration - trim_head - trim_tail <= 0, ngược lại trả giá trị
    dương đó.
    """
    keep = duration - trim_head - trim_tail
    if keep <= 0:
        return None
    return keep


def scan_folder(folder: Path) -> list[Path]:
    """Liệt kê file video nằm trực tiếp trong folder (không đệ quy).

    Lọc theo SUPPORTED_FORMATS, so khớp phần mở rộng không phân biệt hoa thường.
    Kết quả sắp xếp theo tên (case-insensitive) để có thứ tự ổn định.
    """
    if not folder.is_dir():
        return []
    files = [
        p
        for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_FORMATS
    ]
    files.sort(key=lambda p: p.name.lower())
    return files


def pair_videos(
    files1: list[Path],
    files2: list[Path],
    order: MergeOrder,
    rng: random.Random | None = None,
) -> tuple[list[tuple[Path, Path]], list[Path]]:
    """Ghép cặp một-đối-một theo vị trí.

    Trả về (pairs, leftovers). Số cặp = min(len1, len2). leftovers là phần
    thừa của danh sách dài hơn. SORTED sắp xếp theo tên (case-insensitive);
    SHUFFLE xáo trộn độc lập hai danh sách bằng rng truyền vào (để test
    xác định).
    """
    list1 = list(files1)
    list2 = list(files2)

    if order is MergeOrder.SORTED:
        list1.sort(key=lambda p: p.name.lower())
        list2.sort(key=lambda p: p.name.lower())
    else:  # SHUFFLE
        r = rng if rng is not None else random.Random()
        r.shuffle(list1)
        r.shuffle(list2)

    n = min(len(list1), len(list2))
    pairs = [(list1[i], list2[i]) for i in range(n)]

    leftovers: list[Path] = []
    if len(list1) > n:
        leftovers.extend(list1[n:])
    if len(list2) > n:
        leftovers.extend(list2[n:])

    return pairs, leftovers


# ----------------------------------------------------------------- the engine
class MergeEngine:
    """Điều phối scan → pair → (per pair) trim → concat → verify → safe move."""

    def __init__(
        self,
        config: MergeConfig,
        event_queue: "queue.Queue[ProgressEvent]",
        stop_event: threading.Event,
        runner: FfmpegRunner | None = None,
    ) -> None:
        self.config = config
        self.queue = event_queue
        self.stop_event = stop_event
        self.runner = runner if runner is not None else FfmpegRunner()
        self._total = 0
        self._single_thread = True

        # Thư mục con đầu ra
        out = config.output_folder
        self.merged_dir = out / "merged"
        self.used1_dir = out / "used_folder_1"
        self.used2_dir = out / "used_folder_2"

    # ----------------------------------------------------------------- helpers
    def _emit(self, event: ProgressEvent) -> None:
        self.queue.put(event)

    def _ensure_dirs(self) -> None:
        for d in (self.merged_dir, self.used1_dir, self.used2_dir):
            d.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------------------- run
    def run(self) -> RunSummary:
        """Chạy toàn bộ pipeline. Trả RunSummary."""
        summary = RunSummary()

        # Tạo thư mục con (lỗi quyền ghi -> báo và dừng)
        try:
            self._ensure_dirs()
        except OSError as exc:
            self._emit(
                ProgressEvent(
                    kind="done",
                    message=f"Không tạo được thư mục đầu ra: {exc}",
                    summary=summary,
                )
            )
            return summary

        files1 = scan_folder(self.config.folder1)
        files2 = scan_folder(self.config.folder2)

        rng = random.Random(getattr(self.config, "seed", None))
        pairs, leftovers = pair_videos(
            files1, files2, self.config.merge_order, rng
        )

        total = len(pairs)
        summary.unused = len(leftovers)
        self._total = total

        self._emit(
            ProgressEvent(
                kind="init",
                processed=0,
                total=total,
                leftovers=len(leftovers),
                message=(
                    f"Tìm thấy {len(files1)} video ở Folder 1, "
                    f"{len(files2)} video ở Folder 2. "
                    f"Dự kiến ghép {total} cặp."
                ),
            )
        )

        # Ghi nhận các video thừa
        for left in leftovers:
            result = PairResult(
                index=-1,
                stt="",
                file1=left,
                file2=None,
                status=MergeStatus.UNUSED_NO_PAIR,
                detail=f"Video thừa không có cặp: {left.name}",
            )
            summary.results.append(result)
            self._emit(ProgressEvent(kind="status", result=result))

        workers = max(1, int(getattr(self.config, "workers", 1) or 1))
        self._single_thread = workers <= 1
        if workers > 1 and total > 1:
            self._run_parallel(pairs, total, summary, workers)
        else:
            self._run_sequential(pairs, total, summary)

        self._emit(
            ProgressEvent(
                kind="done",
                processed=summary.succeeded + summary.failed,
                total=total,
                leftovers=summary.unused,
                summary=summary,
                message=(
                    f"Hoàn tất: {summary.succeeded} thành công, "
                    f"{summary.failed} lỗi, {summary.unused} video thừa."
                    + (
                        f", {summary.not_processed} cặp chưa xử lý."
                        if summary.stopped
                        else ""
                    )
                ),
            )
        )
        return summary

    def _tally(self, result: PairResult, summary: RunSummary) -> None:
        if result.status is MergeStatus.DONE:
            summary.succeeded += 1
        elif result.status is MergeStatus.FAILED:
            summary.failed += 1

    def _run_sequential(self, pairs, total, summary) -> None:
        for i, (f1, f2) in enumerate(pairs, start=1):
            if self.stop_event.is_set():
                summary.stopped = True
                summary.not_processed = total - (i - 1)
                self._emit(
                    ProgressEvent(
                        kind="stopping", processed=i - 1, total=total,
                        message="Đã dừng theo yêu cầu.",
                    )
                )
                break

            result = self.process_pair(i, f1, f2)
            summary.results.append(result)
            self._tally(result, summary)
            self._emit(
                ProgressEvent(
                    kind="pair", processed=i, total=total, result=result
                )
            )

    def _run_parallel(self, pairs, total, summary, workers) -> None:
        """Xử lý nhiều cặp song song bằng ThreadPoolExecutor.

        ffmpeg là tiến trình con nên chạy song song giúp tận dụng CPU. Thứ tự
        hoàn tất không cố định nhưng STT (index) vẫn gắn đúng từng cặp.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        processed = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self.process_pair, i, f1, f2): i
                for i, (f1, f2) in enumerate(pairs, start=1)
            }
            for fut in as_completed(futures):
                if self.stop_event.is_set():
                    summary.stopped = True
                result = fut.result()
                summary.results.append(result)
                self._tally(result, summary)
                processed += 1
                self._emit(
                    ProgressEvent(
                        kind="pair", processed=processed, total=total,
                        result=result,
                    )
                )
        if summary.stopped:
            summary.not_processed = max(0, total - processed)

    def _caption_for_template(self, f2: Path) -> str:
        """Chữ theo từng video F2 để thay token {ten} trong mẫu.

        Theo caption_source: filename -> tên file F2; textfile -> nội dung
        .txt cùng tên; fixed/khác -> mặc định dùng tên file F2.
        """
        source = getattr(self.config, "caption_source", "fixed")
        if source == "f2_textfile":
            txt = f2.with_suffix(".txt")
            if txt.is_file():
                try:
                    return txt.read_text(encoding="utf-8").strip()
                except OSError:
                    return ""
            return ""
        # filename hoặc fixed: dùng tên file (bỏ phần mở rộng)
        return f2.stem

    def _resolve_caption(self, f2: Path) -> str | None:
        """Lấy caption cho từng video Folder 2 theo caption_source.

        - "fixed": dùng caption_text chung (trả None để runner tự lấy).
        - "f2_filename": dùng tên file F2 (bỏ phần mở rộng) làm caption.
        - "f2_textfile": đọc file .txt cùng tên cạnh video F2; nếu không có
          thì không chèn chữ cho video đó.
        """
        source = getattr(self.config, "caption_source", "fixed")
        if source == "f2_filename":
            return f2.stem
        if source == "f2_textfile":
            txt = f2.with_suffix(".txt")
            if txt.is_file():
                try:
                    content = txt.read_text(encoding="utf-8").strip()
                    return content if content else ""
                except OSError:
                    return ""
            return ""  # không có file txt -> không chèn chữ
        return None  # "fixed": để runner dùng caption_text chung

    # -------------------------------------------------------------- per pair
    def process_pair(self, index: int, f1: Path, f2: Path) -> PairResult:
        """Xử lý một cặp: trim → resize/concat → verify → safe move.

        Luôn cô lập lỗi: mọi ngoại lệ không lường trước trở thành FAILED.
        """
        stt = naming.format_stt(index)
        result = PairResult(
            index=index, stt=stt, file1=f1, file2=f2, status=MergeStatus.FAILED
        )

        try:
            cfg = self.config

            # 1. Đọc thời lượng (unreadable -> skip)
            try:
                dur1 = self.runner.probe_duration(f1)
                dur2 = self.runner.probe_duration(f2)
            except FfprobeError as exc:
                result.status = MergeStatus.SKIPPED_UNREADABLE
                result.detail = f"Không đọc được video: {exc}"
                return result

            # 2. Tính cửa sổ giữ lại (quá ngắn -> skip)
            keep1 = compute_keep_window(dur1, cfg.trim_head_1, cfg.trim_tail_1)
            keep2 = compute_keep_window(dur2, cfg.trim_head_2, cfg.trim_tail_2)
            if keep1 is None or keep2 is None:
                result.status = MergeStatus.SKIPPED_TOO_SHORT
                result.detail = "Video quá ngắn sau khi cắt đầu/cuối."
                return result

            # 3. Chuẩn bị tham số resize
            f1_res = None
            if cfg.resize_mode is ResizeMode.KEEP_SIZE:
                try:
                    f1_res = self.runner.probe_resolution(f1)
                except FfprobeError as exc:
                    result.status = MergeStatus.SKIPPED_UNREADABLE
                    result.detail = f"Không đọc được độ phân giải F1: {exc}"
                    return result

            f1_has_audio = self.runner.probe_has_audio(f1)
            f2_has_audio = self.runner.probe_has_audio(f2)

            # Resolve caption theo từng video Folder 2 (đúng sản phẩm)
            caption_override = self._resolve_caption(f2)

            # Mẫu (template): điền tên video F2 vào lớp chữ của mẫu.
            run_cfg = cfg
            tpl = getattr(cfg, "template", None)
            tpl_has_text = (
                tpl is not None and not tpl.is_empty() and tpl.text_layers
            )
            if tpl is not None and not tpl.is_empty():
                per_video_text = self._caption_for_template(f2)
                new_tpl = _template_with_name(tpl, per_video_text,
                                              self.config)
                if new_tpl is not tpl:
                    run_cfg = replace(cfg, template=new_tpl)

            # Nếu mẫu đã có lớp chữ và đang ở chế độ "chữ theo video", KHÔNG
            # vẽ thêm caption dưới (tránh trùng + tràn viền). Chữ đã nằm trong
            # mẫu rồi.
            source = getattr(self.config, "caption_source", "fixed")
            if tpl_has_text and source in ("f2_filename", "f2_textfile"):
                caption_override = ""

            # 4. Tên file kết quả (chống trùng)
            out_name = naming.merged_name(stt, f1.stem, f2.stem)
            out_path = naming.resolve_collision(self.merged_dir / out_name)

            # 5. Ghép bằng ffmpeg
            def _cb(pct: float) -> None:
                self._emit(
                    ProgressEvent(
                        kind="progress", processed=index,
                        total=self._total, message=f"{pct:.3f}",
                    )
                )

            try:
                self.runner.run_concat(
                    f1, f2, out_path,
                    run_cfg.trim_head_1, keep1,
                    run_cfg.trim_head_2, keep2,
                    run_cfg, f1_res,
                    f1_has_audio=f1_has_audio,
                    f2_has_audio=f2_has_audio,
                    progress_cb=_cb if self._single_thread else None,
                    caption_override=caption_override,
                )
            except FfmpegError as exc:
                # Nếu đang dùng GPU mà lỗi, thử lại bằng CPU (fallback an toàn).
                if getattr(cfg, "use_gpu", False):
                    _cleanup_partial(out_path)
                    cpu_cfg = replace(run_cfg, use_gpu=False)
                    try:
                        self.runner.run_concat(
                            f1, f2, out_path,
                            cpu_cfg.trim_head_1, keep1,
                            cpu_cfg.trim_head_2, keep2,
                            cpu_cfg, f1_res,
                            f1_has_audio=f1_has_audio,
                            f2_has_audio=f2_has_audio,
                            progress_cb=_cb if self._single_thread else None,
                            caption_override=caption_override,
                        )
                    except FfmpegError as exc2:
                        result.status = MergeStatus.FAILED
                        result.detail = f"Lỗi ffmpeg (cả GPU và CPU): {exc2}"
                        _cleanup_partial(out_path)
                        return result
                else:
                    result.status = MergeStatus.FAILED
                    result.detail = f"Lỗi ffmpeg: {exc}"
                    _cleanup_partial(out_path)
                    return result

            # 6. Verify output tồn tại và > 0 byte
            if not (out_path.exists() and out_path.stat().st_size > 0):
                result.status = MergeStatus.FAILED
                result.detail = "File kết quả không hợp lệ (không tồn tại/0 byte)."
                _cleanup_partial(out_path)
                return result

            result.output_path = out_path

            # 7. Di chuyển an toàn video gốc (chỉ khi output hợp lệ)
            #    Giữ NGUYÊN tên file gốc, chỉ move sang used_folder để biết
            #    video nào đã dùng. Nếu trùng tên thì thêm hậu tố cho an toàn.
            try:
                used1_target = naming.resolve_collision(
                    self.used1_dir / f1.name
                )
                used2_target = naming.resolve_collision(
                    self.used2_dir / f2.name
                )
                shutil.move(str(f1), str(used1_target))
                shutil.move(str(f2), str(used2_target))

                if not (used1_target.exists() and used2_target.exists()):
                    result.status = MergeStatus.FAILED
                    result.detail = "Di chuyển video gốc không xác nhận được."
                    return result
            except OSError as exc:
                result.status = MergeStatus.FAILED
                result.detail = f"Lỗi di chuyển video gốc: {exc}"
                return result

            result.status = MergeStatus.DONE
            result.detail = ""
            return result

        except Exception as exc:  # noqa: BLE001 - cô lập lỗi toàn diện
            result.status = MergeStatus.FAILED
            result.detail = f"Lỗi không lường trước: {exc}"
            return result


def _template_with_name(template, per_video_text: str, config):
    """Trả về bản sao template với chữ theo video F2.

    Quy tắc:
    - Nếu có lớp chữ chứa token {ten}: thay {ten} bằng per_video_text.
    - Ngược lại, nếu đang ở chế độ "chữ theo video" (f2_filename/f2_textfile):
      thay nội dung của lớp chữ ĐẦU TIÊN bằng per_video_text (giữ nguyên kiểu
      dáng/vị trí/cỡ đã thiết kế).
    - Nếu không rơi vào trường hợp nào: trả template gốc.
    """
    import copy

    source = getattr(config, "caption_source", "fixed")
    has_token = any(
        "{ten}" in (tl.text or "") for tl in template.text_layers
    )

    if has_token:
        new_tpl = copy.deepcopy(template)
        for tl in new_tpl.text_layers:
            if "{ten}" in (tl.text or ""):
                tl.text = tl.text.replace("{ten}", per_video_text)
        return new_tpl

    if source in ("f2_filename", "f2_textfile") and template.text_layers:
        new_tpl = copy.deepcopy(template)
        new_tpl.text_layers[0].text = per_video_text
        return new_tpl

    return template


def _cleanup_partial(path: Path) -> None:
    """Xóa file kết quả lỗi/dở dang nếu có, bỏ qua mọi lỗi xóa."""
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
