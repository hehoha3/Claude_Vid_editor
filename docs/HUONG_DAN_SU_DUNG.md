# Hướng dẫn làm 1 video từ A đến Z

Tài liệu này dành cho người mới. Chỉ cần làm đúng từng bước, copy đúng lệnh, là ra được 1 video phim tài liệu.
(Muốn hiểu hệ thống chạy bên trong thế nào thì đọc [SYSTEM.md](SYSTEM.md), không bắt buộc.)

---

## 0. Đọc 2 phút này trước

**Bạn làm gì, máy làm gì?**

| Bạn | Claude (máy) |
|---|---|
| Chọn ý tưởng phim, đọc duyệt kịch bản | Viết kịch bản, chọn cảnh, lên plan |
| Đưa transcript lên Genmax lấy giọng đọc | Căn lại thời gian theo giọng đọc |
| (Phim có AI) tạo clip AI theo prompt | Ghép clip vào timeline, chỉnh màu |
| Xem lại trong DaVinci Resolve | Render và đăng YouTube khi bạn bảo |

**Quy tắc vàng**
1. Mỗi lần chỉ gõ **1 lệnh**, đợi Claude trả lời xong rồi mới gõ lệnh tiếp. Không có chuyện "tự chạy tiếp".
2. Trước khi làm: **mở DaVinci Resolve**, mở đúng project của ngày (tên dạng `vid_DDMMYY`, ví dụ `vid_161126`).
3. Claude chỉ trả lời tiếng Việt. Câu nào Claude hỏi thì trả lời bằng cách chọn đáp án hiện ra.
4. Không tự xoá, không tự đổi tên file/thư mục của video. Muốn sửa gì cứ nói với Claude.
5. Ổ `Z:` chỉ để **đọc/copy**, không ghi gì vào đó.

**Tên video nghĩa là gì?** Ví dụ `fa_africa_161126_1`:

| Phần | Nghĩa |
|---|---|
| `f_` | phim chỉ dùng **footage thật** |
| `fa_` | footage thật + **clip AI** (AI không quá 40 %) |
| `a_` | toàn bộ do AI tạo (hướng dẫn riêng, không nằm ở đây) |
| `africa` | vùng: `africa` (thảo nguyên, sa mạc), `amazon` (rừng), `frozen` (tuyết, băng, núi cao) |
| `161126` | ngày làm: 16/11/26 |
| `_1` | video số 1 trong ngày của kênh đó |

Thư mục video nằm ở `D:\Chann_N_<Tên kênh>\<tên video>` (N = số kênh).

---

## Bước 1. Viết kịch bản: `/create-doc-mov`

### 1.1 Gõ lệnh

Cú pháp: `/create-doc-mov Chann<N> <loại> <chủ đề / vùng> <số phút>p`

Ví dụ:

```
/create-doc-mov Chann1 footage africa 15p
```
= kênh 1, phim **footage thật**, vùng **Africa**, dài **15 phút**.

```
/create-doc-mov Chann1 footage+AI africa 15p
```
= như trên nhưng có thêm clip AI.

Làm nhiều phim cùng lúc: `/create-doc-mov Chann1 footage africa 15p, Chann2 footage+AI amazon 30p`

Chọn loại nào?
- `footage` → không cần tự tạo clip AI. **Dễ nhất, nên bắt đầu bằng loại này.**
- `footage+AI` → thêm 1 bước tạo clip AI (xem Bước 4).

> Thiếu thông tin (loại, vùng, số phút) thì Claude sẽ hỏi lại. Phim thực tế sẽ dài ±3 phút so với số bạn chọn
> (ví dụ "15p" ra 12–18 phút) vì Claude kết thúc ở chỗ câu chuyện tự nhiên.

### 1.2 Claude sẽ hỏi bạn 2 lần

1. **Chọn 1 trong 3 ý tưởng phim** (Claude đã xem video đang hot rồi mới đề xuất). Mỗi ý tưởng có: câu hỏi chính của phim,
   tên các phần (story), loài vật chính. Bạn bấm chọn 1 cái. Có ý riêng thì gõ vào ô "Other".
2. **"Giữ nguyên, viết luôn?"** → chọn *Giữ nguyên* nếu hài lòng. Chọn *Đổi dàn nhân vật* nếu muốn đổi con vật.

Sau đó Claude tự viết, mất vài phút. Đừng gõ gì thêm trong lúc chờ.

### 1.3 Claude dừng lại cho bạn duyệt

Claude trả về bản tóm tắt: mở đầu (Intro), Story 1, tên các story còn lại, số dòng. **Bạn chỉ cần đọc Intro và Story 1.**

- Ưng → sang Bước 2.
- Chưa ưng → nói thẳng, ví dụ "Story 1 cho con sư tử vào sớm hơn", Claude sửa và tóm tắt lại. Chỉ sửa ở **giai đoạn này**,
  vì sau khi đọc giọng xong mà sửa lời là phải đọc lại.

### 1.4 Kết quả: 4 file

