#!/usr/bin/env python3
"""
Construct 3 Documentation PDF Updater

Downloads combined PDFs from construct-static.com CDN,
generates individual page PDFs via headless Chrome (Playwright),
and maintains the directory structure + READMEs.

Commands:
    check       Check CDN for updates (HEAD only, no downloads)
    download    Download combined PDFs from CDN
    generate    Generate individual page PDFs via headless Chrome
    update      Full update: download + generate
    discover    Re-discover CDN download URLs from construct.net

Options:
    --target T   Target: manual, addon-sdk, game-services, all (default: all)
    --force      Force re-download/regenerate even if unchanged
    --delay N    Delay between pages in ms (default: 800)
    --batch N    Max pages per target (0 = unlimited, default: 0)

Examples:
    python update_pdfs.py check
    python update_pdfs.py download --force
    python update_pdfs.py generate --target manual --batch 10
    python update_pdfs.py update
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# ─── Paths ───────────────────────────────────────────────────────────

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent
STATE_FILE = SCRIPTS_DIR / "state.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.construct.net"

# ─── Target Configuration ────────────────────────────────────────────

TARGETS = {
    "manual": {
        "name": "Construct 3 Manual",
        "base_path": "/en/make-games/manuals/construct-3",
        "output_dir": "Construct3-Manual",
        "combined_pdf": "construct3-Manual.pdf",
    },
    "addon-sdk": {
        "name": "Addon SDK",
        "base_path": "/en/make-games/manuals/addon-sdk",
        "output_dir": "Construct3-Addon-SDK",
        "combined_pdf": "construct3-Addon-SDK.pdf",
    },
    "game-services": {
        "name": "Game Services",
        "base_path": "/en/game-services/manuals/game-services",
        "output_dir": "Construct3-Game-Services",
        "combined_pdf": "construct3-Game-Services.pdf",
    },
}

# Default CDN URLs (v-prefix is a cache buster, any value works)
DEFAULT_CDN_URLS = {
    "manual": "https://construct-static.com/downloads/v1757/manuals/1/2/668/construct-3.pdf",
    "addon-sdk": "https://construct-static.com/downloads/v1757/manuals/2/2/73/construct-3.pdf",
    "game-services": "https://construct-static.com/downloads/v1757/manuals/7/6/31/game-services.pdf",
}

# Print CSS injected to hide nav/sidebar/footer for clean PDFs
PRINT_CSS = """
    nav, header, footer, .sidebar, .sidebarWrap, .headerWrap,
    .footerWrap, .breadcrumbs, .onThisPageWrap, .downloadManual,
    .manualSearchWrap, .manualNavWrap, .topHeaderWrap,
    .bottomFooterWrap, .shareWrap, #cookieConsent,
    .feedbackWrap, .pageNav, .relatedContent {
        display: none !important;
    }
    .manualContent {
        margin: 0 !important;
        padding: 20px !important;
        max-width: 100% !important;
        width: 100% !important;
    }
    body { background: white !important; }
    @page { margin: 0; }
