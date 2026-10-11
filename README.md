# DVR Co-worker — Claude chuyên gia hậu kỳ cho DaVinci Resolve

Workspace dùng với **Claude Code CLI trên Windows 11**. Gồm:

- **vo-sync**: đọc file timestamp + nghe audio narration bằng Whisper → import vào bin `4. Audio`
  → đặt lên track **A2** của timeline **Edit** → chia thành từng câu và đặt mỗi câu bắt đầu đúng
  thời điểm trong file timestamp.
- **Mắt cho Claude**: xuất frame đã grade từ timeline + "scope số" (độ sáng, clipping, saturation,
  ám màu) để Claude nhận xét có căn cứ.
- **Kiến thức chuyên gia** (Claude Code skills, chỉ nạp khi cần → tiết kiệm token): chỉnh màu,
  dựng phim tài liệu, âm thanh Fairlight, xuất YouTube, xử lý lỗi riêng của footage AI, API Resolve.

## 1. Cài đặt (một lần)

Yêu cầu: DaVinci Resolve 18.5+ (khuyến nghị 19/20), **Python 3.11 hoặc 3.12 64-bit** từ
python.org (tick "Add python.exe to PATH"), Claude Code.

Thêm: **ffmpeg** trên PATH (`winget install Gyan.FFmpeg`), ổ mạng chung map thành **`Z:`** (chỉ đọc + copy),
GPU NVIDIA cho YOLO (không có thì chạy setup với `-SkipYolo`).

1. `git clone <repo> D:\dvr-cowork` (đường dẫn nên không dấu).
2. Sửa `config.toml` → `[paths] ai_video` = thư mục clip AI trên máy bạn (mặc định `D:\AI_video`).
3. Mở PowerShell trong thư mục đó:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\setup.ps1
   ```
   Script tạo `.venv`, cài thư viện + torch/ultralytics (YOLO), tải model Whisper (~0,5 GB, một lần), chạy
   self-test và `doctor`. Index + tag thư viện (`.work/library/`) đã có sẵn trong repo: không cần tag lại.
4. Trong Resolve: **Preferences > System > General > External scripting using = Local**, khởi động lại Resolve.
5. Mở project, chạy lại kiểm tra: `.\dvr.cmd doctor` — cần thấy `[OK]` cho Resolve và timeline `Edit`.

> Nếu `doctor` vẫn không kết nối được (một số bản Free hạn chế scripting từ bên ngoài): chạy
> `install_inapp.ps1` một lần. Khi đó: `.\dvr.cmd vo-sync analyze ...` ở ngoài, rồi trong Resolve
> chọn **Workspace > Scripts > Utility > DVR_VO_Sync_apply_last_plan**.

## 2. Dùng với Claude Code

```powershell
cd D:\dvr-cowork
claude
```
Lệnh nhanh:
- `/sync-vo "D:\VO\ep1.mp3" "D:\VO\ep1_timestamps.txt"` — đồng bộ narration lên A2
- `/review-frame 01:10 02:35 04:02` — Claude xem frame đã grade và đề xuất cách sửa cụ thể
- `/project-status` — tóm tắt project / timeline / track

Hoặc nói tự nhiên: "cảnh rừng ở 03:20 nhìn giả quá, sửa sao?", "mix nhạc dưới narration thế nào?"…

Chạy tay không cần Claude: `.\dvr.cmd vo-sync run "D:\VO\ep1.mp3" "D:\VO\ep1_timestamps.txt"`

## 3. vo-sync hoạt động thế nào

File timestamp (UTF-8), mỗi dòng một câu, `[mm:ss]` là thời điểm câu bắt đầu trên timeline:
```
[00:15] As the first light touches the canopy, the harpy eagle is already watching.
[00:42] Forty metres below, a troop of brown capuchins moves through the figs.
```
Hỗ trợ thêm `[hh:mm:ss]`, `[mm:ss.5]`, dòng `#` là ghi chú, câu xuống dòng được nối vào câu trước.

Các bước:
1. Whisper nghe audio, lấy thời gian từng từ (có cache: chạy lại không phải nghe lại).
2. Khớp từng câu trong file với lời nghe được (chịu được từ nghe sai, số viết bằng chữ/số).
3. Tinh chỉnh điểm cắt vào **đúng khoảng lặng thật** giữa hai câu trên dạng sóng (chính xác ~10 ms;
   Whisper một mình lệch 50–200 ms).
