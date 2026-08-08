"""Hash public share capabilities at rest.

Revision ID: 20260801_0047
Revises: 20260731_0046

Workspace/Research and PHR shares are bearer capabilities.  Before this
migration their raw values were stored in database rows, making a database read
enough to replay a public link.  Backfill a SHA-256 digest, then remove the raw
columns. Existing issued URLs continue working because public readers hash the
incoming value before lookup.

Downgrade restores the old columns for schema compatibility but intentionally
cannot reconstruct capability values from their digests. Roll back application
and database together from a backup if old links must remain manageable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260801_0047"
down_revision: str | None = "20260731_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _backfill_hashes(table_name: str) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(f"SELECT id, share_token FROM {table_name}")
    ).mappings()
    for row in rows:
        raw = row["share_token"]
        if not raw:
            raise RuntimeError(f"{table_name} row {row['id']} has an empty share capability")
        bind.execute(
            sa.text(f"UPDATE {table_name} SET token_hash = :token_hash WHERE id = :id"),
            {"id": row["id"], "token_hash": _digest(str(raw))},
        )


def upgrade() -> None:
    op.add_column(
        "workspace_conversation_shares",
        sa.Column("token_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "phr_shares",
        sa.Column("token_hash", sa.String(length=64), nullable=True),
    )
    _backfill_hashes("workspace_conversation_shares")
    _backfill_hashes("phr_shares")

    # These named indexes predate the model-level constraints and otherwise
    # survive a SQLite batch recreation pointing at a removed column.
    op.drop_index(
        "ix_workspace_conversation_shares_share_token",
        table_name="workspace_conversation_shares",
    )
    op.drop_index("ix_phr_shares_share_token", table_name="phr_shares")

    with op.batch_alter_table(
        "workspace_conversation_shares", recreate="always"
    ) as batch:
        batch.drop_constraint("uq_workspace_conversation_shares_token", type_="unique")
        batch.alter_column("token_hash", existing_type=sa.String(length=64), nullable=False)
        batch.create_unique_constraint(
            "uq_workspace_conversation_shares_token_hash", ["token_hash"]
        )
        batch.create_index("ix_workspace_conversation_shares_token_hash", ["token_hash"])
        batch.drop_column("share_token")

    # SQLite may have created the old ``unique=True`` constraint without a
    # stable name; batch recreation safely discards it together with its column.
    with op.batch_alter_table("phr_shares", recreate="always") as batch:
        batch.alter_column("token_hash", existing_type=sa.String(length=64), nullable=False)
        batch.create_unique_constraint("uq_phr_shares_token_hash", ["token_hash"])
        batch.create_index("ix_phr_shares_token_hash", ["token_hash"])
        batch.drop_column("share_token")


def downgrade() -> None:
    # SHA-256 is intentionally one-way: schema downgrade cannot recreate raw
    # bearer values. Existing capability links must be rotated after rollback.
    with op.batch_alter_table("phr_shares", recreate="always") as batch:
        batch.add_column(sa.Column("share_token", sa.String(length=64), nullable=True))
        batch.drop_constraint("uq_phr_shares_token_hash", type_="unique")
        batch.drop_index("ix_phr_shares_token_hash")
        batch.drop_column("token_hash")
    op.create_index(
        "ix_phr_shares_share_token", "phr_shares", ["share_token"], unique=True
    )

    with op.batch_alter_table(
        "workspace_conversation_shares", recreate="always"
    ) as batch:
        batch.add_column(sa.Column("share_token", sa.String(length=160), nullable=True))
        batch.drop_constraint("uq_workspace_conversation_shares_token_hash", type_="unique")
        batch.drop_index("ix_workspace_conversation_shares_token_hash")
        batch.drop_column("token_hash")
    op.create_index(
        "ix_workspace_conversation_shares_share_token",
        "workspace_conversation_shares",
        ["share_token"],
    )
    with op.batch_alter_table(
        "workspace_conversation_shares", recreate="always"
    ) as batch:
        batch.create_unique_constraint("uq_workspace_conversation_shares_token", ["share_token"])
