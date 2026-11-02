# Claude Video Editor: trợ lý hậu kỳ phim tài liệu thiên nhiên trong DaVinci Resolve

Claude Code + script Python dựng phim tài liệu kiểu BBC Earth (footage thật + clip AI, giọng đọc ElevenLabs/Genmax).
Bạn đưa kịch bản và giọng đọc. Claude đặt narration và phụ đề, chọn footage theo câu chuyện, viết prompt cho shot
thiếu, xoá logo, chỉnh màu, render, viết title / description / tags và upload lên YouTube ở chế độ private.
Gemini làm 3 việc viết dài để Claude đỡ tốn: dịch phụ đề tiếng Việt, viết nháp prompt cho shot thiếu, viết SEO. Claude
duyệt và sửa mọi thứ Gemini viết.

Muốn hiểu bên trong: [docs/SYSTEM.md](docs/SYSTEM.md).

---

## 1. Cần cài trước

| Thứ | Cách cài |
|---|---|
| Windows 10/11 | |
| DaVinci Resolve 19+ (Studio khuyên dùng) | Mở Resolve > Preferences > System > General > **External scripting using = Local**, rồi tắt mở lại Resolve |
| Python 3.12 (64-bit) | python.org > Downloads. Lúc cài **tick ô "Add python.exe to PATH"** |
| Git | `winget install Git.Git` |
| ffmpeg | `winget install Gyan.FFmpeg` |
| Claude Code | `npm i -g @anthropic-ai/claude-code` (cần Node.js: `winget install OpenJS.NodeJS.LTS`), hoặc bản desktop / VS Code |
| Ổ mạng chung map thành `Z:` | Thư viện footage thật, nhạc, SFX. **Chỉ đọc + copy** |
| GPU NVIDIA | Không bắt buộc (dùng cho YOLO, bước 2.4) |

Cài xong thì **đóng hết PowerShell, mở lại** để máy nhận lệnh mới.

## 2. Cài đặt (một lần, khoảng 15 phút)

Mở **PowerShell** và gõ từng dòng, chờ dòng trước chạy xong.

**2.1 Tải code**
```powershell
git clone https://github.com/hehoha3/Claude_Vid_editor.git D:\Claude_editor
cd D:\Claude_editor
```

**2.2 Tạo môi trường Python riêng (`.venv`)**
```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
```

**2.3 Tải model (khoảng 1 GB, chỉ một lần)**
```powershell
.venv\Scripts\python.exe -m dvr_cowork prefetch
.venv\Scripts\python.exe .work\tools\memory_gateway.py selftest
```

**2.4 YOLO (chỉ khi có GPU NVIDIA, khoảng 3 GB)**. Không có GPU thì bỏ qua bước này, plan vẫn chạy bằng tag.
```powershell
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python.exe -m pip install "ultralytics>=8.4"
.venv\Scripts\yolo.exe settings "weights_dir=D:\Claude_editor\.models" "runs_dir=D:\Claude_editor\.work\yolo_runs" sync=False
```

**2.5 Đường dẫn của máy bạn**: mở `config.toml` bằng Notepad, sửa `ai_video` (thư mục clip AI, mặc định
`D:\AI_video`) và `[workspaces] globs` (thư mục kênh, mặc định `D:\Chann_*`).

**2.6 Kiểm tra**: mở Resolve + một project, rồi:
```powershell
.venv\Scripts\python.exe -m tests.test_pipeline
.\dvr.cmd doctor
```
Thấy `[OK]` ở dòng Resolve là xong.

**2.7 Dữ liệu của team** (không có trong git). Xin trưởng nhóm file `team_data_<ngày>.zip`, rồi:
```powershell
.venv\Scripts\python.exe .work\tools\team_data.py import D:\team_data_20261024.zip
.venv\Scripts\python.exe .work\tools\memory_gateway.py index
```
Team mới chưa có gói: bỏ qua, chạy `/scan-source` rồi `/tag-source` để tạo thư viện riêng.

### Có dùng database hay không?