Trong `D:\Chann_N_<Tên>\<video>\audios\` có đúng 4 file `.md`:

| File | Để làm gì |
|---|---|
| `transcript.md` | **Lời đọc (narration). Đây là file bạn đem đi lấy giọng.** |
| `Screenplay` | Kịch bản chi tiết từng cảnh |
| `Timestamp_EN_VI` | Thời điểm từng câu, có tiếng Anh + tiếng Việt |
| `Visual_Edit_Plan` | Cảnh quay nào đặt ở đâu |

> Không tự mở sửa 4 file này. Muốn sửa gì, nhờ Claude.

---

## Bước 2. Lấy giọng đọc trên Genmax

Lấy file `transcript.md` ở thư mục `audios` của video.

**Quy tắc quan trọng nhất: 1 dòng của transcript = 1 file mp3.**
Transcript có bao nhiêu dòng (không tính dòng trống) thì phải có đúng bấy nhiêu file mp3.

Làm theo thứ tự:
1. Mở transcript, **đọc từng dòng từ trên xuống**. Dòng 1 → `1.mp3`, dòng 2 → `2.mp3`, ...
2. Đưa lời từng dòng lên Genmax, chọn giọng narrator của kênh (dùng cùng 1 giọng cho cả phim), generate.
3. Tải file về, đặt tên **chỉ là số**: `1.mp3`, `2.mp3`, ... `N.mp3`. Không thêm chữ, không bỏ số nào.
4. Copy tất cả vào thư mục:

```
D:\Chann_N_<Tên>\<video>\audios\mp3\
```

Kiểm tra trước khi sang bước 3:
- [ ] Số file mp3 = số dòng transcript
- [ ] Tên là `1.mp3` → `N.mp3`, liên tục, không thiếu số
- [ ] Nghe thử 2–3 file: không bị đọc sai tên loài/địa danh, tốc độ đều

> Đọc sai 1 câu? Generate lại **riêng câu đó** rồi ghi đè đúng tên file (ví dụ `37.mp3`). Không cần làm lại cả phim.

---

## Bước 3. Ghép giọng đọc vào timeline: `/doc-edit <đường dẫn thư mục phim>`

**Trước khi gõ lệnh:** mở DaVinci Resolve và để **project của ngày (`vid_DDMMYY`) đang được mở (active)**.
Ví dụ phim `fa_africa_161126_1` thì mở project `vid_161126`. Sai project hoặc chưa mở thì Claude sẽ dừng và báo.

Gõ vào Claude:

```
/doc-edit <đường dẫn thư mục phim>
```

Ví dụ:

```
/doc-edit D:\Chann_1_Wild\fa_africa_161126_1
```

Đường dẫn là **thư mục của phim** (thư mục chứa `audios\`), không cần gõ thêm `\audios`.
Mẹo: mở thư mục trong File Explorer, bấm vào thanh địa chỉ, copy rồi dán vào sau `/doc-edit `.

Claude đọc trạng thái của phim trong thư mục đó rồi tự làm tiếp: chọn cảnh, lên plan, đặt lên timeline
`channN_vidK` trong Resolve. Nếu số file mp3 không bằng số dòng transcript, Claude sẽ dừng và nói thiếu/thừa số mấy:
bạn bổ sung rồi gõ lại đúng lệnh trên.

**Phim `footage` (`f_`):** Claude trả kết quả, gồm số cảnh còn **THIẾU** (chưa có footage đúng ý).
Nếu có THIẾU thì sang Bước 4A.

**Phim `footage+AI` (`fa_`):** Claude dừng lại và đưa **danh sách prompt** cho phần mở đầu + Story 1
(file `missing-prompt.csv`). Sang Bước 4B.

---

## Bước 4. Xử lý cảnh còn THIẾU

### 4A. Phim `footage` (`f_`)

Chọn 1 trong 2 (nói với Claude):

| Bạn nói | Claude làm |
|---|---|
| `/doc-edit fill-THIEU` | Lấp 100 % chỗ thiếu bằng footage có sẵn gần đúng nhất |
| `/doc-edit fallback-species` | Đổi sang loài thay thế ở khoảng thời gian bạn chỉ định |

Sau đó chuyển thẳng sang **Bước 5**.

### 4B. Phim `footage+AI` (`fa_`): 2 cách

**Cách 1: bạn tự tạo clip AI (đẹp hơn, tốn thời gian hơn)**
1. Mở `missing-prompt.csv`, lấy từng prompt, tạo clip bằng Veo/Kling.
2. Lưu clip vào thư mục `<video>\shots\`. **Tên file = mã shot trong cột `shot_id`** (Claude không tự đoán,
   đặt sai tên là clip không vào đúng chỗ).
3. Đợi **copy xong hẳn** (không còn đang chép), rồi gõ:

```
/doc-edit after-gen-vid <đường dẫn video>
```
Ví dụ: `/doc-edit after-gen-vid D:\Chann_1_Wild\fa_africa_161126_1`

Lệnh này tự làm 1 mạch: kiểm tra clip → đặt vào đúng chỗ → thay cảnh cũ → bỏ khoảng trống → xử lý viền đen → chỉnh màu
đồng bộ → chụp frame kiểm tra. Nó tự backup timeline trước khi sửa.

Nếu Claude báo clip **hỏng** hay **tên sai** → sửa theo danh sách Claude đưa, rồi chạy lại lệnh.
Clip sai loài (ví dụ cần sư tử ra báo): nói "clip X sai loài" để Claude loại.

**Cách 2: không tạo AI nữa**
Nói: `không generate nữa, fill THIẾU bằng footage có sẵn` (hoặc `/doc-edit fill-THIEU`). Claude lấp bằng footage thật.

---

## Bước 5. Kiểm tra trong DaVinci Resolve

Mở timeline `channN_vidK` (ví dụ `chann1_vid1`), xem lại cả phim. Tự hỏi:

- [ ] Hình có khớp lời đọc không (nói sư tử mà hiện voi là lỗi)?
- [ ] Có đoạn nào màn hình đen, đứng hình, lặp cảnh quá nhiều?
- [ ] Màu giữa các cảnh có đồng đều? Clip AI có "giả" hơn hẳn cảnh thật?
- [ ] Còn logo / chữ góc hình không?
- [ ] Nhạc và tiếng môi trường có to át lời đọc không?

Thấy lỗi → **nói rõ 1 chỗ cần sửa** với Claude, ví dụ "ở 04:12 cảnh con voi sai loài, đổi cảnh khác".
Claude chỉ sửa đúng chỗ bạn nêu.

Phim `f_` chưa chỉnh màu → gõ `/doc-edit color` ("đồng bộ màu").
Có logo hiện trên clip → gõ `/doc-edit logo` (tìm logo), rồi `/doc-edit delogo` (xoá).

---

## Bước 6. Xuất video

Chỉ làm khi bạn **đã xem xong và hài lòng**.

| Bạn muốn | Gõ |
|---|---|
| Chỉ render ra file mp4, chưa đăng | `/doc-edit done` (hoặc "xong video") |
| Render + tạo tiêu đề/mô tả + đăng YouTube | `/doc-edit push` (hoặc "up youtube") |

- `done` = chỉ render thành `Done_<tên video>.mp4` trong thư mục video.
- `push` = `done` + chọn tiêu đề SEO + upload. Claude đưa 3 tiêu đề, bạn chọn 1, rồi mới upload.

Thumbnail: gõ `/thumbnail` kèm ảnh bạn có. Kết quả nằm ở `<video>\thumb\`.
Ảnh bạn chọn đặt tên `done.*` thì `push` sẽ upload ảnh đó.

---

## Tóm tắt 1 trang (dán ra bàn)

```
1. /create-doc-mov Chann1 footage africa 15p
       → chọn 1/3 ý tưởng → "Giữ nguyên" → đọc Intro + Story 1 → OK
