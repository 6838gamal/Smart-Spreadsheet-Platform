# app/services/indexing_service.py
from sentence_transformers import SentenceTransformer
import numpy as np

class IndexingService:
    def __init__(self):
        # استخدام نموذج تضمين خفيف وسريع
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
    
    async def index_document(self, file_id: int, chunks: List[str]):
        """
        فهرسة مستند عن طريق تقسيمه إلى مقاطع وتضمينها
        """
        embeddings = self.embedder.encode(chunks)
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # تخزين في قاعدة البيانات
            chunk_obj = DocumentChunk(
                document_id=file_id,
                chunk_index=i,
                chunk_text=chunk,
                embedding=embedding.tolist(),
                metadata={"file_id": file_id}
            )
            db.add(chunk_obj)
        
        db.commit()
