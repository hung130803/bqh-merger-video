@echo off
REM ============================================================
REM  BQH Merger Video - Build file .exe (kem ffmpeg) bang PyInstaller
REM  Chay file nay tren may DEV de tao ra ban .exe phat hanh.
REM ============================================================
cd /d "%~dp0"

echo Cai PyInstaller va thu vien...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
python -m pip install pyinstaller --quiet --disable-pip-version-check

REM --- Tim ffmpeg/ffprobe de dong goi kem (de may khac khoi cai) ---
set FFMPEG_BIN=
if exist "C:\ffmpeg\ffmpeg.exe" set FFMPEG_BIN=C:\ffmpeg
if exist "C:\ffmpeg\bin\ffmpeg.exe" set FFMPEG_BIN=C:\ffmpeg\bin

set ADD_FF=
if defined FFMPEG_BIN (
    echo Dong goi kem ffmpeg tu: %FFMPEG_BIN%
    set ADD_FF=--add-binary "%FFMPEG_BIN%\ffmpeg.exe;." --add-binary "%FFMPEG_BIN%\ffprobe.exe;."
) else (
    echo CHU Y: Khong tim thay C:\ffmpeg - se build KHONG kem ffmpeg.
    echo May chay .exe se phai tu cai ffmpeg.
)

echo.
echo Dang build... (co the mat 1-2 phut)
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name "BQH_Merger_Video" ^
  --collect-all customtkinter ^
  --add-data "version.py;." ^
  %ADD_FF% ^
  main.py

echo.
if exist "dist\BQH_Merger_Video.exe" (
    echo ============================================================
    echo  XONG! File .exe nam tai: dist\BQH_Merger_Video.exe
    echo  Hay tao Release moi tren GitHub va dinh kem file nay.
    echo  Nho: tang APP_VERSION trong version.py truoc khi build.
    echo ============================================================
) else (
    echo Build that bai. Xem thong bao loi o tren.
)
pause