2. Lấy transcript.md → Genmax → 1 dòng = 1 file → 1.mp3 ... N.mp3
       → copy vào <video>\audios\mp3\
3. Mở project vid_DDMMYY trên Resolve → /doc-edit <đường dẫn thư mục phim>
4. Có THIẾU?
       footage (f_)      → /doc-edit fill-THIEU
       footage+AI (fa_)  → tạo clip AI vào <video>\shots\ (tên = shot_id)
                           → /doc-edit after-gen-vid <video>
                           (hoặc "không generate nữa, fill THIẾU")
5. Xem lại trong Resolve, báo chỗ cần sửa
6. /doc-edit done      (chỉ render)
   /doc-edit push      (render + SEO + upload YouTube)
```

---

## Gặp lỗi thì làm gì?

| Hiện tượng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Claude báo "Resolve chưa mở / sai project" | Chưa mở Resolve hoặc mở nhầm project | Mở project `vid_DDMMYY` đúng ngày, gõ lại lệnh |
| "Số mp3 không bằng số dòng transcript" | Thiếu/thừa file, đặt tên sai | Xem Claude nói số nào, bổ sung rồi gõ lại `/doc-edit <đường dẫn thư mục phim>` |
| "another Resolve write is running" | Đang có lệnh khác ghi vào Resolve | Đợi lệnh kia xong |
| Clip báo "still copying" | Clip AI đang chép dở | Đợi chép xong rồi chạy lại |
| Clip báo "broken" | File hỏng | Tạo/tải lại clip đó |
| Muốn quay lại bản trước | Lỡ sửa không ưng | Hỏi Claude: các bản `<timeline>_bak_*` là bản backup, Claude sẽ hỏi bạn trước khi khôi phục |

**Điều không được làm**
- Không nhấn Ctrl+Z trong Resolve khi Claude đang chạy lệnh.
- Không xoá hay đổi tên thư mục `audios`, `shots`, `mp3`.
- Không đụng vào thư mục `_pushed` và `_done`.
- Không ghi file vào ổ `Z:`.

Không chắc bước nào → hỏi Claude trước, đừng đoán. Hỏi tốn 10 giây, làm sai tốn cả buổi.
