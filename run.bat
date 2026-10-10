@echo off
chcp 65001 >nul
title YouTube to MP3 & MP4 Converter
color 0A

echo ========================================================
echo    YOUTUBE TO MP3 / MP4 CONVERTER
echo ========================================================
echo.
echo [1/2] Đang kiểm tra môi trường và cấu hình FFmpeg...

REM Add FFmpeg from WinGet if present
if exist "%LOCALAPPDATA%\Microsoft\WinGet\Packages" (
    for /d /r "%LOCALAPPDATA%\Microsoft\WinGet\Packages" %%d in (*bin) do (
        if exist "%%d\ffmpeg.exe" (
            set "PATH=%%d;%PATH%"
            echo [+] Đã tìm thấy FFmpeg tại: %%d
        )
    )
)

echo [2/2] Đang khởi động máy chủ tại http://localhost:8000 ...
echo.
echo ========================================================
echo  Mẹo: Trình duyệt sẽ tự động mở sau vài giây.
echo  Nhấn Ctrl + C để dừng máy chủ khi không sử dụng.
echo ========================================================
echo.

REM Open browser after 2 seconds in background
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

REM Run the python server
python app.py

pause
