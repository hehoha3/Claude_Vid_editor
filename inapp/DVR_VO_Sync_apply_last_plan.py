"""Run from DaVinci Resolve: Workspace > Scripts > Utility > DVR_VO_Sync_apply_last_plan

Applies the plan produced by the last `dvr vo-sync analyze` (or `run`) on this PC.
Use this when external scripting is not available. Needs only the Python standard library.
"""
import json
import os
import sys
import traceback

POINTER = os.path.join(os.path.expanduser("~"), ".dvr_cowork", "last_plan.json")


def _get_resolve():
    g = globals()
    if g.get("resolve"):
        return g["resolve"]
    if "bmd" in g:
        return g["bmd"].scriptapp("Resolve")
    import DaVinciResolveScript as dvr  # noqa: N813
    return dvr.scriptapp("Resolve")


def run():
    if not os.path.exists(POINTER):
        print("[DVR VO Sync] No analysed plan found. Run `dvr vo-sync analyze AUDIO TIMESTAMPS` first.")
        return
    with open(POINTER, encoding="utf-8") as f:
        ptr = json.load(f)
    sys.path.insert(0, ptr["workspace"])
    from dvr_cowork.config import load_config
    from dvr_cowork.report import summary, write_report
    from dvr_cowork.resolve_ops import apply_plan

    with open(ptr["plan"], encoding="utf-8") as f:
        plan = json.load(f)
    cfg = load_config(ptr.get("config"))
    opt = ptr.get("options", {})
    result = apply_plan(_get_resolve(), plan, cfg, log=print,
                        force_clear=bool(opt.get("force_clear")),
                        on_overlap=opt.get("on_overlap"),
                        markers=True if opt.get("markers") else None,
                        backup=False if opt.get("no_backup") else None)
    rp = write_report(os.path.join(os.path.dirname(ptr["plan"]), "report.md"), plan, result)
    print(summary(plan, result, rp))


try:
    run()
except Exception as e:  # noqa: BLE001
    traceback.print_exc()
    print(f"[DVR VO Sync] ERROR: {e}")
