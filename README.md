# BQH Merger Video

Công cụ desktop ghép video hàng loạt theo cặp từ hai thư mục: video Folder 1 đứng trước, Folder 2 đứng sau. Có trình thiết kế mẫu (chữ + sticker), chữ tự theo tên video, nhạc nền, tốc độ, GPU, và **tự cập nhật bản mới ngay trong app**.

---

## A. Dành cho NGƯỜI DÙNG (chỉ cần file .exe)

1. Vào trang **Releases** của dự án trên GitHub:
   <https://github.com/hung130803/bqh-merger-video/releases>
2. Tải file **`BQH_Merger_Video.exe`** ở bản mới nhất về.
3. Cài **ffmpeg** (bắt buộc, để xử lý video):
   - Tải bản "release full" tại <https://www.gyan.dev/ffmpeg/builds/>
   - Giải nén vào `C:\ffmpeg`, thêm `C:\ffmpeg\bin` vào PATH
   - (Hoặc để file `ffmpeg.exe` và `ffprobe.exe` cùng thư mục với file .exe)
4. Bấm đúp `BQH_Merger_Video.exe` để chạy. Xong!

### Cập nhật bản mới
Trong app bấm nút **"⭳ Cập nhật bản mới"** ở góc trên phải. App tự kiểm tra,
tải bản mới và khởi động lại. Không cần làm gì thêm.

---

## B. Dành cho NGƯỜI PHÁT TRIỂN (build & phát hành)

### Chạy từ mã nguồn
```bash
pip install -r requirements.txt
python main.py
```

### Build ra file .exe
Bấm đúp **`build_exe.bat`** (hoặc chạy lệnh trong đó). File ra ở
`dist\BQH_Merger_Video.exe`.

### Phát hành bản mới (để người dùng tự cập nhật được)
1. Sửa/nâng cấp code.
2. Tăng `APP_VERSION` trong `version.py` (vd `1.0.0` → `1.0.1`).
3. Build lại .exe bằng `build_exe.bat`.
4. Đẩy code lên GitHub:
   ```bash
   git add -A
   git commit -m "Mô tả thay đổi"
   git push
   ```
5. Trên GitHub, vào **Releases → Draft a new release**:
   - **Tag**: đặt trùng phiên bản, có chữ v phía trước, vd `v1.0.1`
   - **Title**: vd `v1.0.1`
   - Kéo thả file **`dist\BQH_Merger_Video.exe`** vào phần đính kèm (assets)
   - Bấm **Publish release**
6. Xong. Người dùng bấm "Cập nhật bản mới" trong app là tự tải bản này về.

> Quan trọng: tên file đính kèm phải là **`BQH_Merger_Video.exe`** (trùng với
> `EXE_ASSET_NAME` trong `version.py`), và tag phải mới hơn phiên bản hiện tại.

### Đẩy code lên GitHub lần đầu
```bash
git remote add origin https://github.com/hung130803/bqh-merger-video.git
git branch -M main
git push -u origin main
```

---

## Cấu trúc thư mục đầu ra
```
<Folder xuất>/
├── merged/           # video đã ghép hoàn chỉnh
├── used_folder_1/    # video gốc Folder 1 đã dùng (GIỮ NGUYÊN TÊN)
└── used_folder_2/    # video gốc Folder 2 đã dùng (GIỮ NGUYÊN TÊN)
```
- Hai folder lệch số lượng → chỉ ghép theo folder ít hơn; video thừa giữ nguyên.
- Video gốc chỉ chuyển sau khi ghép thành công.

## Chạy test (dev)
```bash
python -m pytest -q
```
