# YouTube to MP3 & MP4 Converter 🎵 🎥

Ứng dụng chuyển đổi và tải video / âm thanh từ YouTube chất lượng cao (lên tới 4K, 1080p và MP3 320kbps), chạy nội bộ trực tiếp trên máy tính của bạn với giao diện trực quan y hệt mẫu bạn mong muốn.

---

## 🌟 Tính Năng Nổi Bật

- **Đầy đủ định dạng và chất lượng**:
  - **Tab Audio**: MP3 chất lượng cao 320kbps, 256kbps, 192kbps, 128kbps.
  - **Tab Video**: 1080p Full HD (.mp4), 720p (.mp4), 480p, 360p, 240p, 144p.
  - **Tab Other**: Lossless WAV (.wav), FLAC (.flac), M4A (.m4a), WebM (.webm).
- **Giao diện chuẩn mẫu**:
  - Thanh tab chuyển đổi nhanh: `Audio`, `Video`, `Other` với biểu tượng màu sắc nổi bật.
  - Bảng danh sách `File type` | `Format` (Auto) | `Action` với nút bấm màu xanh lá cây `Download`.
  - Hiển thị đầy đủ thông tin: Ảnh Thumbnail, thời lượng, tiêu đề, tên kênh và lượt xem.
- **Tiến trình tải thời gian thực**:
  - Hiển thị thanh phần trăm tiến trình (%), tốc độ tải (MB/s), thời gian còn lại (ETA).
  - Trạng thái rõ ràng: Đang tải -> Đang ghép video/chuyển đổi FFmpeg -> Hoàn tất.
  - Tự động kích hoạt tải về trình duyệt và lưu trữ cục bộ.
- **Lịch sử tải về**:
  - Ghi nhớ các video đã chuyển đổi gần đây, dễ dàng mở lại hoặc tải lại bất kỳ lúc nào.
- **Mở thư mục 1 chạm**: Nút bấm mở trực tiếp thư mục `Downloads/YouTube_Converted` trên Windows Explorer.

---

## 🚀 Hướng Dẫn Sử Dụng

### Cách 1: Khởi động 1 chạm bằng file `run.bat`
Chỉ cần nhấp đúp (Double-click) vào tệp **`run.bat`** trong thư mục dự án:
```
C:\Users\Nhat Huy\.gemini\antigravity\scratch\youtube-downloader-app\run.bat
```
Cửa sổ trình duyệt sẽ tự động mở lên tại địa chỉ: `http://localhost:8000`.

### Cách 2: Khởi động bằng dòng lệnh PowerShell / Terminal
```powershell
cd "C:\Users\Nhat Huy\.gemini\antigravity\scratch\youtube-downloader-app"
python app.py
```
Sau đó mở trình duyệt truy cập: [http://localhost:8000](http://localhost:8000).

---

## 📂 Nơi Lưu Trữ Video / Nhạc Sau Khi Tải
Mặc định các tệp tải về sẽ được lưu tại thư mục:
```
C:\Users\Nhat Huy\Downloads\YouTube_Converted
```
Bạn cũng có thể tải về trực tiếp thông qua trình duyệt web (Chrome, Edge, Cốc Cốc, Firefox...).
