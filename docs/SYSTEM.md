# Hệ thống Claude Video Editor: bên trong hoạt động thế nào

Cài đặt và dùng hằng ngày: [README](../README.md). File này dành cho người muốn hiểu hệ thống: nó làm gì ở từng bước,
dữ liệu nằm ở đâu và trông ra sao, plan chọn clip theo luật nào, và vì sao nó rẻ.

## 1. Bức tranh tổng thể

```
 Bạn (chat tiếng Việt, gọi từng bước)
   │
   ▼
 Claude Code ──luôn nạp──► CLAUDE.md (10 luật) + memory cá nhân + handoff (trạng thái dở dang)
   │
   ├─ skill ──► .claude/skills/<skill>/SKILL.md (+ references/, chỉ nạp khi dùng)
   ├─ subagent ──► .claude/agents/tagger.md (Sonnet nhìn ảnh để tag footage, chỉ Read + Write)
   │
   └─ script Python ──► làm việc nặng, in vài dòng tóm tắt
          ├─► DaVinci Resolve (Scripting API): timeline, media pool, marker, grade, render
          ├─► thư viện: Z:\ (footage thật, nhạc, SFX: chỉ đọc), D:\AI_video (clip AI)
          ├─► .work/ (index + tag, cache, beat sheet, spec, plan, ledger, memory)
          └─► PostgreSQL dvr_library (tuỳ chọn: bản sao để truy vấn)
```

**Năm nguyên tắc**
1. **Truyện trước, footage sau.** Hiểu phim → story → beat → chuỗi shot → mới tìm clip. Giới tính, tuổi, kết cục và
   điều screenplay cấm là luật cứng; không có clip đúng thì báo THIẾU, không lấp bằng clip sai truyện.
2. **Claude phán đoán, script làm phần máy móc.** Claude viết beat sheet (cảm xúc, nội dung shot); script chia độ dài
   shot, đặt nhạc/SFX theo luật dựng, chấm điểm hàng nghìn clip, đặt lên timeline. Claude chỉ đọc vài dòng tóm tắt.
3. **Mọi clip được "nhìn" một lần.** Tag-source lưu những gì thấy trong clip thành tag. Lúc dựng không xem lại video,
   không nghe audio.
4. **Mỗi bước có cổng duyệt.** Claude dừng sau mỗi bước; việc phá huỷ phải có "yes".
5. **Không mất dữ liệu.** Backup timeline trước khi đổi lớn, `Z:` chỉ đọc, Claude không tự xoá file.

## 2. Bản đồ thư mục

| Đường dẫn | Chứa gì | Git? |
|---|---|---|
| `CLAUDE.md` | Luật làm việc của Claude (nạp mọi phiên) | có |
| `.claude/skills/` | 12 skill: `SKILL.md` + `references/` + `scripts/` | có |
| `.claude/agents/tagger.md` | Subagent tag footage (Sonnet, chỉ Read + Write) | có |
| `.claude/commands/` | Lệnh nhanh `/project-status`, `/review-frame`, `/sync-vo` | có |
| `.claude/settings.json` | Quyền chung (hỏi trước `place.py`, `--replace`, `grade.py apply`...; cấm SendKeys) + hook in handoff | có |
| `.claude/settings.local.json` | Quyền riêng từng người | không |
| `dvr_cowork/` | Thư viện Python: kết nối Resolve, vo-sync, `info/at/find/offline/frames/backups`, `backup_timeline` | có |
| `luts/` | 7 LUT AMZ + `make_luts.py` | có |
| `config.toml` | Đường dẫn, workspace, thông số Whisper / vo-sync | có |
| `tests/test_pipeline.py` | Test end-to-end (mock Resolve) + chạy self-test của mọi script | có |
| `.work/library/` | Index thư viện + tag + cache YOLO / màu nền của team | không, gói team (mục 11) |
| `.work/tools/` | `memory_gateway.py`, `library_db.py` (PostgreSQL), `cleanup_workspace.py`, `team_data.py` | có |
| `.work/knowledge/` | Ghi chú memory dự án (Markdown, mở bằng Obsidian) | không, gói team |
| `.work/memory/knowledge.db` | Chỉ mục tìm kiếm của ghi chú (tự dựng lại) | không |
| `.work/doc_edit/<video>/` | `brief.md`, `beats_parts/`, `spec.txt`, `plan.json`, `plan_stdout.txt` | không |
| `.work/doc_edit/ledgers/` | Ledger clip đã dùng, mỗi kênh một file | không, gói team |
| `.work/doc_edit/caption_emb_e5small.npz`, `loudness.json` | Cache vector caption, LUFS đã đo | không |
| `.work/<video>_mp3/plan.json` | Kết quả vo-sync: điểm bắt đầu giọng từng câu | không |
| `.work/tag_source/` | Contact sheet (`sheets/`), batch tag `batch_NN.json` + `_result.json` | không |
| `.work/grade/`, `.work/hide_logo/`, `.work/process_ai_video/` | Plan màu + cache frame; registry logo; log xử lý clip AI | không |
| `.work/scripts/` | Script dùng một lần (dọn bằng `cleanup_workspace.py`) | không |
| `.models/` | Model Whisper, YOLO, e5 (setup tự tải) | không |
| `input/` | Tài liệu riêng của bạn (kế hoạch, mẫu) | không |

