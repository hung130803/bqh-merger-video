# Implementation Plan: Batch Video Merger

## Overview

Triển khai Batch Video Merger theo từng bước tăng dần, bắt đầu từ khung dự án và data models, rồi tới các hàm thuần của engine (naming, ghép cặp, cửa sổ cắt, quét file) kèm unit test và property-based test (Hypothesis), tiếp đến lớp gọi ffmpeg/ffprobe, engine điều phối, GUI customtkinter, và cuối cùng là wiring + tài liệu. Mỗi bước xây trên bước trước và kết thúc bằng việc nối các thành phần lại với nhau, không để code mồ côi. Ngôn ngữ triển khai: **Python** (theo design). Test thuộc loại property/unit/integration được đánh dấu tùy chọn bằng `*`. GUI được xác minh thủ công theo checklist vì không phù hợp tự động hóa.

## Tasks

- [x] 1. Khung dự án và cấu trúc thư mục
  - [x] 1.1 Tạo cấu trúc thư mục và file scaffolding
    - Tạo cây thư mục `app/`, `app/ui/`, `app/engine/`, `tests/` kèm các file `__init__.py` cần thiết cho package
    - Tạo `requirements.txt` liệt kê `customtkinter`, `pytest`, `hypothesis`
    - Tạo `main.py` ở gốc dưới dạng stub entry point (hàm `main()` rỗng và khối `if __name__ == "__main__"`)
    - _Requirements: 8.1, 11.1_

- [x] 2. Data models và enums
  - [x] 2.1 Định nghĩa toàn bộ dataclasses và enums trong `app/engine/models.py`
    - Định nghĩa enum `MergeOrder`, `ResizeMode`, `ResizeSubmode`, `QualityPreset` (CRF: Fast=28, Balanced=23, High=18), `MergeStatus` (đúng chuỗi Status_Vocabulary)
    - Định nghĩa dataclass `MergeConfig` (folders, trim_head/tail cho F1 và F2, merge_order, resize_mode, resize_submode, quality, target_width=1080, target_height=1920, fps=30, audio_rate=44100)
    - Định nghĩa dataclass `PairResult`, `ProgressEvent`, `RunSummary` theo design
    - _Requirements: 2.5, 2.6, 2.8, 5.1, 5.2, 5.3, 5.4_

- [x] 3. Quy ước đặt tên file (naming.py)
  - [x] 3.1 Hiện thực các hàm naming trong `app/engine/naming.py`
    - `format_stt(index)`: số thứ tự bắt đầu từ 1 trả "001"; khi > 999 dùng đủ chữ số không cắt giá trị
    - `merged_name(stt, name1, name2)`: trả `merged_<STT>__<ten-f1>__<ten-f2>.mp4`
    - `used_name(stt, side, name)`: side ∈ {"F1","F2"} trả `<STT>_<side>_<ten>.mp4`
    - `resolve_collision(target)`: chèn hậu tố `_<n>` (n bắt đầu từ 1, tăng dần) trước phần mở rộng cho tới khi tên chưa tồn tại
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x]* 3.2 Viết unit tests cho naming
    - Test `format_stt` cho 1→"001", 999, vượt 999; `merged_name`/`used_name` định dạng; `resolve_collision` chèn suffix khi trùng và biên không trùng
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.6_

  - [x]* 3.3 Viết property test cho STT duy nhất và tăng đơn điệu
    - **Property 4: STT là duy nhất và tăng đơn điệu** (`int(format_stt(n)) == n`, dãy duy nhất từng đôi, bắt đầu "001", tăng đều 1)
    - **Validates: Requirements 6.1, 6.2, 6.5**
    - _Requirements: 6.1, 6.2, 6.5_

  - [x]* 3.4 Viết property test cho cùng cặp dùng chung STT
    - **Property 5: Cùng một cặp dùng chung một STT** (merged_name, used_name F1, used_name F2 cùng chứa một chuỗi STT)
    - **Validates: Requirements 6.3, 6.4, 6.5**
    - _Requirements: 6.3, 6.4, 6.5_

  - [x]* 3.5 Viết property test cho giải quyết trùng tên
    - **Property 6: Giải quyết trùng tên luôn cho tên duy nhất** (`resolve_collision` luôn trả đường dẫn chưa tồn tại; dạng `<stem>_<n><ext>` với n>=1 khi gốc đã tồn tại)
    - **Validates: Requirements 6.6**
    - _Requirements: 6.6_

