# Mountain AI — workspace dựng phim động vật vùng núi

Bản riêng từ nhánh `fear/create_doc_movie_content` của Claude_Vid_editor, dành cho **phim 8–11 phút full AI** ở núi tuyết/núi đá. Kể một câu chuyện sinh tồn liên tục; mở bằng hook 30s + giới thiệu 30s; narrator ít nghỉ. Bạn tự tạo voice và shot, Claude viết nội dung/lập kế hoạch/dựng trong Resolve.

Không dùng database, Gemini, kho footage, scan/tag, xử lý logo, colorist, audio-expert hay thumbnail. Chỉ còn ba skill: `create-doc-mov`, `doc-edit`, `resolve-api`.

## 1. Cài một lần

Giải nén workspace vào một thư mục mới, ví dụ `D:\Claude_Mountain_AI`. Không chép đè lên workspace dựng phim một giờ đang dùng.

Cần Windows 11, Python 3.11/3.12 x64, FFmpeg, Claude Code và DaVinci Resolve có khả năng external scripting. Mở Resolve → Preferences → System → General → External scripting using = Local. API thực tế phụ thuộc bản Resolve/Studio đang cài.

Kiểm tra workspace trước khi setup lần đầu:

```powershell
cd D:\Claude_Mountain_AI
py -0p            # phải thấy Python 3.11/3.12 x64
ffmpeg -version
ffprobe -version
```

Nếu chưa có FFmpeg/ffprobe, cài rồi **mở lại terminal** để PATH cập nhật, sau đó chạy lại hai lệnh kiểm tra:

```powershell
winget install --id Gyan.FFmpeg -e
```

Tạo venv bằng Python 3.12 trước khi chạy setup, rồi mới chạy `setup.ps1`:

```powershell
py -3.12 -m venv .venv
powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Nếu cần YouTube API:
powershell -ExecutionPolicy Bypass -File .\setup.ps1 -YouTube
```

Script chỉ cài dependency Python và chạy test; không tải model, tạo database hay chạy vào Resolve của bạn. Dùng `python -m dvr_cowork --help` trên Linux/macOS để kiểm tra phần file; thiết lập sản xuất dưới đây hướng tới Windows.

Tạo render preset trong Resolve tên **YouTube 1080 HEVC**, MP4/H.265, video + AAC audio, đúng fps của timeline. Tắt burn-in subtitle trong preset nếu không muốn chữ Việt xuất hiện trên phim. Không có preset thì script dừng, không tự đổi codec hay fps.

## 2. Cấu trúc mỗi video

Ví dụ thư mục video: `D:\Chann_3_Mountain\cliff_rescue`.

| Đường dẫn tương đối | Nội dung |
|---|---|
| audios/screenplay.md | Câu chuyện tiếng Anh, nhân vật, địa hình và các beat |
| audios/timestamp.md | Lời EN/VI cùng thời điểm bắt đầu; cập nhật theo MP3 thật |
| audios/transcript.md | Chỉ narrator English; mỗi dòng nội dung không trống = một MP3 |
| audios/visual_plan.md | Toàn bộ slot, thời gian, file và mục đích shot |
| audios/mp3/1.mp3 … N.mp3 | Bạn tạo theo thứ tự đoạn transcript |
| audios/music/ | Nhạc bạn chọn, kèm giấy phép/ghi nhận đăng ký |
| shots/1.mp4 … M.mp4 | Bạn tạo theo số prompt; **M không nhất thiết bằng N** |
| missing-prompt.md | Prompt đầy đủ cho mọi shot cần tạo |
| shot_manifest.csv | Số prompt ↔ tên MP4 ↔ slot timeline, không đổi sau khi phát hành |
| hook_selection.md | 5 đoạn 6s được chọn từ nguồn body đã QC |
| .production/ | Source JSON, plan, trạng thái, QC và receipt của riêng video này |
| Done_cliff_rescue.mp4 | Bản xuất; lần xuất sau dùng _v2, _v3… |