**Ổ đĩa và vùng (region).** Mỗi video thuộc một vùng; plan, fill và prompt chỉ dùng footage của vùng đó:

| Root (tên trong code) | Đường dẫn | Loại | Vùng |
|---|---|---|---|
| `video` | `Z:\Unseen\Amazona\video` | footage thật | amazon |
| `ai` | `D:\AI_video` (`_check` = clip mới chưa xếp, `_nologo` = bản đã xoá logo) | AI | amazon |
| `africa_video` | `Z:\Unseen\Động vật\AAA Trên cạn` (thư mục theo loài, tiếng Việt) | footage thật | africa |
| `africa_ai` | `...\AAA Trên cạn\AI_copyright` | AI | africa |
| `africa_ai_check` | `D:\AI_video\_africa` (`_check` = clip mới) | AI | africa |
| `savannah` | `Z:\Unseen\savannah` | cảnh đồng cỏ | africa |
| `audio`, `sfx`, `sound` | `Z:\Unseen\Amazona\audio`, `Z:\Unseen\SFX`, `Z:\Unseen\Sound` (nhạc theo mood) | âm thanh | chung |

Thư mục kênh: `D:\Chann_<n>_<tên>\<video>\audios\` (đầu vào), `_done\` (video xong), `_pushed\` (của bạn, Claude
không đụng).

## 3. Dữ liệu trông ra sao

**Một clip trong index** (`.work/library/<root>_library.json`, khoá = hash nội dung nên đổi tên/chuyển file vẫn giữ tag):

```json
"path": "Hươu cao cổ\\adult-giraffe-eating-...mp4", "width": 3840, "height": 2160, "fps": 30.0, "duration": 15.0,
"subject": "giraffe", "source": "real",
"tags": {"species": ["giraffe"], "action": ["eat"], "phase": ["eat","eat","eat","eat"], "sex": "unknown",
         "age": "unknown", "outcome": "none", "count": "one", "shot_size": "medium", "angle": "eye",
         "camera": "static", "light": "golden", "setting": ["savanna"], "mood": "calm", "direction": "left",
         "issues": [], "good": [1,2,3,4], "best": [0.45, 14.55], "sure": true, "v": 2,
         "caption": "Giraffe browses leaves from a green acacia bush on golden savanna, medium shot"}
