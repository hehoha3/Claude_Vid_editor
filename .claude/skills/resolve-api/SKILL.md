---
name: resolve-api
description: Use before operating or modifying the new workspace's narrow Resolve adapter, checking project/timeline/media-pool identity, linked V1/A1 audio, A2 narrator placement, SRT import, frame conventions, backups or render jobs.
---

# Resolve adapter

Use `dvr_cowork.resolve_ops`, not ad-hoc keyboard automation. Consult the installed official API reference at `%PROGRAMDATA%\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting\README.txt` before relying on a version-sensitive method.

- Open Resolve with External scripting using = Local and the intended project. One video per channel per project: `Chann_N/` bins and the `Edit` located in `Chann_N/4. Timeline` (identify by bin, since every channel's timeline is named `Edit`); never guess between duplicate Edits in one channel bin, never touch another channel's bin or timeline. This workspace does not require a DaVinci MCP server.
- Resolve record frames are absolute, relative plan frames begin at zero. Add GetStartFrame(); markers are relative. Use actual fractional fps, not rounded nominal fps, for elapsed-time placement.
- Import into the correct current bin and append into the correct current timeline. Restore prior timeline/bin afterward.
- Check every important setter result. Append video and source audio separately, verify both actual start/end/source-in, then SetClipsLinked. A1 is present after eight minutes too.
- Upstream source contains conflicting endFrame notes/tests. This workspace exposes `source_end=exclusive|inclusive`, defaults to the upstream Resolve 21.1 note (exclusive), and aborts on actual mismatch. Never claim the convention was tested on this user's live Resolve from a Linux mock test.
- Back up before writes; do not delete a failed partial item automatically. Describe the journal, backup, frame and recovery choice.
- No automatic track clearing, old-bin migration, grade pass, scaling/stretch, speed change, source rename or broader project cleanup.
- SRT ImportMedia/AppendToTimeline support varies. Verify actual subtitle items; otherwise report the SRT path and manual import requirement.
- Render starts asynchronously; report its job ID and inspect status. Probe/decode the completed output before marking it verified. Never silently reuse an earlier render after manual changes.
