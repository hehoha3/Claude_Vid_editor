# Claude Video Editor: hướng dẫn cho người mới

Hệ thống này giúp bạn làm **phim tài liệu thiên nhiên kiểu BBC Earth** cho các kênh YouTube trong phần mềm dựng phim
**DaVinci Resolve**. Bạn trò chuyện với **Claude** (một trợ lý AI) bằng tiếng Việt. Claude tự làm phần lớn công
việc nặng, và dừng lại ở những chỗ cần bạn quyết định.

Bạn **không cần biết lập trình**. Bạn chỉ cần: cài đặt một lần theo mục 2, rồi mỗi ngày gõ vài câu lệnh ngắn như
trong mục 5.

**Mục lục**
1. [Hệ thống làm gì cho bạn](#1-hệ-thống-làm-gì-cho-bạn)
2. [Cài đặt lần đầu](#2-cài-đặt-lần-đầu-khoảng-1-giờ)
3. [Kết nối Gemini và YouTube](#3-kết-nối-gemini-và-youtube-tuỳ-chọn)
4. [Thư mục và tên gọi](#4-thư-mục-và-tên-gọi)
5. [Làm một video mỗi ngày](#5-làm-một-video-mỗi-ngày)
6. [Những câu bạn hay nói với Claude](#6-những-câu-bạn-hay-nói-với-claude)
7. [Gặp lỗi thì làm gì](#7-gặp-lỗi-thì-làm-gì)
8. [Bảo trì](#8-bảo-trì-dọn-dẹp-cập-nhật)
9. [Từ điển nhỏ](#9-từ-điển-nhỏ)

---

## 1. Hệ thống làm gì cho bạn

| Bạn làm | Claude làm |
|---|---|
| Nói chủ đề / kênh muốn làm | Tìm video đang hot trên YouTube, đưa 3 ý tưởng, viết kịch bản |
| Tạo **giọng đọc** (ElevenLabs) theo kịch bản | Đặt giọng đọc + phụ đề tiếng Việt lên phim |
| Tạo **clip AI** (Veo / Kling) theo câu lệnh Claude đưa | Chọn footage đúng câu chuyện, viết câu lệnh (prompt) cho shot còn thiếu |
| Xem phim và nói chỗ cần sửa | Đặt hình, nhạc, tiếng động, chỉnh màu, sửa theo lời bạn |
| Bấm duyệt | Xuất file phim, viết tiêu đề / mô tả / tags, đăng lên YouTube ở chế độ **riêng tư** |

**Hai loại video.** Video nào cũng thuộc một trong hai loại:

| Loại | Dài | Hình ảnh từ đâu |
|---|---|---|
| **footage+AI** | 1–3 giờ | Kho footage quay thật của nhóm, thêm clip AI cho chỗ còn thiếu |
| **full-AI** | 8–15 phút | Toàn bộ shot do bạn tạo bằng AI theo câu lệnh của Claude |

**Bốn vùng.** Loại nào cũng làm được ở vùng nào:

| Vùng | Là gì |
|---|---|
| `amazon` | Rừng rậm (Amazon, Congo) |
| `africa` | Sa mạc, đồng cỏ savanna châu Phi |
| `himalaya` | Núi tuyết, núi cao, băng tuyết quanh năm |
| `ocean` | Đại dương (chưa làm) |

> Video full-AI ở vùng `amazon` / `africa` còn thiếu "bộ khoá câu lệnh" (quy định chung cho mọi prompt của vùng đó).
> Khi bạn làm loại này, Claude sẽ nhắc bạn bổ sung trước.

---

## 2. Cài đặt lần đầu (khoảng 1 giờ)

Làm **một lần** trên mỗi máy. Đi lần lượt từng bước, xong bước này mới sang bước sau.

### Cách mở PowerShell và dán lệnh

Phần lớn việc cài đặt là **gõ lệnh vào PowerShell** (một cửa sổ chữ của Windows):
1. Bấm nút **Start** (logo Windows), gõ `PowerShell`, bấm vào **Windows PowerShell**.
2. Copy một lệnh trong hướng dẫn này (bôi đen, Ctrl+C).
3. Trong cửa sổ PowerShell, **bấm chuột phải** để dán, rồi bấm **Enter**.
4. Chờ tới khi hiện lại dòng có dấu `>` ở cuối, rồi mới dán lệnh tiếp theo.

Chữ đỏ hiện ra nghĩa là có lỗi: chụp màn hình gửi cho người hỗ trợ, hoặc xem mục 7.

### 2.1 Cài phần mềm cần có

| Phần mềm | Cách cài | Ghi chú |
|---|---|---|
| **DaVinci Resolve** 19 trở lên (bản Studio tốt hơn) | Tải ở blackmagicdesign.com | Xem bước 2.2 |
| **Python 3.12** | python.org > Downloads > Windows. Lúc cài **nhớ tick ô "Add python.exe to PATH"** | Quên tick thì gỡ ra cài lại |
| **Git** | Dán vào PowerShell: `winget install Git.Git` | |
| **ffmpeg** (xử lý âm thanh / video) | `winget install Gyan.FFmpeg` | |
| **Node.js** (để chạy Claude) | `winget install OpenJS.NodeJS.LTS` | |
| **Claude Code** | `npm i -g @anthropic-ai/claude-code` | Hoặc cài **VS Code** rồi thêm extension "Claude Code" |
| Ổ mạng chung **`Z:`** | Nhờ người quản lý map giúp | Kho footage, nhạc, tiếng động của nhóm. **Chỉ đọc** |

Cài xong: **đóng hết cửa sổ PowerShell, mở cửa sổ mới**, để máy nhận các phần mềm vừa cài.

### 2.2 Chỉnh DaVinci Resolve (2 việc)

1. **Cho phép điều khiển tự động**: mở Resolve > menu **DaVinci Resolve** > **Preferences** > tab **System** >
   **General** > mục **External scripting using** chọn **Local** > Save. Tắt Resolve rồi mở lại.
2. **Tạo preset xuất phim**: mở một project bất kỳ > trang **Deliver** (biểu tượng tên lửa ở dưới cùng) > chọn
   preset **YouTube** > Format **MP4**, Codec **H.265** > bấm **...** cạnh tên preset > **Save As New Preset**, đặt tên
   đúng **`YouTube 1080 HEVC`**. Thiếu preset này thì Claude không xuất phim được.

### 2.3 Tải hệ thống về máy

Dán từng dòng:
```powershell
git clone https://github.com/hehoha3/Claude_Vid_editor.git D:\Claude_editor
cd D:\Claude_editor
```
Đúng: có thư mục `D:\Claude_editor` chứa nhiều file.

### 2.4 Cài phần Python (khoảng 10 phút)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m dvr_cowork prefetch
.venv\Scripts\python.exe .work\tools\memory_gateway.py selftest
```
Lệnh thứ 4 tải bộ nhận dạng giọng nói (khoảng 1 GB), nên có thể mất vài phút.

*(Chỉ khi máy có card đồ hoạ NVIDIA, không có thì bỏ qua)* bộ nhận diện con vật (YOLO, khoảng 3 GB):
```powershell
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv\Scripts\python.exe -m pip install "ultralytics>=8.4"
.venv\Scripts\yolo.exe settings "weights_dir=D:\Claude_editor\.models" "runs_dir=D:\Claude_editor\.work\yolo_runs" sync=False
```

### 2.5 Khai báo thư mục của máy bạn

Mở file `D:\Claude_editor\config.toml` bằng **Notepad** (chuột phải > Open with > Notepad). Tìm và sửa nếu máy bạn
khác:
- `ai_video = 'D:\AI_video'`: nơi bạn lưu clip AI.
- `audio_lib = 'D:\Audio_lib'`: nơi lưu nhạc / tiếng động tải về (Epidemic Sound, Suno).
- `globs = ['D:\Chann_*']`: nơi chứa các thư mục kênh.

Lưu file (Ctrl+S). Để nguyên mặc định cũng được nếu máy bạn dùng đúng các ổ đĩa đó.

### 2.6 Lấy dữ liệu của nhóm

Kho footage đã được "xem" và gắn nhãn sẵn, đóng gói trong một file zip. Xin trưởng nhóm file `team_data_<ngày>.zip`,
chép vào `D:\`, rồi chạy (đổi tên file cho đúng):
```powershell
.venv\Scripts\python.exe .work\tools\team_data.py import D:\team_data_20261024.zip
.venv\Scripts\python.exe .work\tools\memory_gateway.py index
```
Nhóm mới, chưa có gói: bỏ qua bước này. Sau khi cài xong, nói với Claude `/scan-source` rồi `/tag-source` để Claude tự
xem kho footage (lâu, chỉ làm một lần).

### 2.7 Kiểm tra mọi thứ đã chạy

Mở DaVinci Resolve và mở một project bất kỳ, rồi:
```powershell
cd D:\Claude_editor
.\dvr.cmd doctor
.venv\Scripts\python.exe -m unittest discover -s dvr_cowork\fullai\tests -t .
```
Đúng: lệnh `doctor` có dòng Resolve ghi **`[OK]`**; lệnh thứ ba kết thúc bằng chữ **`OK`**.

### 2.8 Mở Claude lần đầu

```powershell
cd D:\Claude_editor
claude
```
Lần đầu Claude yêu cầu đăng nhập tài khoản Anthropic: làm theo hướng dẫn trên màn hình. Thấy ô để gõ chữ là xong.
Từ giờ, mỗi lần làm việc chỉ cần hai dòng trên. Dùng VS Code: **File > Open Folder > `D:\Claude_editor`**, rồi mở
khung Claude ở cạnh màn hình.

---

## 3. Kết nối Gemini và YouTube (tuỳ chọn)

Không có hai thứ này thì vẫn dựng phim bình thường. Chỉ khác là: thiếu Gemini thì Claude tự dịch / tự viết (tốn hơn
một chút); thiếu YouTube thì không tự tìm trend và không tự đăng video.

### 3.1 Gemini (miễn phí, khoảng 2 phút)

Gemini là một AI khác của Google. Claude nhờ Gemini viết nháp những đoạn dài, ví dụ SEO, cho đỡ tốn.
1. Vào **https://aistudio.google.com/apikey**, đăng nhập Gmail, bấm **Create API key**, bấm nút copy.
2. Trong PowerShell (đang ở `D:\Claude_editor`):
   ```powershell
   .venv\Scripts\python.exe .claude\skills\gemini-assist\scripts\gemini_bridge.py setup-key
   ```
   Bấm chuột phải để dán key, rồi Enter. **Màn hình không hiện chữ khi dán: bình thường.**
3. Kiểm tra: `.venv\Scripts\python.exe .claude\skills\gemini-assist\scripts\gemini_bridge.py check`. Thấy
   `"ok": true` là xong. Key được cất an toàn trong Windows, không nằm trong file nào.

### 3.2 YouTube (khoảng 15 phút, một lần)

**a) Tạo "chìa khoá" Google** (làm một lần cho cả nhóm kênh):
1. Vào **https://console.cloud.google.com**, đăng nhập Gmail. Ở góc trên, bấm chọn project > **New Project** > đặt
   tên bất kỳ > **Create**.
2. Ô tìm kiếm phía trên: gõ **YouTube Data API v3** > bấm vào kết quả > **Enable**.
3. Menu bên trái **Google Auth Platform** (hoặc "OAuth consent screen") > **Get started**: điền tên app, chọn Gmail
   của bạn, chọn **External** > **Create**. Vào **Audience** > **Test users** > **Add users**: thêm Gmail đang sở hữu
   các kênh YouTube.
4. **Clients** > **Create client** > loại **Desktop app** > **Create** > **Download JSON**.
5. Tạo thư mục `D:\Claude_editor\.secrets\youtube\`, chép file vừa tải vào, đổi tên thành **`client_secret.json`**.

**b) Đăng nhập từng kênh.** Mỗi kênh mang một số: kênh 1 là `Chann_1`, kênh 2 là `Chann_2`...
```powershell
.\dvr.cmd youtube login --key Chann_1
```
- Trình duyệt mở ra: chọn đúng tài khoản / kênh. Gặp "Google hasn't verified this app" thì bấm **Continue**.
- Xong, hệ thống **tự tạo thư mục kênh** theo tên kênh, ví dụ kênh "Wild Peril" thành `D:\Chann_1_WildPeril`. Có sẵn
  thư mục `D:\Chann_1_...` tên khác thì nó tự đổi tên (đóng Resolve / cửa sổ thư mục đang mở nó trước).
- Muốn dừng giữa chừng: bấm **Ctrl+C**. Không đăng nhập trong 5 phút thì tự dừng. Dừng thì không lưu gì.
- Kênh tiếp theo: chạy lại với `Chann_2`, `Chann_3`...

**c) Xem các kênh đã gắn:** `.\dvr.cmd youtube channels`

| Muốn | Gõ |
|---|---|
| Thêm kênh mới (ví dụ kênh 3) | `.\dvr.cmd youtube login --key Chann_3` |
| Gỡ một kênh khỏi máy | `.\dvr.cmd youtube remove Chann_3` |
| Kênh báo lỗi đăng nhập (token hỏng) | `.\dvr.cmd youtube remove Chann_3`, rồi `.\dvr.cmd youtube login --key Chann_3` |
| Gắn số `Chann_3` cho kênh khác | Như dòng trên, lúc đăng nhập chọn kênh mới (thư mục tự đổi tên) |

Gỡ kênh chỉ xoá trên máy này, thư mục kênh vẫn giữ nguyên. Muốn thu hồi quyền hẳn: vào
**https://myaccount.google.com/permissions** > gỡ app. Một số `Chann_N` đang dùng thì phải gỡ trước rồi mới gắn lại
được.

> Video đăng lên luôn ở chế độ **riêng tư (private)**. Bạn tự chọn công khai / hẹn giờ và thumbnail trong YouTube
> Studio. Mỗi ngày Google cho miễn phí khoảng 6 lần đăng video.

---

## 4. Thư mục và tên gọi

```
D:\Chann_1_ShadowCanopy\          <- thư mục một kênh (tự tạo khi đăng nhập YouTube)
    amazon_051126_1\              <- một video: <vùng>_<ngàyThángNăm>_<số thứ tự>
        audios\                   <- kịch bản (Claude viết) + giọng đọc của bạn
        voice\                    <- (full-AI) giọng đọc 1.mp3, 2.mp3 ...
        shots\                    <- (full-AI) clip bạn tạo 1.mp4, 2.mp4 ...
    _done\                        <- bạn tự kéo video đã xong vào đây
    _pushed\                      <- thư mục riêng của bạn: Claude không bao giờ đụng vào
```
- **Tên video**: `himalaya_051126_2` = vùng himalaya, ngày 05/11/2026, video thứ 2 trong ngày. Claude tự đặt tên.
- **Giọng đọc**: mỗi dòng của kịch bản là một file, đánh số 1, 2, 3... đúng thứ tự (`1.mp3` = dòng 1).
- **Clip full-AI**: đặt tên đúng **số câu lệnh**, ví dụ câu lệnh số 7 lưu thành `shots\7.mp4`.

**Trong DaVinci Resolve**, mỗi video có:
- **Một timeline tên "Edit"**: đây là bản dựng. Các bản sao lưu tên `Edit_bak_...` (Claude tạo trước khi sửa lớn) giúp
  quay lại khi cần.
- **Các bin** (thư mục trong Media Pool): `1. Other_roll`, `2. Attack_roll`, `3. Run_roll` (hình theo hành động),
  `4. Audio` (giọng đọc, nhạc, tiếng động), `5. Graphics` (phụ đề), `6. Timeline`; video footage+AI có thêm
  `7. Open` chứa các shot của đoạn mở đầu (~1 phút 30).
- **Các track âm thanh**: A1 tiếng gốc của clip (footage+AI để trống), A2 giọng đọc, A3–A6 không khí / tiếng tự nhiên,
  A7 nhạc, A8–A9 tiếng động.

---

## 5. Làm một video mỗi ngày

Mở **DaVinci Resolve** (Claude cần Resolve đang mở), rồi mở **Claude** (mục 2.8). Sau đó chỉ cần gõ câu lệnh vào ô
chat của Claude. Mỗi lệnh bắt đầu bằng dấu `/`. Claude trả lời bằng tiếng Việt và luôn nói rõ bước tiếp theo bạn cần
làm.

### Bước 0: Kịch bản (cả hai loại)

Gõ: **`/create-doc-mov Chann_1`**. Muốn dựa theo một video mẫu: **`/create-doc-mov Chann_1 <link YouTube>`**.

Claude hỏi loại video + vùng (nếu bạn chưa nói), tìm video đang hot, đưa 3 ý tưởng để bạn chọn, rồi viết kịch bản vào
`audios\`. Bạn đọc kịch bản rồi **tạo giọng đọc**: mỗi dòng của file `transcript` là một file mp3, đặt tên theo số.

### 5.1 Video footage+AI (1–3 giờ): 3 lần gõ

| Lần | Bạn gõ | Claude làm | Bạn làm tiếp |
|---|---|---|---|
| 1 | `/doc-edit D:\Chann_1_ShadowCanopy\amazon_051126_1` | Đặt giọng đọc + phụ đề, chọn footage cho từng câu, dựng intro + thân phim, viết câu lệnh cho các shot **THIẾU**. Rồi dừng | Tạo clip AI theo câu lệnh, lưu vào `D:\AI_video\_check` (africa: `D:\AI_video\_africa\_check`). Clip có logo: gõ `/doc-edit logo` rồi `/doc-edit delogo` |
| 2 | `/scan-source /tag-source và tiếp` | Xem clip mới, xếp vào kho, lấp vào chỗ THIẾU. Rồi dừng | Xem phim trong Resolve, nói chỗ cần sửa |
| 3 | `/doc-edit color n done` | Chỉnh màu, viết tiêu đề / mô tả / tags, xuất file phim `Done_<video>.mp4`, đăng YouTube riêng tư | Vào YouTube Studio: thumbnail, công khai / hẹn giờ |

Câu lệnh tạo clip chỉ dành cho phần intro + story 1 (các phần sau tự lấp bằng footage có sẵn). Không muốn tạo clip
nữa mà muốn lấp nốt chỗ THIẾU bằng footage có sẵn: gõ `/doc-edit fill-THIEU <video>`.

**Mở đầu 0:00 (phim footage+AI 1-3h từ 2026-11-06):** màn hình đen + tiếng dây đàn rít lên → cú impact (~0:01),
shot mở đầu và nhạc intro vào đúng cú hit, narrator từ 0:03.6, rồi intro ~1:30 như cũ. Claude tự chọn cú impact
(`D:\Audio_lib\SXF\impact`, hai phim cùng ngày không trùng). Phim full-AI 8-15p vẫn mở bằng hook 30 s từ 0:00.

### 5.2 Video full-AI (8–15 phút): 3 lần gõ

| Lần | Bạn gõ | Claude làm | Bạn làm tiếp |
|---|---|---|---|
| 1 | `/doc-edit D:\Chann_3_WildPeril\himalaya_051126_2` (đã có giọng đọc trong `voice\`) | Đặt giọng đọc + phụ đề, viết câu lệnh cho **mọi** shot (file `missing-prompt.csv`). Rồi dừng | Tạo toàn bộ clip theo câu lệnh, lưu vào `shots\` đúng số (`1.mp4`, `2.mp4`...) |
| 2 | Gõ lại **đúng lệnh trên** | Kiểm tra clip, đặt cả phim lên timeline: 30 giây mở đầu gay cấn, câu chuyện, nhạc, gió, chim hót. Rồi dừng | Xem phim. Shot nào hỏng: "làm lại 3, 7, 12" (Claude đưa lại câu lệnh), tạo lại, ghi đè file cũ |
| 3 | `/doc-edit done <đường dẫn video>` | Xuất file phim (không chỉnh màu); nếu bạn muốn thì viết SEO và đăng YouTube riêng tư sau khi bạn duyệt | YouTube Studio: thumbnail, công khai / hẹn giờ |

**Mẹo:** lấy đường dẫn video bằng cách mở thư mục video trong Windows, bấm vào thanh địa chỉ ở trên, Ctrl+C, rồi dán
vào sau `/doc-edit `.

### Xem video đang ở bước nào

Gõ **`/doc-edit status`**. Claude liệt kê mọi video, mỗi video đang ở bước nào và lệnh cần gõ tiếp.

---

## 6. Những câu bạn hay nói với Claude

Nói tự nhiên bằng tiếng Việt, kèm thời điểm (phút:giây) trên timeline:

| Bạn nói | Claude làm |
|---|---|
| "ở 12:30 đang là clip gì?" | Cho biết tên clip, nguồn |
| "đổi shot ở 00:43, đang có cá sấu" | Thay đúng một shot đó |
| "shot ở 21:38 có logo góc trên trái" | Xoá logo |
| "đoạn 12:00–14:00 cần căng hơn" | Gợi ý / sửa nhịp, nhạc |
| "làm lại 3, 7, 12" (full-AI) | Đưa lại câu lệnh cho các shot đó |
| "dùng title 2" | Đổi tiêu đề YouTube |
| "nhớ là ..." | Ghi nhớ quy tắc cho các lần sau |
| `/thumbnail` + kéo ảnh vào | Làm thumbnail 4K có chữ + logo kênh |
| `/review-frame 01:10` | Nhận xét màu / khung hình tại thời điểm đó |
| `/research-youtube africa-wildlife` | 20 video nhiều view nhất 10 ngày qua |

**Màu trên timeline / trong plan (footage+AI):** **OK** = khớp câu chuyện; **WEAK** (vàng) = tạm được, nên xem lại;
**THIẾU** (đỏ) = cần clip AI; **FALLBACK** = shot thay thế gần đúng.

**Claude sẽ hỏi lại** trước khi làm việc có thể mất dữ liệu (xoá clip, đặt lại cả timeline, áp màu...). Bạn trả lời
"yes" thì nó mới làm. Gọi đúng lệnh của một bước (ví dụ `/doc-edit color`) là bạn đã đồng ý cho bước đó.

---

## 7. Gặp lỗi thì làm gì

Thông thường **Claude tự nói lỗi và cách sửa** bằng tiếng Việt. Một số lỗi hay gặp:

| Thấy | Làm |
|---|---|
| "DaVinci Resolve is not reachable" / Claude nói không thấy Resolve | Mở Resolve và mở đúng project; kiểm tra lại bước 2.2 mục 1 |
| `py` hoặc `python` không chạy | Cài lại Python, **tick "Add python.exe to PATH"**, mở PowerShell mới |
| Clip trong Resolve báo **Media Offline** (khung đỏ) | Nói với Claude "relink lại media" |
| Không thấy ổ `Z:` | Map lại ổ mạng (nhờ người quản lý) |
| `No Gemini API key saved` | Làm lại mục 3.1 |
| Lỗi đăng nhập YouTube (`not logged in`, `token invalid`, `revoked`) | Bảng ở mục 3.2 c, dòng "token hỏng" |
| `No full-AI prompt locks for region ...` | Vùng đó chưa có bộ khoá câu lệnh full-AI: nhờ người kỹ thuật thêm (docs/SYSTEM.md mục 12) |
| `Another writer owns ...` | Claude đang làm một việc khác trong Resolve: chờ xong |
| `quotaExceeded` | Hết lượt YouTube miễn phí trong ngày: chờ khoảng 14–15 giờ chiều (giờ VN) |
| Resolve chạy chậm dần | Nói với Claude "dọn bớt backup timeline" |
| Muốn kiểm tra tổng thể | Chạy lại bước 2.7 |

Vẫn không được: chụp màn hình lỗi, gửi cho Claude (kéo ảnh vào ô chat) hoặc người hỗ trợ.

---

## 8. Bảo trì: dọn dẹp, cập nhật

**Dọn file thừa** (an toàn: lệnh đầu chỉ liệt kê, không xoá gì):
```powershell
cd D:\Claude_editor
.venv\Scripts\python.exe .work\tools\cleanup_workspace.py
.venv\Scripts\python.exe .work\tools\cleanup_workspace.py --apply
```
Xem danh sách ở lệnh đầu trước, thấy ổn mới chạy lệnh thứ hai (xoá thật). Công cụ này không bao giờ đụng vào footage,
kho dữ liệu của nhóm hay video đang làm.

**Cập nhật bản mới** (khi trưởng nhóm báo có bản mới):
```powershell
cd D:\Claude_editor
git pull
.venv\Scripts\python.exe -m pip install -e .
```

**Luật an toàn Claude luôn tuân theo**
- Ổ `Z:` chỉ đọc, không bao giờ ghi / xoá. Thư mục `_pushed` là của riêng bạn.
- Claude không tự xoá file: nó đưa lệnh để bạn tự chạy.
- Luôn sao lưu timeline trước khi sửa lớn.
- Không bao giờ tự đăng video công khai.

---

## 9. Từ điển nhỏ

| Từ | Nghĩa |
|---|---|
| **Claude** | Trợ lý AI bạn trò chuyện để dựng phim |
| **Lệnh `/...`** | Câu bắt đầu bằng `/` gõ cho Claude, ví dụ `/doc-edit` |
| **PowerShell** | Cửa sổ gõ lệnh của Windows (chỉ dùng khi cài đặt / bảo trì) |
| **Project (Resolve)** | Một "hồ sơ" dựng phim trong Resolve; nhiều kênh làm cùng ngày có thể dùng chung một project |
| **Timeline "Edit"** | Bản dựng phim trong project |
| **Bin** | Thư mục chứa clip / âm thanh trong Resolve |
| **Track** | Một "làn" trên timeline: V1 hình, A1–A9 âm thanh |
| **Footage** | Đoạn phim quay thật trong kho của nhóm |
| **Clip AI** | Đoạn phim tạo bằng AI (Veo, Kling...) |
| **Prompt / câu lệnh** | Đoạn mô tả Claude viết để bạn dán vào công cụ tạo clip AI |
| **THIẾU** | Chỗ trên phim chưa có hình phù hợp |
| **Render / xuất phim** | Tạo file video hoàn chỉnh `Done_<video>.mp4` |
| **SEO** | Tiêu đề, mô tả, tags giúp video dễ được tìm thấy trên YouTube |
| **Chann_N** | Số thứ tự của kênh YouTube trên máy này |
| **Vùng** | amazon / africa / himalaya / ocean |

Muốn hiểu bên trong hệ thống hoạt động thế nào: [docs/SYSTEM.md](docs/SYSTEM.md).