```
`phase` = hành động ở 4 frame của contact sheet (15/40/65/90 %), để plan cắt đúng đoạn có hành động; `best` = đoạn dùng
được; `issues` = morph, blur, logo...; `outcome` = none / miss / catch / kill.

**Bản đọc phim** (`brief.md`, do `story.py brief` tạo): screenplay nguyên văn, dòng narrator của mỗi beat được thay
bằng các câu đã đánh số và có thời gian:
```
**004 · 01:30.6–02:00.6** — Earlier light: wide Liuwa plain, scattered rain pools and a wildebeest carcass...
*Character lock:* H1 adult spotted hyenas (sex undetermined), L1/L2 adult females...
  12 01:30.6 4.1s vo2.6 | The plain is wet after the first rains.
```
`4.1s` = khoảng của câu tới câu sau, `vo2.6` = giọng đọc dài 2.6 s (phần còn lại là khoảng lặng có thể cho hình tự
kể). Character lock chỉ in khi đổi. Phần sau là Visual Edit Plan, bỏ bảng beat vì trùng screenplay.

**Beat sheet** (`beats_parts/01.txt`..., Claude viết):
```
# REGION africa
# CAST [L] sp=lion sex=female            <- mọi dòng bắt đầu bằng [L] tự có token này
# STORY 1 @16 no=river,crocodile          <- @16 = thời điểm câu 16
>> 1-15 raw                               <- intro: dòng spec viết tay
>> 16-18 calm A3=wind,insects             <- câu 16-18, cảm xúc, âm thanh nền
[L] Sư tử cái nằm trong bóng cỏ | sp=lion act=rest size=close_up
[Z] Đàn ngựa vằn gặm cỏ phía xa | sp=zebra size=wide count=many
~ Cỏ lay trong gió | real | sp=none size=wide          <- shot phụ, chỉ vào khoảng lặng
>> 19-20 build
>> 21 strike
21: [L] Sư tử cái bật khỏi cỏ | real | act=attack size=medium
```

**Spec** (`spec.txt`, do `story.py expand` sinh; video cũ viết tay): mỗi câu `## n`, mỗi shot một dòng
`độ dài | shot cần (tiếng Việt) | real/ai/any/GFX | bộ lọc | âm thanh`:
```
## 21
# TURN
* | [L] Sư tử cái bật khỏi cỏ | real | act=attack size=medium sp=lion sex=female | A8=hit
1.6 | [L] Sư tử cái bật khỏi cỏ | real | act=attack size=medium sp=lion sex=female |
```

**Một slot trong plan.json** (`.work/doc_edit/<video>/plan.json`, không bao giờ sửa tay):
```json
{"slot": 1, "line": 1, "start": 0.0, "dur": 1.71, "need": "[CP] Capybara lao xuống mép sông", "src": "any",
 "filter": {"sp": ["capybara"], "act": ["run","swim"], "size": ["medium"], "no": ["caiman"]},
 "status": "OK", "path": "D:\\AI_video\\capybara\\...mp4", "intro": true, "vo": true, "rej": {"resting": 18},
 "audio": [{"track": 6, "kw": ["footsteps"], "status": "OK", "path": "Z:\\Unseen\\SFX\\shared_footsteps_walk_grass_01.mp3"},
           {"track": 7, "kw": ["epic"], "span": 79.1, "status": "OK", "path": "Z:\\Unseen\\Sound\\DonDap_KichTinh\\..."}]}
```
`rej` = bao nhiêu clip đúng loài bị từ chối vì sai truyện (đang nằm nghỉ, sai giới tính, có cảnh giết...).
`<video>\plan.md` là bảng dễ đọc của cùng dữ liệu cho bạn duyệt.

**Ledger** (`.work/doc_edit/ledgers/<kênh>.json`): `{"workspace": ..., "videos": [{"video": "africa_3", "checked":
"2026-10-24", "clips": [<hash>...], "open_clips": [...]}, ...]}`, video mới nhất đứng đầu.

## 4. Thư viện: quét, tag, đo

1. **scan-source** (`scan_source.py`): duyệt các root, tính hash nội dung, đọc kích thước/fps/độ dài → index. Clip đổi
   tên/chuyển chỗ giữ nguyên tag; báo "moved N", "new N".