4. Trong Resolve: tạo bin `4. Audio` nếu chưa có, import audio nếu chưa có, tạo track A2 nếu chưa
   có, **sao lưu timeline** (`Edit_bak_...`), xoá các đoạn cũ của chính file này trên A2, rồi đặt
   từng câu sao cho **âm tiết đầu tiên rơi đúng timestamp** (giữ 0,10 s trước và 0,25 s sau câu để
   không mất hơi thở/đuôi âm).
5. Kiểm tra lại vị trí từng đoạn, ghi báo cáo `.work/<tên audio>/report.md`.

**Về "blade":** API scripting của Resolve không có lệnh Blade. Khi bạn blade bằng tay, Resolve tạo
nhiều clip trên timeline cùng trỏ vào **một file nguồn** với điểm in/out khác nhau. Công cụ tạo ra
đúng cấu trúc đó — **không cắt ra file nhỏ nào**, vẫn roll/slip/ripple từng đoạn như clip đã blade.

Màu trên A2: **cam** = câu cần nghe lại (nhận dạng kém / ranh giới không rõ), **hồng** = câu bị đẩy
muộn vì câu trước dài hơn khoảng trống tới timestamp kế tiếp. Không màu = sạch.

Tuỳ chọn: `--markers` (marker kèm nội dung câu), `--dry-run` (chỉ tính, không đổi gì),
`--on-overlap push|trim|abort`, `--force-clear` (A2 đang có clip khác), `--no-backup`.
Mọi thông số khác trong `config.toml`.

**Lần chạy thật đầu tiên:** nên chạy `--dry-run` trước, sau đó chạy thật và nghe 2–3 điểm nối.
Dòng `verify:` trong kết quả phải là `0f`. Đây là phần duy nhất tôi không thể chạy thử trên
Resolve thật (toàn bộ logic đã được test với Resolve giả lập), nên hãy để ý dòng này lần đầu.

## 4. Chi phí và tốc độ
- Phần nặng (nghe, khớp, tính frame) chạy bằng Python cục bộ, **không tốn token Claude**. Claude
  chỉ đọc bản tóm tắt vài dòng.
- Whisper `small.en` trên CPU: vài phút cho 30 phút narration. Nhanh hơn: `model = "base.en"`.
- Skills chỉ nạp khi chủ đề liên quan; `CLAUDE.md` giữ ngắn.

## 5. Về CLI-Anything
Không cần cho workspace này: Resolve đã có API Python chính thức (công cụ dùng trực tiếp) và bạn đã
có MCP DaVinci cho thao tác chung. CLI-Anything hữu ích với phần mềm *không* có API tốt (như
FreeCAD/KiCad trong project robot của bạn).

## 6. Cấu trúc
```
CLAUDE.md                vai trò + quy tắc (luôn nạp, ngắn)
.claude/commands/        /sync-vo, /review-frame, /project-status
.claude/skills/          doc-edit, scan-source, tag-source, process-ai-video, audio-expert, colorist,
                         edit-craft, hide-logo, resolve-api
dvr_cowork/              mã nguồn CLI (vo-sync, frames, info, doctor)
luts/                    LUT Amazona (make_luts.py, README = luật thiết kế)
.models/                 Whisper, YOLO-World + CLIP (tải tự động)
.work/                   cache + index thư viện + plan từng video (không commit)
inapp/                   script chạy trong Resolve (phương án dự phòng)
tests/                   self-test (audio tổng hợp + Resolve giả lập)
config.toml              thông số
setup.ps1, dvr.cmd, install_inapp.ps1
examples/                file timestamp mẫu
```

## 7. Sự cố thường gặp
| hiện tượng | cách xử lý |
|---|---|
| `ERROR (resolve)` không kết nối | Resolve đang mở project? External scripting = Local? Hoặc dùng in-app |
| `ERROR (input) line N` | sửa dòng N trong file timestamp (thời gian không tăng, thiếu `[ ]`, giây ≥ 60) |
| nhiều câu bị đẩy (hồng) vài phần mười giây | timestamp chỉ chính xác tới giây; dùng `[01:10.4]` hoặc giãn kịch bản |
| mọi câu lệch đều một khoảng | `timestamp_offset` trong config |
| lệch tăng dần trên timeline 23.976 | đổi `timestamp_clock` thành `"realtime"` nếu timestamp lấy từ trình phát media |
| A2 đang có clip khác | chuyển chúng sang track khác hoặc dùng `--force-clear` |
