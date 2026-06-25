"""enhance_source_registry

Revision ID: 494b69db86d1
Revises: 687e04a5c9c3
Create Date: 2026-06-26 00:17:25.020891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '494b69db86d1'
down_revision: Union[str, Sequence[str], None] = '687e04a5c9c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'source_registry',
        sa.Column(
            'confidence_score',
            sa.Float(),
            nullable=False,
            server_default='1.0',
        )
    )

    op.add_column(
        'source_registry',
        sa.Column(
            'collector_version',
            sa.String(length=50),
            nullable=True,
        )
    )

    op.alter_column(
        'source_registry',
        'professional_id',
        existing_type=sa.VARCHAR(),
        nullable=True,
    )

    op.alter_column(
        'source_registry',
        'source_url',
        existing_type=sa.VARCHAR(),
        nullable=True,
    )

def downgrade() -> None:
    op.alter_column(
        'source_registry',
        'source_url',
        existing_type=sa.VARCHAR(),
        nullable=False,
    )

    op.alter_column(
        'source_registry',
        'professional_id',
        existing_type=sa.VARCHAR(),
        nullable=False,
    )

    op.drop_column(
        'source_registry',
        'collector_version'
    )

    op.drop_column(
        'source_registry',
        'confidence_score'
    )
