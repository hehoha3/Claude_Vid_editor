# Hệ thống Claude Video Editor: cách mọi thứ hoạt động

Tài liệu này giải thích **bên trong** hệ thống. Cài đặt và dùng hằng ngày: xem [README](../README.md).

## 1. Bức tranh tổng thể

```
 Bạn (chat tiếng Việt)
   │
   ▼
 Claude Code ──đọc──► CLAUDE.md (luật, mọi phiên)  +  memory (xem mục 4)
   │
   ├─ chọn skill ──► .claude/skills/<skill>/SKILL.md (hướng dẫn, chỉ nạp khi cần)
   │
   └─ chạy script Python ──► làm việc nặng, in ra tóm tắt ngắn
          │
          ├─► DaVinci Resolve (Scripting API): timeline, media pool, marker, grade
          ├─► thư viện: Z:\ (footage thật, nhạc, SFX, chỉ đọc), D:\AI_video (clip AI)
          └─► .work/ (index, cache, plan, ledger, memory)
```

**Nguyên tắc cốt lõi**
- **Script làm việc nặng, Claude chỉ đọc kết quả tóm tắt.** Claude không xem lại video hay nghe audio khi dựng:
  mọi clip đã được "nhìn" một lần (tag-source) và lưu thành tag. Nhờ vậy rẻ và nhanh.
- **Mỗi bước có cổng duyệt.** Claude dừng sau mỗi bước, bạn duyệt rồi mới đi tiếp.
- **Không mất dữ liệu.** Backup timeline trước khi đổi lớn, Z: chỉ đọc, Claude không tự xoá file.

## 2. Thư mục

| Đường dẫn | Chứa gì | Trong git? |
|---|---|---|
| `CLAUDE.md` | Luật làm việc của Claude (nạp mọi phiên) | có |
| `.claude/skills/` | 12 skill: SKILL.md + `references/` + `scripts/` | có |
| `.claude/commands/` | Lệnh nhanh `/project-status`, `/review-frame`, `/sync-vo` | có |
| `.claude/settings.json` | Quyền chung (hỏi trước `place.py`, `--replace`, `grade.py apply`...; cấm SendKeys) + hook in handoff lúc mở phiên | có |
| `.claude/settings.local.json` | Quyền riêng từng người | không |
| `dvr_cowork/` | Thư viện Python: kết nối Resolve, vo-sync, `info/at/find/offline/frames` | có |
| `luts/` | 7 LUT AMZ + cách tạo (`make_luts.py`, README) | có |
| `config.toml` | Đường dẫn, workspace, thông số Whisper/vo-sync | có |
| `.work/library/` | Index thư viện + tag + cache YOLO (dùng chung để không phải tag lại) | có |
| `.work/tools/memory_gateway.py` | Bộ nhớ dự án (mục 4) | có |
| `.work/knowledge/` | Ghi chú memory dự án (Markdown, mở được bằng Obsidian) | không, nhận riêng |
| `.work/memory/knowledge.db` | Chỉ mục tìm kiếm của ghi chú (tự dựng lại) | không |
| `.work/doc_edit/<video>/` | spec.txt, plan.json của từng video | không |
| `.work/doc_edit/ledgers/` | Ledger clip đã dùng, mỗi workspace một file | không, nhận riêng |
| `.work/doc_edit/caption_emb_e5small.npz` | Cache vector caption (tự dựng lại) | không |
| `.models/` | Model Whisper, YOLO, e5 (setup tự tải) | không |
| `.work/scripts/` | Script dùng một lần | không |

Ổ đĩa: `Z:\Unseen\Amazona\video` (footage thật), `Z:\Unseen\Amazona\audio`, `Z:\Unseen\SFX`, `Z:\Unseen\Sound`
(nhạc Envato theo mood), `D:\AI_video` (clip AI; `_check` = clip mới chưa xếp, `_nologo` = bản đã xoá logo),
`D:\Chann_*` (thư mục kênh).

## 3. Luồng một video