2. **tag-source** (`tag_source.py prepare` → agent `tagger` → `apply`): mỗi clip một contact sheet 2x2 (960x540) ở
   `.work/tag_source/sheets/`; 20 clip một batch; mỗi agent Sonnet làm 4 batch, mở ảnh song song, ghi
   `batch_NN_result.json`; `apply` kiểm tra từ vựng rồi gộp vào index. Clip phong cảnh (không con vật) được điền story
   field không cần nhìn. `--retag action,sex,age,outcome,phase` bổ sung trường mới cho clip đã tag. Africa tag theo
   loài khi phim cần (`--subject lion --sample 60`).
3. **YOLO** (`yolo.py`, GPU, 0 token): đo con vật nằm ở đâu, chiếm bao nhiêu khung → cache `.work/library/yolo.json`.
   Plan chỉ cắt đoạn có con vật, và biết cỡ cảnh thật. Africa (4K trên NAS, chậm) chỉ dùng cache.
4. **Màu nền** (`look.json`): tỉ lệ xanh của nền từ contact sheet, để giữ cảnh khô / xanh liền mạch (`# LOOK`).
5. **organize.py**: clip AI mới ở `_check` được đặt tên `<loài>_<từ khoá>-<cỡ>.mp4` và chuyển vào thư mục loài;
   clip lỗi (morph, logo...) ở lại `_check`.

## 5. Luồng một video

```
audios/ (screenplay + timestamp EN/VI + mp3/1..n)
  │ A (nền)  vo-sync: đo điểm bắt đầu giọng từng file → A2 (mỗi câu một item) + subtitles_vi.srt → Subtitle 1
  │ B (chính)
  │   story.py brief ──► brief.md ──► Claude đọc 1 lần (+ edit-grammar.md)
  │   Claude viết beat sheet (bible, HOOK, CAST, cảm xúc + shot từng beat)
  │   story.py expand ──► spec.txt
  │   plan.py ──► plan.json + plan.md (+ 25 dòng tóm tắt)      ◄─ sửa beat, expand, plan lại
  │   missing.py ──► missing_prompts.txt (1 prompt / slot THIẾU)
  ▼
 intro.py tự chọn nhạc intro → plan.py → place.py: backup → intro + thân phim cùng lúc (V1 + A1 + A3-A9 + marker)
  │ bạn tạo clip AI → logo / delogo → ingest --fill (scan + tag + organize + plan + place --fill)
  │ reframe · audio-expert · color (light pass)
  ▼
 done: render Done_<project>.mp4 (preset "YouTube 1080 HEVC", tắt phụ đề) → license → ledger → relink
       → đóng Resolve → chuyển thư mục vào _done
```

### 5.1 story.py: từ truyện ra spec

`brief` gom ba file đầu vào thành một bản đọc (africa_4: 74 KB thay vì 183 KB). `expand` biến các luật dựng có thể
máy móc hoá thành code, theo cảm xúc của từng beat:

| Cảm xúc | Độ dài shot trung bình (đầu → cuối beat) | Nhạc A7 khi đổi cảm xúc | Thêm |
|---|---|---|---|
| `calm` | 4.5 s | calm | shot phụ trong khoảng lặng |
| `wonder` | 5.0 → 4.5 s | wonder | shot phụ |
| `observe` (kể bình thường) | 3.6 → 3.2 s | neutral | shot phụ |
| `build` | 3.4 → 1.8 s, ngắn dần | tense | riser nếu sau đó là strike |
| `tense` | 3.0 → 2.4 s | tense | |
| `chase` | 1.9 → 1.4 s, ngắn dần | chase | whoosh ở shot đầu |
| `strike` | 1.6 → 1.4 s | tắt nhạc ở shot trước | hit + `# TURN` |
| `release` | 5.5 → 3.5 s, shot đầu dài nhất | calm | shot phụ |
| `sad` | 5.0 → 4.5 s | calm | shot phụ |

