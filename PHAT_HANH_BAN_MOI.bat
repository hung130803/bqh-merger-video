@echo off
REM ============================================================
REM  BQH Merger Video - Phat hanh ban moi (GitHub TU build .exe)
REM  Chi can chay file nay sau khi da sua code va tang version.py
REM ============================================================
cd /d "%~dp0"
chcp 65001 >nul

REM Doc so phien ban tu version.py
for /f "tokens=2 delims== " %%v in ('findstr /b "APP_VERSION" version.py') do set RAWV=%%v
set VER=%RAWV:"=%
set VER=%VER: =%

echo ============================================================
echo  Chuan bi phat hanh phien ban: v%VER%
echo ============================================================
echo.

echo [1/3] Day code len GitHub...
git add -A
git commit -m "Phat hanh v%VER%"
git push
if errorlevel 1 (
    echo Khong day duoc code. Kiem tra ket noi/git.
    pause
    exit /b 1
)

echo.
echo [2/3] Tao tag v%VER% va day len (GitHub se tu build .exe)...
git tag v%VER%
git push origin v%VER%
if errorlevel 1 (
    echo Khong day duoc tag. Co the tag da ton tai - hay tang version.py.
    pause
    exit /b 1
)

echo.
echo [3/3] XONG!
echo GitHub dang tu build file .exe. Theo doi tai:
echo   https://github.com/hung130803/bqh-merger-video/actions
echo Sau vai phut, ban moi se xuat hien o muc Releases.
echo.
pause
