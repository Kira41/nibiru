from __future__ import annotations

import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
DATABASE_DIR = REPO_ROOT / "database"


def ensure_database_dir() -> Path:
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    return DATABASE_DIR


def database_path(filename: str, *legacy_candidates: str | Path) -> Path:
    target_path = ensure_database_dir() / filename

    if target_path.exists():
        return target_path

    candidates = []
    for candidate in legacy_candidates:
        candidate_path = Path(candidate)
        if not candidate_path.is_absolute():
            candidate_path = REPO_ROOT / candidate_path
        candidates.append(candidate_path)

    for candidate_path in candidates:
        if candidate_path.exists() and candidate_path != target_path:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(candidate_path), str(target_path))
            break

    return target_path