`1.mp3` = **dòng nội dung không trống đầu tiên trong transcript**; `1.mp4` = **prompt hình đầu tiên**. Một dòng narrator có thể gồm nhiều câu nối thành đoạn tự nhiên. Dòng trống chỉ phân cảnh, không tạo MP3. Không đếm số đoạn Markdown đang hiển thị trên màn hình. Hai bộ số độc lập. Nếu bạn tạo một voice.mp3 dài cho cả phim, cần tách theo các block trước khi chạy; bản nhẹ này không có Whisper để tự căn một file dài.

## 3. Quy trình bạn sử dụng hằng ngày

Mở Claude Code trong thư mục workspace mới.

| Bạn nói/gõ | Claude thực hiện | Điểm dừng |
|---|---|---|
| `/create-doc-mov Chann_1` | Tra xu hướng (vidIQ), đề xuất 3–5 concept 8–15 phút; bạn chọn concept + xác nhận dàn nhân vật; tạo `D:\Chann_1_*\vid_DDMMYY_N` và 4 file | Chờ bạn tạo voice |
| `/create-doc-mov Chann_1 <link YouTube>` | Phân tích video mẫu, giữ kiểu truyện + cách tạo căng thẳng, đổi địa hình/sự kiện/lời kể; hỏi bạn có đổi dàn nhân vật không; tạo folder và 4 file | Chờ bạn tạo voice |
| `/create-doc-mov D:\Chann_3_Mountain\cliff_rescue 8 <ý tưởng>` | Viết câu chuyện gốc, khóa nhân vật/địa hình, hook 30s + setup 30s, xuất và kiểm tra 4 file | Chờ bạn tạo voice |
| “Voice đã ở …\audios\mp3”, hoặc `/doc-edit …\audios` | Đo/kiểm tra MP3, conform timestamp, đưa narrator lên A2, tạo phụ đề Việt, plan mọi slot và missing-prompt | Chờ bạn tạo video |
| “Shot đã ở …\shots”, hoặc `/doc-edit ingest <video-folder>` | Kiểm tra số/file/duration/audio, xem ảnh đối chiếu prompt, chọn hook từ clip thật, dựng toàn bộ V1 + A1 | Chờ bạn review |
| “OK” rồi `/doc-edit done <video-folder>` | Kiểm tra timeline bạn đã sửa, render và xác minh file; chuẩn bị upload nếu cấu hình | Giao bản render; upload theo đúng thông tin đã duyệt |

Ghi rõ `11` thay `8` nếu muốn 11 phút; thời lượng dài hơn cũng được. Hệ thống không ép 60 scene × 10s.

## 4. Timeline và bin

Một project `vid_DDMMYY_N` chứa video cùng số của mọi kênh (mỗi kênh một video): `D:\Chann_1_*\vid_021126_1`, `D:\Chann_2_*\vid_021126_1`… cùng dựng trong project `vid_021126_1`. Mỗi kênh có bin gốc riêng `Chann_N`:

| Bin (trong `Chann_N/`) | Dùng cho |
|---|---|
| 1. shots | Shot video và natural audio gắn cùng nguồn |
| 2. Audio/Narrator | Narrator MP3 |
| 2. Audio/Music | Nhạc |
| 3. Graphics/sub-title | SRT tiếng Việt |
| 4. Timeline | `Edit` của kênh đó và các backup của nó |

Các kênh đều có timeline tên `Edit`; công cụ phân biệt theo bin `Chann_N/4. Timeline`, nên đừng kéo `Edit` sang bin kênh khác. Hai `Edit` trong cùng bin một kênh, hoặc track A4+, sẽ bị từ chối. Thư mục video nằm ngoài `Chann_N_*` dùng bố cục cũ (bin ở gốc). Muốn tên project khác thì ghi `resolve_project` trong source trước khi build.

Folder kế tiếp của một kênh (kèm archetype nên dùng và các video gần đây): `.\dvr.cmd next-video Chann_1`. Tra xu hướng YouTube không cần thư mục video: `.\dvr.cmd youtube-trends Chann_1 [--query "..."]`, xem số liệu video mẫu: `.\dvr.cmd youtube-reference Chann_1 <link>` (API chính thức không cho tải transcript video kênh khác; transcript lấy qua vidIQ).

