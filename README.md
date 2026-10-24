# Claude Video Editor: trợ lý hậu kỳ phim tài liệu thiên nhiên trong DaVinci Resolve

Claude Code + các script Python dựng phim tài liệu kiểu BBC Earth (footage thật + clip AI Veo/Kling, giọng đọc
ElevenLabs). Bạn đưa kịch bản và giọng đọc. Claude đặt narration và phụ đề, hiểu câu chuyện, chọn footage theo cảm xúc
từng đoạn, đặt lên timeline, viết prompt cho shot thiếu, xoá logo, chỉnh màu và sắp xếp âm thanh. **Bạn gọi và duyệt
từng bước**; Claude làm xong một bước thì dừng.

Đọc file này là đủ để dùng hằng ngày. Muốn hiểu bên trong (dữ liệu nằm ở đâu, trông ra sao, plan chọn clip thế nào):
[docs/SYSTEM.md](docs/SYSTEM.md).

---

## 1. Cần có

| Thứ | Ghi chú |
|---|---|
| Windows 10/11 | |
| DaVinci Resolve 19+ (Studio khuyên dùng) | Preferences > System > General > **External scripting using = Local**, rồi mở lại Resolve |
| Python 3.11 hoặc 3.12, 64-bit | python.org, tick "Add python.exe to PATH" |
| Claude Code | `npm i -g @anthropic-ai/claude-code`, hoặc bản desktop / VS Code |
| ffmpeg | `winget install Gyan.FFmpeg` |
| GPU NVIDIA (khuyên dùng) | YOLO đo vị trí con vật lúc plan; không có thì cài với `-SkipYolo` |
| Ổ mạng chung map thành `Z:` | Thư viện footage thật, nhạc, SFX. **Chỉ đọc + copy** |
| PostgreSQL 18 (tuỳ chọn) | Bản sao thư viện để tra cứu nhanh (mục 8). Không có vẫn chạy bình thường |

## 2. Cài đặt (một lần)

```powershell
git clone https://github.com/hehoha3/Claude_Vid_editor.git D:\Claude_editor
cd D:\Claude_editor
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

`setup.ps1` tạo `.venv`, cài thư viện và YOLO, tải model Whisper + e5 (~1 GB, một lần), chạy toàn bộ self-test và
`doctor`. Không có GPU NVIDIA: thêm `-SkipYolo`.

Sau đó:
1. Mở `config.toml`, kiểm tra `[paths] ai_video` (thư mục clip AI trên máy bạn, mặc định `D:\AI_video`) và
   `[workspaces] globs` (thư mục kênh, mặc định `D:\Chann_*`).
2. Mở Resolve + một project, chạy `.\dvr.cmd doctor`: phải thấy `[OK]` cho Resolve.
3. **Dữ liệu của team bạn** (không bao giờ có trong git: repo này dùng chung cho nhiều team). Xin trưởng nhóm gói
   `team_data_<ngày>.zip`, rồi nhập vào repo:
   ```powershell
   .venv\Scripts\python.exe .work\tools\team_data.py import D:\team_data_20261024.zip
   .venv\Scripts\python.exe .work\tools\memory_gateway.py index      # dựng lại chỉ mục memory
   ```
   Gói chứa: index thư viện + tag (`.work\library\`), plan + ledger (`.work\doc_edit\`), memory dự án
   (`.work\knowledge\`), license nhạc, registry logo, batch tag đang dở. Team mới (chưa có gói): bỏ qua bước này,
   chạy `/scan-source` rồi `/tag-source` để tạo thư viện của team mình (mục 7).
4. Clip AI của team đặt ở `D:\AI_video\` (Africa: `D:\AI_video\_africa\`); thư viện chung ở `Z:` (chỉ đọc).

Mỗi lần mở phiên, Claude tự in trạng thái dự án (`handoffs/current.md`) nhờ hook trong `.claude\settings.json`.
Quyền riêng của bạn (nếu cần) đặt trong `.claude\settings.local.json`, file này không lên git.

## 3. Chuẩn bị một video

```
D:\Chann_<số>_<tên kênh>\        <- một "workspace" = một kênh (ví dụ D:\Chann_2_darkAmazona)
    <video>\audios\              <- đầu vào của video (ví dụ africa_4\audios)
        <Tên>_Screenplay_EN.md         bắt buộc: kịch bản theo beat (mục 3.1)
        <Tên>_Timestamp_EN_VI.md       bắt buộc: mỗi câu narration một dòng [mm:ss.s], phần ## English + ## Vietnamese
        <Tên>_Visual_Edit_Plan_EN.md   tuỳ chọn: bible nhân vật, luật chọn shot, cung chương
        mp3\1.mp3, 2.mp3 ...           giọng đọc, mỗi câu một file, file n = dòng timestamp n
    _done\<video>\               <- video đã xong (bước done tự chuyển vào)
    _pushed\                     <- của riêng bạn, Claude không bao giờ đụng
