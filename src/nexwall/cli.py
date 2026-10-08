"""Command-line interface: ``nexwall --help``."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, List, Optional

from . import __version__
from .client import REGISTER_URL, NexWallClient, NexWallError, RateLimitError

SORTS = ["newest", "oldest", "popular", "random"]


def _print_wallpapers(items: List[dict]) -> None:
    for w in items:
        category = (w.get("category") or {}).get("name", "")
        print(f"{w['id']:>8}  {w.get('resolution') or '':<11}  {category:<20}  {w['image_url']}")


def _maybe_download(client: NexWallClient, wallpaper: dict, path: Optional[str]) -> None:
    if path:
        saved = client.download(wallpaper, path)
        print(f"Saved {saved}", file=sys.stderr)


def _run(args: argparse.Namespace) -> Any:
    client = NexWallClient(api_key=args.api_key)

    if args.command == "demo":
        page = client.demo(per_page=args.per_page, category_id=args.category, search=args.search, sort=args.sort)
        if args.json:
            return page
        _print_wallpapers(page["data"])
        print(f"\nKeyless demo. Get a free API key for more: {REGISTER_URL}", file=sys.stderr)
        return None

    if args.command == "categories":
        categories = client.categories()
        if args.json:
            return categories
        for c in categories:
            premium = "  (premium)" if c.get("is_premium") else ""
            print(f"{c['id']:>5}  {c['name']:<24} {c.get('wallpaper_count', 0):>6} wallpapers{premium}")

    elif args.command == "list":
        page = client.wallpapers(
            page=args.page,
            per_page=args.per_page,
            category_id=args.category,
            search=args.search,
            sort=args.sort,
            type=args.type,
        )
        if args.json:
            return page
        _print_wallpapers(page["data"])
        print(f"\nPage {page.get('current_page')} of {page.get('last_page')} ({page.get('total')} total)")

    elif args.command == "random":
        wallpaper = client.random(category_id=args.category, search=args.search)
        if args.json:
            _maybe_download(client, wallpaper, args.download)
            return wallpaper
        _print_wallpapers([wallpaper])
        _maybe_download(client, wallpaper, args.download)

    elif args.command == "get":
        wallpaper = client.wallpaper(args.id)
        if args.json:
            _maybe_download(client, wallpaper, args.download)
            return wallpaper
        _print_wallpapers([wallpaper])
        _maybe_download(client, wallpaper, args.download)

    if client.remaining_today is not None and not args.json:
        print(f"[{client.remaining_today} API requests left today, plan: {client.plan}]", file=sys.stderr)
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nexwall",
        description="NexWall free wallpaper API from the command line. "
        f"Try `nexwall demo` without a key, or set NEXWALL_API_KEY (free key: {REGISTER_URL}).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Options accepted by every subcommand, e.g. `nexwall categories --json`.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--api-key", help="API key (default: NEXWALL_API_KEY env variable)")
    common.add_argument("--json", action="store_true", help="print raw JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    p_demo = sub.add_parser("demo", parents=[common], help="try up to 10 free wallpapers without an API key")
    p_demo.add_argument("--category", type=int, help="category id")
    p_demo.add_argument("--search", help="tag search, 2-100 characters")
    p_demo.add_argument("--sort", choices=["newest", "popular", "random"], default="newest")
    p_demo.add_argument("--per-page", type=int, default=10, help="1-10")

    sub.add_parser("categories", parents=[common], help="list categories available on your plan")

    p_list = sub.add_parser("list", parents=[common], help="list wallpapers (one page)")
    p_list.add_argument("--category", type=int, help="category id")
    p_list.add_argument("--search", help="tag search, 2-100 characters")
    p_list.add_argument("--sort", choices=SORTS, default="newest")
    p_list.add_argument("--type", choices=["image", "live"], help="live requires the Ultra plan")
    p_list.add_argument("--page", type=int, default=1)
    p_list.add_argument("--per-page", type=int, default=20, help="1-100")

    p_random = sub.add_parser("random", parents=[common], help="pick one random wallpaper")
    p_random.add_argument("--category", type=int, help="category id")
    p_random.add_argument("--search", help="tag search, 2-100 characters")
    p_random.add_argument("--download", metavar="PATH", help="save the image to a file or directory")

    p_get = sub.add_parser("get", parents=[common], help="show one wallpaper by id")
    p_get.add_argument("id", type=int)
    p_get.add_argument("--download", metavar="PATH", help="save the image to a file or directory")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = _run(args)
    except RateLimitError as e:
        wait = f" Try again in {e.retry_after} seconds." if e.retry_after else ""
        print(f"Rate limit reached: {e.message.rstrip('.')}.{wait}", file=sys.stderr)
        return 2
    except NexWallError as e:
        print(f"Error {e.status}: {e.message}", file=sys.stderr)
        return 1
    except OSError as e:  # network errors (requests exceptions subclass OSError) and file errors
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
