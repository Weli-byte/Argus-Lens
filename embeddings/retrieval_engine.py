from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Dict
import json

from monitoring.log_pipeline import logger

class RetrievalEngine:
    """
    Semantic AI Layer using pgvector and SentenceTransformers.
    Allows for contextual memory and similarity search over detected objects/events.
    """
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.encoder = SentenceTransformer(model_name)
        logger.info(f"SentenceTransformer {model_name} loaded for Vector Embedding.")

    def generate_embedding(self, text_content: str) -> List[float]:
        """Converts text to a vector embedding array."""
        vector = self.encoder.encode(text_content)
        return vector.tolist()

    async def save_context(self, db: AsyncSession, session_id: str, context_text: str):
        """
        Saves text embedding to pgvector database.
        Requires `pgvector` extension and a table column of type `VECTOR(384)`.
        """
        vector = self.generate_embedding(context_text)
        vector_str = "[" + ",".join([str(v) for v in vector]) + "]"
        
        # Note: Using raw SQL here to ensure pgvector syntax is executed. 
        # In a full ORM setup, we'd use pgvector.sqlalchemy types.
        query = text("""
            INSERT INTO contextual_memory (session_id, content, embedding)
            VALUES (:session_id, :content, :embedding::vector)
        """)
        
        await db.execute(query, {
            "session_id": session_id,
            "content": context_text,
            "embedding": vector_str
        })
        await db.commit()
        logger.info(f"Contextual memory saved for session {session_id}")

    async def search_similar(self, db: AsyncSession, query_text: str, limit: int = 5) -> List[Dict]:
        """
        Performs Cosine Similarity Search (`<=>`) using pgvector.
        """
        query_vector = self.generate_embedding(query_text)
        vector_str = "[" + ",".join([str(v) for v in query_vector]) + "]"
        
        query = text("""
            SELECT session_id, content, 1 - (embedding <=> :query_vector::vector) as similarity
            FROM contextual_memory
            ORDER BY embedding <=> :query_vector::vector
            LIMIT :limit
        """)
        
        result = await db.execute(query, {"query_vector": vector_str, "limit": limit})
        
        matches = []
        for row in result:
            matches.append({
                "session_id": row.session_id,
                "content": row.content,
                "similarity": float(row.similarity)
            })
            
        return matches
