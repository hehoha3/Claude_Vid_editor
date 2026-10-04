"""Human/Claude-readable reports. stdlib-only."""
from __future__ import annotations

from pathlib import Path

from .timecode import fmt_seconds, frames_to_tc

FLAG_HELP = {
    "low_confidence": "few script words recognised - listen to this line",
    "text_not_heard": "no script words recognised; position interpolated - CHECK",
    "no_pause": "no pause found before this line; cut placed mid-way - listen to the cut",
    "boundary_uncertain": "pause found far from Whisper's word times - listen to the cut",
    "very_short": "segment shorter than 0.2 s",
    "pushed": "line was longer than the gap; start moved later than its timestamp",
    "speech_cut": "end of the previous line was cut to fit (on_overlap=trim)",
    "tail_trimmed": "tail silence shortened to fit (harmless)",
    "head_trimmed": "head silence shortened to fit (harmless)",
    "start_clamped": "could not start before timeline start",
}
HARMLESS = {"tail_trimmed", "head_trimmed"}


def flagged(items):
    return [it for it in items if set(it["flags"]) - HARMLESS]


def summary(plan: dict, result: dict | None, report_path: Path | None) -> str:
    segs = plan["segments"]
    lines = [f"VO-SYNC  audio={Path(plan['audio']).name}  lines={len(segs)}  "
             f"audio_len={fmt_seconds(plan['stats']['duration'])}  model={plan.get('model')}"]
    if result:
        items = result["items"]
        fps = result["fps"]
        head = "DRY-RUN " if result.get("dry_run") else ""
        lines.append(f"{head}timeline='{result['timeline']}' fps={fps:g} track=A{result['track']}  "
                     f"placed={result.get('placed', 0)}/{len(items)}"
                     + (f"  backup='{result['backup']}'" if result.get("backup") else ""))
        if not result.get("dry_run"):
            in_dev = result.get("max_in_dev")
            lines.append(f"verify: max start deviation={result.get('max_start_dev', 0)}f"
                         + ("" if in_dev is None else f", max source-in deviation={in_dev}f"))
        groups: dict[str, list[str]] = {}
        for it in items:
            for f in it["flags"]:
                if f in HARMLESS:
                    continue
                extra = f"(+{it['shift_f'] / fps:.2f}s)" if f == "pushed" else ""
                groups.setdefault(f, []).append(f"#{it['i']}{extra}")
        if result.get("failed"):
            groups["FAILED_TO_PLACE"] = [f"#{i}" for i in result["failed"]]
        if groups:
            for f, ids in groups.items():
                shown = ", ".join(ids[:15]) + (f" ... (+{len(ids) - 15})" if len(ids) > 15 else "")
                lines.append(f"  {f}: {shown}")
        else:
            lines.append("  all lines clean")
    else:
        bad = [s for s in segs if s["flags"]]
        lines.append(f"analysis only: {len(bad)} line(s) flagged")
    if report_path:
        lines.append(f"report: {report_path}")
    return "\n".join(lines)


def write_report(path, plan: dict, result: dict | None) -> Path:
    path = Path(path)
    out = ["# VO sync report", "",
           f"- Audio: `{plan['audio']}`", f"- Timestamps: `{plan['timestamps']}`",
           f"- Whisper: {plan.get('model')}  | pause threshold {plan['stats']['threshold_db']} dB"
           f" | speech level {plan['stats']['speech_db']} dB", ""]
    if result:
        fps, start = result["fps"], result["tl_start"]
        out += [f"- Project / timeline: {result['project']} / {result['timeline']} @ {fps:g} fps, track A{result['track']}",
                f"- Placed {result.get('placed', 0)}/{len(result['items'])}"
                + (" (dry run)" if result.get("dry_run") else ""), ""]
        out += ["| # | stamp | speech in audio | len | item start (TC) | onset (TC) | conf | flags | text |",
                "|---|---|---|---|---|---|---|---|---|"]
        segs = {s["i"]: s for s in plan["segments"]}
        for it in result["items"]:
            s = segs[it["i"]]
            onset_rec = it["rec_f"] + round(it["speech_in_f"] - it["src_in_f"])
            txt = it["text"].replace("|", "/")
            out.append(
                f"| {it['i']} | {fmt_seconds(it['ts'])} | {fmt_seconds(s['onset'])}-{fmt_seconds(s['offset'])} "
                f"| {s['offset'] - s['onset']:.2f}s | {frames_to_tc(start + it['rec_f'], fps)} "
                f"| {frames_to_tc(start + onset_rec, fps)} | {it['conf']:.2f} | {' '.join(it['flags'])} "
                f"| {txt[:70]}{'...' if len(txt) > 70 else ''} |")
    else:
        out += ["| # | stamp | speech in audio | conf | flags | text |", "|---|---|---|---|---|---|"]
        for s in plan["segments"]:
            out.append(f"| {s['i']} | {fmt_seconds(s['ts'])} | {fmt_seconds(s['onset'])}-{fmt_seconds(s['offset'])} "
                       f"| {s['conf']:.2f} | {' '.join(s['flags'])} | {s['text'][:70]} |")
    out += ["", "## Flag meanings", ""] + [f"- **{k}**: {v}" for k, v in FLAG_HELP.items()]
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path