```
audios/ (timestamp + narration)
   │  1. /doc-edit <audios>   vo-sync: Whisper nghe → cắt đúng khoảng lặng → A2
   ▼
 Claude viết spec.txt (shot cho từng câu: nội dung, bộ lọc, âm thanh)
   │  2. /doc-edit plan       plan.py: lọc + chấm điểm clip theo tag, YOLO, ngữ nghĩa, ledger → plan.md
   ▼
 bạn duyệt plan.md
   │  3. /doc-edit place      place.py: backup → V1 + A1 + A3-A9 + marker THIẾU/WEAK/GFX
   ▼
 shot THIẾU → missing-prompts → bạn tạo clip AI → process → scan → tag → organize → plan lại
   │  reframe · intro · audio-expert · colorist · sửa logo
   ▼
 4. /doc-edit done          ledger lần cuối → relink → đóng Resolve → chuyển thư mục vào _done
```

**Cách plan chọn clip** (`plan.py`)
1. **Lọc cứng**: đúng loài (`sp=`), đêm/ngày, `no=` loại trừ, không thuộc ledger (4 video gần nhất cùng kênh).
2. **Chấm điểm theo tag**: hành động (nặng nhất), bối cảnh, cỡ cảnh, ánh sáng, mood, góc máy, hướng, `kw=`.
   Trừ điểm clip có lỗi (morph, mờ...). Shot tấn công mà clip không có hành động → tối đa WEAK.
3. **Xếp hạng**: footage thật trước nếu đủ tốt; các clip cùng mức được phân định bằng **ngữ nghĩa** (mục 5).
4. **Trạng thái**: OK (≥ 0.6), WEAK (≥ 0.35, màu vàng), THIẾU (đỏ, cần tạo clip), FALLBACK (shot phụ thay thế sau phút 5).
5. Shot dài hơn mọi clip → cắt 2-3 clip (⧉). Một clip dùng tối đa 3 lần trong một video, cách nhau ≥ 2 phút.
6. YOLO đo vị trí con vật → chỉ cắt đoạn có con vật trong khung, đo cỡ cảnh thật.
7. Âm thanh: khớp từ khoá với tên file; SFX/âm thanh tự nhiên **không bao giờ thay bằng thứ gần giống**
   (thiếu → báo "audio THIẾU").

## 4. Memory: Claude nhớ bằng gì

| Lớp | Ở đâu | Nạp khi nào | Chứa gì |
|---|---|---|---|
| **Luật** | `CLAUDE.md` | Mọi phiên | Luật an toàn, track, công cụ. Chung cả team |
| **Memory cá nhân** | `~/.claude/projects/.../memory/` | Mọi phiên | ≤ 6 mục: sở thích và giới hạn của từng người (không git, ...) |
| **Memory dự án (gateway)** | `.work/knowledge/` | Khi cần tìm + handoff lúc mở phiên | Quyết định, sự cố, quy trình, trạng thái video |
| **Kiến thức nghề** | `SKILL.md` + `references/` | Khi dùng skill | Cách dựng, chỉnh màu, ngữ pháp shot... |

**Quy tắc**: mỗi điều chỉ nằm ở **một** nơi. Cần ở mọi phiên → memory cá nhân/CLAUDE.md; chỉ cần khi làm việc cụ thể →
gateway. Điều đã có trong CLAUDE.md hay SKILL.md thì không lưu lại.

### Gateway: 4 thư mục

| Thư mục | Lưu gì | Ví dụ | Khi nào lưu / sửa |
|---|---|---|---|
| `decisions/` | Quyết định đã chốt + lý do | "Xoá logo bằng clone-patch + haze, không dùng delogo thuần" | Bạn chốt một cách làm. Đổi ý → **sửa** ghi chú cũ, ghi "trước đây là X" |
| `incidents/` | Sự cố + cách đã sửa để không lặp lại | "`rm -rf` mất 104 file audio" | Sau mỗi sự cố |
| `workflows/` | Quy trình, vị trí dữ liệu | "Clip AI mới: process → scan → tag → organize → plan" | Có quy trình mới / đường dẫn đổi |
| `handoffs/` | `current.md`: trạng thái hiện tại (video nào đang làm, việc đang chờ) | "Chờ bạn quyết ghi đè 14 bản _nologo" | Video đổi trạng thái; `done` tự ghi |

