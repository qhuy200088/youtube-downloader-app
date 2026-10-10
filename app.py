import os
import sys

# Ensure UTF-8 output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import shutil
import uuid
import time
import re
import threading
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import yt_dlp

# --- Detect and configure FFmpeg ---
def find_ffmpeg_dir() -> Optional[str]:
    # 1. System PATH
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return os.path.dirname(ffmpeg_in_path)
    # 2. Check WinGet package path
    winget_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
    if os.path.exists(winget_dir):
        for root, dirs, files in os.walk(winget_dir):
            if "ffmpeg.exe" in files:
                return root
    # 3. imageio_ffmpeg
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        return os.path.dirname(exe)
    except Exception:
        pass
    return None

FFMPEG_DIR = find_ffmpeg_dir()
if FFMPEG_DIR:
    os.environ["PATH"] = FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")
    print(f"[INFO] Using FFmpeg from: {FFMPEG_DIR}")
else:
    print("[WARNING] FFmpeg not found in known locations!")

# --- Storage paths ---
USER_DOWNLOADS = Path.home() / "Downloads" / "YouTube_Converted"
USER_DOWNLOADS.mkdir(parents=True, exist_ok=True)
CACHE_DIR = Path(__file__).parent / "temp_downloads"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="YouTube Downloader & Converter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tasks in-memory storage
tasks: Dict[str, Dict[str, Any]] = {}
download_history: List[Dict[str, Any]] = []

def sanitize_filename(name: str) -> str:
    # Replace invalid Windows filename characters and URL hash/slashes with clean separators
    cleaned = re.sub(r'[\\/*?:"<>|#]+', " - ", name)
    cleaned = re.sub(r'\s+', " ", cleaned).strip(" -")
    return cleaned[:150] if cleaned else "download"

def format_bytes(bytes_num: Optional[float]) -> str:
    if not bytes_num or bytes_num <= 0:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.1f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.1f} TB"

def format_speed(speed: Optional[float]) -> str:
    if not speed or speed <= 0:
        return "0 KB/s"
    return f"{format_bytes(speed)}/s"

