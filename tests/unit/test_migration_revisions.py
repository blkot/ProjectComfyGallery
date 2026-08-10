from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_VERSION_COLUMN_LENGTH = 32


def test_migration_revision_ids_fit_production_version_column() -> None:
    config = Config(str(ROOT / "packages/py/core/alembic.ini"))
    revisions = ScriptDirectory.from_config(config).walk_revisions()

    overlong = sorted(
        revision.revision
        for revision in revisions
        if len(revision.revision) > ALEMBIC_VERSION_COLUMN_LENGTH
    )

    assert overlong == []
