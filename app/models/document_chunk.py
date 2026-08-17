# app/models/document_chunk.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, JSON
from pgvector.sqlalchemy import Vector

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("source_documents.id", ondelete="CASCADE"))
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(Vector(1536))  # متجه التضمين
    metadata = Column(JSON)  # اسم الملف، الصفحة، إلخ.
    
    __table_args__ = (
        UniqueConstraint('document_id', 'chunk_index'),
        Index('document_chunks_document_id_idx', 'document_id'),
        Index('document_chunks_doc_chunk_idx', 'document_id', 'chunk_index'),
    )
