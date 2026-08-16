import logging
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncSession
from alembic import command
from alembic.config import Config

logger = logging.getLogger(__name__)

class MigrationManager:
    """مدير الترحيلات التلقائية"""
    
    @staticmethod
    async def ensure_storage_columns(session: AsyncSession):
        """التحقق من وجود أعمدة التخزين وإنشاؤها إذا لزم الأمر"""
        try:
            # التحقق من وجود الأعمدة
            inspector = inspect(session.bind)
            columns = [col['name'] for col in inspector.get_columns('files')]
            
            required_columns = [
                'storage_key',
                'is_locally_stored',
                'last_synced_at',
                'storage_backend',
                'storage_bucket',
                'storage_object_key'
            ]
            
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                logger.warning(f"الأعمدة المفقودة: {missing_columns}")
                await MigrationManager._add_missing_columns(session, missing_columns)
                return True
            return False
            
        except Exception as e:
            logger.error(f"خطأ في التحقق من الأعمدة: {e}")
            return False
    
    @staticmethod
    async def _add_missing_columns(session: AsyncSession, missing_columns: list):
        """إضافة الأعمدة المفقودة"""
        try:
            for column in missing_columns:
                sql = f"""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 
                        FROM information_schema.columns 
                        WHERE table_name = 'files' 
                        AND column_name = '{column}'
                    ) THEN
                        ALTER TABLE files ADD COLUMN {column} {MigrationManager._get_column_type(column)};
                    END IF;
                END $$;
                """
                await session.execute(text(sql))
                logger.info(f"تم إضافة العمود: {column}")
            
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"خطأ في إضافة الأعمدة: {e}")
            raise
    
    @staticmethod
    def _get_column_type(column_name: str) -> str:
        """الحصول على نوع العمود"""
        types = {
            'storage_key': 'VARCHAR',
            'is_locally_stored': 'BOOLEAN DEFAULT TRUE',
            'last_synced_at': 'TIMESTAMP',
            'storage_backend': 'VARCHAR',
            'storage_bucket': 'VARCHAR',
            'storage_object_key': 'VARCHAR'
        }
        return types.get(column_name, 'VARCHAR')
    
    @staticmethod
    def run_alembic_migrations():
        """تشغيل ترحيلات Alembic عند بدء التطبيق"""
        try:
            alembic_cfg = Config("alembic.ini")
            command.upgrade(alembic_cfg, "head")
            logger.info("تم تشغيل ترحيلات Alembic بنجاح")
            return True
        except Exception as e:
            logger.error(f"خطأ في تشغيل ترحيلات Alembic: {e}")
            return False
