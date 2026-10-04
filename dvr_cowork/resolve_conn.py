"""Connect to a running DaVinci Resolve from an external Python process.

Loads fusionscript directly with importlib, so it does not depend on the bundled
DaVinciResolveScript.py (older copies import the 'imp' module, removed in Python 3.12).
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys


class ResolveConnectionError(Exception):
    pass


HELP = """DaVinci Resolve is not reachable.
  1. Open DaVinci Resolve and load your project.
  2. Preferences > System > General > "External scripting using" = Local, then restart Resolve.
  3. Use 64-bit Python 3.11/3.12 (the .venv created by setup.ps1).
  4. Still failing? Use in-app mode: run install_inapp.ps1 once, then in Resolve
     Workspace > Scripts > Utility > DVR_VO_Sync_apply_last_plan  (applies the last analyzed plan)."""


def default_paths() -> tuple[str, str]:
    if sys.platform.startswith("win"):
        pd = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        api = os.path.join(pd, "Blackmagic Design", "DaVinci Resolve", "Support", "Developer", "Scripting")
        lib = os.path.join(pf, "Blackmagic Design", "DaVinci Resolve", "fusionscript.dll")
    elif sys.platform == "darwin":
        api = "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
        lib = "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so"
    else:
        api = "/opt/resolve/Developer/Scripting"
        lib = "/opt/resolve/libs/Fusion/fusionscript.so"
    return api, lib


def connect(cfg: dict | None = None):
    rc = (cfg or {}).get("resolve", {})
    api, lib = default_paths()
    api = rc.get("script_api") or os.environ.get("RESOLVE_SCRIPT_API") or api
    lib = rc.get("script_lib") or os.environ.get("RESOLVE_SCRIPT_LIB") or lib
    if not os.path.isfile(lib):
        raise ResolveConnectionError(
            f"fusionscript library not found: {lib}\n"
            "Is DaVinci Resolve installed? Otherwise set [resolve] script_lib in config.toml.")
    os.environ["RESOLVE_SCRIPT_API"] = api
    os.environ["RESOLVE_SCRIPT_LIB"] = lib
    if sys.platform.startswith("win") and hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(os.path.dirname(lib))
        except OSError:
            pass
    try:
        loader = importlib.machinery.ExtensionFileLoader("fusionscript", lib)
        spec = importlib.util.spec_from_file_location("fusionscript", lib, loader=loader)
        mod = importlib.util.module_from_spec(spec)
        loader.exec_module(mod)
    except Exception as e:  # noqa: BLE001
        raise ResolveConnectionError(f"Could not load {lib}: {e}\n{HELP}") from e
    resolve = mod.scriptapp("Resolve")
    if resolve is None:
        raise ResolveConnectionError(HELP)
    return resolve