- [x] 4. Logic quét và ghép cặp video (trong merge_engine.py)
  - [x] 4.1 Hiện thực `compute_keep_window` và `scan_folder`
    - `compute_keep_window(duration, trim_head, trim_tail)` (hàm thuần): trả `None` khi `d - head - tail <= 0`, ngược lại trả giá trị giữ lại
    - `scan_folder(folder)`: liệt kê file trực tiếp (không đệ quy), lọc theo Supported_Format (`.mp4/.mov/.mkv/.avi/.webm`) không phân biệt hoa thường
    - _Requirements: 3.1, 4.2, 4.3_

  - [x] 4.2 Hiện thực `pair_videos` (sort/shuffle, one-to-one, leftovers)
    - Sắp xếp theo tên không phân biệt hoa thường khi SORTED; xáo trộn độc lập hai danh sách khi SHUFFLE (dùng `random.Random` truyền vào để test xác định)
    - Ghép một-đối-một theo vị trí, số cặp = `min(len1, len2)`, trả `(pairs, leftovers)` với leftover là phần thừa của danh sách dài hơn
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x]* 4.3 Viết unit tests cho scan_folder, compute_keep_window, pair_videos
    - Test `scan_folder` lọc định dạng + case-insensitive + không đệ quy; `compute_keep_window` biên `<=0`; `pair_videos` số cặp/leftover, sort, one-to-one
    - _Requirements: 3.1, 3.2, 3.4, 3.6, 4.3_

  - [x]* 4.4 Viết property test cho phân hoạch không trùng lặp
    - **Property 1: Mỗi video nguồn được dùng nhiều nhất một lần** (tập file trong cặp + leftover là phân hoạch không trùng của nguồn)
    - **Validates: Requirements 3.5**
    - _Requirements: 3.5_

  - [x]* 4.5 Viết property test cho số cặp bằng min
    - **Property 2: Số cặp bằng min của hai số lượng** (số cặp = `min(len1, len2)`, số leftover = `abs(len1 - len2)`)
    - **Validates: Requirements 3.4, 3.6, 3.7**
    - _Requirements: 3.4, 3.6, 3.7_

  - [x]* 4.6 Viết property test cho ghép cặp theo vị trí
    - **Property 3: Ghép cặp theo vị trí một-đối-một** (cặp tại chỉ số N gồm phần tử thứ N của hai danh sách đã xử lý)
    - **Validates: Requirements 3.4**
    - _Requirements: 3.4_

  - [x]* 4.7 Viết property test cho cửa sổ cắt
    - **Property 7: Cửa sổ cắt đúng và bỏ qua khi không dương** (`compute_keep_window` trả None ⟺ `d - head - tail <= 0`, ngược lại trả đúng giá trị dương)
    - **Validates: Requirements 4.2, 4.3**
    - _Requirements: 4.2, 4.3_

  - [x]* 4.8 Viết property test cho quét file
    - **Property 8: Quét file lọc đúng định dạng, không phân biệt hoa thường, không đệ quy**
    - **Validates: Requirements 3.1**
    - _Requirements: 3.1_

- [x] 5. Checkpoint - Đảm bảo các test logic thuần đều pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Kiểm tra ffmpeg/ffprobe (ffmpeg_check.py)
  - [x] 6.1 Hiện thực `check_tools` trong `app/engine/ffmpeg_check.py`
    - Chạy `ffmpeg -version` / `ffprobe -version` qua subprocess; trả `ToolCheckResult` với cờ `ffmpeg_ok`, `ffprobe_ok` và thông điệp hướng dẫn cài đặt khi thiếu
    - Hoàn tất kiểm tra trong giới hạn thời gian hợp lý (timeout subprocess)
    - _Requirements: 10.1, 10.2_

  - [x]* 6.2 Viết unit/integration tests cho check_tools
    - Test phát hiện thiếu công cụ khi truyền đường dẫn không tồn tại; test thông điệp hướng dẫn nêu đúng công cụ còn thiếu
    - _Requirements: 10.1, 10.2_