| Track | Nội dung |
|---|---|
| V1 | Hình, mọi shot 6–9s |
| A1 — Shot Sound | Tiếng đúng shot trên V1, được link, suốt cả phim |
| A2 — Narrator Voice | Narrator theo timestamp đã conform |
| A3 — Music | Nhạc bạn chọn |

Hook dùng 5 đoạn × 6s từ body, không làm mất shot trong phần kể chuyện. Đây là lặp có chủ đích cho teaser. Không tự rút shot hook xuống 1–3s; nếu muốn một cấu hình cắt nhanh khác, cần đổi rõ quy tắc với Claude trước khi tạo shot.

Giọng đọc được lập ngân sách theo 85–92% thời lượng; khoảng nghỉ mặc định tối đa 3s. Compiler kiểm tra duration file, không nhận diện mọi khoảng lặng trong file; vẫn cần nghe voice thật.

## 5. Lệnh kỹ thuật để kiểm tra

Thay `<video>` bằng đường dẫn video đầy đủ, luôn đặt trong dấu ngoặc kép.

```powershell
.\dvr.cmd init "<video>" --minutes 8 --title "English title"
# Claude viết source: <video>\.production\story.json
.\dvr.cmd build "<video>"
.\dvr.cmd validate "<video>"
.\dvr.cmd conform "<video>"
.\dvr.cmd info "<video>"
.\dvr.cmd voice "<video>" --apply
.\dvr.cmd plan "<video>"
.\dvr.cmd prompts "<video>"
# Chờ shots/1.mp4…M.mp4
.\dvr.cmd ingest "<video>"
.\dvr.cmd sheets "<video>"
# Claude xem ảnh, đối chiếu prompt và điền .production/shot_qc.json
.\dvr.cmd hook "<video>"
.\dvr.cmd assemble "<video>" --apply
.\dvr.cmd check "<video>"
# Chờ bạn review/OK
.\dvr.cmd done "<video>" --apply
.\dvr.cmd render-status "<video>"
.\dvr.cmd status "<video>"
```

`voice`, `assemble`, `music`, `done` không có `--apply` chỉ in phạm vi dự kiến. `/doc-edit` là skill điều phối các lệnh; file source chưa viết hoàn chỉnh thì `build` sẽ dừng có lý do, không tạo một phim giả để báo PASS.

Nhạc: cạnh `track.mp3`, tạo `track.mp3.license.txt` chứa giấy phép hoặc thông tin đăng ký thực tế cho project. Dùng `dvr music "<video>" "<file>" --start 0 --apply`. A1 −12dB và A3 −24dB chỉ là gain ban đầu; nghe và sửa nhạc trong review, không coi đó là chuẩn LUFS.

## 6. Upload YouTube, tùy chọn

### 6.1 Cài kênh (một lần, khoảng 10 phút)

1. Vào **https://console.cloud.google.com** > **New Project** > đặt tên > Create.
2. Ô tìm kiếm: **YouTube Data API v3** > **Enable**.
3. **Google Auth Platform** (hoặc "OAuth consent screen") > Get started: tên app, Gmail của bạn, chọn **External** > Create. **Audience** > **Test users** > **Add users**: thêm Gmail sở hữu kênh.
4. **Clients** > **Create client** > **Desktop app** > Create > **Download JSON**.
5. Chép file vào `.secrets\youtube\client_secret.json` (`.secrets/` đã nằm trong `.gitignore`). Không gửi JSON/token lên chat hay commit.
6. Thêm kênh bằng các lệnh ở mục 6.2.

### 6.2 Quản lý kênh

| Việc | Lệnh |
|---|---|
| Thêm kênh mới (số kế tiếp, ví dụ 3) | `.\dvr.cmd youtube-login --key Chann_3`, rồi tạo thư mục `D:\Chann_3_<tên kênh>` |
| Xem các kênh hiện có, token còn tốt không | `.\dvr.cmd youtube-channels` |
| Đăng nhập lại khi token hỏng / bị thu hồi | `.\dvr.cmd youtube-login --key Chann_N` (đúng số cũ, chọn đúng kênh đó) |
| Gỡ kênh khỏi máy | `.\dvr.cmd youtube-remove Chann_N`, rồi thu hồi quyền app ở https://myaccount.google.com/permissions nếu không dùng nữa |

