# Phạm vi thay đổi từ workspace gốc

Nguồn: https://github.com/hehoha3/Claude_Vid_editor/tree/fear/create_doc_movie_content

Snapshot đã lấy: `21d90227a1235a486e0b7690f71e33fdcdd1c81e`.

Đã lập danh mục 120 file tracked, SHA-256 và kích thước trong `source_inventory.json`, kiểm tra phụ thuộc/điểm vào của các module Python, đọc sâu CLAUDE/skill tạo bốn file/skill dựng/Resolve adapter/timing/intro/missing-prompts/delivery/YouTube và tests liên quan. Các LUT/ảnh nhị phân được kiểm kê để bỏ khỏi workspace, không coi là tài liệu kể chuyện cần học.

Không tuyên bố mọi dòng của mọi công cụ cũ đã được kiểm chứng chức năng. Bản mới thay bộ công cụ gắn thư viện bằng package riêng nhỏ hơn, thay vì giữ planner hơn 2.000 dòng rồi chỉ thay tên biome.

| Thành phần cũ | Bản mới |
|---|---|
| 30–60+ phút, 3–5 story, intro90s, voice35–40% | Một câu chuyện 8/11 phút hoặc dài hơn, hook30s + setup30s, khuyến nghị voice85–92% |
| Africa/Amazon/Congo + library species matching | Mountain cast/terrain lock + numbered generated media |
| scan/tag/organize, SQLite/PostgreSQL/memory embeddings | Manifest JSON/CSV và state JSON per-video, khóa file của hệ điều hành |
| Gemini helper, Genmax auto voice | Bỏ; người dùng tự tạo voice và video |
| A1 trước08:00 + A2…A9 | Linked A1 suốt phim; A2 Narrator Voice; A3 Music |
| Bin4.Audio/6.Timeline, day project đa kênh | Bin1.shots/2.Audio/3.Graphics/4.Timeline; một project/video |
| Chọn footage có sẵn, broad fallback | Mọi non-hook slot có prompt riêng; không fill bằng hình sai truyện |
| Colorist/audio-expert/thumbnail/process-ai-video/hide-logo | Loại bỏ; user review và sửa tay |
| Whisper căn một voice dài | Bỏ khỏi bản nhẹ; nhận numbered MP3 khớp từng paragraph |
| Done phụ thuộc ledger/library/license crawler | Kiểm tra live timeline, render job, probe/decode output và optional upload riêng |
| Upload có thể dùng title tạm, synthetic=false | Metadata cuối được duyệt, private mặc định, synthetic=true, chặn retry khi outcome chưa rõ |

Giữ cách kết nối `fusionscript` bằng importlib từ repo gốc. Viết lại adapter Resolve có phạm vi hẹp, composer/validator, số hóa MP4, QC, hook và state file. Không tự di chuyển project, thư mục video hay media cũ. Source checkout và nhánh documentary gốc giữ nguyên; bản mới được triển khai trên nhánh riêng.

## Những lựa chọn cần hiểu trước khi dùng

- Hook5×6s là cách dung hòa “phân đoạn cao trào ngắn” với yêu cầu “shot6–9s”. Muốn hook cắt1–3s phải đổi cấu hình/validator trước, không để agent tùy tiện vi phạm.
- Khung30+30 là yêu cầu thiết kế mới, không phải kết quả đo thấy ở cả hai video mẫu.
- Đọc prompt giúp chọn ứng viên; QC hình thật và clean source-in quyết định đoạn được dùng.
- Timeline/voice/prompts đã phát hành cần version ổn định; đổi câu chuyện lớn sau khi generate sẽ tạo version mới. Rebuild không được âm thầm căn lại timeline đã đặt.
- Ba skill là project-local trong `.claude/skills`, không cài thêm skill cá nhân vào ChatGPT.

## Nguồn kỹ thuật

- API Resolve: dùng bản `Support/Developer/Scripting/README.txt` đi cùng cài đặt. Hai ghi chú upstream về endFrame không nhất quán; bản mới cho chọn inclusive/exclusive và kiểm tra từng append, không nhận là đã kiểm thử trên Resolve của người dùng.
- YouTube video resource: https://developers.google.com/youtube/data/reference/rest/v3/videos — private/schedule và containsSyntheticMedia.
- YouTube insert: https://developers.google.com/youtube/data/reference/rest/v3/videos/insert — upload và giới hạn của API project.

Thông tin khoa học về loài/địa lý phải được nghiên cứu riêng cho mỗi câu chuyện. Các video AI mẫu không phải bằng chứng cho hành vi tự nhiên.
