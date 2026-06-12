# BQH Merger Video

Công cụ desktop (Python + giao diện customtkinter) để **ghép video hàng loạt theo cặp** từ hai thư mục: video Folder 1 luôn đứng trước, video Folder 2 đứng sau. Sau khi ghép thành công, video gốc đã dùng được **chuyển sang thư mục lưu trữ** (giữ nguyên tên) để biết video nào đã dùng.

Tính năng nổi bật:
- Ghép cặp 1-1, theo thứ tự tên hoặc ngẫu nhiên (có seed)
- Cắt đầu/cuối, chuẩn hóa, resize 9:16 / 1:1 / 16:9, nhiều mức chất lượng
- Nhạc nền, chỉnh âm lượng, tốc độ video, tăng tốc GPU NVENC
- **Trình thiết kế mẫu (template)**: kéo-thả chữ + sticker, font/màu/nền bo góc, lưu nhiều mẫu
- Chữ tự điền theo **tên video Folder 2** (hoặc file .txt cùng tên), tự xuống dòng
- Tiến độ %, ETA, mở thư mục kết quả, ghi nhớ cài đặt
- **Tự cập nhật bản mới từ GitHub** (nút trong app)

---

## 1. Cài đặt lần đầu (máy mới)

### Bước 1: Cài các phần mềm nền
- **Python 3.10+**: tải tại <https://www.python.org/downloads/> (khi cài nhớ tick "Add Python to PATH").
- **Git for Windows**: tải tại <https://git-scm.com/download/win> (để dùng tính năng cập nhật).
- **ffmpeg + ffprobe**: tải bản "release full" tại <https://www.gyan.dev/ffmpeg/builds/>, giải nén vào `C:\ffmpeg`, thêm `C:\ffmpeg\bin` vào biến môi trường PATH. Kiểm tra bằng cách mở CMD gõ `ffmpeg -version`.

### Bước 2: Tải ứng dụng về (clone từ GitHub)
Mở CMD/PowerShell tại nơi muốn lưu, chạy:
```bash
git clone https://github.com/<TEN_TAI_KHOAN>/bqh-merger-video.git
cd bqh-merger-video
```
> Thay `<TEN_TAI_KHOAN>` bằng tài khoản GitHub thật.

### Bước 3: Chạy ứng dụng
Bấm đúp vào file **`BQH_Merger_Video.bat`** (tự cài thư viện Python lần đầu rồi mở app).
Hoặc chạy thủ công:
```bash
pip install -r requirements.txt
python main.py
```

## 2. Cập nhật bản mới

Có 3 cách, chọn 1:
- **Trong app**: bấm nút **"⭳ Cập nhật bản mới"** ở góc trên phải, rồi khởi động lại app.
- **Bấm đúp** file **`CAP_NHAT_BAN_MOI.bat`** (tự `git pull` + chạy lại).
- **Thủ công**: `git pull` trong thư mục ứng dụng.

> Cập nhật chỉ hoạt động khi bạn **clone từ GitHub** (không phải tải file .zip).

## 3. Dành cho người phát triển (đẩy code lên GitHub)

Lần đầu tạo repo:
```bash
# 1. Tạo repo rỗng trên github.com (không thêm README)
# 2. Trong thư mục dự án:
git remote add origin https://github.com/<TEN_TAI_KHOAN>/bqh-merger-video.git
git branch -M main
git push -u origin main
```

Mỗi lần nâng cấp về sau:
```bash
# Sửa code, tăng số ở version.py rồi:
git add -A
git commit -m "Mô tả thay đổi"
git push
```
Máy khác chỉ cần bấm "Cập nhật bản mới" là có bản mới.

## 4. Cấu trúc thư mục đầu ra

```
<Folder xuất>/
├── merged/           # video đã ghép hoàn chỉnh
├── used_folder_1/    # video gốc Folder 1 đã dùng (GIỮ NGUYÊN TÊN)
└── used_folder_2/    # video gốc Folder 2 đã dùng (GIỮ NGUYÊN TÊN)
```

- Hai folder lệch số lượng → chỉ ghép theo folder ít hơn; video thừa giữ nguyên ở folder gốc.
- Video lỗi/quá ngắn sau khi cắt cũng giữ nguyên ở folder gốc.
- Video gốc **chỉ được chuyển sau khi** ghép thành công.

## 5. Đóng gói thành .exe (tuỳ chọn)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name "BQH Merger Video" main.py
```
File `.exe` nằm trong `dist/`. Lưu ý: bản `.exe` không tự cập nhật qua git; muốn tự cập nhật thì dùng cách clone + .bat ở trên.

## 6. Chạy test (dành cho dev)

```bash
python -m pytest -q
```

## 7. Cấu trúc mã nguồn

```
main.py                       # entry point
version.py                    # tên app + phiên bản
BQH_Merger_Video.bat          # chạy app
CAP_NHAT_BAN_MOI.bat          # cập nhật từ GitHub
app/
├── ui/
│   ├── main_window.py        # giao diện chính
│   └── template_designer.py  # trình thiết kế mẫu
└── engine/
    ├── models.py             # dataclasses & enums
    ├── naming.py             # đặt tên file
    ├── ffmpeg_check.py       # kiểm tra ffmpeg/ffprobe + GPU
    ├── ffmpeg_runner.py      # gọi ffmpeg/ffprobe
    ├── merge_engine.py       # quét, ghép cặp, xử lý, di chuyển
    ├── text_render.py        # render chữ + nền bo góc (Pillow)
    ├── fonts.py              # danh mục font
    ├── template_model.py     # mô hình mẫu
    ├── template_store.py     # thư viện mẫu
    ├── settings_store.py     # ghi nhớ cài đặt
    └── updater.py            # cập nhật từ GitHub
tests/                        # unit + property + integration tests
```
