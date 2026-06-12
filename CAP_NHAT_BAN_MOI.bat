@echo off
REM ============================================================
REM  BQH Merger Video - Cap nhat ban moi tu GitHub
REM ============================================================
cd /d "%~dp0"

echo Dang kiem tra va tai ban moi nhat tu GitHub...
git pull --ff-only
if errorlevel 1 (
    echo.
    echo Khong cap nhat duoc. Co the do:
    echo   - Chua cai Git for Windows
    echo   - Thu muc nay khong phai ban clone tu GitHub
    echo   - File bi sua cuc bo gay xung dot
    echo.
    pause
    exit /b 1
)

echo.
echo Cap nhat thu vien Python (neu co thay doi)...
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

echo.
echo Da cap nhat xong! Dang khoi dong ung dung...
python main.py
