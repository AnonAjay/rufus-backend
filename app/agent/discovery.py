"""
Application Discovery and Normalization Engine for Windows.
Scans Windows Registry (App Paths & Protocols), Dual Start Menus, and System PATH.
Matches against the Integration Catalog and caches discovered applications to JSON.
"""
import os
import json
import logging
import shutil
import subprocess
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.agent.catalog import INTEGRATIONS_CATALOG, IntegrationDefinition

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CACHE_PATH = BASE_DIR / "data" / "installed_apps.json"


def _scan_uri_schemes(schemes: list[str]) -> dict[str, bool]:
    """Check if specific URI protocol schemes are registered in Windows."""
    import winreg
    results = {}
    for scheme in schemes:
        found = False
        for root in (winreg.HKEY_CLASSES_ROOT, winreg.HKEY_CURRENT_USER):
            sub_path = scheme if root == winreg.HKEY_CLASSES_ROOT else f"Software\\Classes\\{scheme}"
            try:
                with winreg.OpenKey(root, sub_path):
                    found = True
                    break
            except Exception:
                pass
        results[scheme] = found
    return results


def _scan_app_paths(exe_names: list[str]) -> dict[str, str | None]:
    """Check Windows Registry App Paths for registered executables."""
    import winreg
    results: dict[str, str | None] = {}
    for exe in exe_names:
        found_path = None
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            key_path = f"Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\{exe}"
            try:
                with winreg.OpenKey(root, key_path) as key:
                    val, _ = winreg.QueryValueEx(key, "")
                    if val and Path(str(val)).exists():
                        found_path = str(val)
                        break
            except Exception:
                pass
        results[exe] = found_path
    return results


def _scan_start_menu_shortcuts() -> set[str]:
    """Scan both User and System Start Menu directories for shortcut (.lnk) names."""
    shortcut_names = set()
    dirs = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        Path(os.environ.get("ALLUSERSPROFILE", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for d in dirs:
        if d.exists():
            try:
                for f in d.rglob("*.lnk"):
                    shortcut_names.add(f.stem.lower())
            except Exception as exc:
                logger.warning("Error scanning start menu directory %s: %s", d, exc)
    return shortcut_names


def scan_system_applications() -> list[dict[str, Any]]:
    """Perform hybrid scan across Windows and match against the Integration Catalog."""
    start_shortcuts = _scan_start_menu_shortcuts()

    # Collect unique URI schemes and App Path names to scan
    all_schemes = []
    all_app_paths = []
    for entry in INTEGRATIONS_CATALOG:
        det = entry.get("detection", {})
        all_schemes.extend(det.get("uri_schemes", []))
        all_app_paths.extend(det.get("app_path_names", []))

    detected_schemes = _scan_uri_schemes(list(set(all_schemes)))
    detected_app_paths = _scan_app_paths(list(set(all_app_paths)))

    discovered: list[dict[str, Any]] = []

    for entry in INTEGRATIONS_CATALOG:
        det = entry.get("detection", {})
        is_installed = False
        resolved_launch_type = None
        resolved_target = None

        # 1. Check URI schemes (highest fidelity for Store/packaged apps like WhatsApp)
        for scheme in det.get("uri_schemes", []):
            if detected_schemes.get(scheme):
                is_installed = True
                resolved_launch_type = "uri"
                resolved_target = f"{scheme}:"
                break

        # 2. Check App Paths in registry (Chrome, Brave, Docker)
        if not is_installed:
            for exe in det.get("app_path_names", []):
                p = detected_app_paths.get(exe)
                if p:
                    is_installed = True
                    resolved_launch_type = "path"
                    resolved_target = p
                    break

        # 3. Check System PATH via shutil.which
        if not is_installed:
            for exe in det.get("executable_names", []):
                which_p = shutil.which(exe)
                if which_p:
                    is_installed = True
                    resolved_launch_type = "command"
                    resolved_target = which_p
                    break

        # 4. Check Start Menu shortcuts
        if not is_installed:
            for sm_name in det.get("start_menu_names", []):
                if sm_name.lower() in start_shortcuts:
                    is_installed = True
                    resolved_launch_type = "uri" if entry.get("default_uri") else "command"
                    resolved_target = entry.get("default_uri") or entry.get("default_command") or sm_name
                    break

        # Fallback targets if marked installed
        if is_installed and not resolved_target:
            resolved_target = entry.get("default_uri") or entry.get("default_command") or entry["id"]
            resolved_launch_type = "uri" if entry.get("default_uri") else "command"

        discovered.append({
            "id": entry["id"],
            "display_name": entry["display_name"],
            "category": entry["category"],
            "type": entry["type"],
            "installed": is_installed,
            "capabilities": entry["capabilities"],
            "launch_type": resolved_launch_type,
            "launch_target": resolved_target,
            "description": entry["description"],
        })

    # Save to JSON cache
    save_discovered_cache(discovered)
    return discovered


def save_discovered_cache(apps: list[dict[str, Any]]) -> None:
    """Save detected apps list to JSON cache."""
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_scanned_at": datetime.now(timezone.utc).isoformat(),
            "total_catalog": len(apps),
            "installed_count": sum(1 for a in apps if a.get("installed")),
            "applications": apps,
        }
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as exc:
        logger.error("Failed to write installed apps cache: %s", exc)


def get_installed_apps(force_rescan: bool = False) -> list[dict[str, Any]]:
    """Retrieve installed apps from cache (<5ms), or trigger scan if missing."""
    if not force_rescan and CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("applications", [])
        except Exception as exc:
            logger.warning("Failed to read apps cache, performing fresh scan: %s", exc)

    return scan_system_applications()


def resolve_application(query: str) -> dict[str, Any] | None:
    """Match a user query string against discovered applications."""
    q = (query or "").strip().lower()
    if not q:
        return None

    apps = get_installed_apps()
    # 1. Exact ID or display name match
    for a in apps:
        if a["id"].lower() == q or a["display_name"].lower() == q:
            return a

    # 2. Substring or alias match
    for a in apps:
        if q in a["id"].lower() or q in a["display_name"].lower():
            return a

    return None


def launch_application(app_entry: dict[str, Any]) -> tuple[bool, str]:
    """Safely execute or open an application using its resolved launch signature."""
    launch_type = app_entry.get("launch_type")
    target = app_entry.get("launch_target")
    name = app_entry.get("display_name", "Application")

    if not target:
        return False, f"No launch target resolved for {name}."

    try:
        if launch_type == "uri":
            os.startfile(target)
            return True, f"Successfully launched {name} via protocol."
        elif launch_type in {"path", "command"}:
            subprocess.Popen([target], shell=False)
            return True, f"Successfully opened {name}."
        else:
            try:
                os.startfile(target)
                return True, f"Opened {name}."
            except Exception:
                subprocess.Popen([target], shell=False)
                return True, f"Launched {name}."
    except Exception as exc:
        logger.error("Failed to launch application %s (%s): %s", name, target, exc)
        return False, f"Failed to launch {name}: {exc}"