Ngoài ra: độ dài không đều (không bao giờ như máy đếm nhịp), `*` đặt vào shot dài nhất; shot phụ chỉ trong khoảng lặng
≥ 3 s của beat yên, không hai shot phụ liền nhau, ≤ 22 % thời lượng; âm thanh tự nhiên A6 suy từ hành động (bước chân,
cỏ, uống nước, ăn, nước, cánh, thở), cách nhau ≥ 8 s; token viết tay luôn thắng. Benchmark africa_3 (cùng footage):
shot ≤ 2 s 0 % → 30 %, `# TURN` 0 → 11, SFX 5 → 27, âm thanh tự nhiên 6 → 70.

### 5.2 plan.py: chọn clip thế nào

1. **Lọc cứng**: đúng vùng, đúng loài (`sp=`), ngày/đêm, `no=` (kể cả `no=` của cả story), không thuộc ledger của 6
   video gần nhất cùng kênh, không cảnh ôn đới / sở thú / máu.
2. **Sự thật của truyện** (`hard()`): sai `sex=` / `age=` → loại; không thấy giới tính → tối đa WEAK, marker "kiểm tra";
   dòng săn/đuổi không nhận clip chỉ nằm nghỉ; clip có con mồi bị bắt/giết chỉ dùng khi dòng có `out=kill`.
3. **Chấm điểm tag**: hành động (nặng nhất, theo `phase` từng frame), bối cảnh, cỡ cảnh, ánh sáng, mood, góc máy, hướng
   màn hình, `kw=`; trừ điểm clip lỗi. OK ≥ 0.6, WEAK ≥ 0.35, dưới đó THIẾU.
4. **Phân định** clip cùng mức bằng ngữ nghĩa: câu "shot cần" (tiếng Việt) so với caption (tiếng Anh) bằng e5.
5. **Dùng lại trong một video**: một clip tối đa 6 slot, cách nhau ≥ 90 s, ưu tiên đoạn khác của clip; cùng frame tối
   đa 3 lần, cách ≥ 5 phút. Shot dài hơn mọi clip → 2-3 clip (⧉).
6. **YOLO**: chỉ lấy đoạn có con vật trong khung; **vary**: tốc độ gốc frame-exact, slow-mo thật cho shot tĩnh dài,
   punch-in trên nguồn 4K.
7. **Intro**: shot con vật ở intro lấy cao trào của story sau cùng loài (136-150 %), cắt theo hit/bar của nhạc intro;
   4 s cuối intro là phong cảnh fade.
8. **Âm thanh**: từ khoá khớp tên file. SFX / âm thanh tự nhiên không bao giờ thay bằng thứ gần giống (thiếu → audio
   THIẾU); tiếng loài vật chỉ từ chính loài hoặc họ hàng; tiếng nước chỉ khi hình có nước. Nhạc: bài hợp nhất, không xét
   số lần đã dùng: khớp nhiều từ mood nhất, rồi phủ hết đoạn, rồi độ dài sát đoạn nhất; không hai cue liền nhau
   cùng một bài.

### 5.3 Track của timeline Edit

A1 tiếng clip AI (-12 dB) · A2 narrator (mỗi câu một item) · A3/A4 nền ambience (luân phiên, crossfade 4 s) · A5 lớp
môi trường · A6 âm thanh tự nhiên · A7 nhạc · A8/A9 SFX. Subtitle 1 = phụ đề tiếng Việt. Marker: đỏ THIẾU (ghi chú =
shot cần), vàng WEAK, xanh GFX. Bin video theo hành động: `1. Other_roll`, `2. Attack_roll`, `3. Run_roll`; âm thanh
trong `4. Audio/...`; mọi timeline (trừ Master) trong `6. Timeline`: bin tạo nếu thiếu, gom lại mỗi lần script tạo
backup (`dvr_cowork.resolve_ops.tidy_timelines`; `.\dvr.cmd timelines` gom ngay).

## 6. Memory: Claude nhớ bằng gì

