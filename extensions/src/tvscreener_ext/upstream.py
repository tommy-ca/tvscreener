from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import sysconfig
from pathlib import Path


def _repo_root() -> Path:
    # extensions/src/tvscreener_ext/upstream.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3]


def ensure_upstream_tvscreener() -> None:
    """Ensure `import tvscreener` resolves from site-packages.

    When running from within a repo checkout, the current working directory can shadow
    the installed upstream `tvscreener` distribution (because a `tvscreener/` source
    directory exists at the repo root).
    """

    repo_root = _repo_root()

    # Prefer venv site-packages first.
    purelib = sysconfig.get_paths().get("purelib")
    platlib = sysconfig.get_paths().get("platlib")
    preferred: list[str] = []
    for p in (purelib, platlib):
        if p and p not in preferred:
            preferred.append(p)
    sys.path[:0] = [p for p in preferred if p not in sys.path]

    # Remove repo root from sys.path.
    cleaned: list[str] = []
    for entry in sys.path:
        if not entry:
            # Empty entry means CWD; drop it if it points at repo root.
            try:
                if Path.cwd().resolve() == repo_root:
                    continue
            except Exception:
                pass
        try:
            if Path(entry).resolve() == repo_root:
                continue
        except Exception:
            pass
        cleaned.append(entry)
    sys.path[:] = cleaned

    # If a prior import happened, prefer failing loudly.
    if "tvscreener" in sys.modules:
        mod = sys.modules.get("tvscreener")
        src = getattr(mod, "__file__", "") or ""
        # Only treat it as a failure if we imported from the repo's source tree
        # (`<repo_root>/tvscreener/...`), not from a repo-local venv.
        try:
            src_path = Path(src).resolve()
            repo_src_dir = (repo_root / "tvscreener").resolve()
            imported_from_repo_src = repo_src_dir in src_path.parents
        except Exception:
            imported_from_repo_src = False

        if imported_from_repo_src:
            raise RuntimeError(
                "tvscreener was already imported from repo checkout; "
                "run extensions from a clean process or outside the repo root"
            )

    # Allow explicit opt-out for local dev.
    if (os.getenv("TVSCREENER_EXT_ALLOW_REPO_IMPORT") or "").strip() == "1":
        return

    # Fail fast if resolution still points at the repo source tree.
    try:
        spec = importlib.util.find_spec("tvscreener")
        origin = Path(spec.origin).resolve() if spec and spec.origin else None
    except Exception:
        origin = None

    if origin:
        repo_src_dir = (repo_root / "tvscreener").resolve()
        if repo_src_dir in origin.parents:
            raise RuntimeError(
                "import tvscreener resolved to repo source tree; "
                "use an installed upstream package (site-packages)"
            )
