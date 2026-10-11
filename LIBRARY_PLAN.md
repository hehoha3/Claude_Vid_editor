# Kế hoạch: Agent tự dựng phim (narration → footage → timeline "Edit")

Mục tiêu: sau khi narration đã nằm trên A2 và được duyệt, agent tự chia mỗi câu thoại thành chuỗi shot
1.5–2.5 s, tìm clip phù hợp nhất trong `D:\AI_video` (AI) + `Z:\Unseen\Amazona\video` (real), chọn đúng
đoạn trong clip, thêm ambience/SFX từ `Z:\Unseen\Amazona\audio`, đặt lên timeline rồi dừng cho người dùng duyệt.

Ví dụ câu "The jaguar won't have to go hungry tonight." (9 s):

| # | dài | shot cần | lọc cứng | ưu tiên |
|---|---|---|---|---|
| 1 | 2.0 | trăng + trời đêm (establishing) | landscape, night | sky_weather, wide |
| 2 | 2.0 | cận mặt báo rình sau bụi | jaguar, stalk/hide | close_up, night/dusk |
| 3 | 2.0 | capybara ăn bên suối, đêm | capybara, eat | medium, water, night |
| 4 | 1.5 | không gian đêm tĩnh + SFX dế/côn trùng | landscape, night | forest; audio: insects/night ambience |
| 5 | 1.5 | high-angle báo + mồi chung khung (payoff) | jaguar + prey | source=ai, high_angle |

## Kiến trúc

```
scan-source (đã có)      tag-source (MỚI, 1 lần/clip)        doc-edit
 hash + ffprobe  ──►  _library.json + tags  ◄── tra cứu ── B1 narration → A2 (đã có)      DỪNG
                                                           B2 shot list (Claude viết)     (tuỳ chọn DỪNG)
                                                           B3 match (script) + chọn       
                                                           B4 đặt lên V1/V2/A3–A9 + markers DỪNG
                                                           B5 sửa theo góp ý
```

Nguyên tắc chia việc để rẻ và đúng:
- **Hiểu ảnh (đắt) chỉ làm 1 lần / clip**, lưu thành tag. Khi dựng, không xem lại video.
- **Sáng tạo (chia câu thành shot) do Claude làm**, chỉ đọc chữ: câu thoại + thời lượng.
- **Tìm kiếm do script Python làm** (lọc + chấm điểm), Claude chỉ chọn trong top-3 mỗi slot.
- **Resolve chỉ bị chạm ở B4**, có backup timeline trước.

## Phase 1 — `tag-source`: hiểu nội dung từng clip (nền tảng, làm trước)

Đã build: `.claude/skills/tag-source/`. Clip AI không có file prompt → tag hoàn toàn bằng vision.

Hiện chỉ có tag folder (subject, action) + 54 clip real có tag vision cũ. Thiếu những gì ví dụ trên cần:
ngày/đêm, cỡ cảnh, góc máy, hành động cụ thể, có mấy loài trong khung.

Schema (mở rộng tag hiện có, giữ tương thích):

| trường | giá trị |
|---|---|
| species[] , count | loài trong khung (nhiều loài → shot "payoff") |
| action[] | rest, look, walk, run, stalk, hunt, eat, drink, swim, fly, climb, fight, groom, sleep, call |
| shot_size | extreme_close, close_up, medium, wide, aerial |
| angle | eye, low, high, top_down |
| camera | static, pan, tilt, push, pull, track, handheld |
| light | day, golden, dusk, night, moon |
| setting[] | canopy, forest_floor, river, riverbank, swamp, grassland, sky, moon, cave… |
| mood | calm, tense, dramatic, playful |
| direction | subject di chuyển trái→phải / phải→trái / tới / xa (để nối hướng giữa shot) |
| best | đoạn đẹp nhất: begin / mid / end + in/out gợi ý (giây) |
| issues[] | logo, text, morph (lỗi AI), blur, character_sheet |
| caption | 1 câu mô tả (để Claude đọc khi chọn) |

