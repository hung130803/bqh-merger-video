@echo off
REM ============================================================
REM  BQH Merger Video - Chay ung dung
REM ============================================================
cd /d "%~dp0"

REM Cai thu vien Python neu thieu (chi chay lan dau, rat nhanh sau do)
python -m pip install -r requirements.txt --quiet --disable-pip-version-check

python main.py
if errorlevel 1 (
    echo.
    echo Co loi xay ra. Nhan phim bat ky de dong.
    pause >nul
)
