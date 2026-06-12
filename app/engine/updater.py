"""Cập nhật ứng dụng từ GitHub bằng git.

Cơ chế: thư mục cài đặt là một bản clone git từ GitHub. Khi bấm "Cập nhật",
tool chạy `git pull` để kéo code mới nhất. Hỗ trợ kiểm tra xem có bản mới
không (so sánh commit local với remote).

Yêu cầu: máy người dùng có cài git, và thư mục ứng dụng được clone từ git
(không phải tải zip). README hướng dẫn cách clone.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

# Thư mục gốc ứng dụng (chứa main.py) = cha của thư mục app/
APP_ROOT = Path(__file__).resolve().parents[2]


def _no_window_flag() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _git(*args: str, timeout: float = 60) -> tuple[int, str, str]:
    """Chạy lệnh git trong thư mục ứng dụng. Trả (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(APP_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            creationflags=_no_window_flag(),
        )
    except FileNotFoundError:
        return 127, "", "Chưa cài git trên máy."
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, "", str(exc)
    return (
        result.returncode,
        result.stdout.decode("utf-8", "replace").strip(),
        result.stderr.decode("utf-8", "replace").strip(),
    )


@dataclass
class UpdateResult:
    ok: bool
    message: str
    changed: bool = False  # True nếu code đã được cập nhật


def is_git_repo() -> bool:
    code, out, _ = _git("rev-parse", "--is-inside-work-tree")
    return code == 0 and out == "true"


def has_git() -> bool:
    code, _, _ = _git("--version")
    return code == 0


def check_for_update() -> UpdateResult:
    """Kiểm tra remote có commit mới hơn local không (không thay đổi gì)."""
    if not has_git():
        return UpdateResult(False, "Chưa cài git. Hãy cài Git for Windows.")
    if not is_git_repo():
        return UpdateResult(
            False,
            "Thư mục này chưa phải bản clone từ GitHub. Xem README để clone.",
        )
    code, _, err = _git("fetch", "--quiet")
    if code != 0:
        return UpdateResult(False, f"Không kết nối được GitHub: {err}")

    # So sánh local vs remote upstream
    code, local, _ = _git("rev-parse", "@")
    code2, remote, _ = _git("rev-parse", "@{u}")
    if code != 0 or code2 != 0:
        return UpdateResult(False, "Không xác định được nhánh theo dõi remote.")

    if local == remote:
        return UpdateResult(True, "Bạn đang dùng bản mới nhất.", changed=False)
    return UpdateResult(True, "Có bản cập nhật mới trên GitHub.", changed=True)


def pull_update() -> UpdateResult:
    """Kéo code mới nhất từ GitHub (git pull)."""
    if not has_git():
        return UpdateResult(False, "Chưa cài git. Hãy cài Git for Windows.")
    if not is_git_repo():
        return UpdateResult(
            False,
            "Thư mục này chưa phải bản clone từ GitHub. Xem README để clone.",
        )

    code, out, err = _git("pull", "--ff-only", timeout=120)
    if code != 0:
        # Thường do người dùng sửa file cục bộ gây xung đột
        return UpdateResult(
            False,
            "Cập nhật thất bại (có thể do file bị sửa cục bộ):\n"
            + (err or out),
        )

    if "Already up to date" in out or "Already up-to-date" in out:
        return UpdateResult(True, "Bạn đang dùng bản mới nhất.", changed=False)
    return UpdateResult(
        True,
        "Đã cập nhật bản mới! Hãy khởi động lại ứng dụng để áp dụng.\n" + out,
        changed=True,
    )