Cách làm: mỗi clip 1 ảnh ghép 4 frame nhỏ (ffmpeg) → Sonnet subagent theo lô 20 (mặc định từ 2026-10-07), bắt buộc kiểm tra
`tool_uses ≥ số clip` (bài học: Haiku đoán theo tên file nên đã bỏ). Kết quả ghi vào `_library.json`
theo hash, nên đổi tên/chuyển folder không mất tag. Lần sau chỉ tag clip NEW từ `scan-source`.

Chi phí: ~1450 clip (1149 AI + 305 real) × ~1.5k token ≈ 2.2M token, **1 lần**.
Kiểm tra: người dùng xem ngẫu nhiên 40 clip (bảng caption + tag) trước khi dùng thật.

## Phase 2 — `doc-edit` B2: shot list cho từng câu

> Cập nhật 2026-10-09: gộp còn 3 bước. Phase 2+3 = `/doc-edit plan` (scripts/plan.py: spec.txt → shot list +
> tự chọn clip/audio, người dùng duyệt plan.md một lần); Phase 4 = `/doc-edit place` (scripts/place.py).
> Xem `.claude/skills/doc-edit/SKILL.md`; các mục dưới là thiết kế gốc.

Input: folder audios của B1 (`timestamp.md`, `script.md`, `kịch_bản.md`) + vị trí/thời lượng các câu trên A2
(đọc từ timeline, không nghe audio).

Phân bố audio track (timeline "Edit") — shot list ghi nhu cầu audio của mỗi slot theo đúng track:

| track | nội dung |
|---|---|
| A2 | Narrator Voice (B1, không đặt gì khác) |
| A3 | Ambience 1 |
| A4 | Ambience 2 |
| A5 | Ambience 3 |
| A6 | Natural sounds |
| A7 | Music |
| A8 | SXF 1 |
| A9 | SXF 2 |
Claude viết `.work/doc_edit/<video>/shotlist.json`, mỗi slot: thời lượng, mô tả, lọc cứng, ưu tiên,
nguồn (real/ai/any), SFX nếu có. Theo lô ~20 câu, có ngữ cảnh câu trước/sau.

Quy tắc dựng (file `references/edit-grammar.md`, rút từ ví dụ của người dùng + skill edit-craft):
- shot thường 1.5–2.5 s; được để lâu hơn (3–5 s) khi cần kể thêm tình tiết (hành động diễn ra, khoảnh khắc
  cảm xúc, establishing rộng); câu dài → nhiều shot, khoảng lặng giữa câu → shot không khí kéo dài (J/L-cut).
- trình tự: establishing → chủ thể → đối tượng/phản ứng → không khí → payoff.
- đổi cỡ cảnh giữa 2 shot liền nhau; giữ hướng chuyển động; ngày/đêm phải khớp câu.
- real ưu tiên cho shot thông thường; AI cho shot real không thể có (2 loài chung khung, góc bay cao).
- không ghép real + AI thành "cùng một cá thể" liền nhau; không lặp clip trong 1 video.

Gate BẮT BUỘC (quyết định 2026-10-07): người dùng duyệt shotlist (bảng ngắn) trước khi tìm footage.

## Phase 3 — `doc-edit` B3: tìm và chọn clip

Script `match.py` (không tốn token): lọc cứng theo slot → chấm điểm ưu tiên (cỡ cảnh, light, action,
setting, mood) − phạt (đã dùng, issues, cùng clip với shot kề, trùng cỡ cảnh shot trước) → top-3.
Claude đọc top-3 dưới dạng 1 dòng caption/clip và chọn (~300 token/slot). In/out lấy từ `best`,
bỏ 0.3 s đầu/cuối clip AI (hay bị morph). Audio: lọc audio index theo category + từ khoá.

Không có clip đạt ngưỡng → slot "THIẾU": đặt marker đỏ lên timeline "Edit" phủ đúng đoạn của slot
(start = đầu slot, duration = độ dài slot), note = mô tả shot cần để người dùng tự tạo. Marker không
phá timeline nên được đặt ngay ở B3; không đặt clip tạm. Kết quả: `edit_plan.json` (slot → clip, in/out, lý do) — người dùng sửa tay được.

