"""Crash-safe, append-only result store for the Phase 3 study.

One completed run = one JSON object on one line, flushed and fsync'd before the
next run starts. A kill -9, a flat battery or a closed laptop lid therefore
costs at most the single run that was in flight. Restarting skips everything
already on disk.

Why JSONL and not a database: the study is append-only, single-writer and read
once at the end. A line-delimited file survives partial writes (a torn final
line is dropped on read), needs no schema migration when a metric is added, and
can be inspected with `wc -l` while the study is running.

A row is identified by `key()` -- stage, speed, scenario, connectivity, method,
budget target and seed. A row is only treated as done if its `cfg_hash` matches
the config currently in force, so changing the configuration invalidates the
affected rows instead of silently reusing stale ones.
"""
from __future__ import annotations

import gzip
import json
import os
import pathlib
from typing import Dict, Iterator, Optional, Set, Tuple

Key = Tuple[str, str, str, str, str, str, int]


def key(stage: str, speed: float, scenario: str, conn: str, method: str,
        budget: Optional[float], seed: int) -> Key:
    """Identity of one run. `budget` is None for the matched-budget stage."""
    return (stage, f"{speed:g}", scenario, conn, method,
            "-" if budget is None else f"{budget:g}", int(seed))


class ResultStore:
    """Append-only JSONL store with fsync-per-row durability."""

    def __init__(self, path: str | os.PathLike):
        self.path = pathlib.Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = None

    # -- reading -----------------------------------------------------------
    def rows(self) -> Iterator[Dict]:
        """Every intact row. A torn final line (interrupted write) is skipped.

        Reads the plain file if present, otherwise falls back to a `.gz`
        alongside it -- the archived form committed to the repository, since the
        uncompressed store is too large for version control. So an analysis runs
        from a fresh clone with no extra step.
        """
        path = self.path
        if not path.exists():
            gz = path.with_suffix(path.suffix + ".gz")
            if not gz.exists():
                return
            with gzip.open(gz, "rt") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
            return
        with path.open("r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue        # torn last line: the run will simply re-run

    def done_keys(self, cfg_hash: Optional[str] = None) -> Set[Key]:
        """Keys already on disk. With `cfg_hash`, only rows written under that
        configuration count -- so a config change re-runs what it invalidates
        rather than mixing two configurations in one table."""
        out = set()
        for r in self.rows():
            if cfg_hash is not None and r.get("cfg_hash") != cfg_hash:
                continue
            out.add(key(r["stage"], r["speed"], r["scenario"], r["conn"],
                        r["method"], r.get("budget"), r["seed"]))
        return out

    # -- writing -----------------------------------------------------------
    def open(self):
        if self._fh is None:
            self._fh = self.path.open("a")
        return self

    def append(self, row: Dict) -> None:
        """Write one row and make it durable before returning.

        flush() pushes it out of Python's buffer; fsync() pushes it out of the
        OS page cache onto the disk. Without the fsync a power cut can lose
        rows that the program believed were written.
        """
        assert self._fh is not None, "call open() first"
        self._fh.write(json.dumps(row, default=float) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()
        return False