def format_eta(eta: Optional[int]) -> str:
    if not eta or eta <= 0:
        return "--:--"
    m, s = divmod(int(eta), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def get_base_ydl_opts() -> dict:
    opts = {
        'quiet': True,
        'no_warnings': True,
        'js_runtimes': {'node': {}},
        'remote_components': ['ejs:github'],
    }
    if FFMPEG_DIR:
        opts['ffmpeg_location'] = FFMPEG_DIR
    return opts

class InfoRequest(BaseModel):
    url: str

class DownloadRequest(BaseModel):
    url: str
    type: str       # 'video', 'audio', 'other'
    quality: str    # '1080p', '720p', '320k', etc.
    format: str     # 'mp4', 'mp3', 'wav', 'm4a', etc.
    save_to_downloads: bool = True

@app.post("/api/info")
def get_video_info(req: InfoRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng cung cấp link YouTube hợp lệ.")

    opts = get_base_ydl_opts()
    opts['skip_download'] = True

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        error_msg = str(e)
        if "unavailable" in error_msg.lower():
            raise HTTPException(status_code=404, detail="Video không tồn tại hoặc đã bị ẩn/xoá.")
        raise HTTPException(status_code=400, detail=f"Không thể tải thông tin video: {error_msg}")

    title = info.get("title", "Video không tiêu đề")
    duration = info.get("duration", 0)
    duration_str = info.get("duration_string", "0:00")
    thumbnail = info.get("thumbnail", "")
    uploader = info.get("uploader") or info.get("channel", "YouTube Channel")
    view_count = info.get("view_count", 0)
    video_id = info.get("id", "")

    # Extract available video heights
    raw_formats = info.get("formats", [])
    available_heights = set()
    for f in raw_formats:
        h = f.get("height")
        if h and f.get("vcodec") != "none":
            available_heights.add(h)

    standard_heights = [1080, 720, 480, 360, 240, 144]
    max_height = max(available_heights) if available_heights else 720
    
    # Estimate video sizes roughly if not directly provided
    # Average video bitrates: 1080p ~ 3500kbps, 720p ~ 1800kbps, 480p ~ 1000kbps, 360p ~ 600kbps, 240p ~ 350kbps, 144p ~ 180kbps
    bitrate_map = {
        1080: 3500,
        720: 1800,
        480: 1000,
        360: 600,
        240: 350,
        144: 180
    }

    video_options = []
    for h in standard_heights:
        # Check if this quality is available
        is_available = any(ah >= h for ah in available_heights) if available_heights else True
        if is_available:
            approx_bytes = int((bitrate_map.get(h, 1000) * 1000 / 8) * (duration or 180))
            video_options.append({
                "label": f"{h}p (.mp4)",
                "quality": f"{h}p",
                "format": "mp4",
                "format_display": "Auto",
                "size_approx": format_bytes(approx_bytes),
                "is_hd": h >= 720
            })

    # Audio options
    audio_bitrates = [
        {"rate": "320", "label": "MP3 - 320kbps", "quality": "320k"},
        {"rate": "256", "label": "MP3 - 256kbps", "quality": "256k"},
        {"rate": "192", "label": "MP3 - 192kbps", "quality": "192k"},
        {"rate": "128", "label": "MP3 - 128kbps", "quality": "128k"},
    ]
    audio_options = []
    for a in audio_bitrates:
        approx_bytes = int((int(a["rate"]) * 1000 / 8) * (duration or 180))
        audio_options.append({
            "label": a["label"],
            "quality": a["quality"],
            "format": "mp3",
            "format_display": "Auto",
            "size_approx": format_bytes(approx_bytes)
        })

    # Other options
    other_options = [
        {
            "label": "M4A Audio (.m4a)",
            "quality": "best",
            "format": "m4a",
            "format_display": "Auto",
            "size_approx": format_bytes(int((160 * 1000 / 8) * (duration or 180)))
        },
        {
            "label": "WAV Lossless (.wav)",
            "quality": "lossless",
            "format": "wav",
            "format_display": "Auto",
            "size_approx": format_bytes(int((1411 * 1000 / 8) * (duration or 180)))
        },
        {
            "label": "FLAC Lossless (.flac)",
            "quality": "lossless",
            "format": "flac",
            "format_display": "Auto",
            "size_approx": format_bytes(int((900 * 1000 / 8) * (duration or 180)))
        },
        {
            "label": "WebM Video (.webm)",
            "quality": "best",
            "format": "webm",
            "format_display": "Auto",
            "size_approx": format_bytes(int((1800 * 1000 / 8) * (duration or 180)))
        }
    ]

    return {
        "id": video_id,
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "duration_str": duration_str,
        "thumbnail": thumbnail,
        "view_count": f"{view_count:,}",
        "video_options": video_options,
        "audio_options": audio_options,
        "other_options": other_options,
        "original_url": url
    }

def run_download_task(task_id: str, req: DownloadRequest):
    task = tasks[task_id]
    task["status"] = "downloading"
    task["status_text"] = "Đang kết nối tới máy chủ YouTube..."

    out_folder = USER_DOWNLOADS if req.save_to_downloads else CACHE_DIR
    out_tmpl = str(out_folder / f"{task_id}_%(title).100s.%(ext)s")

    def progress_hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            speed = d.get("speed")
            eta = d.get("eta")

            if total > 0:
                # Keep up to 90% for download phase, remaining 10% for merge/convert
                pct = min(90.0, (downloaded / total) * 90.0)
            else:
                pct = 50.0

            task["progress"] = round(pct, 1)
            task["percent_str"] = f"{task['progress']}%"
            task["speed_str"] = format_speed(speed)
            task["eta_str"] = format_eta(eta)
            task["downloaded_str"] = format_bytes(downloaded)
            task["total_str"] = format_bytes(total) if total > 0 else "..."
            task["status_text"] = f"Đang tải: {task['percent_str']} ({task['speed_str']})"

        elif d.get("status") == "finished":
            task["progress"] = 92.0
            task["percent_str"] = "92%"
            task["status_text"] = "Đang xử lý / chuyển đổi định dạng qua FFmpeg..."

    def postprocessor_hook(d):
        if d.get("status") == "started":
            task["progress"] = 94.0
            task["status_text"] = "FFmpeg đang chuyển đổi định dạng và đóng gói..."
        elif d.get("status") == "finished":
            task["progress"] = 98.0
            task["status_text"] = "Đang hoàn tất tệp tin..."

    opts = get_base_ydl_opts()
    opts.update({
        'outtmpl': out_tmpl,
        'progress_hooks': [progress_hook],
        'postprocessor_hooks': [postprocessor_hook],
        'overwrites': True,
    })

    download_type = req.type
    quality = req.quality
    fmt = req.format.lower()

    if download_type == "audio" or fmt in ["mp3", "m4a", "wav", "flac"]:
        opts['format'] = 'bestaudio/best'
        bitrate = "320"
        if "256" in quality:
            bitrate = "256"
        elif "192" in quality:
            bitrate = "192"
        elif "128" in quality:
            bitrate = "128"

        codec = "mp3" if fmt == "mp3" else fmt
        pp = {
            'key': 'FFmpegExtractAudio',
            'preferredcodec': codec,
        }
        if codec == "mp3":
            pp['preferredquality'] = bitrate
        opts['postprocessors'] = [pp]

    elif download_type == "video" or fmt in ["mp4", "webm"]:
        # Extract height number from quality like '1080p' -> 1080
        h_match = re.search(r'\d+', quality)
        h = int(h_match.group()) if h_match else 720
        if fmt == "mp4":
            opts['format'] = f"bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
            opts['merge_output_format'] = 'mp4'
        else:
            opts['format'] = f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"
            opts['merge_output_format'] = fmt

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info_dict = ydl.extract_info(req.url, download=True)
            video_title = info_dict.get("title", "Video")

        # Find the resulting file
        matching_files = list(out_folder.glob(f"{task_id}_*"))
        if not matching_files:
            raise FileNotFoundError("Không tìm thấy file kết quả sau khi tải.")

        final_file = matching_files[0]
        ext = final_file.suffix.lstrip(".")
        clean_title = sanitize_filename(video_title)
        friendly_filename = f"{clean_title}.{ext}"

        task["progress"] = 100.0
        task["percent_str"] = "100%"
        task["status"] = "completed"
        task["status_text"] = "Chuyển đổi thành công! Sẵn sàng tải xuống."
        task["file_path"] = str(final_file)
        task["filename"] = friendly_filename
        task["filesize"] = final_file.stat().st_size
        task["filesize_str"] = format_bytes(final_file.stat().st_size)
        task["title"] = video_title

        # Add to history
        download_history.insert(0, {
            "task_id": task_id,
            "title": video_title,
            "filename": friendly_filename,
            "filesize_str": task["filesize_str"],
            "type": download_type,
            "quality": quality,
            "format": ext.upper(),
            "time": time.strftime("%H:%M:%S %d/%m/%Y"),
            "file_path": str(final_file)
        })

    except Exception as e:
        task["status"] = "error"
        task["error_message"] = str(e)
        task["status_text"] = f"Lỗi: {str(e)}"
        print(f"[ERROR in task {task_id}]: {e}")

@app.post("/api/download")
def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())[:8]
    tasks[task_id] = {
        "task_id": task_id,
        "url": req.url,
        "type": req.type,
        "quality": req.quality,
        "format": req.format,
        "status": "pending",
        "progress": 0.0,
        "percent_str": "0%",
        "speed_str": "0 KB/s",
        "eta_str": "--:--",
        "status_text": "Đang chuẩn bị xử lý...",
        "file_path": None,
        "filename": None,
        "filesize_str": "0 MB",
        "created_at": time.time(),
    }

    # Start thread for download
    thread = threading.Thread(target=run_download_task, args=(task_id, req), daemon=True)
    thread.start()

    return {"task_id": task_id}

@app.get("/api/progress/{task_id}")
def get_progress(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task không tồn tại")
    return task

@app.get("/api/file/{task_id}")
def download_file(task_id: str):
    task = tasks.get(task_id)
    if not task or task.get("status") != "completed":
        raise HTTPException(status_code=404, detail="File chưa sẵn sàng hoặc không tồn tại")

    file_path = task.get("file_path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy tệp trên ổ cứng")

    filename = task.get("filename", "download.mp4")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream"
    )

@app.post("/api/open-folder/{task_id}")
def open_folder(task_id: str, request: Request):
    # Prevent remote users coming via Cloudflare Tunnel from opening Explorer on host PC
    if request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for"):
        raise HTTPException(status_code=403, detail="Tính năng mở thư mục chỉ khả dụng trực tiếp trên máy chủ.")

    task = tasks.get(task_id)
    if not task or not task.get("file_path"):
        raise HTTPException(status_code=404, detail="File không tồn tại")

    file_path = task["file_path"]
    if os.path.exists(file_path):
        subprocess.run(f'explorer.exe /select,"{os.path.abspath(file_path)}"', shell=True)
        return {"status": "ok"}
    else:
        folder = os.path.dirname(file_path)
        if os.path.exists(folder):
            subprocess.run(f'explorer.exe "{folder}"', shell=True)
            return {"status": "ok"}
        raise HTTPException(status_code=404, detail="Thư mục không tồn tại")

@app.get("/api/history")
def get_history():
    return download_history[:20]

@app.get("/api/ping")
def ping():
    return {"status": "ok"}

@app.get("/config.json")
def get_config():
    cfg_path = Path(__file__).parent / "config.json"
    if cfg_path.exists():
        return FileResponse(str(cfg_path), media_type="application/json")
    return {"api_base": ""}

# Static files mount
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/")
def index():
    return FileResponse(str(static_dir / "index.html"))

def start_cloudflare_tunnel_and_sync(port: int):
    project_dir = Path(__file__).parent
    cf_exe = project_dir / "cloudflared.exe"
    if not cf_exe.exists():
        cf_in_path = shutil.which("cloudflared")
        if cf_in_path:
            cf_exe = Path(cf_in_path)
        else:
            print("[WARNING] Không tìm thấy cloudflared.exe để tạo kết nối công khai.")
            return

    print("[INFO] Đang khởi tạo Cloudflare Tunnel kết nối với GitHub Pages...")
    try:
        proc = subprocess.Popen(
            [str(cf_exe), "tunnel", "--url", f"http://127.0.0.1:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        tunnel_url = None
        for line in proc.stdout:
            match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
            if match:
                tunnel_url = match.group(0)
                break

        if tunnel_url:
            print(f"======================================================")
            print(f" [PUBLIC] Cloudflare Tunnel URL: {tunnel_url}")
            print(f" [GITHUB] Link cố định: https://qhuy200088.github.io/youtube-downloader-app/")
            print(f"======================================================")
            cfg_file = project_dir / "config.json"
            cfg_data = {
                "api_base": tunnel_url,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            cfg_file.write_text(json.dumps(cfg_data, indent=2), encoding="utf-8")

            # Push updated config.json to GitHub so GitHub Pages connects immediately
            subprocess.run(["git", "add", "config.json"], cwd=str(project_dir), capture_output=True)
            subprocess.run(["git", "commit", "-m", f"Auto-update tunnel URL: {tunnel_url}"], cwd=str(project_dir), capture_output=True)
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=str(project_dir), capture_output=True, text=True)
            if push_res.returncode == 0:
                print("[INFO] Đã đồng bộ địa chỉ Tunnel lên GitHub thành công!")
            else:
                print(f"[WARNING] Không thể push tự động lên GitHub: {push_res.stderr}")

        # Keep draining stdout so pipe buffer never blocks cloudflared
        for _ in proc.stdout:
            pass
    except Exception as e:
        print(f"[ERROR] Lỗi khởi tạo Cloudflare Tunnel: {e}")

if __name__ == "__main__":
    port = 8000
    print(f"======================================================")
    print(f" YouTube to MP3 / MP4 Converter Server Running!")
    print(f" Truy cập trên PC: http://localhost:{port}")
    print(f" Thư mục tải về mặc định: {USER_DOWNLOADS}")
    print(f"======================================================")
    threading.Thread(target=start_cloudflare_tunnel_and_sync, args=(port,), daemon=True).start()
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)