| Lớp | Ở đâu | Nạp khi nào | Chứa gì |
|---|---|---|---|
| Luật | `CLAUDE.md` | Mọi phiên | An toàn, track, công cụ (chung cả team) |
| Memory cá nhân | `~/.claude/projects/.../memory/` | Mọi phiên (mục lục `MEMORY.md`) | Sở thích và cách làm của từng người |
| Memory dự án (gateway) | `.work/knowledge/` | Khi cần tìm; handoff in lúc mở phiên | Quyết định, sự cố, quy trình, trạng thái video |
| Kiến thức nghề | `SKILL.md` + `references/` | Khi dùng skill | Ngữ pháp dựng, màu, âm thanh |

Gateway có 4 thư mục: `decisions/` (đã chốt + lý do), `incidents/` (sự cố + cách tránh), `workflows/` (quy trình),
`handoffs/` (`current.md` = đang dở gì; `archive_2026-10.md` = lịch sử). Tìm kiếm lai: từ khoá (SQLite FTS5) + ý nghĩa
(vector `multilingual-e5-small` trong `sqlite-vec`), gộp RRF; hỏi tiếng Việt tìm được ghi chú tiếng Anh.

```
memory_gateway.py search "logo bị bóng" --limit 3     → tối đa 3 dòng: [đường dẫn] tiêu đề | đoạn trích
memory_gateway.py save --type decisions --title .. --text ..    (chỉ điều bạn đã xác nhận)
memory_gateway.py startup | index | doctor | selftest
```
Xem: mở thư mục `.work\knowledge` bằng Obsidian (dữ liệu thật), hoặc `knowledge.db` bằng DB Browser for SQLite (chỉ
mục, chế độ Read Only; bảng vector cần extension nên bỏ qua).

## 7. PostgreSQL: bản sao để truy vấn

`library_db.py sync` xoá và chép lại toàn bộ từ JSON (vài giây); JSON luôn là dữ liệu gốc. Kết nối: biến `LIBRARY_DB`,
mật khẩu chỉ ở `%APPDATA%\postgresql\pgpass.conf`.

| Bảng | Một dòng là |
|---|---|
| `clips(root, id, source, path, subject, duration, width, height, fps, tags jsonb)` | một clip video + tag (index GIN trên tags) |
| `usage(workspace, video, rank, clip_id, timeline)` | clip đã dùng trong một video (rank 0 = video mới nhất của kênh) |
| `slots(video, region, slot, line, start, dur, tag, need, species, filter, status, clip_id, path, source, intro, vo, rej)` | một shot trong plan.json của mọi video |
| `slot_audio(video, slot, start, track, kw, status, path)` | một cue âm thanh A3-A9 trong plan |
| `audio(root, id, path, category, duration, sample_rate, channels, title_hint, lufs, blocked)` | một file âm thanh |

Ví dụ: `SELECT count(*) FROM clips WHERE tags->'species' ? 'lion' AND tags->>'sex' = 'female' AND tags->'action' ? 'run'`;
`SELECT kw, count(*) FROM slot_audio WHERE status = 'THIEU' GROUP BY 1 ORDER BY 2 DESC`.

## 8. Các skill

