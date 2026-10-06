#!/usr/bin/env python3
"""Daily desktop wallpaper changer using the NexWall free wallpaper API.

Downloads one random wallpaper and sets it as the desktop background on
Windows, macOS or Linux (GNOME, KDE Plasma, XFCE, or any WM with feh).
One run uses one API request, so a daily schedule fits easily in the free
plan (100 requests/day).

Usage:
    export NEXWALL_API_KEY=your_key          # Windows: set NEXWALL_API_KEY=your_key
    python examples/daily_wallpaper.py                 # any category
    python examples/daily_wallpaper.py --category 5    # one category
    python examples/daily_wallpaper.py --search mountains

Schedule it once a day with Task Scheduler, cron or launchd (see README).
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from nexwall import NexWallClient, NexWallError, RateLimitError

DEFAULT_DIR = Path.home() / "Pictures" / "NexWall"


def set_wallpaper(path: Path) -> None:
    """Set ``path`` as the desktop wallpaper on the current OS."""
    path = path.resolve()
    system = platform.system()

    if system == "Windows":
        import ctypes

        SPI_SETDESKWALLPAPER = 20
        SPIF_UPDATEINIFILE_SENDCHANGE = 0x01 | 0x02
        if not ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, str(path), SPIF_UPDATEINIFILE_SENDCHANGE
        ):
            raise OSError("SystemParametersInfoW failed")
        return

    if system == "Darwin":
        script = f'tell application "System Events" to tell every desktop to set picture to POSIX file "{path}"'
        subprocess.run(["osascript", "-e", script], check=True)
        return

    # Linux / BSD: try the common desktop environments in order.
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    uri = path.as_uri()

    if "kde" in desktop and shutil.which("plasma-apply-wallpaperimage"):
        subprocess.run(["plasma-apply-wallpaperimage", str(path)], check=True)
        return
    if "xfce" in desktop and shutil.which("xfconf-query"):
        props = subprocess.run(
            ["xfconf-query", "-c", "xfce4-desktop", "-l"], capture_output=True, text=True, check=True
        ).stdout.split()
        for prop in (p for p in props if p.endswith("/last-image")):
            subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p", prop, "-s", str(path)], check=True)
        return
    if shutil.which("gsettings"):  # GNOME, Cinnamon, Budgie, Unity
        schema = "org.cinnamon.desktop.background" if "cinnamon" in desktop else "org.gnome.desktop.background"
        subprocess.run(["gsettings", "set", schema, "picture-uri", uri], check=True)
        # GNOME 42+ uses a separate key for dark mode; ignore if it doesn't exist.
        subprocess.run(["gsettings", "set", schema, "picture-uri-dark", uri], check=False, capture_output=True)
        return
    if shutil.which("feh"):
        subprocess.run(["feh", "--bg-fill", str(path)], check=True)
        return

    raise OSError(f"Don't know how to set the wallpaper on this desktop ({desktop or 'unknown'}).")


def cleanup(directory: Path, keep: int) -> None:
    """Keep only the newest ``keep`` downloaded wallpapers."""
    files = sorted(directory.glob("nexwall-*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[keep:]:
        old.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Set a random NexWall wallpaper as your desktop background.")
    parser.add_argument("--category", type=int, help="category id (see `nexwall categories`)")
    parser.add_argument("--search", help="tag search, 2-100 characters")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help=f"download folder (default: {DEFAULT_DIR})")
    parser.add_argument("--keep", type=int, default=7, help="how many old wallpapers to keep (default: 7)")
    args = parser.parse_args()

    try:
        client = NexWallClient()
        wallpaper = client.random(category_id=args.category, search=args.search)
        args.dir.mkdir(parents=True, exist_ok=True)
        path = client.download(wallpaper, args.dir)
        set_wallpaper(path)
        cleanup(args.dir, max(args.keep, 1))
    except RateLimitError as e:
        wait = f" Retry in {e.retry_after}s." if e.retry_after else ""
        print(f"Quota exceeded, keeping the current wallpaper.{wait}", file=sys.stderr)
        return 2
    except (NexWallError, OSError, subprocess.CalledProcessError) as e:
        print(f"Failed: {e}", file=sys.stderr)
        return 1

    print(f"Wallpaper set: {path} (id {wallpaper['id']}, {client.remaining_today} requests left today)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