"""

# ─── State Management ────────────────────────────────────────────────


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "last_updated": None,
        "construct_version": None,
        "cdn_urls": dict(DEFAULT_CDN_URLS),
        "cdn_last_modified": {},
        "targets": {},
    }


def save_state(state: dict) -> None:
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


# ─── HTTP Helpers ────────────────────────────────────────────────────


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    # Disable compression so HEAD returns Content-Length
    s.headers["Accept-Encoding"] = "identity"
    return s


# ─── Check Command ───────────────────────────────────────────────────


def cmd_check(state: dict, target_keys: list[str]) -> dict[str, dict]:
    """HEAD each CDN PDF, return dict of changed targets."""
    print("Checking CDN for updates...")
    session = make_session()
    changes: dict[str, dict] = {}

    for key in target_keys:
        url = state.get("cdn_urls", {}).get(key, DEFAULT_CDN_URLS.get(key))
        if not url:
            print(f"  {key}: no CDN URL configured, skipping")
            continue

        try:
            resp = session.head(url, allow_redirects=True, timeout=30)
        except requests.RequestException as e:
            print(f"  {key}: request failed ({e})")
            continue

        if resp.status_code == 404:
            print(f"  {key}: 404 — CDN URL may have changed, run 'discover' to update")
            continue
        if resp.status_code != 200:
            print(f"  {key}: HTTP {resp.status_code}")
            continue

        last_modified = resp.headers.get("Last-Modified", "")
        content_length = int(resp.headers.get("Content-Length", "0"))
        stored_lm = state.get("cdn_last_modified", {}).get(key)

        if stored_lm != last_modified:
            changes[key] = {
                "last_modified": last_modified,
                "content_length": content_length,
            }
            size_mb = content_length / 1024 / 1024
            status = "NEW" if stored_lm is None else "CHANGED"
            print(f"  {key}: {status} — {last_modified} ({size_mb:.1f} MB)")
        else:
            print(f"  {key}: unchanged")

    if changes:
        print(f"\n{len(changes)} target(s) have updates available.")
    else:
        print("\nAll targets are up to date.")

    return changes


# ─── Download Command ────────────────────────────────────────────────


def cmd_download(state: dict, target_keys: list[str], force: bool = False) -> None:
    """Download combined PDFs from CDN."""
    if not force:
        changes = cmd_check(state, target_keys)
        if not changes:
            print("Nothing to download.")
            return
        target_keys = [k for k in target_keys if k in changes]

    session = make_session()
    print("\nDownloading combined PDFs...")

    for key in target_keys:
        url = state.get("cdn_urls", {}).get(key, DEFAULT_CDN_URLS.get(key))
        if not url:
            continue

        target = TARGETS[key]
        output_path = REPO_ROOT / target["combined_pdf"]
        print(f"  {key}: downloading... ", end="", flush=True)

        try:
            resp = session.get(url, stream=True, timeout=300)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"FAILED ({e})")
            continue

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        size_mb = output_path.stat().st_size / 1024 / 1024
        last_modified = resp.headers.get("Last-Modified", "")
        print(f"{size_mb:.1f} MB")

        # Update state
        state.setdefault("cdn_last_modified", {})[key] = last_modified

    save_state(state)
    print("Done.")


# ─── Discover Command ────────────────────────────────────────────────


def cmd_discover(state: dict, target_keys: list[str]) -> None:
    """Navigate to construct.net and extract current CDN download URLs + version."""
    from playwright.sync_api import sync_playwright

    print("Discovering CDN URLs from construct.net...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for key in target_keys:
            target = TARGETS[key]
            url = BASE_URL + target["base_path"]
            print(f"  {key}: navigating to {url}")

            page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # Wait for Cloudflare challenge to pass
            try:
                page.wait_for_selector(".manualContent", timeout=30000)
            except Exception:
                print(f"    Could not load page (Cloudflare?), skipping")
                continue

            # Extract PDF download link
            cdn_url = page.evaluate("""() => {
                const link = document.querySelector('a[href*="construct-static.com/downloads"]');
                return link ? link.href : null;
            }""")

            if cdn_url:
                state.setdefault("cdn_urls", {})[key] = cdn_url
                print(f"    CDN URL: {cdn_url}")
            else:
                print(f"    No download link found on page")

            # Extract construct-version meta tag
            version = page.evaluate("""() => {
                const meta = document.querySelector('meta[name="construct-version"]');
                return meta ? meta.content : null;
            }""")
            if version:
                state["construct_version"] = version
                print(f"    construct-version: {version}")

        browser.close()

    save_state(state)
    print("Done.")


# ─── Generate Command ────────────────────────────────────────────────


def _discover_page_urls(page, target: dict) -> list[str]:
    """Extract all manual page URLs from sidebar navigation."""
    url = BASE_URL + target["base_path"]
    page.goto(url, wait_until="domcontentloaded", timeout=60000)

    try:
        page.wait_for_selector(".manualContent", timeout=30000)
    except Exception:
        # Retry once — Cloudflare sometimes needs a moment
        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".manualContent", timeout=30000)

    base_path = target["base_path"]
    urls: list[str] = page.evaluate(
        """(basePath) => {
            const links = document.querySelectorAll('nav a');
            const urlSet = new Set();
            links.forEach(a => {
                const href = a.href.split('#')[0].split('?')[0];
                if (href.includes(basePath)) urlSet.add(href);
            });
            return [...urlSet].sort();
        }""",
        base_path,
    )

    # Ensure index page is included
    index_url = BASE_URL + base_path
    if index_url not in urls:
        urls.insert(0, index_url)

    return urls


def _url_to_filepath(url: str, target: dict) -> Path:
    """Convert a manual page URL to local PDF file path."""
    base = BASE_URL + target["base_path"]
    rel_path = url.replace(base + "/", "").replace(base, "")
    if rel_path.startswith("/"):
        rel_path = rel_path[1:]
    if not rel_path:
        rel_path = "home"

    parts = rel_path.split("/")
    filename = parts[-1] + ".pdf"
    directory = "/".join(parts[:-1]) if len(parts) > 1 else ""

    output_dir = REPO_ROOT / target["output_dir"]
    if directory:
        return output_dir / directory / filename
    return output_dir / filename


def _generate_page_pdf(page, url: str, output_path: Path) -> bool:
    """Navigate to a page, inject print CSS, save as PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        page.goto(url, wait_until="networkidle", timeout=60000)
    except Exception:
        # Fallback: wait for content selector instead of full network idle
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector(".manualContent", timeout=15000)
        except Exception:
            return False

    # Inject CSS to produce clean print output
    page.add_style_tag(content=PRINT_CSS)

    # Wait briefly for styles to apply
    page.wait_for_timeout(300)

    page.pdf(
        path=str(output_path),
        format="A4",
        margin={"top": "20mm", "right": "15mm", "bottom": "20mm", "left": "15mm"},
        print_background=True,
    )
    return True


