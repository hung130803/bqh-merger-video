"""Phiên bản ứng dụng BQH Merger Video.

Mỗi lần phát hành bản mới:
  1. Tăng APP_VERSION (vd 1.0.0 -> 1.0.1).
  2. Build lại .exe (xem build_exe.bat).
  3. Tạo một Release mới trên GitHub với tag trùng phiên bản (vd v1.0.1)
     và đính kèm file .exe.
Người dùng bấm "Cập nhật bản mới" trong app sẽ tự tải .exe mới về.
"""

APP_NAME = "BQH Merger Video"
APP_VERSION = "1.0.0"

# Repo GitHub để kiểm tra/tải bản cập nhật
GITHUB_OWNER = "hung130803"
GITHUB_REPO = "bqh-merger-video"

# Tên file .exe đính kèm trong Release (phải trùng khi upload)
EXE_ASSET_NAME = "BQH_Merger_Video.exe"
