# Claude Video Editor: trợ lý hậu kỳ phim tài liệu thiên nhiên trong DaVinci Resolve

Claude Code + các script Python giúp dựng phim kiểu BBC Earth: đặt narration, chọn footage (thật + AI), đặt lên
timeline, xoá logo, chỉnh màu, sắp xếp âm thanh. Claude làm việc với Resolve qua script; **bạn luôn duyệt từng bước**.

Muốn hiểu sâu cách hệ thống chạy: [docs/SYSTEM.md](docs/SYSTEM.md).

---

## 1. Cần có

| Thứ | Ghi chú |
|---|---|
| Windows 10/11 | |
| DaVinci Resolve 19+ (Studio khuyên dùng) | Preferences > System > General > **External scripting using = Local**, rồi mở lại Resolve |
| Python 3.11 hoặc 3.12, 64-bit | python.org, tick "Add python.exe to PATH" |
| Claude Code | `npm i -g @anthropic-ai/claude-code` hoặc bản desktop / VS Code |
| ffmpeg | `winget install Gyan.FFmpeg` |
| GPU NVIDIA (khuyên dùng) | cho YOLO lúc plan; không có thì cài với `-SkipYolo` |
| Ổ mạng chung map thành `Z:` | thư viện footage thật, nhạc, SFX. **Chỉ đọc + copy** |

## 2. Cài đặt (một lần)

```powershell
git clone https://github.com/hehoha3/Claude_Vid_editor.git D:\Claude_editor
cd D:\Claude_editor
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

`setup.ps1` tạo `.venv`, cài thư viện, YOLO, tải model Whisper + e5 (~1 GB, một lần), chạy self-test và `doctor`.

Sau đó:
1. Mở `config.toml`, kiểm tra `[paths] ai_video` (thư mục clip AI trên máy bạn, mặc định `D:\AI_video`) và
   `[workspaces] globs` (thư mục kênh, mặc định `D:\Chann_*`).
2. Mở Resolve + một project, chạy `.\dvr.cmd doctor`: phải thấy `[OK]` cho Resolve.
3. Chép các file **nhận riêng** (không có trong git) vào đúng chỗ:

| Nhận riêng | Đặt vào | Để làm gì |
|---|---|---|
| Ghi chú memory dự án | `.work\knowledge\` | Claude nhớ quyết định, sự cố, trạng thái video |
| Ledger clip của kênh bạn dựng | `.work\doc_edit\ledgers\` | Video mới không lặp clip của 4 video gần nhất |
| `audio_licenses.md` | `.work\` | License nhạc Envato |
| Clip AI | `D:\AI_video\` | Footage AI |

Mỗi lần mở phiên, Claude tự in trạng thái dự án (`handoffs/current.md`) nhờ hook trong `.claude\settings.json`.
Quyền riêng của bạn (nếu cần) đặt trong `.claude\settings.local.json`, file này không lên git.

## 3. Cách tổ chức thư mục video

```
D:\Chann_<tên kênh>\           <- một "workspace" = một kênh
    <video>\audios\            <- timestamp.md + narration .mp3 + screenplay
    _done\<video>\             <- video đã xong (do /doc-edit done chuyển vào)
```
Tên project trong Resolve = tên thư mục video. Mỗi project có timeline **Edit** (phim) và **Open** (intro).
Một video mới **không dùng lại clip** của 4 video gần nhất cùng kênh.

## 4. Quy trình làm một video

Mở Claude trong thư mục repo (`claude`), mở project video trong Resolve, rồi gõ lần lượt. **Sau mỗi bước Claude
dừng lại để bạn duyệt**; bạn nói "ok" thì mới sang bước sau.

| # | Gõ | Kết quả |
|---|---|---|
| 1 | `/doc-edit D:\Chann_X\video\audios` | Narration lên A2, cắt đúng từng câu theo timestamp |
| 2 | `/doc-edit plan` | Danh sách shot + clip chọn sẵn + âm thanh → `plan.md` để bạn duyệt |
| 3 | `/doc-edit place` | Đặt V1, âm thanh A3-A9, marker đỏ ở chỗ THIẾU footage (có backup timeline) |
| 4 | `/doc-edit missing-prompts` | Prompt để bạn tự tạo clip AI cho các shot THIẾU |
| 5 | Lưu clip AI mới vào `D:\AI_video\_check` → `/process-ai-video` → `/scan-source ai` → `/tag-source` | Clip mới được xử lý, gắn tag, xếp vào thư mục loài |
| 6 | Lặp lại 2 → 3 | Lấp chỗ THIẾU |
| 7 | `/doc-edit reframe` | Lấp viền đen, vài cú punch-in có chủ đích |
| 8 | `/intro-music-visualization` | Dựng intro theo nhạc trên timeline Open |
| 9 | `/audio-expert` | Nhạc, SFX, âm thanh tự nhiên A5-A9 |
| 10 | "chỉnh màu cho đồng bộ" | `colorist` (grade.py): cả phim như cùng một nơi |
| 11 | `/doc-edit done <video>` | Ghi ledger, chuyển thư mục vào `_done`, đóng Resolve |

Sửa nhỏ bất cứ lúc nào, nói tự nhiên:
- "shot ở 21:38 có logo góc trên trái" → xoá logo, relink (bản sạch nằm ở `D:\AI_video\_nologo`)
- "đổi shot ở 00:43 vì có cá sấu" → thay đúng 1 clip
- "media offline, relink lại" / "ở 12:30 đang là clip gì?"
- "nhớ là ..." → Claude lưu vào memory dự án

## 5. Lệnh hữu ích

| Lệnh | Việc |
|---|---|
| `/project-status` | Tóm tắt project, timeline, track |
| `/review-frame 01:10 02:35` | Claude xem frame đã grade và đề xuất cách sửa |
| `/doc-edit check-timelines` | Ghi lại clip đang dùng trên Edit + Open vào ledger |
| `/memory-find <từ khoá>` / `/memory-save <điều cần nhớ>` | Tìm / lưu memory dự án |
| `.\dvr.cmd info` · `at 21:09` · `find shot_028` · `offline` | Xem nhanh không cần Claude |

## 6. Luật an toàn (Claude luôn tuân theo)

- Việc phá huỷ (xoá clip/track, đặt lại timeline, áp grade) → Claude **liệt kê trước và chờ bạn nói "yes"**.
- Luôn có timeline backup `Edit_bak_*` trước khi đổi lớn. Không bao giờ đụng timeline **Master**.
- Ổ `Z:` chỉ đọc. Claude **không tự xoá file**: nó đưa lệnh để bạn chạy.
- Thư mục `D:\Chann_*\_pushed` là của bạn: Claude không đọc, không đụng.

## 7. Gặp lỗi

| Hiện tượng | Cách xử lý |
|---|---|
| "DaVinci Resolve is not reachable" | Mở Resolve + project; kiểm tra External scripting = Local |
| Media offline | Nói "relink lại media", hoặc `.\dvr.cmd offline --relink <cũ> <mới> --apply` |
| `Z:` không thấy | Map lại ổ mạng |
| Plan chạy lâu lần đầu | Đang đo YOLO / embed caption lần đầu, các lần sau dùng cache |
| Kiểm tra cài đặt | `.\dvr.cmd doctor` và `.venv\Scripts\python.exe .work\tools\memory_gateway.py doctor` |