`youtube-login` mở trình duyệt; chọn đúng tài khoản / Brand Account (gặp "Google hasn't verified this app" thì bấm Continue; 5 phút không đăng nhập thì lệnh tự dừng). Token lưu ở `.secrets\youtube\tokens\<channel_id>.json`, `--key` ghi vào `.secrets\youtube\channels.json`. Một số `Chann_N` đã gắn kênh khác thì lệnh dừng, không ghi đè: gỡ bằng `youtube-remove` trước. Video đặt trong `D:\Chann_N_<tên>\<video>` tự lên kênh `Chann_N`.

### 6.3 SEO và upload

1. `youtube-seo "<video>"`: tìm trend YouTube từ tên loài trong story (video 4–20 phút, 90 ngày, xếp theo view/ngày; khoảng 200 quota lần đầu, cache 7 ngày) và in bản tóm tắt ngắn. Claude chỉ viết `.production/seo_draft.json` (3 title, hook, tóm tắt, tags).
2. `youtube-seo "<video>" --write`: code tự ráp `youtube_meta.json` (giữ nguyên 3 title Claude viết theo kiểu 3 video mẫu, chỉ kiểm tra dạng `<câu chuyện> | <nhãn>` ≤100 ký tự; mô tả có chương mục từ plan và câu công bố AI, tags ≤500 ký tự) và cảnh báo nếu title nhắc loài không có trong phim. Đổi title: sửa `pick` trong draft rồi `--write` lại.
3. Preview bằng `youtube-upload "<video>"` (kênh suy ra từ thư mục; `--channel UC...` để ghi đè).
4. Duyệt đúng kênh, file, metadata và chế độ. Claude ghi hash của preview đã duyệt, rồi chạy thêm `--apply`. Mặc định **private**. Lịch công khai chỉ được thêm khi bạn yêu cầu, ví dụ `--publish-at "2026-11-03T18:00:00+07:00"`.

Quota miễn phí 10.000/ngày: một lần upload khoảng 1.600, một lần SEO khoảng 200 (0 nếu cache). Hết quota (`quotaExceeded`) thì chờ khoảng 14:00–15:00 giờ VN. Thumbnail đặt tay trong Studio.

Luôn bật trường công bố realistic synthetic media. API project chưa được YouTube audit có thể bị khóa upload private; bản code không tự vượt giới hạn đó. Upload có kết quả chưa rõ thì dừng để kiểm tra Studio, tránh tạo bản trùng.

## 7. Kiểm thử và giới hạn

```powershell
.venv\Scripts\python.exe -m unittest discover -v
```

Tests kiểm tra 8/11 phút, slot6–9s (sai số lượng tử tối đa một frame ở fps phân số), mapping, lỗi voice, stale QC, giữ chỉnh sửa tay, backup, linked A1 sau phút8, endpoint convention, upload metadata và FFmpeg thật. Resolve được mô phỏng trong tests: **chưa xác minh trên Windows/Resolve đang chạy của bạn**. Làm smoke test theo [docs/LIVE_SMOKE_TEST.md](docs/LIVE_SMOKE_TEST.md) trên một project mới trước khi dựng hàng loạt.

Ghi nhận nghiên cứu hai video và quyết định kể chuyện: [reference-analysis.md](.claude/skills/create-doc-mov/references/reference-analysis.md). Video1 có phân tích hình qua vidIQ; video2 mới có caption vì thiếu credit visual analysis. Không tuyên bố đã xem toàn bộ hình video2.

So sánh với repo gốc và phần đã loại bỏ: [docs/MIGRATION.md](docs/MIGRATION.md). Schema đầy đủ: [source-contract.md](.claude/skills/create-doc-mov/references/source-contract.md).

Kết quả kiểm tra bàn giao: [docs/VALIDATION.md](docs/VALIDATION.md). Có kèm source ví dụ gốc `examples/last-dry-seam.story.json` để xem một hợp đồng8 phút đầy đủ. Để thử compiler, init một thư mục video mới rồi copy source mẫu vào `.production/story.json`, chạy build/validate; không dùng kết quả thử để giả định đã có MP3/MP4 hoặc đã duyệt hình.
