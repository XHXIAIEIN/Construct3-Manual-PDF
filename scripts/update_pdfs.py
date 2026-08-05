#!/usr/bin/env python3
"""
Construct 3 Documentation PDF Updater

Downloads combined PDFs from construct-static.com CDN, splits them into
individual page PDFs, and maintains the directory structure + READMEs.

The split adds what the CDN's PDFs lack: a bookmark outline on the combined
files, per-chapter outlines on the split ones, cross-references rewritten to
jump between local files instead of back to the website, and page footers
renumbered to match the file they now live in.

Commands:
    check       Check CDN for updates (HEAD only, no downloads)
    download    Download combined PDFs from CDN
    generate    Split combined PDFs into individual page PDFs
    update      Full update: download + generate + readme
    discover    Re-discover CDN download URLs from construct.net
    readme      Regenerate README.md for each target directory

Options:
    --target T     Target: manual, addon-sdk, game-services, all (default: all)
    --force        Force re-download even if CDN is unchanged
    --incremental  Keep existing individual PDFs, only write missing ones
    --batch N      Max pages per target (0 = unlimited, default: 0)

Examples:
    python update_pdfs.py check
    python update_pdfs.py download --force
    python update_pdfs.py generate --target manual
    python update_pdfs.py update
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import fitz
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

# Type scale of the combined PDFs: 31.2pt chapter heading, 18pt section
# heading, 12pt body and footer. Chapter starts also carry a "View online:"
# line naming the manual page they came from.
CHAPTER_SIZE = 24
SECTION_SIZE = 14
FOOTER_SIZE = 12
VIEW_ONLINE_RE = re.compile(r"View online:\s*(\S+)")

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


def _headings(page, min_size: float, max_size: float | None = None) -> list[str]:
    """Collect a page's headings, grouped by text block.

    A heading may wrap across lines within its block, so spans are joined per
    block rather than per line.
    """
    found = []

    for block in page.get_text("dict")["blocks"]:
        spans = [s for line in block.get("lines", []) for s in line["spans"]]
        if not spans:
            continue
        size = spans[0]["size"]
        if size < min_size or (max_size is not None and size >= max_size):
            continue
        text = " ".join("".join(s["text"] for s in spans).split())
        if text:
            found.append(text)

    return found


def _url_to_relpath(url: str, base_path: str) -> Path | None:
    """Map a manual page URL onto its output path, mirroring the URL hierarchy.

    Returns None for URLs pointing outside this target. Links inside the PDFs
    appear in both /en/... and bare /... forms, so each is tried.
    """
    path = urlsplit(url).path.rstrip("/")

    for prefix in (base_path, base_path.replace("/en", "", 1)):
        if path == prefix:
            return Path("index.pdf")
        if path.startswith(f"{prefix}/"):
            return Path(f"{path[len(prefix) + 1:]}.pdf")

    return None


def _extract_sections(doc, base_path: str) -> list[dict]:
    """Locate every chapter start in a combined PDF.

    A chapter opens with an oversized heading followed by a "View online: <url>"
    line naming the manual page it came from. The text layer wraps that URL
    across lines, so the full URL is read back from the link annotation
    covering it.
    """
    sections: list[dict] = []

    for i, page in enumerate(doc):
        match = VIEW_ONLINE_RE.search(page.get_text())
        if not match:
            continue

        prefix = match.group(1)
        uri = next(
            (l["uri"] for l in page.get_links() if l.get("uri", "").startswith(prefix)),
            None,
        )
        relpath = _url_to_relpath(uri, base_path) if uri else None
        if relpath is None:
            print(f"  page {i + 1}: unresolved URL {prefix} — skipped")
            continue

        heading = _headings(page, CHAPTER_SIZE)
        sections.append({
            "start": i,
            "path": relpath,
            "title": heading[0] if heading else relpath.stem,
        })

    # A chapter runs until the next one begins
    for n, sec in enumerate(sections):
        sec["end"] = (
            sections[n + 1]["start"] - 1 if n + 1 < len(sections) else doc.page_count - 1
        )

    return sections


def _localise_links(out, source: Path, known: set[Path], base_path: str) -> int:
    """Repoint links that target other manual pages at the local split files.

    The combined PDF carries only web links, so a split file would otherwise
    send every cross-reference back online. Rewriting them as cross-document
    jumps keeps the whole set navigable offline.
    """
    rewritten = 0

    for page in out:
        for link in page.get_links():
            if link["kind"] != fitz.LINK_URI:
                continue
            target = _url_to_relpath(link["uri"], base_path)
            if target is None or target == source or target not in known:
                continue

            link.pop("uri")
            link.update({
                "kind": fitz.LINK_GOTOR,
                "file": os.path.relpath(target, source.parent).replace(os.sep, "/"),
                "page": 0,
                "to": fitz.Point(0, 0),
            })
            page.update_link(link)
            rewritten += 1

    return rewritten


def _restamp_footers(out) -> None:
    """Rewrite the "Page N of <total>" footer to match the split file.

    Page numbers are painted into the combined PDF's content stream, so left
    alone a one-page chapter would still claim to be "Page 5 of 1183".
    """
    total = out.page_count

    for n, page in enumerate(out, 1):
        footer = fitz.Rect(0, page.rect.height - 40, page.rect.width, page.rect.height)
        hits = page.search_for("Page ", clip=footer)
        if not hits:
            continue

        box = fitz.Rect(hits[0].x0, hits[0].y0 - 2, page.rect.width, hits[0].y1 + 2)
        page.add_redact_annot(box)
        page.apply_redactions()
        page.insert_text(
            (box.x0, hits[0].y1 - 3),
            f"Page {n} of {total}",
            fontname="hebo",
            fontsize=FOOTER_SIZE,
        )


def _clean_output_dir(target: dict) -> None:
    """Remove all existing PDFs and subdirs in a target's output directory."""
    import shutil

    output_dir = REPO_ROOT / target["output_dir"]
    if not output_dir.exists():
        return

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
    batch: int = 0,
) -> None:
    """Split each combined PDF into one PDF per manual page.

    Default: full deploy — wipe output dir, re-split everything.
    With --incremental: keep existing files, only write missing ones.
    """
    print("Splitting combined PDFs...")

    for key in target_keys:
        target = TARGETS[key]
        combined = REPO_ROOT / target["combined_pdf"]
        output_dir = REPO_ROOT / target["output_dir"]
        base_path = target["base_path"]

        if not combined.exists():
            print(f"\n[{target['name']}] {combined.name} not found — run 'download' first")
            continue

        doc = fitz.open(combined)
        sections = _extract_sections(doc, base_path)
        print(f"\n[{target['name']}] {doc.page_count} pages → {len(sections)} sections")

        if not sections:
            print("  No sections found — PDF layout may have changed")
            doc.close()
            continue

        if not incremental:
            _clean_output_dir(target)

        known = {sec["path"] for sec in sections}
        base_meta = doc.metadata or {}
        combined_toc: list[list] = []
        stats = {"written": 0, "skipped": 0, "links": 0}

        for sec in sections[:batch] if batch else sections:
            output_path = output_dir / sec["path"]

            # Outline for the combined PDF: chapters, each with its own sections
            combined_toc.append([1, sec["title"], sec["start"] + 1])
            for n in range(sec["start"], sec["end"] + 1):
                combined_toc += [
                    [2, text, n + 1]
                    for text in _headings(doc[n], SECTION_SIZE, CHAPTER_SIZE)
                ]

            if incremental and output_path.exists():
                stats["skipped"] += 1
                continue

            output_path.parent.mkdir(parents=True, exist_ok=True)

            out = fitz.open()
            out.insert_pdf(doc, from_page=sec["start"], to_page=sec["end"])
            out.set_metadata({**base_meta, "title": sec["title"]})
            out.set_toc([
                [1, text, n + 1]
                for n, page in enumerate(out)
                for text in _headings(page, SECTION_SIZE, CHAPTER_SIZE)
            ])
            stats["links"] += _localise_links(out, sec["path"], known, base_path)
            _restamp_footers(out)
            # Each slice inherits the full font set of the combined PDF; subsetting
            # to the glyphs actually used cuts roughly a third off the total size
            out.subset_fonts()
            out.save(str(output_path), garbage=4, deflate=True)
            out.close()

            stats["written"] += 1

        # The CDN ships these with no outline at all, leaving 1000+ pages
        # unnavigable. Skip the rewrite when unchanged — saveIncr appends.
        if not batch and doc.get_toc() != combined_toc:
            doc.set_toc(combined_toc)
            doc.saveIncr()
        doc.close()

        state.setdefault("targets", {})[key] = {
            "total_pages": len(sections),
            "last_generated": datetime.now(timezone.utc).isoformat(),
        }

        print(
            f"  Done: {stats['written']} written, {stats['skipped']} skipped, "
            f"{stats['links']} links localised, {len(combined_toc)} bookmarks"
        )

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
    batch: int = 0,
) -> None:
    """Full update: download combined + split individual + update READMEs."""
    cmd_download(state, target_keys, force=force)
    cmd_generate(state, target_keys, incremental=incremental, batch=batch)
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
        cmd_generate(state, target_keys, incremental=args.incremental, batch=args.batch)

    elif args.command == "update":
        cmd_update(
            state,
            target_keys,
            force=args.force,
            incremental=args.incremental,
            batch=args.batch,
        )

    elif args.command == "discover":
        cmd_discover(state, target_keys)

    elif args.command == "readme":
        cmd_update_readmes(target_keys)


if __name__ == "__main__":
    main()
