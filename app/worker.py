import json
import redis
import os
from app.celery_app import celery_app
from app.config import settings
from app.tools import extract_text_from_pdf, chunk_text
from app.database import SessionLocal, DocumentChunkAnalysis
from app.embeddings import get_embeddings_model
from sqlalchemy import delete

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

@celery_app.task(name="process_document_task")
def process_document_task(session_id: str, file_path: str):
    channel_name = f"channel:{session_id}"

    def publish_update(message: str):
        payload = {"event": "milestone", "detail": message}
        redis_client.publish(channel_name, json.dumps(payload))

    try:
        publish_update(f"Opening local document: {file_path}")
        text = extract_text_from_pdf(file_path)
        
        publish_update("Chunking text for vectorization...")
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        if not chunks:
            raise ValueError("The PDF does not contain any extractable text.")
        
        # Batch generate embeddings for all chunks at once
        vectors = get_embeddings_model().embed_documents(chunks)

        publish_update("Saving chunks and vectors to PostgreSQL...")
        db = SessionLocal()
        try:
            # Create database records for each chunk and its corresponding vector
            db.execute(
                delete(DocumentChunkAnalysis).where(
                    DocumentChunkAnalysis.session_id == session_id
                )
            )
            db_records = []
            for i, chunk in enumerate(chunks):
                record = DocumentChunkAnalysis(
                    session_id=session_id,
                    chunk_index=i,
                    file_name=os.path.basename(file_path),
                    chunk_text=chunk,
                    chunk_embedding=vectors[i]
                )
                db_records.append(record)
            
            # Bulk insert for efficiency
            db.bulk_save_objects(db_records)
            db.commit()
            publish_update("Successfully stored in database.")
        except Exception as db_err:
            db.rollback()
            publish_update(f"Database error: {str(db_err)}")
            raise db_err
        finally:
            db.close()
        
        result_payload = {
            "event": "result",
            "summary": f"Ingestion complete. {len(chunks)} chunks vectorized and stored.",
            "total_chunks": len(chunks)
        }
        redis_client.publish(channel_name, json.dumps(result_payload))

        return {"status": "success", "session_id": session_id}

    except Exception as e:
        error_payload = {"event": "error", "detail": str(e)}
        redis_client.publish(channel_name, json.dumps(error_payload))
        raise