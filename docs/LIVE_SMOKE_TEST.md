# Smoke test trên máy dựng

Bước này chưa được thực hiện bởi bộ tests chạy trong môi trường Linux. Dùng một project Resolve mới, không dùng project đang dựng dở.

1. Cài workspace bằng setup.ps1. Tạo một video thử theo schema, build/validate; giữ target8 phút hoặc11 phút. Có thể dùng media thử tự tạo để kiểm tra API, nhưng không dùng QC giả của tests cho video xuất bản.
2. Mở project có tên đúng thư mục video. Đặt fps đúng source (mặc định24) và External scripting=Local. Chạy info.
3. Tạo numbered MP3 đúng số paragraph. Conform; kiểm tra onset đầu, block qua ranh giới scene, block cuối và nghe các khoảng lặng. Nếu tràn cảnh, sửa/re-record trước khi phát hành prompt.
4. Chạy voice --apply. Xác nhận đúng bin/track, backup tồn tại, A2 có đủ item, SRT đúng thời gian. Nếu source_end sai, script phải dừng ngay với backup và pending journal; không tự retry/xóa clip. Đối chiếu Scripting/README.txt của phiên bản cài.
5. Chạy prompts, tạo đầy đủ MP4 theo số; deliberately để thiếu một số rồi ingest để xác nhận báo đúng file, không import nhầm. Sau khi đủ, ingest và tạo contact sheets. Xem clip thật, điền QC có bằng chứng và clean range cho hook.
6. Hook + assemble --apply. Kiểm tra 00:00–00:30 có đúng5 nguồn, 00:30–01:00 setup, body giữ nguyên thứ tự. Đi tới sau08:00 trên phim11 phút: A1 phải luôn đi cùng V1. Mỗi shot6–9s. A2 không bị di chuyển.
7. Chạy lại assemble: phải placed=0. Thử sửa vị trí/nguồn một shot trong timeline thử rồi chạy lại: phải dừng bảo toàn chỉnh sửa tay. Không dùng lệnh xóa/clear để “sửa cho qua”.
8. User review/OK; check live timeline. Tạo preset YouTube1080HEVC, cấu hình subtitle burn-in theo ý muốn. Done --apply trả job ID; render-status phải đợi Complete rồi kiểm tra MP4 có hình+tiếng/duration trước VERIFIED.
9. Sửa tay rồi done lần nữa: tạo _v2, không ghi đè file trước. Giữ Resolve mở và không di chuyển folder.
10. Nếu dùng YouTube: login đúng channel, preview metadata, công bố AI=true và private. Duyệt preview rồi upload private một bản thử. Xem receipt và Studio. Không thử lịch public nếu chưa được user yêu cầu; không tự reset UNKNOWN upload receipt.

Nếu kiểm tra nào thất bại, giữ nguyên project thử/backup/journal và sửa adapter theo phiên bản API thực tế trước khi dùng hàng loạt. Tests mô phỏng không xác nhận codec, SRT append, audio source-frame behavior hay preset của mọi phiên bản Resolve.
