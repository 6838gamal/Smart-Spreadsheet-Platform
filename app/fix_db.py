import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import os

DATABASE_URL = os.environ.get('DATABASE_URL')

async def run():
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found")
        return
    
    engine = create_async_engine(DATABASE_URL)
    async with engine.connect() as conn:
        try:
            await conn.execute(text('ALTER TABLE extracted_tables ADD COLUMN IF NOT EXISTS table_index INTEGER;'))
            await conn.commit()
            print("✅ Column table_index added!")
        except Exception as e:
            print(f"⚠️ Error adding column: {e}")
        
        try:
            await conn.execute(text('CREATE INDEX IF NOT EXISTS ix_extracted_tables_table_index ON extracted_tables (table_index);'))
            await conn.commit()
            print("✅ Index created!")
        except Exception as e:
            print(f"⚠️ Error creating index: {e}")

if __name__ == "__main__":
    asyncio.run(run())