- `handoffs/current.md` được **in ra lúc mở phiên** (700 ký tự đầu), nên Claude biết ngay đang dở việc gì.
- File bắt đầu bằng `_` (như `_template.md`) không được index.

### Gateway hoạt động thế nào

```
memory_gateway.py search "logo bị bóng"      → tối đa 3 dòng: [đường dẫn] tiêu đề | đoạn trích
memory_gateway.py save --type decisions --title .. --text ..     (ghi chú mới, ≤ 2500 ký tự)
memory_gateway.py save --update decisions/xxx.md --title .. --text ..   (viết lại ghi chú có sẵn)
memory_gateway.py startup | index | doctor | selftest
```
- **Tìm kiếm lai**: từ khoá (SQLite FTS5) + ý nghĩa (vector, model `multilingual-e5-small`, bảng `sqlite-vec`),
  gộp bằng RRF. Hỏi tiếng Việt vẫn tìm được ghi chú tiếng Anh. Không liên quan → `NO_MATCH`.
- Ghi chú dài được chia đoạn ~500 ký tự trước khi tạo vector; chỉ ghi chú mới/sửa mới được tính lại.
- Hỏng model hoặc sqlite-vec → tự quay về tìm từ khoá. `startup` không nạp model (mở phiên 0,05 s).
- Lệnh trong Claude: `/memory-find`, `/memory-save`. Claude chỉ lưu điều bạn đã xác nhận.

## 5. Ngữ nghĩa trong plan (`--sem`, mặc định bật)

Nhiều clip thường có **cùng điểm tag**; trước đây clip được chọn theo thứ tự thư viện (gần như ngẫu nhiên). Giờ plan so
câu "shot cần" (tiếng Việt) với caption clip (tiếng Anh) bằng e5 và chọn clip **khớp nghĩa nhất** trong nhóm cùng
mức. Trạng thái OK/WEAK/THIẾU vẫn do tag quyết định. Tắt: `--no-sem`. Cache vector caption: lần đầu ~15 s.

## 6. Workspace, ledger, done

- **Workspace** = thư mục khớp `config.toml [workspaces] globs` (mặc định `D:\Chann_*`). Kênh mới = tạo thư mục.
- **Ledger** (`.work/doc_edit/ledgers/<workspace>.json`): clip có trên timeline **Edit + Open** của từng video,
  đọc từ Resolve (`/doc-edit check-timelines`). Plan cấm clip của `recent = 4` video mới nhất **cùng workspace**.
  Bản xoá logo tính như clip gốc. Ledger không lên git: người dựng cùng một kênh nhận file này riêng (sau mỗi `done`, gửi lại bản mới).
- **`/doc-edit done <video>`**: ghi ledger lần cuối → relink media trong thư mục video sang `_done\<video>` (qua
  junction tạm) → lưu → đóng Resolve → đổi chỗ thư mục (một bước, không copy + xoá) → ghi handoff. Không tự mở lại Resolve.
  Tên project khác tên thư mục: `--project <tên>`.

## 7. Các skill