```

- Tên project trong Resolve: tên thư mục video, hoặc tên kênh kiểu `c2_africa4` (nói rõ khi gọi lệnh). Mỗi project có
  timeline **Edit** (phim) và **Open** (intro riêng, nếu có). Mọi timeline luôn nằm trong bin `6. Timeline`
  (tự tạo nếu chưa có): mỗi lần script tạo backup `Edit_bak_*`, mọi timeline nằm ngoài bin (trừ Master) được gom vào.
- Timestamp: phần `## English` là thứ được đặt lên A2 và dùng để plan; phần `## Vietnamese` (cùng số dòng) thành
  phụ đề `subtitles_vi.srt` trên Subtitle 1. Thiếu phần tiếng Việt thì Claude dừng và báo.
- Chưa có giọng đọc vẫn plan được (độ dài câu được ước tính); thả `mp3\` vào rồi gọi lại lệnh để đặt A2.
- File mp3 lỗi của ElevenLabs thường nhỏ hơn 2 KB: Claude kiểm tra trước và liệt kê mọi file hỏng một lần.

### 3.1 Screenplay mà hệ thống đọc tốt nhất

Mỗi beat một khối như sau (Claude gắn các câu narration vào đúng beat theo thời gian):

```markdown
**001 · 00:00.6–00:30.6** — Wide dusk: hyenas around a wildebeest carcass; a lioness makes a short rush; cut before possession.
*Character lock:* H1 adult spotted hyenas (sex undetermined), L1/L2 adult female lions.
*Narrator:* The meal is already on the ground. A lioness charges through the hyenas...
```

Ghi rõ giới tính, tuổi, kết cục (bắt được hay hụt) và điều **không** được thấy (không giết, không máu, không con
đực...). Hệ thống coi đó là luật cứng: thà báo THIẾU còn hơn dùng một clip kể sai truyện.

## 4. Quy trình làm một video

Mở Claude trong thư mục repo (`claude`), mở project video trong Resolve, rồi **bạn tự gọi từng bước**:

| # | Bạn gõ | Claude làm | Bạn kiểm tra |
|---|---|---|---|
| 1 | `/doc-edit D:\Chann_2_darkAmazona\africa_4\audios africa` (vùng: `amazon` hoặc `africa`; nói tên project nếu khác tên thư mục) | Narration lên A2 + phụ đề; đọc kịch bản → beat sheet (cảm xúc từng đoạn) → spec → plan; prompt cho shot THIẾU; đặt V1, A1, A3-A9 + marker từ story 1 (intro 0:00-1:30 để trống, cắt chung sau) | `<video>\plan.md`, `missing_prompts.txt`, marker đỏ/vàng trên timeline |
| 2 | (bạn) tạo clip AI theo `missing_prompts.txt` | | Lưu vào `D:\AI_video\_check` (Africa: `D:\AI_video\_africa\_check`) |
| 3 | `/doc-edit logo`, rồi `/doc-edit delogo` | Tìm logo trên clip mới, xoá bằng MiniMax → bản sạch ở `D:\AI_video\_nologo` | Các clip "REVIEW FIRST" |
| 4 | `/doc-edit ingest --fill` | Quét + tag clip mới, xếp vào thư mục loài, lấp các slot THIẾU trên timeline | Dòng "THIẾU left" |
| 5 | `/doc-edit reframe` | Lấp viền đen, vài cú punch-in có chủ đích | |
| 6 | `/audio-expert` | Nhạc, SFX, âm thanh tự nhiên A5-A9 | Nghe lại các điểm Claude nêu |
| 7 | `/doc-edit color` | Chỉnh màu nhẹ, tươi sáng; cỏ vàng chỉ trong đoạn cỏ cháy (xem trước rồi mới áp) | ≥ 12 frame Claude đã xem |
| 8 | `/doc-edit done <video>` | Render `Done_<project>.mp4`, ghi license, ledger, chuyển thư mục vào `_done`, đóng Resolve | |

Lệnh rời: `/doc-edit plan` (lên lại plan sau khi sửa), `/doc-edit missing-prompts [mm:ss-mm:ss]`,
`/doc-edit place`, `/doc-edit fill`, `/doc-edit status` (mọi video đang ở bước nào, lệnh tiếp theo là gì).

**Đọc plan.md**: mỗi dòng là một shot. **OK** = khớp tốt; **WEAK** (vàng) = tạm được, nên xem; **THIẾU** (đỏ) =
không có clip đúng truyện, cần tạo clip AI; **FALLBACK** = shot phụ thay thế. `VO ●` = có giọng đọc; `★` = shot intro
lấy từ cao trào của story sau; `↻` = clip dùng lại một đoạn khác; `⏱` / `🔍` = đổi tốc độ / punch-in.

### Sửa nhỏ bất cứ lúc nào, nói tự nhiên
- "shot ở 21:38 có logo góc trên trái" → xoá logo, relink
- "đổi shot ở 00:43 vì có cá sấu" → thay đúng 1 clip, không đụng phần khác
- "đoạn 12:00-14:00 phải căng hơn" → Claude đổi cảm xúc của beat đó, plan lại
- "media offline, relink lại" / "ở 12:30 đang là clip gì?"
- "nhớ là ..." → Claude lưu vào memory dự án

## 5. Lệnh hữu ích

| Lệnh | Việc |
|---|---|
| `/project-status` | Tóm tắt project, timeline, track |
| `/review-frame 01:10 02:35` | Claude xem frame đã grade và đề xuất cách sửa |
| `/doc-edit check-timelines` | Ghi lại clip đang dùng trên Edit + Open vào ledger |
| `/scan-source`, `/tag-source` | Sau khi thêm/đổi footage vào thư viện: quét lại, tag clip mới |
| `/thumbnail` | Hoàn thiện ảnh thumbnail (crop 16:9, màu, chữ, logo) vào `D:\Thumbs` |
| `/memory-find <từ khoá>` / `/memory-save <điều cần nhớ>` | Tìm / lưu memory dự án |
| `.\dvr.cmd info` · `at 21:09` · `find shot_028` · `offline` | Xem nhanh không cần Claude |
| `.\dvr.cmd backups` | Đếm timeline backup (nhiều quá làm Resolve lag); `--keep 3 --apply` dọn bớt |
| `.\dvr.cmd timelines` | Gom mọi timeline (trừ Master) vào bin `6. Timeline`; script cũng tự gom mỗi lần tạo backup |

## 6. Luật an toàn (Claude luôn tuân theo)

- Việc phá huỷ (xoá clip/track, đặt lại timeline, áp grade) → Claude **liệt kê trước và chờ bạn nói "yes"**.
  Gọi đúng lệnh của một bước = đồng ý cho thay đổi bước đó ghi rõ.
- Luôn có timeline backup `Edit_bak_*` trước khi đổi lớn. Không bao giờ đụng timeline **Master**.
- Ổ `Z:` chỉ đọc. Claude **không tự xoá file**: nó đưa lệnh để bạn chạy.
- Thư mục `D:\Chann_*\_pushed` là của bạn: Claude không đọc, không liệt kê, không đụng.
- Không chạy git trừ khi bạn yêu cầu.

## 7. Bảo trì

```powershell
.venv\Scripts\python.exe -m tests.test_pipeline                 # mọi self-test (không cần Resolve), ~10 s
.venv\Scripts\python.exe .work\tools\cleanup_workspace.py       # liệt kê rác có thể xoá (dry run)
.venv\Scripts\python.exe .work\tools\cleanup_workspace.py --apply   # xoá thật (bạn tự chạy)
.venv\Scripts\python.exe .claude\skills\tag-source\scripts\tag_source.py status   # bao nhiêu clip đã tag
.venv\Scripts\python.exe .work\tools\team_data.py export D:\team_data_<ngày>.zip   # gói dữ liệu team để gửi đồng đội
```

**Team mới dùng repo này**: thư viện footage / nhạc của team bạn có thể ở chỗ khác `Z:\Unseen\...`. Đường dẫn các
root nằm trong `ROOTS` của `.claude\skills\scan-source\scripts\scan_source.py` (vùng: `REGION`), thư mục clip AI và
thư mục kênh trong `config.toml`. Sửa cho đúng máy team bạn, rồi `/scan-source` → `/tag-source`.

## 8. PostgreSQL (tuỳ chọn): tra cứu thư viện nhanh

JSON trong `.work\library\` vẫn là dữ liệu gốc; PostgreSQL chỉ là bản sao để Claude (và bạn) hỏi nhanh kiểu "bao nhiêu
clip sư tử cái đang chạy chưa dùng trong 6 video gần nhất", "nhạc nào đã dùng ở video khác".

1. Cài PostgreSQL 18 (bộ cài EDB; không cần Stack Builder). Tạo database `dvr_library` (pgAdmin: Databases >
   Create > Database).
2. Lưu mật khẩu vào `%APPDATA%\postgresql\pgpass.conf`, một dòng: `localhost:5432:dvr_library:postgres:<mật khẩu>`.
   Không bao giờ ghi mật khẩu vào file trong repo.
3. Biến môi trường người dùng: `LIBRARY_DB` = `host=localhost dbname=dvr_library user=postgres`.
4. `.venv\Scripts\python.exe .work\tools\library_db.py sync` (chép lại toàn bộ, vài giây; Claude tự chạy sau khi
   tag hoặc plan).
5. Xem: pgAdmin (`dvr_library > Schemas > public > Tables`, chuột phải > View/Edit Data) hoặc
   `library_db.py query "SELECT ..."`. Đừng sửa tay: lần `sync` sau sẽ ghi đè.

## 9. Gặp lỗi

| Hiện tượng | Cách xử lý |
|---|---|
| "DaVinci Resolve is not reachable" | Mở Resolve + project; kiểm tra External scripting = Local |
| Media offline | Nói "relink lại media", hoặc `.\dvr.cmd offline --relink <cũ> <mới> --apply` |
| `Z:` không thấy | Map lại ổ mạng |
| Claude báo "unreadable file(s), re-export" | Xuất lại đúng các file mp3 được liệt kê từ ElevenLabs |
| Plan chạy lâu lần đầu | Đang đo YOLO / embed caption lần đầu; lần sau dùng cache. Africa luôn chỉ dùng cache |
| Resolve chậm dần | Nhiều timeline backup: `.\dvr.cmd backups --keep 3 --apply` |
| Kiểm tra cài đặt | `.\dvr.cmd doctor` và `.venv\Scripts\python.exe .work\tools\memory_gateway.py doctor` |