Ước tính: video 10 phút ≈ 300 slot ≈ 100k token (chủ yếu Claude chọn + viết shot list).

## Phase 4 — `doc-edit` B4: đặt lên Resolve

- Backup timeline `Edit_bak_footage_<stamp>`.
- `MediaPool.AppendToTimeline([{mediaPoolItem, startFrame, endFrame, recordFrame, trackIndex}])`:
  V1 = shot chính, audio theo bảng track ở Phase 2 (A3–A9). Import clip vào bin theo nguồn ("1. Real", "2. AI", "3. SFX").
- Marker mỗi slot (xanh = khớp tốt, vàng = tạm được, đỏ = THIẾU, đã đặt ở B3), note = lý do chọn.
- Báo: số slot, số THIẾU, danh sách slot vàng/đỏ. **DỪNG cho người dùng duyệt.**

## Phase 5 — sửa theo góp ý

`/doc-edit fix <slot> [ghi chú]` → lấy ứng viên kế tiếp hoặc tìm lại theo ghi chú, thay đúng 1 item.
Mọi lần người dùng từ chối/sửa ghi vào `feedback.jsonl` → cập nhật trọng số `match.py` và edit-grammar.

## Sau này (không làm bây giờ)
Match màu tự động giữa shot real/AI trong cùng cảnh, transition, nhạc nền theo mood + ducking, render.

## Thứ tự làm & kiểm tra (cập nhật 2026-10-07)

Đã xong: B1 narration (`/doc-edit <audios-folder>` → A2), scan-source, Phase 1 tag 2,062 clip
(batch 146–167 tag lại bằng Sonnet vì Haiku đoán sai).

| # | việc | ra | gate |
|---|---|---|---|
| 1 | Kiểm tra tag: `review` 40 clip ngẫu nhiên (ưu tiên batch 146–167) | `review.md` | người dùng duyệt |
| 2 | Chạy thử B1 với 1 folder audios thật (format mới, A2) | narration trên A2 | người dùng nghe |
| 3 | Phase 1b — tag 77 file audio (chỉ từ tên file + duration + loudness, không nghe): `role` (ambience_bed / natural / music / sfx_hit), `track` gợi ý (A3–A9), `light` (day/night), `keywords`, `loop` | `audio/_library.json` | người dùng sửa bảng 77 dòng |
| 4 | Phase 2 — `references/edit-grammar.md` + schema `shotlist.json` (slot: thời lượng, mô tả, lọc cứng, ưu tiên, nguồn, audio theo track) | shotlist 1 video cũ, chạy khô | người dùng duyệt shotlist |
| 5 | Phase 3 — `match.py` + self-check; `edit_plan.json`; marker đỏ cho slot THIẾU | edit_plan + marker | người dùng xem marker |
| 6 | Phase 4 — đặt V1 + A3–A9 trên bản copy timeline | timeline dựng thô | người dùng duyệt |
| 7 | Phase 5 — `/doc-edit fix`, `feedback.jsonl` | | |

Test: `match.py` có self-check (không lặp clip, lọc cứng không bị vi phạm, slot thiếu được báo,
không đặt gì lên A2).

Gợi ý gán track cho audio: ambience_sound → A3/A4 (2 lớp nền), Nature_sound dài/loop → A6,
Nature_sound ngắn (< ~4 s, tiếng gọi, cành gãy) → A8/A9, tense_music → A7.
Thư viện nhạc hiện chỉ có "tense" (15 file) → video cần đoạn calm/majestic sẽ thiếu nhạc: báo THIẾU như footage.

## Rủi ro
- Tag sai → chọn sai: người dùng sửa tag/edit_plan; sửa được lưu lại theo hash.
- Thư viện thiếu cảnh (vd capybara ban đêm): slot THIẾU là bình thường, báo rõ để người dùng tạo thêm.
- Câu trừu tượng ("thời gian đang cạn dần"): dùng bối cảnh câu trước/sau, rơi về shot không khí.
