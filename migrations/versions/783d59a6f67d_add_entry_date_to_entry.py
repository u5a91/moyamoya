"""add entry_date to entry

Revision ID: 783d59a6f67d
Revises: da0ab9996028
Create Date: 2026-01-27 23:45:40.329932

"""
from alembic import op
import sqlalchemy as sa

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# revision identifiers, used by Alembic.
revision = "783d59a6f67d"
down_revision = "da0ab9996028"
branch_labels = None
depends_on = None

JST = ZoneInfo("Asia/Tokyo")


def _to_entry_date(created_at) -> str | None:
    """
    created_at から 'YYYY-MM-DD' を作る
    created_at が str の場合もあるかも?
    tzinfo None は UTC とみなす
    """
    if created_at is None:
        return None

    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)

    if not isinstance(created_at, datetime):
        return None

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return created_at.astimezone(JST).date().isoformat()


def upgrade():
    op.add_column("entry", sa.Column("entry_date", sa.Date(), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, created_at FROM entry")).fetchall()

    for entry_id, created_at in rows:
        entry_date = _to_entry_date(created_at)
        if entry_date is None:
            continue
        bind.execute(
            sa.text("UPDATE entry SET entry_date = :d WHERE id = :id"),
            {"d": entry_date, "id": entry_id},
        )

    with op.batch_alter_table("entry") as batch:
        batch.alter_column("entry_date", existing_type=sa.Date(), nullable=False)


def downgrade():
    with op.batch_alter_table("entry") as batch:
        batch.drop_column("entry_date")
