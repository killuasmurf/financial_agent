from langchain_core.tools import tool
from app.database import SessionLocal, DocumentChunkAnalysis
from app.embeddings import get_embeddings_model
from sqlalchemy import select

@tool
def search_financial_documents(query: str) -> str:
    """Searches ingested financial documents for context relevant to the user's query."""
    # Convert the text query into a 768-dimensional vector
    query_vector = get_embeddings_model().embed_query(query)
    
    db = SessionLocal()
    try:
        # pgvector calculates the mathematical distance directly at the database layer
        results = db.scalars(
            select(DocumentChunkAnalysis)
            .order_by(DocumentChunkAnalysis.chunk_embedding.cosine_distance(query_vector))
            .limit(5)
        ).all()
        
        if not results:
            return "No relevant documents found in the database."
            
        # Format the chunks into a readable string for the LLM
        return "\n\n".join([f"Source: {r.file_name}\nContent: {r.chunk_text}" for r in results])
    except Exception as e:
        return f"Database search failed: {str(e)}"
    finally:
        db.close()