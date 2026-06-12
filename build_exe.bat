@echo off
REM ============================================================
REM  BQH Merger Video - Build file .exe bang PyInstaller
REM  Chay file nay tren may DEV de tao ra ban .exe phat hanh.
REM ============================================================
cd /d "%~dp0"

echo Cai PyInstaller va thu vien...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check
python -m pip install pyinstaller --quiet --disable-pip-version-check

echo.
echo Dang build... (co the mat 1-2 phut)
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name "BQH_Merger_Video" ^
  --collect-all customtkinter ^
  main.py

echo.
if exist "dist\BQH_Merger_Video.exe" (
    echo ============================================================
    echo  XONG! File .exe nam tai: dist\BQH_Merger_Video.exe
    echo  Hay tao Release moi tren GitHub va dinh kem file nay.
    echo ============================================================
) else (
    echo Build that bai. Xem thong bao loi o tren.
)
pause