| Skill | Làm gì | Script chính | Ghi vào |
|---|---|---|---|
| `doc-edit` | Narration → brief → beat sheet → plan → place; missing-prompts, logo, delogo, ingest, fill, color, reframe, status, check-timelines, done | `story.py`, `plan.py`, `place.py`, `missing.py`, `ledger.py`, `reframe.py`, `yolo.py`, `beats.py` (nhịp nhạc), `state.py`, `bench_story_first.py` | Timeline Edit, `.work/doc_edit/` |
| `tag-source` | Agent tagger nhìn 4 frame/clip một lần → tag; xếp clip AI mới vào thư mục loài | `tag_source.py`, `organize.py` | `.work/library/` |
| `scan-source` | Cập nhật index sau khi thêm/đổi/xoá file | `scan_source.py` | `.work/library/` |
| `process-ai-video` | Làm clip AI trông như quay thật, cắt character sheet đầu clip | `process_ai_video.py` | Ghi đè clip trong `D:\AI_video` |
| `hide-logo` | Xoá logo bằng MiniMax-Remover → `_nologo`, relink; ghi đè gốc khi xong video | `hide_logo.py`, `minimax_worker.py` | `D:\AI_video\_nologo`, Resolve |
| `colorist` | `/doc-edit color` = light pass (CDL nhẹ, màu tươi, cỏ vàng trong đoạn cỏ cháy); match/grade khi gọi tên | `light.py`, `match.py`, `grade.py`, `dry_preview.py` | Node 1 trong Resolve |
| `audio-expert` | Bản đồ âm thanh, chọn nhạc/SFX/âm tự nhiên, đặt A5-A9, rollback | `index.py`, `plan.py`, `execute.py` | A5-A9 |
| `thumbnail` | Hoàn thiện thumbnail bằng PhotoCraft (PSD, PNG, JPG 3840x2160) | `thumb.py` | `D:\Thumbs\<tên>\` |
| `edit-craft` | Kiến thức dựng: nhịp, điểm cắt, J/L cut, xuất YouTube | — | — |
| `resolve-api` | Lưu ý khi viết script cho Resolve | — | — |
| `memory-find` / `memory-save` | Tìm / lưu memory dự án | `memory_gateway.py` | `.work/knowledge/` |
| `gemini-assist` | Ý kiến thứ hai từ Gemini (REST API, chỉ đọc, không tool, không web); key trong Windows Credential Manager | `gemini_bridge.py` | `.work/gemini/` (cache, `usage.jsonl`) |

## 9. An toàn

- **CLAUDE.md**: "yes" trước mọi việc phá huỷ (gọi lệnh của một bước = đồng ý cho đúng thay đổi của bước đó); chỉ đổi
  đúng thứ được nói (một shot = thay một item, không plan/place lại); `Z:` chỉ đọc; không tự xoá file; không đụng
  `Master` và `_pushed`; preflight trước mỗi việc; việc bị từ chối không thử lại y hệt.
- **`.claude/settings.json`**: luôn hỏi trước `place.py`, `--replace`, `grade.py apply`, `reframe --apply`, xoá
  clip/timeline; cấm gửi phím tắt.
- **Backup**: `Edit_bak_<loại>_<giờ>` (bin `6. Timeline`) trước vo-sync, place, reframe, màu, audio-expert. Khôi phục
  = mở lại backup (hỏi trước). Quá nhiều backup làm Resolve lag: `.\dvr.cmd backups --keep 3 --apply`.

## 10. Nhanh và rẻ: vì sao

| Kỹ thuật | Tiết kiệm |
|---|---|
| Tag mỗi clip một lần; clip phong cảnh điền story field không cần nhìn; agent tagger chỉ Read + Write, 4 batch/agent, mở ảnh song song | Phần tốn nhất (nhìn ảnh) chỉ trả một lần |
| `story.py brief`: một bản đọc ~40 % dung lượng ba file đầu vào | Token đọc kịch bản |
| Beat sheet thay vì viết tay ~1000 dòng spec | ~1/3 token viết, luật dựng áp đều tay |
| Script in tóm tắt; Claude không mở plan.json, audio, index | Token mỗi bước nhỏ |
| Skill và `references/` chỉ nạp khi dùng | Token mọi lượt thấp |
| Cache: Whisper, YOLO, vector caption, màu nền, LUFS, vector memory | Lần sau nhanh (plan ~20-60 s cho ~1000 shot) |
| PostgreSQL cho câu hỏi xuyên video | Một câu SQL thay vì script quét JSON |
| Preflight một lệnh; việc bị chặn không thử lại | Không mất lượt vô ích |

## 11. Dữ liệu của team: chia sẻ code, giữ riêng dữ liệu

Repo (git) chỉ chứa hệ thống: code, skill, tài liệu, dùng chung cho nhiều team. Dữ liệu làm việc của mỗi team nằm
trong `.work/` (trừ `.work/tools/`), `input/` và `.claude/settings.local.json`. Phần này không bao giờ lên git, và đi
trong team bằng một file zip:

```powershell
.venv\Scripts\python.exe .work\tools\team_data.py list                           # có gì, bao nhiêu MB
.venv\Scripts\python.exe .work\tools\team_data.py export D:\team_data_<ngày>.zip  # đóng gói + kiểm tra từng file
.venv\Scripts\python.exe .work\tools\team_data.py import <zip> [--overwrite]     # máy đồng đội: nhập vào repo
.venv\Scripts\python.exe .work\tools\team_data.py clean --pack <zip> [--apply]   # xoá dữ liệu team khỏi máy này
```
Những thứ dựng lại được thì không đóng gói: chỉ mục memory, contact sheet của batch đã tag, vector caption, cache frame
màu. Riêng sheet của batch **đang chờ tag** thì có trong gói, vì `prepare` không tạo lại chúng. `clean` từ chối chạy nếu
gói không chứa đủ mọi file với đúng kích thước. Sau `import`: `memory_gateway.py index`, rồi `library_db.py sync`
(PostgreSQL là bản sao, mỗi máy tự sync). Thư viện của team không nằm ở `Z:\Unseen`: sửa `ROOTS` trong
`scan_source.py` và `config.toml`.

## 12. Bảo trì và mở rộng

```powershell
.venv\Scripts\python.exe -m tests.test_pipeline            # test + self-test của 19 script, ~10 s
.venv\Scripts\python.exe .work\tools\cleanup_workspace.py  # rác có thể xoá (dry run; --apply = xoá, bạn chạy)
.venv\Scripts\python.exe .claude\skills\doc-edit\scripts\plan.py <audios> --spec=<file> --out=<thư mục>   # thử spec khác, không đụng plan thật
.venv\Scripts\python.exe .claude\skills\doc-edit\scripts\bench_story_first.py <video>   # so luật chọn shot mới với plan cũ
```
- **Thêm footage**: `/scan-source` → `/tag-source`. Đổi tên/chuyển file ngoài pipeline làm clip "offline" trong
  project cũ (`.\dvr.cmd offline --relink`).
- **Thêm root / vùng**: `scan_source.py` `ROOTS` + `REGION`; root âm thanh mới thêm `CATEGORY` trong `plan.py`.
- **Thêm loài Africa**: `AFRICA_FOLDERS` (scan_source), `KIN` (plan.py, tiếng gọi họ hàng), thư mục AI
  (`tag-source/scripts/make_africa_ai_folders.ps1`).
- **Đổi luật nhịp / âm thanh của beat**: bảng `EMO`, `NAT`, `SIDE_*` trong `story.py` (chạy lại `--selftest`).
- **Đổi model ngữ nghĩa**: đo lại `SEM_LO/SEM_HI` (plan.py) và `MAX_DIST` (memory_gateway.py).

## Từ điển

| Từ | Nghĩa |
|---|---|
| beat | Một đoạn truyện có một cảm xúc (screenplay chia ~30 s; beat sheet có thể chia nhỏ hơn) |
| beat sheet | File Claude viết: câu nào, cảm xúc gì, những shot nào |
| spec | Danh sách shot cho từng câu narration, sinh từ beat sheet |
| slot | Một shot trên timeline (thời điểm + độ dài) |
| THIẾU / WEAK / OK / FALLBACK | Không có clip đúng (đỏ) / tạm được (vàng) / khớp / shot phụ thay thế |
| truth token | `sex=` `age=` `out=kill` `xact=` `no=`: luật cứng của truyện |
| shot phụ (side shot) | Cảnh không có nhân vật chính, chỉ trong khoảng lặng, ≤ 30 % |
| ledger | Clip đã dùng của mỗi kênh, để video sau không lặp |
| handoff | Ghi chú trạng thái hiện tại để phiên sau làm tiếp |
| workspace | Một thư mục kênh `D:\Chann_*` |
