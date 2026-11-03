from sqlalchemy import create_engine, Column, Integer, String, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker
from pgvector.sqlalchemy import Vector
from app.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DocumentChunkAnalysis(Base):
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    file_name = Column(String)
    chunk_text = Column(Text)
    # We allocate 3072 dimensions, which is standard for many embedding models
    chunk_embedding = Column(Vector(3072)) 

def init_db() -> None:
    """Create the pgvector extension and application tables when the service starts."""
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE document_chunks "
                "DROP CONSTRAINT IF EXISTS document_chunks_session_id_key"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE document_chunks "
                "ADD COLUMN IF NOT EXISTS chunk_index INTEGER NOT NULL DEFAULT 0"
            )
        )