- [x] 7. Bọc lệnh ffmpeg/ffprobe (ffmpeg_runner.py)
  - [x] 7.1 Hiện thực probe và dựng filter_complex trong `app/engine/ffmpeg_runner.py`
    - `probe_duration(path)`: đọc thời lượng qua ffprobe, raise lỗi khi không parse được
    - `probe_resolution(path)`: đọc width,height (dùng cho keep-size)
    - `build_filter_complex(config, f1_res)`: dựng chuỗi filter cho 9:16 fit-with-padding (scale+pad), 9:16 fill-crop (scale+crop), và keep-size (chuẩn hóa F2 về WxH của F1); mọi nhánh đặt `fps=30`, `setsar=1`, kết thúc bằng `concat=n=2:v=1:a=1`
    - _Requirements: 4.1, 5.5, 5.6, 5.7_

  - [x] 7.2 Hiện thực `run_concat` (một lệnh ffmpeg duy nhất)
    - Đặt `-ss`/`-t` trước mỗi `-i` theo cửa sổ giữ lại; áp `-c:v libx264 -crf <CRF> -pix_fmt yuv420p -r 30 -c:a aac -ar 44100`; xử lý input thiếu audio (anullsrc) để concat hợp lệ; raise `FfmpegError` khi exit code != 0
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x]* 7.3 Viết integration tests cho ffmpeg_runner với video mẫu nhỏ
    - Sinh 2-3 video mẫu nhỏ bằng ffmpeg (`testsrc`/`sine`, khác kích thước) trong fixture; chạy `run_concat` end-to-end; xác minh output `.mp4` tồn tại, >0 byte, đúng 30fps/yuv420p/AAC 44100Hz bằng ffprobe; chạy mỗi Resize_Mode/Submode một ví dụ
    - _Requirements: 5.1, 5.2, 5.3, 5.5, 5.6, 5.7_

- [x] 8. Engine điều phối (merge_engine.py)
  - [x] 8.1 Hiện thực `MergeEngine.process_pair` (trim → normalize/resize → concat → verify → safe move)
    - Probe duration F1/F2; tính keep window (Skipped too short khi None); bắt lỗi probe (Skipped unreadable + lý do); gọi `run_concat`; verify `output.exists() and st_size > 0`; chỉ khi đạt mới `shutil.move` gốc sang Used_Folder_1/2 và verify đích tồn tại; bọc `try/except` để trả `PairResult(FAILED, detail)` khi lỗi không lường trước; giữ nguyên gốc khi thất bại
    - _Requirements: 4.1, 4.3, 4.4, 7.3, 7.4, 7.5, 7.6, 10.4_

  - [x] 8.2 Hiện thực `MergeEngine.run` (orchestration + tạo thư mục + Stop + emit ProgressEvent)
    - Tạo Merged/Used_Folder_1/Used_Folder_2 (bắt OSError → không bắt đầu); scan + pair; emit ProgressEvent init (total, leftovers) và status `Unused because no pair` cho leftover; lặp từng cặp, kiểm tra `stop_event.is_set()` ở đầu vòng lặp (hoàn tất cặp hiện tại rồi dừng); cô lập lỗi từng cặp (tiếp tục khi lỗi); emit ProgressEvent pair/status/done; trả `RunSummary` (succeeded/failed/unused/not_processed)
    - _Requirements: 3.7, 7.1, 7.2, 9.2, 9.3, 9.4, 9.5, 9.6, 10.5_

  - [x]* 8.3 Viết property test cho an toàn di chuyển gốc
    - **Property 9: Gốc chỉ được di chuyển khi output đã xác minh** (move ⟹ output tồn tại & >0 byte; thất bại ⟹ cả hai gốc còn nguyên tại thư mục gốc) — dùng FfmpegRunner giả lập (fake/mock) để điều khiển kết quả output
    - **Validates: Requirements 7.3, 7.4, 7.5, 10.4**
    - _Requirements: 7.3, 7.4, 7.5, 10.4_

  - [x]* 8.4 Viết integration tests cho run/process_pair end-to-end
    - Dùng video mẫu nhỏ chạy `run` qua vài cặp; xác minh output trong Merged_Folder, gốc đã move sang Used_Folder; test một cặp lỗi không dừng toàn bộ; test stop_event dừng trước cặp kế tiếp và giữ nguyên cặp chưa xử lý
    - _Requirements: 7.4, 9.2, 9.3, 9.4, 10.5_

