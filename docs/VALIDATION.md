# Kết quả kiểm tra trước bàn giao

Ngày: 02/11/2026. Snapshot gốc: `21d90227a1235a486e0b7690f71e33fdcdd1c81e`.

## Kiểm tra tự động

`python -m unittest discover -q`: **25 tests PASS** trong lượt cuối. `git diff --check`, compile Python và kiểm tra link Markdown/frontmatter của ba skill: PASS.

Các ca chính:

- Phim 8/11 phút, toàn bộ timeline phủ kín, shot6–9s; xử lý fps phân số không cộng dồn sai lệch.
- Bốn file khớp source; EN/VI đồng bộ; transcript bị sửa riêng thì dừng.
- Narration quá dài/quá thưa bị chặn; conform thử với **MP3 thật tạo bằng FFmpeg** đo duration và cập nhật timestamp. Đây là tín hiệu thử thời gian, không phải voice diễn xuất và không được coi là video xuất bản.
- Missing/extra/alias filename; prompt1↔1.mp4; prompt được đóng băng; phải có receipt A2 hợp lệ mới phát hành.
- Technical ingest không tự duyệt hình; media thay đổi làm QC hết hiệu lực; hook phải có đủ năm vai và không dùng shot kết cục.
- File lỗi/quá ngắn được gom báo; FFmpeg probe/decode thật với clip30fps có hình+tiếng.
- Hai kênh có tên video giống nhau vẫn tách state theo đường dẫn đầy đủ; khóa file được giải phóng khi process lỗi.
- Resolve **mô phỏng**: backup thất bại không append; chạy lại không trùng; conflict giữ chỉnh sửa tay; V1/A1 đúng nguồn, link và có âm thanh sau phút8; source30fps sang timeline24fps; endpoint convention khác thì dừng.
- Render **mô phỏng**: RUNNING không được coi là xong; output thiếu không VERIFIED; render lại tạo v2; upload UNKNOWN chặn retry và COMPLETE không upload trùng.
- YouTube request luôn private mặc định + synthetic=true; chặn lịch không timezone hoặc đã qua.

Không upload video thật, không đăng public, không gọi TTS hay generator trong các tests.

## Thử độc lập bằng skill

Một lượt agent độc lập dùng skill đã viết source gốc **The Last Dry Seam**, bối cảnh núi giả tưởng, thỏ núi bị cáo truy đuổi trong đường thoát nước đá đang dâng nước. Source mẫu ở `examples/last-dry-seam.story.json`.

Kết quả build/validate: **480s, 24fps, 16 scene, 1.065 từ English, 32 block EN/VI, 91,89% estimated voice-file occupancy, khoảng nghỉ dài nhất2,71s, 80 slot gồm5 hook và75 prompt hình**. Không voice/video nào được giả tạo để vượt các gate sản xuất. Conform báo đúng thiếu MP3; các bước cần media dừng đúng prerequisite; dry-run không kết nối Resolve.

Lượt này phát hiện và đã sửa: (1) nói rõ đơn vị MP3 là dòng nội dung vật lý không trống, không đếm paragraph Markdown hiển thị; (2) chặn phát hành prompt nếu A2 chưa có receipt xác minh tương ứng. Hai điểm có regression coverage.

Source mẫu để học schema và thử compiler, không phải mẫu sự kiện bắt buộc cho mọi phim. Chưa có footage/QC/voice thật cho phim mẫu.

## Phần chưa được xác minh

- Chưa chạy setup.ps1 trên Windows hoặc adapter trên DaVinci đang mở của người dùng.
- Chưa xác minh frame endpoint/audio-import/SRT append/preset/codec trên phiên bản Resolve thực tế; xem LIVE_SMOKE_TEST.md.
- Chưa login/upload bằng YouTube account của người dùng trong workspace mới.
- Video mẫu1 có kết quả visual analysis từ vidIQ; mẫu2 mới có caption do thiếu credit cho visual analysis. Chưa có phân tích toàn bộ hình/musical cut của mẫu2.
- Tests không đo audience retention, tính hấp dẫn của mọi kịch bản mới, chất lượng voice, giải phẫu chuyển động của footage thật hoặc độ chính xác khoa học của một câu chuyện tương lai.
