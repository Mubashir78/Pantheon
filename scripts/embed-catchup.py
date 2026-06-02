#!/usr/bin/env python3
"""Fast parallel embedding catch-up.

Uses ThreadPoolExecutor to embed multiple files concurrently into ChromaDB.
Covers ALL codexes (auto-discovered) including distilled/sessions/archive.

Usage:
    python3 scripts/embed-catchup.py                    # Default: 4 workers
    python3 scripts/embed-catchup.py --workers 8         # More parallel
    python3 scripts/embed-catchup.py --dry-run           # Just report gap
    python3 scripts/embed-catchup.py --quick             # Raw files only (skip distilled/sessions/archive)
"""

import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("embed-catchup")

R = os.path.expanduser("~konan")
ATH = Path(f"{R}/athenaeum")
CHR = f"{R}/.hermes/pantheon/chroma"
EXTS = {".md", ".txt", ".json", ".yaml", ".yml"}
GOD_PREFIX = "Codex-God-"


def get_missing_files(quick: bool = False):
    """Compare ChromaDB against filesystem, return list of (codex, path) to embed."""
    import chromadb

    c = chromadb.PersistentClient(path=CHR)

    # Build embedded set
    s = set()
    for col in c.list_collections():
        if col.count() == 0:
            continue
        r = col.get(include=["metadatas"])
        if r and r.get("metadatas"):
            for m in r["metadatas"]:
                if m and "source" in m:
                    s.add(m["source"])

    # Discover codexes
    codexes = sorted(
        d.name for d in ATH.iterdir()
        if d.is_dir() and d.name.startswith("Codex-") and not d.name.startswith(GOD_PREFIX)
    )

    # Find files
    embeddable = []
    total_on_disk = 0
    for cn in codexes:
        d = ATH / cn
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in EXTS:
                continue
            total_on_disk += 1
            if quick:
                parts = p.relative_to(ATH).parts
                if any(x in parts for x in ("archive", "distilled", "sessions")):
                    if str(p) not in s:
                        pass  # count as skipped
                    continue
            if str(p) not in s:
                embeddable.append((cn, p))

    return embeddable, total_on_disk, len(s)


def embed_one(codex_name: str, file_path: Path) -> bool:
    """Embed a single file. Uses Ollama via the _Embedder class."""
    try:
        sys.path.insert(0, f"{R}/pantheon/lib")
        from ichor_hybrid import _Embedder
        import chromadb

        embedder = _Embedder()
        if not embedder.is_available():
            logger.warning("Embedder not available, aborting")
            return False

        content = file_path.read_text(encoding="utf-8", errors="replace").strip()
        if not content:
            return True  # empty files don't need embedding

        # Truncate to 3000 chars for speed (Ollama context limit anyway)
        if len(content) > 3000:
            content = content[:3000]

        vector = embedder.embed(content)
        if vector is None:
            logger.warning("Embed returned None: %s", file_path.name)
            return False

        client = chromadb.PersistentClient(path=CHR)
        cname = f"pantheon_codex_{codex_name.lower().replace('codex-', '').replace('-', '_')}"
        try:
            collection = client.get_collection(name=cname)
        except Exception:
            collection = client.create_collection(name=cname)

        doc_id = str(file_path.relative_to(ATH))
        collection.add(
            embeddings=[vector],
            documents=[content],
            ids=[doc_id],
            metadatas=[{
                "codex": codex_name,
                "source": str(file_path),
                "filename": file_path.name,
            }],
        )
        return True

    except Exception as exc:
        logger.debug("Fail %s: %s", file_path.name, exc)
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Fast parallel embedding catch-up")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers (default: 4)")
    parser.add_argument("--dry-run", action="store_true", help="Only report what would be embedded")
    parser.add_argument("--quick", action="store_true", help="Skip distilled/sessions/archive (surgical)")
    args = parser.parse_args()

    logger.info("Scanning ChromaDB vs filesystem...")
    start = time.time()
    missing, total_on_disk, total_in_chroma = get_missing_files(quick=args.quick)
    scan_time = time.time() - start

    logger.info("ChromaDB has %d vectors", total_in_chroma)
    logger.info("Filesystem has %d embeddable files", total_on_disk)
    logger.info("Missing: %d files (scan in %.1fs)", len(missing), scan_time)

    if not missing:
        logger.info("Gap closed! Nothing to do.")
        return

    # Group by codex
    by_codex = {}
    for cn, fp in missing:
        by_codex.setdefault(cn, []).append(fp)

    logger.info("Breakdown by codex:")
    for cn, files in sorted(by_codex.items(), key=lambda x: -len(x[1])):
        sizes = sum(os.path.getsize(f) for f in files)
        logger.info("  %s: %d files (%dKB)", cn, len(files), sizes // 1024)

    if args.dry_run:
        logger.info("Dry run — %d files would be embedded", len(missing))
        return

    # Embed with parallel workers
    logger.info("Embedding %d files with %d workers...", len(missing), args.workers)
    ok = 0
    fail = 0
    embed_start = time.time()

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(embed_one, cn, fp): (cn, fp)
            for cn, fp in missing
        }

        done = 0
        for f in as_completed(futures):
            done += 1
            cn, fp = futures[f]
            try:
                if f.result():
                    ok += 1
                else:
                    fail += 1
            except Exception:
                fail += 1

            # Progress report every 10 files
            if done % 10 == 0 or done == len(missing):
                elapsed = time.time() - embed_start
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(missing) - done) / rate if rate > 0 else 0
                logger.info(
                    "  [%d/%d] %d ok, %d fail | %.1f files/s | ETA: %.0fs",
                    done, len(missing), ok, fail, rate, eta,
                )

    elapsed = time.time() - embed_start
    logger.info("Done! %d embedded, %d failed in %.1fs (%.1f files/s)", ok, fail, elapsed, len(missing) / elapsed if elapsed > 0 else 0)


if __name__ == "__main__":
    main()