def _clean_output_dir(target: dict) -> None:
    """Remove all existing PDFs and empty subdirs in a target's output directory."""
    import shutil

    output_dir = REPO_ROOT / target["output_dir"]
    if not output_dir.exists():
        return

    # Delete everything except README.md
    for item in list(output_dir.iterdir()):
        if item.name == "README.md":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()

    print(f"  Cleaned {output_dir.name}/")


def cmd_generate(
    state: dict,
    target_keys: list[str],
    incremental: bool = False,
    delay: int = 800,
    batch: int = 0,
) -> None:
    """Generate individual page PDFs using headless Chrome.

    Default: full deploy — wipe output dir, regenerate everything.
    With --incremental: keep existing files, only generate missing ones.
    """
    from playwright.sync_api import sync_playwright

    print("Generating individual page PDFs...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        for key in target_keys:
            target = TARGETS[key]
            print(f"\n[{target['name']}] Discovering pages...")
            urls = _discover_page_urls(page, target)
            print(f"  Found {len(urls)} pages")

            # Default: wipe old files for a clean deploy
            if not incremental:
                _clean_output_dir(target)

            if batch:
                urls = urls[:batch]

            stats = {"success": 0, "skipped": 0, "failed": 0}

            for i, url in enumerate(urls, 1):
                output_path = _url_to_filepath(url, target)

                if incremental and output_path.exists():
                    stats["skipped"] += 1
                    continue

                slug = url.rstrip("/").split("/")[-1] or "home"
                print(f"  [{i}/{len(urls)}] {slug}... ", end="", flush=True)

                try:
                    ok = _generate_page_pdf(page, url, output_path)
                    if ok:
                        pages_hint = ""
                        try:
                            import fitz
                            doc = fitz.open(str(output_path))
                            pages_hint = f" ({doc.page_count}p)"
                            doc.close()
                        except ImportError:
                            pass
                        print(f"ok{pages_hint}")
                        stats["success"] += 1
                    else:
                        print("FAILED (content not found)")
                        stats["failed"] += 1
                except Exception as e:
                    print(f"ERROR ({e})")
                    stats["failed"] += 1

                if delay:
                    time.sleep(delay / 1000)

            # Update state
            state.setdefault("targets", {})[key] = {
                "total_pages": len(urls),
                "last_generated": datetime.now(timezone.utc).isoformat(),
            }

            print(
                f"  Done: {stats['success']} generated, "
                f"{stats['skipped']} skipped, {stats['failed']} failed"
            )

        browser.close()

    save_state(state)


# ─── README Generation ───────────────────────────────────────────────


def _collect_pdf_tree(root_dir: Path) -> dict:
    """Walk a directory and collect PDF files into a nested structure."""
    tree: dict = {}
    if not root_dir.exists():
        return tree

    for pdf in sorted(root_dir.rglob("*.pdf")):
        rel = pdf.relative_to(root_dir)
        # Use forward slashes for cross-platform compatibility
        parts = list(rel.as_posix().split("/"))

        # Place in tree
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = rel.as_posix()

    return tree


def _generate_target_readme(target_key: str) -> str:
    """Generate README.md content for a target directory."""
    target = TARGETS[target_key]
    output_dir = REPO_ROOT / target["output_dir"]
    tree = _collect_pdf_tree(output_dir)

    # Count total PDFs
    total = sum(1 for _ in output_dir.rglob("*.pdf")) if output_dir.exists() else 0

    lines = [
        f"# {target['name']} (PDF)",
        "",
        "This directory contains PDF documentation extracted from the official documentation.",
        "",
        "## Source",
        "",
        "All PDFs are generated from the official documentation:",
        "",
        f"> Source: [{target['name']}]({BASE_URL}{target['base_path']})",
        "",
        "---",
        "",
        f"## Files ({total} PDFs)",
        "",
    ]

    # Root-level PDFs
    root_pdfs = {k: v for k, v in tree.items() if isinstance(v, str)}
    subdirs = {k: v for k, v in tree.items() if isinstance(v, dict)}

    if root_pdfs:
        lines.append("### Root")
        lines.append("")
        lines.append("| File | Path |")
        lines.append("|------|------|")
        for name, rel_path in sorted(root_pdfs.items()):
            display = name.replace(".pdf", "")
            lines.append(f"| [{display}]({rel_path}) | `{rel_path}` |")
        lines.append("")

    # Subdirectories
    for dirname, contents in sorted(subdirs.items()):
        section_name = dirname.replace("-", " ").title()
        # Count files in this section (recursive)
        count = sum(1 for _ in (output_dir / dirname).rglob("*.pdf"))
        lines.append(f"### {section_name} ({count} files)")
        lines.append("")
        lines.append("| File | Path |")
        lines.append("|------|------|")

        # Flatten nested structure for table
        def flatten(node, prefix=""):
            items = []
            for k, v in sorted(node.items()):
                if isinstance(v, str):
                    items.append((k, v))
                elif isinstance(v, dict):
                    items.extend(flatten(v, f"{prefix}{k}/"))
            return items

        for name, rel_path in flatten(contents):
            display = name.replace(".pdf", "")
            lines.append(f"| [{display}]({rel_path}) | `{rel_path}` |")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## License",
        "",
        "All content belongs to Scirra Ltd. This repository is for personal learning and reference purposes only.",
        "",
    ])

    return "\n".join(lines)


