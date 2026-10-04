"""dvr - DaVinci Resolve co-worker CLI.

  dvr doctor
  dvr info
  dvr frames --at 01:10 02:05 [--stats]
  dvr prefetch
  dvr vo-sync run     AUDIO TIMESTAMPS [--dry-run] [--on-overlap push|trim|abort] [--markers] [--force-clear] [--no-backup]
  dvr vo-sync analyze AUDIO TIMESTAMPS
  dvr vo-sync apply   [PLAN] [...]
  dvr vo-sync verify  [PLAN]

Exit codes: 0 ok | 1 error | 2 bad input | 3 overlap (abort) | 4 Resolve not reachable / project issue
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from . import __version__
from .config import POINTER, load_config, models_dir, work_root

EXIT_OK, EXIT_ERR, EXIT_INPUT, EXIT_OVERLAP, EXIT_RESOLVE = 0, 1, 2, 3, 4


def log(msg=""):
    print(msg, flush=True)


def elog(msg=""):
    print(msg, file=sys.stderr, flush=True)


# ----------------------------------------------------------------- helpers
def _connect(cfg):
    from .resolve_conn import connect
    return connect(cfg)


def _load_plan(path: str | None) -> tuple[dict, Path]:
    if not path:
        if not POINTER.exists():
            raise FileNotFoundError("No plan given and no previous analysis found. Run `vo-sync analyze` first.")
        path = json.loads(POINTER.read_text(encoding="utf-8"))["plan"]
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")), p


def _apply_and_report(plan, plan_path, cfg, args):
    from .report import summary, write_report
    from .resolve_ops import apply_plan
    resolve = _connect(cfg)
    result = apply_plan(resolve, plan, cfg, log=elog, dry_run=args.dry_run,
                        force_clear=args.force_clear, on_overlap=args.on_overlap,
                        markers=True if args.markers else None,
                        backup=False if args.no_backup else None)
    rp = write_report(plan_path.parent / ("report_dryrun.md" if args.dry_run else "report.md"), plan, result)
    log(summary(plan, result, rp))
    return EXIT_OK


# ----------------------------------------------------------------- commands
def cmd_doctor(args, cfg):
    ok = True

    def line(status, msg):
        log(f"[{status}] {msg}")

    v = sys.version_info
    line("OK" if v >= (3, 11) else "WARN", f"Python {v.major}.{v.minor}.{v.micro} ({sys.executable})")
    for mod in ("numpy", "faster_whisper", "PIL"):
        try:
            m = __import__(mod)
            line("OK", f"{mod} {getattr(m, '__version__', '')}")
        except ImportError:
            ok = False
            line("FAIL", f"{mod} missing -> run setup.ps1")
    md = models_dir(cfg)
    has_model = any(md.rglob("model.bin"))
    line("OK" if has_model else "WARN",
         f"Whisper model '{cfg['whisper']['model']}' " + ("cached" if has_model else "not downloaded yet (run: dvr prefetch)"))
    try:
        from .resolve_ops import project_info
        resolve = _connect(cfg)
        info = project_info(resolve, cfg)
        line("OK", f"Resolve {info.get('resolve_version', '')} | project '{info['project']}'")
        tl_name = cfg["resolve"]["timeline_name"]
        if tl_name in info["timelines"]:
            t = info["timeline"]
            line("OK", f"timeline '{tl_name}' {t['fps']:g} fps {t['resolution']} | audio tracks: {len(t['tracks']['audio'])}")
        else:
            ok = False
            line("FAIL", f"timeline '{tl_name}' not found. Timelines: {', '.join(info['timelines'])}")
        line("OK" if info.get("audio_bin_exists") else "INFO",
             f"bin '{cfg['resolve']['audio_bin']}' " + ("exists" if info.get("audio_bin_exists") else "will be created"))
    except Exception as e:  # noqa: BLE001
        ok = False
        line("FAIL", f"Resolve: {e}")
    return EXIT_OK if ok else EXIT_RESOLVE


def cmd_info(args, cfg):
    from .resolve_ops import project_info
    log(json.dumps(project_info(_connect(cfg), cfg), ensure_ascii=False, indent=1))
    return EXIT_OK


def cmd_frames(args, cfg):
    from .resolve_ops import export_frames
    out = Path(args.out) if args.out else work_root(cfg) / "stills" / time.strftime("%Y%m%d_%H%M%S")
    res = export_frames(_connect(cfg), cfg, args.at, out)
    if args.stats:
        from .stills import still_stats
        for r in res:
            if r["ok"]:
                r["stats"] = still_stats(r["path"])
    log(json.dumps(res, ensure_ascii=False, indent=1))
    return EXIT_OK if all(r["ok"] for r in res) else EXIT_ERR


def cmd_prefetch(args, cfg):
    from .transcribe import load_model
    log(f"downloading/loading Whisper model '{cfg['whisper']['model']}' into {models_dir(cfg)} ...")
    load_model(cfg)
    log("model ready")
    return EXIT_OK


def cmd_analyze(args, cfg):
    from .report import summary, write_report
    from .vosync import analyze, write_pointer
    plan, plan_path = analyze(args.audio, args.timestamps, cfg, log=elog, transcript_json=args.transcript)
    write_pointer(plan_path, {"on_overlap": args.on_overlap, "markers": args.markers,
                              "force_clear": args.force_clear, "no_backup": args.no_backup}, args.config)
    rp = write_report(plan_path.parent / "analysis.md", plan, None)
    log(summary(plan, None, rp))
    log(f"plan: {plan_path}")
    return EXIT_OK


def cmd_apply(args, cfg):
    plan, plan_path = _load_plan(getattr(args, "plan", None))
    return _apply_and_report(plan, plan_path, cfg, args)


def cmd_run(args, cfg):
    from .resolve_conn import ResolveConnectionError
    from .vosync import analyze, write_pointer
    # Fail fast if Resolve is not reachable, before spending time on transcription.
    try:
        _connect(cfg)
    except ResolveConnectionError as e:
        elog(f"warning: {e}\n-> analysing anyway; apply later with `vo-sync apply` or the in-app script.")
    plan, plan_path = analyze(args.audio, args.timestamps, cfg, log=elog, transcript_json=args.transcript)
    write_pointer(plan_path, {"on_overlap": args.on_overlap, "markers": args.markers,
                              "force_clear": args.force_clear, "no_backup": args.no_backup}, args.config)
    return _apply_and_report(plan, plan_path, cfg, args)


def cmd_verify(args, cfg):
    from .resolve_ops import verify_track
    plan, _ = _load_plan(args.plan)
    log(json.dumps(verify_track(_connect(cfg), plan, cfg), indent=1))
    return EXIT_OK


# ----------------------------------------------------------------- parser
def build_parser():
    p = argparse.ArgumentParser(prog="dvr", description="DaVinci Resolve co-worker tools")
    p.add_argument("--config", help="path to config.toml (default: workspace config.toml)")
    p.add_argument("--version", action="version", version=f"dvr {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check Python deps, Whisper model and the Resolve connection").set_defaults(fn=cmd_doctor)
    sub.add_parser("info", help="project / timeline / track summary as JSON").set_defaults(fn=cmd_info)
    sub.add_parser("prefetch", help="download the Whisper model now").set_defaults(fn=cmd_prefetch)
    f = sub.add_parser("frames", help="export graded stills at timeline positions")
    f.add_argument("--at", nargs="+", required=True, help="mm:ss | hh:mm:ss | hh:mm:ss:ff (absolute TC)")
    f.add_argument("--out", help="output folder")
    f.add_argument("--stats", action="store_true", help="add luma/saturation/colour-cast numbers")
    f.set_defaults(fn=cmd_frames)

    vo = sub.add_parser("vo-sync", help="sync narration to a [mm:ss] timestamp file on the VO track")
    vsub = vo.add_subparsers(dest="vo_cmd", required=True)

    def common(sp, with_inputs):
        if with_inputs:
            sp.add_argument("audio")
            sp.add_argument("timestamps")
            sp.add_argument("--transcript", help="use an existing transcript JSON instead of Whisper")
        sp.add_argument("--on-overlap", choices=["push", "trim", "abort"], default=None,
                        help="when a line runs into the next timestamp (default from config: push)")
        sp.add_argument("--markers", action="store_true", help="add a timeline marker with the text at every onset")
        sp.add_argument("--force-clear", action="store_true", help="replace ANY clip already on the VO track")
        sp.add_argument("--no-backup", action="store_true", help="skip the backup copy of the timeline")
        sp.add_argument("--dry-run", action="store_true", help="compute and report, change nothing")

    r = vsub.add_parser("run", help="analyze + apply in one go")
    common(r, True)
    r.set_defaults(fn=cmd_run)
    a = vsub.add_parser("analyze", help="transcribe + match + build plan.json (Resolve not needed)")
    common(a, True)
    a.set_defaults(fn=cmd_analyze)
    ap = vsub.add_parser("apply", help="apply a plan.json (default: last analyzed)")
    ap.add_argument("plan", nargs="?")
    common(ap, False)
    ap.set_defaults(fn=cmd_apply)
    v = vsub.add_parser("verify", help="compare the VO track with the plan")
    v.add_argument("plan", nargs="?")
    v.set_defaults(fn=cmd_verify)
    return p


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    cfg = load_config(args.config)
    from .align import AlignError
    from .resolve_conn import ResolveConnectionError
    from .resolve_ops import OpsError, OverlapError
    from .timestamps import TimestampError
    try:
        return args.fn(args, cfg)
    except OverlapError as e:
        elog(f"ERROR (overlap): {e}\n-> shorten/move those timestamps, or re-run with --on-overlap push|trim")
        return EXIT_OVERLAP
    except (TimestampError, FileNotFoundError, AlignError, ValueError) as e:
        elog(f"ERROR (input): {e}")
        return EXIT_INPUT
    except (ResolveConnectionError, OpsError) as e:
        elog(f"ERROR (resolve): {e}")
        return EXIT_RESOLVE
    except KeyboardInterrupt:
        return EXIT_ERR
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        elog(f"ERROR: {e}")
        return EXIT_ERR


if __name__ == "__main__":
    raise SystemExit(main())
