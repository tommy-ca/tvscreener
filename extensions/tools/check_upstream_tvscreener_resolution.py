from __future__ import annotations

from pathlib import Path


def main() -> int:
    try:
        from tvscreener_ext.upstream import ensure_upstream_tvscreener

        ensure_upstream_tvscreener()
        import tvscreener

        src = Path(getattr(tvscreener, "__file__", "")).resolve()
        repo_root = Path(__file__).resolve().parents[2]

        # This check is intended to catch accidental imports from the repo checkout's
        # `tvscreener/` source directory, not from an extensions venv living under the repo.
        repo_src_dir = (repo_root / "tvscreener").resolve()
        if repo_src_dir in src.parents:
            print(f"FAIL: tvscreener resolved to repo source tree: {src}")
            return 2

        # Accept site-packages/dist-packages anywhere (including inside repo-local venvs).
        parts = {p.lower() for p in src.parts}
        if "site-packages" not in parts and "dist-packages" not in parts:
            print(f"WARN: tvscreener did not resolve from site-packages: {src}")
            return 1

        print(f"OK: tvscreener resolved to {src}")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