def cmd_update_readmes(target_keys: list[str]) -> None:
    """Regenerate README.md files for each target directory."""
    print("\nUpdating READMEs...")
    for key in target_keys:
        target = TARGETS[key]
        output_dir = REPO_ROOT / target["output_dir"]
        if not output_dir.exists():
            print(f"  {key}: directory does not exist, skipping")
            continue

        readme_path = output_dir / "README.md"
        content = _generate_target_readme(key)
        readme_path.write_text(content, encoding="utf-8")
        total = sum(1 for _ in output_dir.rglob("*.pdf"))
        print(f"  {key}: {readme_path.relative_to(REPO_ROOT)} ({total} PDFs)")

    print("Done.")


# ─── Update Command (Full Pipeline) ─────────────────────────────────


def cmd_update(
    state: dict,
    target_keys: list[str],
    force: bool = False,
    incremental: bool = False,
    delay: int = 800,
    batch: int = 0,
) -> None:
    """Full update: download combined + generate individual + update READMEs."""
    cmd_download(state, target_keys, force=force)
    cmd_generate(state, target_keys, incremental=incremental, delay=delay, batch=batch)
    cmd_update_readmes(target_keys)


# ─── CLI ─────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construct 3 Documentation PDF Updater"
    )
    parser.add_argument(
        "command",
        choices=["check", "download", "generate", "update", "discover", "readme"],
        help="Command to run",
    )
    parser.add_argument(
        "--target",
        default="all",
        choices=["manual", "addon-sdk", "game-services", "all"],
        help="Target documentation (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-download combined PDFs even if unchanged",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Keep existing individual PDFs, only generate missing ones",
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=800,
        help="Delay between pages in ms (default: 800)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=0,
        help="Max pages per target, 0 = unlimited (default: 0)",
    )
    return parser.parse_args()


def resolve_targets(target_arg: str) -> list[str]:
    if target_arg == "all":
        return list(TARGETS.keys())
    return [target_arg]


def main() -> None:
    args = parse_args()
    state = load_state()
    target_keys = resolve_targets(args.target)

    if args.command == "check":
        cmd_check(state, target_keys)

    elif args.command == "download":
        cmd_download(state, target_keys, force=args.force)

    elif args.command == "generate":
        cmd_generate(
            state, target_keys, incremental=args.incremental, delay=args.delay, batch=args.batch
        )

    elif args.command == "update":
        cmd_update(
            state, target_keys, force=args.force, incremental=args.incremental, delay=args.delay, batch=args.batch
        )

    elif args.command == "discover":
        cmd_discover(state, target_keys)

    elif args.command == "readme":
        cmd_update_readmes(target_keys)


if __name__ == "__main__":
    main()
