# Runtime contracts and recovery

| Phase | Inputs | Output / stopping point |
|---|---|---|
| Author | Original source, requested duration | Four validated MD files → WAITING_FOR_VOICE |
| Voice/conform | audios/mp3/1…N.mp3 | Measured duration and consistent four files |
| Voice/place + plan | Conformed source, correct clean Resolve project | A2/SRT, frozen manifest + prompts → WAITING_FOR_SHOTS |
| Ingest/QC | shots/1…M.mp4, issued manifest | Technical pass, evidence-based visual approval |
| Hook + assemble | Approved clips, five teaser roles | V1/A1 + unchanged A2 → WAITING_FOR_REVIEW |
| Done | User's review approval, live Edit | RENDERING → verified output; optional exact approved upload |

The timeline plan is the source of placement, and the live timeline is the truth after the user edits. Source JSON and receipts are stored per full video path to avoid same-name collisions across channels. Global Resolve lock serializes writers across this checkout. Do not run two different workspace copies as simultaneous writers against one Resolve instance.

`voice` and `assemble` are resumable additive commands. Exact existing path/range/source-in items are retained; any conflicting item aborts before a new clip is written. Every append is written to a JSON journal immediately, and actual frames must match. A backup exists before nonempty changes. A failed command can leave a partial additive result: read journal and backup; do not clear or automatically restore. If a source-end convention mismatch occurs, correct configuration against installed Resolve API and let the user choose how to recover the partial item.

Issued prompt IDs cannot be redefined. Re-running `prompts` with the same plan is safe; a changed plan is rejected. New media hashes reset the corresponding visual approval. Do not edit the manifest or hashes to make mismatches pass.

One project `vid_DDMMYY_N` holds one video per channel. The adapter derives `Chann_N` from the video folder (`D:\Chann_N_*\vid_DDMMYY_N`), uses bins under `Chann_N/` and the `Edit` whose timeline clip sits in `Chann_N/4. Timeline` (several channels' timelines share the name `Edit`). Two Edits in one channel's bin, or more than three audio tracks, are refused. Folders outside a `Chann_N_*` directory use the legacy root-level bins. It deliberately does not automatically migrate an in-use 1h Resolve project. Start a separate project for this workflow.

SRT append support varies by Resolve version. Always create and import it under `3. Graphics/sub-title`; if appending fails/partially works, report manual placement. Do not destroy an existing subtitle track to retry. Subtitle burn-in is determined by the named render preset; configure it once to avoid unintended Vietnamese subtitles in the public render.

YouTube metadata file shape:

```json
{
  "title": "Approved English title",
  "description": "Approved description, including the AI dramatization disclosure.",
  "tags": ["wildlife", "mountains"],
  "approved_request_hash": "copy the exact preview hash only after the user's approval"
}
```

Call `youtube-upload <video> --channel UC...` for the preview, optionally with `--publish-at 2026-11-03T18:00:00+07:00`. Scheduling is private until publication and requires a future timezone-aware timestamp. Private-only restrictions of unaudited YouTube API projects can still apply; successful upload is not proof the scheduled public release is permitted. Receipts block duplicates and preserve an UNKNOWN outcome for reconciliation in Studio.
