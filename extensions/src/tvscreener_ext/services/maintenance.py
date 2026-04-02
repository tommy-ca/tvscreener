from __future__ import annotations

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class MaintenanceService:
    """Service for repository and artifact maintenance."""

    def migrate_artifacts(self, base_dir: Path) -> dict[str, int]:
        """Migrate artifacts from legacy 'prefect/' to 'runs/' directory."""
        legacy_dir = base_dir / "artifacts" / "prefect"
        target_dir = base_dir / "artifacts" / "runs"

        results = {"migrated": 0, "skipped": 0, "errors": 0}

        if not legacy_dir.exists():
            logger.info("Legacy directory %s does not exist. Skipping migration.", legacy_dir)
            return results

        target_dir.mkdir(parents=True, exist_ok=True)

        # Legacy prefect dir usually has subdirs named by params_hash
        for item in legacy_dir.iterdir():
            if item.is_dir():
                dest = target_dir / item.name
                if dest.exists():
                    logger.debug("Destination %s already exists. Skipping.", dest)
                    results["skipped"] += 1
                    continue

                try:
                    logger.info("Migrating %s to %s", item, dest)
                    shutil.move(str(item), str(dest))
                    results["migrated"] += 1
                except Exception as e:
                    logger.error("Failed to migrate %s: %s", item, e)
                    results["errors"] += 1

        return results

    def prune_artifacts(self, base_dir: Path, older_than_days: int = 30) -> int:
        """Prune artifacts older than specified days."""
        import time

        runs_dir = base_dir / "artifacts" / "runs"
        count = 0

        if not runs_dir.exists():
            return 0

        now = time.time()
        cutoff = now - (older_than_days * 86400)

        for item in runs_dir.iterdir():
            if item.is_dir() and item.stat().st_mtime < cutoff:
                try:
                    logger.info("Pruning old artifact directory: %s", item)
                    shutil.rmtree(item)
                    count += 1
                except Exception as e:
                    logger.error("Failed to prune %s: %s", item, e)

        return count