| Skill | Làm gì | Script chính | Ghi vào |
|---|---|---|---|
| `doc-edit` | Narration → plan → place, reframe, missing-prompts, check-timelines, done | `plan.py`, `place.py`, `reframe.py`, `missing.py`, `ledger.py`, `yolo.py` | Timeline Edit, `.work/doc_edit/` |
| `tag-source` | Subagent Sonnet nhìn 4 frame/clip một lần → tag; xếp clip AI mới vào thư mục loài | `tag_source.py`, `organize.py` | `.work/library/` |
| `scan-source` | Cập nhật index sau khi thêm/đổi/xoá file | `scan_source.py` | `.work/library/` |
| `process-ai-video` | Làm clip AI trông như quay thật, cắt character sheet đầu clip | `process_ai_video.py` | Ghi đè clip trong `D:\AI_video` |
| `hide-logo` | Xoá logo bằng clone-patch → `_nologo`, relink; ghi đè gốc khi xong video | `hide_logo.py` | `D:\AI_video\_nologo`, Resolve |
| `colorist` | Kiến thức màu + `grade.py`: nhóm Day/Golden/Dusk (LUT AMZ) + CDL từng clip | `grade.py` | Grade trong Resolve |
| `audio-expert` | Bản đồ âm thanh, chọn nhạc/SFX/âm tự nhiên, đặt A5-A9, rollback | `index.py`, `plan.py`, `execute.py` | A5-A9 |
| `intro-music-visualization` | Intro cắt theo nhạc trên timeline Open | `music_pick/map.py`, `pool.py`, `storyboard.py`, `build.py` | Timeline Open, bin "7. Open" |
| `edit-craft` | Kiến thức dựng: nhịp, điểm cắt, J/L cut, xuất YouTube | — | — |
| `resolve-api` | Lưu ý khi viết script cho Resolve | — | — |
| `memory-find` / `memory-save` | Tìm / lưu memory dự án | `memory_gateway.py` | `.work/knowledge/` |

Track timeline Edit: A1 tiếng clip AI (-12 dB) · A2 narrator · A3/A4 nền ambience (crossfade) · A5 lớp môi trường ·
A6 âm thanh tự nhiên · A7 nhạc · A8/A9 SFX.

## 8. An toàn

- **CLAUDE.md** (10 luật): hỏi "yes" trước mọi việc phá huỷ, chỉ đổi đúng thứ được nói, Z: chỉ đọc, không tự xoá file,
  không đụng `Master` và `_pushed`, kiểm tra môi trường trước mỗi việc (preflight), việc bị từ chối không thử lại.
- **`.claude/settings.json`**: Claude Code luôn hỏi trước `place.py`, `--replace`, `grade.py apply`, `reframe --apply`,
  xoá clip/timeline; cấm gửi phím tắt (SendKeys).
- **Backup**: `Edit_bak_<loại>_<giờ>` trước place / reframe / grade / vo-sync. Khôi phục = mở lại backup (hỏi trước).

## 9. Nhanh và rẻ: vì sao

| Kỹ thuật | Tiết kiệm |
|---|---|
| Tag mỗi clip **một lần**, dựng chỉ đọc tag | Không tốn token xem video khi dựng |
| Script in **tóm tắt**, Claude không mở plan.json, audio, index | Token mỗi bước nhỏ |
| Skill và `references/` chỉ nạp khi dùng; mô tả skill ngắn | Token mọi lượt thấp |
| Cache: Whisper, YOLO (`yolo.json`), vector caption, vector memory | Lần chạy sau nhanh |
| Plan: lọc rẻ trước, tính toán đắt sau | Plan ~5 s cho ~760 shot |
| Preflight 1 lệnh, không thử lại việc bị chặn | Không mất lượt vô ích |

## 10. Bảo trì

```powershell
# Mọi script có selftest (không cần Resolve):
.venv\Scripts\python.exe .claude\skills\doc-edit\scripts\plan.py --selftest
.venv\Scripts\python.exe -m tests.test_pipeline
.venv\Scripts\python.exe .work\tools\memory_gateway.py selftest
```
- Thêm footage → `/scan-source` → `/tag-source`. Đổi tên/chuyển file ngoài pipeline làm clip "offline" trong project cũ.
- Đổi model ngữ nghĩa → đo lại `SEM_LO/SEM_HI` (plan.py) và `MAX_DIST` (memory_gateway.py).

## Từ điển

| Từ | Nghĩa |
|---|---|
| slot | Một shot trên timeline (thời điểm + độ dài) |
| spec | File Claude viết: shot cần cho từng câu narration |
| THIẾU | Không có clip phù hợp → marker đỏ, cần tạo clip AI |
| WEAK | Có clip nhưng chưa khớp tốt → vàng, nên xem |
| shot phụ (side shot) | Cảnh không có nhân vật chính (phong cảnh, chim...), tối đa 30% |
| ledger | Danh sách clip đã dùng, để video sau không lặp |
| handoff | Ghi chú trạng thái hiện tại để phiên sau làm tiếp |