| Cách | Cần làm gì | Khi nào chọn |
|---|---|---|
| **Không database** (mặc định) | Không làm gì thêm. Thư viện là file JSON trong `.work\library\`; trạng thái video và memory là SQLite, tự tạo, không cần cài | Hầu hết mọi người |
| **Có PostgreSQL** (tuỳ chọn) | Làm mục 6 | Bạn muốn tự hỏi nhanh kiểu "clip sư tử cái nào chưa dùng trong 6 video gần nhất" |

## 3. Gemini và YouTube (dịch, prompt, SEO, upload)

Không có Gemini thì Claude tự dịch và tự viết prompt như trước (tốn hơn); không có YouTube thì bước SEO và upload
bỏ qua. Mọi bước dựng vẫn chạy.

### 3.1 Gemini API key (miễn phí, khoảng 2 phút)
1. Vào **https://aistudio.google.com/apikey**, đăng nhập bằng Gmail.
2. Bấm **Create API key**, rồi bấm nút copy.
3. Trong PowerShell (ở `D:\Claude_editor`):
   ```powershell
   .venv\Scripts\python.exe .claude\skills\gemini-assist\scripts\gemini_bridge.py setup-key
   ```
   Dán key bằng chuột phải, rồi Enter. **Màn hình sẽ không hiện chữ**, đó là bình thường.
4. Kiểm tra:
   ```powershell
   .venv\Scripts\python.exe .claude\skills\gemini-assist\scripts\gemini_bridge.py check
   ```
   Thấy `"ok": true` là xong. Key được cất trong Windows Credential Manager, không nằm trong file nào, không lên git.

### 3.2 YouTube Data API (khoảng 10 phút, một lần)
1. Vào **https://console.cloud.google.com**, bấm chọn project ở góc trên > **New Project** > đặt tên > Create.
2. Ô tìm kiếm phía trên: gõ **YouTube Data API v3** > **Enable**.
3. Menu **Google Auth Platform** (hoặc "OAuth consent screen") > Get started: điền tên app, Gmail của bạn, chọn
   **External** > Create. Vào **Audience** > **Test users** > **Add users**: thêm Gmail sở hữu kênh YouTube.
4. **Clients** > **Create client** > loại **Desktop app** > Create > **Download JSON**.
5. Tạo thư mục `D:\Claude_editor\.secrets\youtube\`, chép file vừa tải vào, đổi tên thành `client_secret.json`.
6. Đăng nhập **từng kênh** (trình duyệt mở ra; chọn đúng tài khoản / kênh; gặp "Google hasn't verified this app" thì
   bấm Continue):
   ```powershell
   .venv\Scripts\python.exe -m dvr_cowork.youtube login
   ```
   Màn hình in `channel: <tên> | id: UC...`. Kênh thứ hai thì chạy lại lệnh và chọn kênh đó.
7. Tạo file `.secrets\youtube\channels.json` bằng Notepad, ghép thư mục kênh với ID vừa in:
   ```json
   {"Chann_1": "UCxxxxxxxxxxxxxxxxxxxxxx", "Chann_2": "UCyyyyyyyyyyyyyyyyyyyyyy"}
   ```
8. Kiểm tra: `.venv\Scripts\python.exe -m dvr_cowork.youtube channels` in ra đủ các kênh.

Ghi chú: project chưa được YouTube audit thì video upload luôn là **private**. Bạn tự bật public hoặc đặt lịch
trong Studio, và chọn **Thông tin tài sản: Web** (API không đặt được). Quota miễn phí 10.000/ngày: một lần upload
khoảng 1.600, một lần tìm trend SEO khoảng 300 (kết quả cache 7 ngày).

## 4. Chuẩn bị một video

```
D:\Chann_<số>_<tên kênh>\        <- một kênh (ví dụ D:\Chann_1_shadowCanopy)
    <video>\audios\              <- ví dụ amazon_301026\audios
        <Tên>_Screenplay_EN.md         kịch bản theo beat
        <Tên>_Timestamp_EN_VI.md       mỗi câu một dòng [mm:ss.s], phần ## English + ## Vietnamese (thành phụ đề)
        <Tên>_Visual_Edit_Plan_EN.md   tuỳ chọn
        mp3\1.mp3, 2.mp3 ...           giọng đọc, file n = dòng timestamp n
    _done\                       <- bạn tự chuyển video xong vào đây
    _pushed\                     <- của riêng bạn, Claude không bao giờ đụng
