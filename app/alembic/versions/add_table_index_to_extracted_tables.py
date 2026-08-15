"""Add table_index to extracted_tables

Revision ID: add_table_index_to_extracted_tables
Revises: (revision_id السابق)
Create Date: 2026-08-15 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_table_index_to_extracted_tables'
down_revision: Union[str, None] = None  # ضع الـ revision السابق هنا
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """إضافة عمود table_index إلى جدول extracted_tables"""
    op.add_column('extracted_tables', sa.Column('table_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    """حذف عمود table_index"""
    op.drop_column('extracted_tables', 'table_index')
