"""Provenance stamped onto every result row (F5).

A results table that cannot be traced back to the code and configuration that
produced it is not evidence. Every row carries:

  git_sha    the commit the run came from, with '+dirty' if the tree was not
             clean -- a dirty-tree result is NOT reproducible and must be
             visible as such in the CSV, not discovered later
  cfg_hash   a hash of the fully-expanded config, so two rows can be compared
             without trusting the scenario labels
  lib        numpy / scipy / sklearn / python versions, which move underneath
             long-running studies

All three are cached: they are constant within a process, and `run()` is
called tens of thousands of times.
"""
import dataclasses
import hashlib
import json
import platform
import subprocess
from functools import lru_cache


@lru_cache(maxsize=1)
def git_sha() -> str:
    def g(*a):
        return subprocess.run(("git",) + a, capture_output=True, text=True,
                              timeout=10).stdout.strip()
    try:
        sha = g("rev-parse", "--short", "HEAD")
        if not sha:
            return "nogit"
        return sha + ("+dirty" if g("status", "--porcelain") else "")
    except Exception:
        return "nogit"


@lru_cache(maxsize=1)
def lib_versions() -> str:
    import numpy, scipy, sklearn
    return (f"py{platform.python_version()} np{numpy.__version__} "
            f"sp{scipy.__version__} sk{sklearn.__version__}")


@lru_cache(maxsize=64)
def config_hash(cfg) -> str:
    """Stable 10-hex digest of the fully-expanded config.

    Tuples become lists under JSON, which is fine: the mapping is applied
    uniformly, so two configs hash equal iff their values are equal.
    """
    blob = json.dumps(dataclasses.asdict(cfg), sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


def manifest(cfg) -> dict:
    return dict(git_sha=git_sha(), cfg_hash=config_hash(cfg),
                lib=lib_versions())