```
Bốn file trên do skill `/create-doc-mov` viết. Tên vùng nằm trong tên thư mục video (`amazon_...`, `africa_...`).
Nhiều kênh trong một ngày dùng chung project Resolve `vid_DDMMYY` (mỗi kênh một bin `Chann_N` và timeline Edit riêng).

## 5. Làm một video: 3 lệnh, 2 lần dừng

Mở Claude trong `D:\Claude_editor` (gõ `claude`), mở project trong Resolve, rồi:

| Phase | Bạn gõ | Claude làm | Rồi bạn |
|---|---|---|---|
| 1 | `/doc-edit D:\Chann_1_shadowCanopy\amazon_301026\audios` (2 kênh: thêm đường dẫn thứ hai) | Narration lên A2 + phụ đề, đọc kịch bản, plan, đặt intro + thân phim, viết `missing_prompts.txt` cho các shot THIẾU. **Dừng** | Tạo clip AI theo prompt, lưu vào `D:\AI_video\_check`; có logo thì `/doc-edit logo` + `/doc-edit delogo` |
| 2 | `/scan-source /tag-source và tiếp` | Quét + tag clip mới, xếp vào thư mục loài, lấp slot THIẾU. **Dừng** | Xem timeline, xử lý logo còn sót; tuỳ chọn `/doc-edit reframe`, `/audio-expert` |
| 3 | `/doc-edit color n done` | Chỉnh màu; cùng lúc tìm trend YouTube và nhờ Gemini viết 3 title trend cao nhất dạng `WILD AMAZON \| ... \| Wildlife Documentary` (title 1 = hút view nhất, được dùng), description, tags; render `Done_<video>.mp4`; upload **private, không thumbnail** | Xem trong YouTube Studio, đặt thumbnail, đặt lịch / public |

Không tạo clip nữa mà muốn lấp THIẾU bằng footage có sẵn: `/doc-edit fill-THIEU <video>`.
Muốn đổi title: nói "dùng title 2", hoặc `.venv\Scripts\python.exe -m dvr_cowork.seo <thư mục video> --pick 2`.

Lệnh lẻ (khi cần): `/doc-edit plan`, `/doc-edit missing-prompts [mm:ss-mm:ss]`, `/doc-edit fill`, `/doc-edit color`,
`/doc-edit seo`, `/doc-edit done`, `/doc-edit status` (video nào đang ở bước nào), `/thumbnail`, `/review-frame 01:10`.

**Sửa nhỏ, nói tự nhiên**: "shot ở 21:38 có logo góc trên trái", "đổi shot ở 00:43 vì có cá sấu", "đoạn 12:00-14:00
phải căng hơn", "ở 12:30 đang là clip gì?", "nhớ là ..." (lưu vào memory dự án).

**plan.md**: **OK** = khớp; **WEAK** (vàng) = nên xem; **THIẾU** (đỏ) = cần clip AI; **FALLBACK** = shot thay thế.

## 6. PostgreSQL (tuỳ chọn)

JSON trong `.work\library\` vẫn là dữ liệu gốc; PostgreSQL chỉ là bản sao để hỏi nhanh.
1. Cài PostgreSQL 18 (bộ cài EDB, bỏ Stack Builder). Mở pgAdmin > Databases > Create > Database: `dvr_library`.
2. Tạo file `%APPDATA%\postgresql\pgpass.conf`, một dòng: `localhost:5432:dvr_library:postgres:<mật khẩu>`.
3. Thêm biến môi trường người dùng `LIBRARY_DB` = `host=localhost dbname=dvr_library user=postgres`.
4. `.venv\Scripts\python.exe .work\tools\library_db.py sync` (Claude tự chạy lại sau khi tag hoặc plan).

## 7. Luật an toàn (Claude luôn tuân theo)

- Việc phá huỷ (xoá clip/track, đặt lại timeline, áp grade): Claude liệt kê trước và chờ bạn nói "yes". Gọi đúng
  lệnh của một bước = đồng ý cho thay đổi bước đó.
- Luôn có backup `Edit_bak_*` trước khi đổi lớn. Không đụng timeline **Master**.
- Ổ `Z:` chỉ đọc. Claude không tự xoá file, chỉ đưa lệnh để bạn chạy. `_pushed` là của bạn.
- Không bao giờ tự đăng video public. Không chạy git trừ khi bạn yêu cầu.

## 8. Gặp lỗi

| Hiện tượng | Cách xử lý |
|---|---|
| "DaVinci Resolve is not reachable" | Mở Resolve + project; kiểm tra External scripting = Local |
| `py` không chạy được | Cài lại Python và tick "Add python.exe to PATH"; mở PowerShell mới |
| Media offline | Nói "relink lại media", hoặc `.\dvr.cmd offline --relink <cũ> <mới> --apply` |
| `Z:` không thấy | Map lại ổ mạng |
| `No Gemini API key saved` | Làm lại mục 3.1 |
| `youtube: ... not logged in` / `token invalid` | `.venv\Scripts\python.exe -m dvr_cowork.youtube login`, chọn đúng kênh |
| `youtube: no channel for Chann_N` | Thêm `Chann_N` vào `.secrets\youtube\channels.json` |
| `quotaExceeded` | Hết quota YouTube trong ngày: chờ sang ngày mới (giờ Mỹ) |
| Resolve chậm dần | Nhiều backup: `.\dvr.cmd backups --keep 3 --apply` |
| Kiểm tra tổng | `.\dvr.cmd doctor` và `.venv\Scripts\python.exe -m tests.test_pipeline` |

Bảo trì, thêm root / vùng / loài, chia sẻ dữ liệu team: [docs/SYSTEM.md](docs/SYSTEM.md) mục 11-12.
