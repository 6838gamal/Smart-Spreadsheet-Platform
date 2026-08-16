# migrations/versions/20260816_add_storage_columns.py

"""Add storage columns to files table

Revision ID: 20260816_add_storage_columns
Revises: previous_revision
Create Date: 2026-08-16 06:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = '20260816_add_storage_columns'
down_revision = 'previous_revision'  # استبدل بـ revision السابقة
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add storage columns to files table."""
    # إضافة الأعمدة
    op.add_column('files', sa.Column('storage_key', sa.String(100), nullable=True, unique=True))
    op.add_column('files', sa.Column('is_locally_stored', sa.Boolean, server_default='true', nullable=False))
    op.add_column('files', sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True))
    
    # إضافة الفهارس
    op.create_index('ix_files_storage_key', 'files', ['storage_key'], unique=True)
    op.create_index('ix_files_is_locally_stored', 'files', ['is_locally_stored'])
    op.create_index('ix_files_last_synced_at', 'files', ['last_synced_at'])


def downgrade() -> None:
    """Remove storage columns from files table."""
    # حذف الفهارس
    op.drop_index('ix_files_last_synced_at', table_name='files')
    op.drop_index('ix_files_is_locally_stored', table_name='files')
    op.drop_index('ix_files_storage_key', table_name='files')
    
    # حذف الأعمدة
    op.drop_column('files', 'last_synced_at')
    op.drop_column('files', 'is_locally_stored')
    op.drop_column('files', 'storage_key')
