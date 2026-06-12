"""Bọc các lệnh ffmpeg/ffprobe qua subprocess.

Chịu trách nhiệm: đọc thời lượng/độ phân giải, dựng filter_complex cho từng
chế độ resize, và chạy một lệnh ffmpeg duy nhất để ghép hai clip.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .models import MergeConfig, QualityPreset, ResizeMode, ResizeSubmode


class FfmpegError(RuntimeError):
    """Lỗi khi chạy ffmpeg (exit code != 0 hoặc output không hợp lệ)."""


class FfprobeError(RuntimeError):
    """Lỗi khi chạy ffprobe hoặc không đọc được thông tin video."""


def _no_window_flag() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _default_ffmpeg() -> str:
    try:
        from .ffmpeg_paths import ffmpeg_path
        return ffmpeg_path()
    except Exception:
        return "ffmpeg"


def _default_ffprobe() -> str:
    try:
        from .ffmpeg_paths import ffprobe_path
        return ffprobe_path()
    except Exception:
        return "ffprobe"


def _escape_drawtext(text: str) -> str:
    """Escape ký tự đặc biệt cho filter drawtext của ffmpeg."""
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("'", "\u2019")  # nháy đơn -> nháy cong tránh lỗi
    text = text.replace("%", "\\%")
    return text


def _escape_fontpath(path: str) -> str:
    """Escape đường dẫn font cho drawtext (Windows: đổi \\ thành / và escape :)."""
    p = path.replace("\\", "/")
    p = p.replace(":", "\\:")
    return p


def _overlay_position(pos: str) -> str:
    """Trả về toạ độ overlay cho từng vị trí watermark."""
    margin = 20
    return {
        "top-left": f"{margin}:{margin}",
        "top-right": f"main_w-overlay_w-{margin}:{margin}",
        "bottom-left": f"{margin}:main_h-overlay_h-{margin}",
        "bottom-right": f"main_w-overlay_w-{margin}:main_h-overlay_h-{margin}",
        "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
    }.get(pos, f"main_w-overlay_w-{margin}:{margin}")


def _atempo_chain(speed: float) -> str:
    """Tạo chuỗi atempo để đổi tốc độ audio.

    atempo của ffmpeg chỉ chấp nhận 0.5..2.0 trong một lần, nên với speed
    nằm ngoài khoảng đó ta nối nhiều atempo lại. Trả về chuỗi bắt đầu bằng
    dấu phẩy (ví dụ: ",atempo=2.0,atempo=1.5") hoặc chuỗi rỗng nếu speed=1.
    """
    if speed == 1.0:
        return ""
    factors: list[float] = []
    s = speed
    while s > 2.0:
        factors.append(2.0)
        s /= 2.0
    while s < 0.5:
        factors.append(0.5)
        s /= 0.5
    factors.append(s)
    return "".join(f",atempo={f:.4f}" for f in factors)


class FfmpegRunner:
    """Lớp bọc ffmpeg/ffprobe."""

    def __init__(
        self, ffmpeg_path: str | None = None, ffprobe_path: str | None = None
    ) -> None:
        self.ffmpeg_path = ffmpeg_path or _default_ffmpeg()
        self.ffprobe_path = ffprobe_path or _default_ffprobe()

    # ------------------------------------------------------------------ probe
    def _run_probe(self, cmd: list[str]) -> str:
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                creationflags=_no_window_flag(),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise FfprobeError(f"Không chạy được ffprobe: {exc}") from exc

        if result.returncode != 0:
            err = result.stderr.decode("utf-8", "replace").strip()
            raise FfprobeError(f"ffprobe lỗi: {err}")
        return result.stdout.decode("utf-8", "replace").strip()

    def probe_duration(self, path: Path) -> float:
        """Đọc thời lượng (giây) của video bằng ffprobe.

        Raise FfprobeError nếu ffprobe lỗi hoặc không parse được thời lượng.
        """
        raw = self._run_probe([
            self.ffprobe_path,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ])
        try:
            duration = float(raw)
        except ValueError as exc:
            raise FfprobeError(
                f"Không đọc được thời lượng (giá trị: {raw!r})"
            ) from exc

        if duration <= 0:
            raise FfprobeError(f"Thời lượng không hợp lệ: {duration}")
        return duration

    def probe_resolution(self, path: Path) -> tuple[int, int]:
        """Đọc (width, height) của stream video đầu tiên."""
        raw = self._run_probe([
            self.ffprobe_path,
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0",
            str(path),
        ])
        try:
            w_str, h_str = raw.lower().split("x")
            return int(w_str), int(h_str)
        except ValueError as exc:
            raise FfprobeError(
                f"Không đọc được độ phân giải (giá trị: {raw!r})"
            ) from exc

    def probe_has_audio(self, path: Path) -> bool:
        """Trả True nếu video có ít nhất một audio stream."""
        try:
            raw = self._run_probe([
                self.ffprobe_path,
                "-v", "error",
                "-select_streams", "a",
                "-show_entries", "stream=index",
                "-of", "csv=p=0",
                str(path),
            ])
        except FfprobeError:
            return False
        return bool(raw.strip())

    # ----------------------------------------------------------- filter graph
    def _video_norm_chain(
        self, config: MergeConfig, f1_res: tuple[int, int] | None
    ) -> tuple[str, str]:
        """Trả về (chain cho input 0, chain cho input 1) chuẩn hóa video."""
        fps = config.fps

        if config.resize_mode is ResizeMode.NINE_SIXTEEN:
            w, h = config.target_width, config.target_height
            if config.resize_submode is ResizeSubmode.FIT_PAD:
                norm = (
                    f"fps={fps},"
                    f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
                )
                return norm, norm
            # FILL_CROP
            norm = (
                f"fps={fps},"
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},setsar=1"
            )
            return norm, norm

        # KEEP_SIZE: chuẩn hóa F2 về đúng WxH của F1
        if f1_res is None:
            raise ValueError("KEEP_SIZE cần f1_res")
        w1, h1 = f1_res
        norm0 = f"fps={fps},setsar=1"
        norm1 = (
            f"fps={fps},"
            f"scale={w1}:{h1}:force_original_aspect_ratio=decrease,"
            f"pad={w1}:{h1}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1"
        )
        return norm0, norm1

    def build_filter_complex(
        self, config: MergeConfig, f1_res: tuple[int, int] | None
    ) -> str:
        """Dựng chuỗi filter_complex (giả định cả hai input đều có audio).

        Dùng cho mục đích kiểm thử/đọc hiểu. run_concat tự dựng phiên bản
        có xử lý audio fallback.
        """
        norm0, norm1 = self._video_norm_chain(config, f1_res)
        return (
            f"[0:v]{norm0}[v0];"
            f"[1:v]{norm1}[v1];"
            f"[v0][0:a][v1][1:a]concat=n=2:v=1:a=1[v][a]"
        )

    def _apply_template(
        self, template, parts: list[str], cmd: list[str],
        cur_v: str, next_index: int, frame_wh: tuple[int, int],
        tmp_dir: Path, tmp_pngs: list,
    ) -> tuple[str, int]:
        """Áp các lớp của Template lên nhãn video hiện tại.

        Text layer -> render PNG (chữ + nền bo góc) bằng Pillow rồi overlay,
        để có nền bo góc tròn + độ mờ thật, khớp khung xem trước.
        Sticker layer -> overlay ảnh.
        Trả về (nhãn video mới, next_index cập nhật).
        """
        from .text_render import render_text_layer_png

        fw, fh = frame_wh
        for tl in template.text_layers:
            if not (tl.text or "").strip():
                continue
            try:
                rendered = render_text_layer_png(tl, fw, fh, tmp_dir)
            except Exception:
                rendered = None
            if rendered is None:
                continue
            png_path, _, _ = rendered
            tmp_pngs.append(png_path)
            cmd += ["-i", str(png_path)]
            tin = next_index
            next_index += 1
            # PNG đã cùng kích thước khung, overlay tại (0,0); scale2ref để
            # khớp đúng kích thước video chính phòng khi lệch.
            ref_label = f"tvs{tin}"
            scaled = f"tsc{tin}"
            parts.append(
                f"[{cur_v}][{tin}:v]scale2ref=w=main_w:h=main_h"
                f"[{ref_label}][{scaled}]"
            )
            out_label = f"tvo{tin}"
            parts.append(
                f"[{ref_label}][{scaled}]overlay=0:0[{out_label}]"
            )
            cur_v = out_label

        for sl in template.sticker_layers:
            if not sl.path or not Path(sl.path).is_file():
                continue
            cmd += ["-i", str(sl.path)]
            stk_in = next_index
            next_index += 1
            raw_label = f"stk{stk_in}"
            parts.append(
                f"[{stk_in}:v]format=rgba,"
                f"colorchannelmixer=aa={sl.opacity}[{raw_label}]"
            )
            ref_label = f"vs{stk_in}"
            scaled = f"sc{stk_in}"
            parts.append(
                f"[{cur_v}][{raw_label}]"
                f"scale2ref=w=main_w*{sl.scale_frac}:h=ow/mdar"
                f"[{ref_label}][{scaled}]"
            )
            x_expr = f"main_w*{sl.x}-overlay_w/2"
            y_expr = f"main_h*{sl.y}-overlay_h/2"
            out_label = f"vo{stk_in}"
            parts.append(
                f"[{ref_label}][{scaled}]overlay={x_expr}:{y_expr}[{out_label}]"
            )
            cur_v = out_label

        return cur_v, next_index

    # ------------------------------------------------------------------- merge
    def run_concat(
        self,
        f1: Path,
        f2: Path,
        output: Path,
        head1: float,
        keep1: float,
        head2: float,
        keep2: float,
        config: MergeConfig,
        f1_res: tuple[int, int] | None,
        f1_has_audio: bool = True,
        f2_has_audio: bool = True,
        progress_cb=None,
        caption_override: str | None = None,
    ) -> None:
        """Ghép hai clip bằng một lệnh ffmpeg duy nhất.

        head*/keep* là điểm bắt đầu và thời lượng giữ lại (giây) của mỗi clip.
        Khi một input thiếu audio, dùng nguồn câm anullsrc để concat hợp lệ.
        Hỗ trợ nhạc nền (background_music), tắt tiếng gốc (mute_original),
        và encoder GPU NVENC (use_gpu). Khi NVENC lỗi sẽ raise FfmpegError
        để engine fallback về CPU.
        Raise FfmpegError nếu exit code != 0.
        """
        norm0, norm1 = self._video_norm_chain(config, f1_res)
        crf = (
            config.quality.value
            if isinstance(config.quality, QualityPreset)
            else 23
        )
        ar = config.audio_rate
        total_dur = keep1 + keep2

        # Inputs: 0 = f1, 1 = f2; thêm anullsrc cho input nào thiếu audio.
        cmd = [self.ffmpeg_path, "-y"]
        cmd += ["-ss", f"{head1}", "-t", f"{keep1}", "-i", str(f1)]
        cmd += ["-ss", f"{head2}", "-t", f"{keep2}", "-i", str(f2)]

        next_index = 2
        if f1_has_audio:
            a0_label = "[0:a]"
        else:
            cmd += [
                "-f", "lavfi", "-t", f"{keep1}",
                "-i", f"anullsrc=channel_layout=stereo:sample_rate={ar}",
            ]
            a0_label = f"[{next_index}:a]"
            next_index += 1

        if f2_has_audio:
            a1_label = "[1:a]"
        else:
            cmd += [
                "-f", "lavfi", "-t", f"{keep2}",
                "-i", f"anullsrc=channel_layout=stereo:sample_rate={ar}",
            ]
            a1_label = f"[{next_index}:a]"
            next_index += 1

        # Input nhạc nền (nếu có): lặp lại để đủ độ dài rồi cắt theo total_dur.
        music = getattr(config, "background_music", None)
        music_label = None
        if music is not None:
            cmd += ["-stream_loop", "-1", "-i", str(music)]
            music_label = f"[{next_index}:a]"
            next_index += 1

        # Xây filter graph video + audio.
        parts = [
            f"[0:v]{norm0}[v0]",
            f"[1:v]{norm1}[v1]",
        ]

        mute_original = getattr(config, "mute_original", False)
        music_volume = float(getattr(config, "music_volume", 1.0))
        speed = float(getattr(config, "video_speed", 1.0) or 1.0)
        if speed <= 0:
            speed = 1.0
        vol_boost = float(getattr(config, "volume_boost", 1.0) or 1.0)

        # Bộ lọc tốc độ: video dùng setpts=PTS/speed, audio dùng atempo
        # (atempo chỉ chấp nhận 0.5..2.0 nên tách thành chuỗi nhiều atempo).
        v_speed = f",setpts=PTS/{speed}" if speed != 1.0 else ""
        a_tempo_chain = _atempo_chain(speed) if speed != 1.0 else ""

        boost_step = f",volume={vol_boost}" if vol_boost != 1.0 else ""
        post_step = f"{boost_step}{a_tempo_chain},aresample={ar}"
        if not post_step.startswith(","):
            post_step = "," + post_step
        # Loại dấu phẩy đầu nếu rỗng (không xảy ra vì luôn có aresample)
        post_step = post_step.lstrip(",")

        if mute_original and music_label is not None:
            # Bỏ tiếng gốc, chỉ ghép video, audio lấy hoàn toàn từ nhạc nền.
            parts.append(f"[v0][v1]concat=n=2:v=1:a=0[vc]")
            parts.append(f"[vc]setpts=PTS/{speed}[vbase]" if v_speed
                         else "[vc]null[vbase]")
            parts.append(
                f"{music_label}atrim=0:{total_dur},asetpts=PTS-STARTPTS,"
                f"volume={music_volume}{a_tempo_chain},aresample={ar}[a]"
            )
        elif music_label is not None:
            # Ghép audio gốc + boost, trộn nhạc nền, đổi tempo cuối cùng.
            parts.append(
                f"[v0]{a0_label}[v1]{a1_label}concat=n=2:v=1:a=1[vc][aorig0]"
            )
            parts.append(f"[vc]setpts=PTS/{speed}[vbase]" if v_speed
                         else "[vc]null[vbase]")
            parts.append(f"[aorig0]volume={vol_boost}[aorig]")
            parts.append(
                f"{music_label}atrim=0:{total_dur},asetpts=PTS-STARTPTS,"
                f"volume={music_volume}[abg]"
            )
            parts.append(
                f"[aorig][abg]amix=inputs=2:duration=first:"
                f"dropout_transition=0{a_tempo_chain},aresample={ar}[a]"
            )
        else:
            # Không nhạc nền: ghép video + audio gốc; áp boost & speed.
            parts.append(
                f"[v0]{a0_label}[v1]{a1_label}concat=n=2:v=1:a=1[vc][aorig]"
            )
            parts.append(f"[vc]setpts=PTS/{speed}[vbase]" if v_speed
                         else "[vc]null[vbase]")
            parts.append(f"[aorig]{post_step}[a]")

        # Thời lượng video cuối cùng (sau khi đổi tốc độ).
        out_dur = total_dur / speed

        # --- Fade in/out (tuỳ chọn) ---
        cur_v = "vbase"
        fade_in_out = getattr(config, "fade_in_out", False)
        fade_d = float(getattr(config, "fade_duration", 0.5) or 0.5)
        if fade_in_out and out_dur > 2 * fade_d:
            fade_out_st = max(0.0, out_dur - fade_d)
            parts.append(
                f"[{cur_v}]fade=t=in:st=0:d={fade_d},"
                f"fade=t=out:st={fade_out_st:.3f}:d={fade_d}[vfade]"
            )
            cur_v = "vfade"

        # --- Caption / text cố định (tuỳ chọn) ---
        caption = caption_override
        if caption is None:
            caption = getattr(config, "caption_text", "") or ""
        caption = caption.strip()
        if caption:
            csize = int(getattr(config, "caption_size", 48) or 48)
            ccolor = getattr(config, "caption_color", "white") or "white"
            cpos = getattr(config, "caption_position", "bottom")
            y_expr = {
                "top": "h*0.08",
                "center": "(h-text_h)/2",
                "bottom": "h-text_h-h*0.08",
            }.get(cpos, "h-text_h-h*0.08")
            esc = _escape_drawtext(caption)
            parts.append(
                f"[{cur_v}]drawtext=text='{esc}':"
                f"fontcolor={ccolor}:fontsize={csize}:"
                f"x=(w-text_w)/2:y={y_expr}:"
                f"box=1:boxcolor=black@0.5:boxborderw=12[vtxt]"
            )
            cur_v = "vtxt"

        # --- Watermark / logo (tuỳ chọn) ---
        watermark = getattr(config, "watermark", None)
        if watermark is not None:
            cmd += ["-i", str(watermark)]
            wm_input = next_index
            next_index += 1
            scale = float(getattr(config, "watermark_scale", 0.15) or 0.15)
            opacity = float(getattr(config, "watermark_opacity", 1.0) or 1.0)
            pos = getattr(config, "watermark_position", "top-right")
            overlay_xy = _overlay_position(pos)
            parts.append(
                f"[{wm_input}:v]format=rgba,"
                f"colorchannelmixer=aa={opacity}[wmraw]"
            )
            parts.append(
                f"[{cur_v}][wmraw]scale2ref=w=main_w*{scale}:h=ow/mdar"
                f"[mainv][wm]"
            )
            parts.append(f"[mainv][wm]overlay={overlay_xy}[vwm]")
            cur_v = "vwm"

        # --- Template overlay (mẫu chữ + sticker, tuỳ chọn) ---
        _tmp_dir = None
        _tmp_pngs: list = []
        template = getattr(config, "template", None)
        if template is not None and not template.is_empty():
            import tempfile as _tf
            _tmp_dir = Path(_tf.mkdtemp(prefix="bvm_txt_"))
            # Xác định kích thước khung đích để render chữ bằng Pillow.
            if config.resize_mode is ResizeMode.NINE_SIXTEEN:
                frame_wh = (config.target_width, config.target_height)
            elif f1_res is not None:
                frame_wh = f1_res
            else:
                frame_wh = (config.target_width, config.target_height)
            cur_v, next_index = self._apply_template(
                template, parts, cmd, cur_v, next_index, frame_wh,
                _tmp_dir, _tmp_pngs,
            )

        def _cleanup_tmp():
            for p in _tmp_pngs:
                try:
                    Path(p).unlink()
                except OSError:
                    pass
            if _tmp_dir is not None:
                try:
                    _tmp_dir.rmdir()
                except OSError:
                    pass

        # Hoàn thiện nhãn video cuối cùng.
        parts.append(f"[{cur_v}]null[v]")

        filter_complex = ";".join(parts)

        # Chọn encoder: GPU (NVENC) hoặc CPU (libx264).
        use_gpu = getattr(config, "use_gpu", False)
        if use_gpu:
            video_opts = [
                "-c:v", "h264_nvenc",
                "-rc", "vbr", "-cq", str(crf), "-preset", "p4",
            ]
        else:
            video_opts = ["-c:v", "libx264", "-crf", str(crf)]

        cmd += [
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            *video_opts,
            "-pix_fmt", "yuv420p", "-r", str(config.fps),
            "-c:a", "aac", "-ar", str(ar),
        ]

        # Xoá metadata để chống trùng lặp khi up hàng loạt.
        if getattr(config, "strip_metadata", False):
            cmd += ["-map_metadata", "-1", "-fflags", "+bitexact"]

        cmd += [str(output)]

        if progress_cb is None:
            # Chạy đơn giản, không theo dõi tiến độ.
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=_no_window_flag(),
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise FfmpegError(f"Không chạy được ffmpeg: {exc}") from exc

            if result.returncode != 0:
                err = result.stderr.decode("utf-8", "replace").strip()
                tail = "\n".join(err.splitlines()[-12:])
                _cleanup_tmp()
                raise FfmpegError(
                    f"ffmpeg kết thúc với mã {result.returncode}:\n{tail}"
                )
            _cleanup_tmp()
            return

        # Chạy có theo dõi tiến độ: thêm -progress pipe:1, đọc out_time.
        prog_cmd = list(cmd)
        prog_cmd.insert(1, "-progress")
        prog_cmd.insert(2, "pipe:1")
        prog_cmd.insert(3, "-nostats")
        total_us = max(1.0, out_dur * 1_000_000)

        import tempfile
        # stderr ghi ra file tạm để tránh deadlock khi buffer đầy.
        with tempfile.TemporaryFile(mode="w+") as errfile:
            try:
                proc = subprocess.Popen(
                    prog_cmd,
                    stdout=subprocess.PIPE,
                    stderr=errfile,
                    creationflags=_no_window_flag(),
                    text=True,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise FfmpegError(f"Không chạy được ffmpeg: {exc}") from exc

            assert proc.stdout is not None
            for line in proc.stdout:
                line = line.strip()
                if line.startswith(("out_time_us=", "out_time_ms=")):
                    raw = line.split("=", 1)[1]
                    try:
                        val = float(raw)
                    except ValueError:
                        continue
                    pct = max(0.0, min(1.0, val / total_us))
                    try:
                        progress_cb(pct)
                    except Exception:
                        pass
            proc.wait()
            if proc.returncode != 0:
                errfile.seek(0)
                err = errfile.read()
                tail = "\n".join(err.splitlines()[-12:])
                _cleanup_tmp()
                raise FfmpegError(
                    f"ffmpeg kết thúc với mã {proc.returncode}:\n{tail}"
                )
        _cleanup_tmp()
        try:
            progress_cb(1.0)
        except Exception:
            pass
