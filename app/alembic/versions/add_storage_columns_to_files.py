"""add_storage_columns_to_files

Revision ID: xxxxxxxx
Revises: previous_revision_id
Create Date: 2026-08-16 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'xxxxxxxx'  # الرقم الذي تم إنشاؤه تلقائياً
down_revision: Union[str, None] = 'previous_revision_id'  # التعديل السابق
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """إضافة أعمدة التخزين إلى جدول files"""
    # التحقق من وجود الأعمدة قبل إضافتها
    connection = op.get_bind()
    
    # قائمة الأعمدة المطلوب إضافتها
    columns_to_add = [
        ('storage_key', sa.String(), None),
        ('is_locally_stored', sa.Boolean(), True),
        ('last_synced_at', sa.DateTime(), None),
        ('storage_backend', sa.String(), None),
        ('storage_bucket', sa.String(), None),
        ('storage_object_key', sa.String(), None),
    ]
    
    for column_name, column_type, default_value in columns_to_add:
        # التحقق من وجود العمود
        inspector = sa.inspect(connection)
        existing_columns = [col['name'] for col in inspector.get_columns('files')]
        
        if column_name not in existing_columns:
            op.add_column('files', sa.Column(column_name, column_type, server_default=default_value if default_value is not None else None))


def downgrade() -> None:
    """حذف أعمدة التخزين من جدول files"""
    # قائمة الأعمدة المطلوب حذفها
    columns_to_drop = [
        'storage_key',
        'is_locally_stored', 
        'last_synced_at',
        'storage_backend',
        'storage_bucket',
        'storage_object_key'
    ]
    
    for column_name in columns_to_drop:
        op.drop_column('files', column_name)