- [x] 9. Checkpoint - Đảm bảo engine + ffmpeg tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Giao diện customtkinter (main_window.py)
  - [x] 10.1 Xây dựng khung cửa sổ và các nhóm điều khiển
    - Lớp `MainWindow(ctk.CTk)`; appearance mode dark mặc định + toggle sáng/tối; kích thước tối thiểu 900x650; dựng 4 nhóm: Sources (nút chọn F1/F2/Output + nhãn đường dẫn, mặc định "chưa chọn"), Trim settings (Trim_Head/Trim_Tail cho F1 và F2, mặc định 1), Output options (Merge_Order mặc định sort, Resize_Mode mặc định keep-size, Submode mặc định Fit-pad, Quality mặc định Balanced), Actions/Progress (Start primary, Stop secondary, Progress_Bar + % văn bản, Status_Area cuộn, Results_Summary_Panel)
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.4, 2.5, 2.6, 2.8, 8.1, 8.2, 8.3, 8.4_

  - [x] 10.2 Hiện thực sự kiện chọn thư mục, đổi resize mode, toggle theme
    - `_on_select_folder1/2/output`: hiển thị đường dẫn tuyệt đối; `_on_resize_mode_change`: bật Submode khi 9:16, vô hiệu khi keep-size; `_on_toggle_theme`
    - _Requirements: 1.3, 1.4, 1.5, 2.6, 2.7, 8.1_

  - [x] 10.3 Hiện thực `_build_config` và validation phía UI
    - Build `MergeConfig` từ UI; validate: thiếu thư mục (nêu rõ thiếu gì), xung đột thư mục (F1≡F2, Output trùng/nằm trong F1/F2), thư mục không tồn tại/không truy cập, trim không phải số thực không âm hoặc ngoài [0,3600]; giữ nguyên giá trị đã nhập và không bắt đầu khi lỗi
    - _Requirements: 1.6, 1.7, 1.8, 2.3_

  - [x] 10.4 Hiện thực `_on_start`, `_on_stop`, `_poll_queue` (worker thread + queue polling)
    - `_on_start`: validate → `check_tools` (thiếu → thông báo + hướng dẫn, không bắt đầu) → kiểm tra thư mục nguồn rỗng (thông báo, không bắt đầu) → reset progress 0% + hiển thị tổng số cặp → disable Start/enable Stop → spawn `threading.Thread` chạy `MergeEngine.run` → bắt đầu `_poll_queue`
    - `_on_stop`: `stop_event.set()` + hiển thị "đang chờ dừng"
    - `_poll_queue`: `get_nowait()` đến rỗng, cập nhật Progress_Bar/% , Status_Area (STT, tên F1, tên F2, trạng thái), Results_Summary_Panel; khi nhận `done` đặt 100% + bật lại Start; lên lịch lại `self.after(POLL_INTERVAL_MS=100, ...)`
    - _Requirements: 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 9.1, 9.6, 9.7, 10.2, 10.3_

- [x] 11. Nối kết entry point (main.py)
  - [x] 11.1 Hoàn thiện `main.py`
    - Đặt appearance mode dark + color theme; khởi tạo `MainWindow`; chạy `mainloop()`; nối khối `if __name__ == "__main__"`
    - _Requirements: 8.1_

- [x] 12. Tài liệu hướng dẫn cài đặt và đóng gói (README)
  - [x] 12.1 Viết `README.md`
    - Liệt kê thư viện Python cần thiết (`customtkinter`) kèm lệnh cài đặt cụ thể; các bước cài ffmpeg/ffprobe trên Windows + bước kiểm tra xác nhận khả dụng; cách chạy từ mã nguồn; cách đóng gói `.exe` bằng PyInstaller (`pyinstaller --onefile --windowed main.py`); giải thích cấu trúc Merged_Folder/Used_Folder_1/Used_Folder_2 và cách xử lý video thừa không có cặp
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 13. Checkpoint cuối - Đảm bảo toàn bộ test pass và GUI xác minh thủ công
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Các task gắn `*` là tùy chọn (test) và có thể bỏ qua khi cần MVP nhanh; các task triển khai cốt lõi không bao giờ gắn `*`.
- Mỗi task tham chiếu requirement cụ thể để truy vết.
- Property-based test dùng **Hypothesis** (>= 100 iteration mỗi property), mỗi property là một sub-task riêng và tham chiếu thẳng tới property trong design.
- GUI (Req 1, 2, 8, 9 phần hiển thị) được xác minh thủ công theo checklist vì customtkinter không phù hợp tự động hóa property-based.
- Integration test ffmpeg giữ ở mức tối thiểu do chi phí cao; ưu tiên property test cho logic phổ quát.
- Checkpoint đảm bảo xác thực tăng dần ở các mốc hợp lý.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["3.1", "4.1", "6.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "4.2", "6.2", "7.1"] },
    { "id": 4, "tasks": ["4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "7.2"] },
    { "id": 5, "tasks": ["7.3", "8.1"] },
    { "id": 6, "tasks": ["8.2"] },
    { "id": 7, "tasks": ["8.3", "8.4", "10.1"] },
    { "id": 8, "tasks": ["10.2", "10.3"] },
    { "id": 9, "tasks": ["10.4"] },
    { "id": 10, "tasks": ["11.1"] },
    { "id": 11, "tasks": ["12.1"] }
  ]
}
```
