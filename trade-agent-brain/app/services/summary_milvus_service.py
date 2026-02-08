"""Milvus 向量存储服务 — BM25 稀疏 + 密集向量混合检索"""
import time
from typing import Any, Dict, List, Optional

from loguru import logger
from pymilvus import (
    MilvusClient, DataType, Function, FunctionType,
    AnnSearchRequest, RRFRanker,
)

from app.config.llm_config import embedding_model
from app.config.settings import settings

COLLECTION_NAME = "chat_summaries"
DENSE_DIM = 1024


class SummaryMilvusService:

    def __init__(self):
        self.client = MilvusClient(uri=f"http://{settings.milvus_host}:{settings.milvus_port}")
        self.collection_name = COLLECTION_NAME
        self._init_collection()

    def _init_collection(self):
        if self.client.has_collection(self.collection_name):
            return

        schema = self.client.create_schema()
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("summary_id", DataType.VARCHAR, max_length=64, nullable=True)
        schema.add_field("user_id", DataType.INT64, nullable=True)
        schema.add_field("session_id", DataType.VARCHAR, max_length=64, nullable=True)
        schema.add_field("context_text", DataType.VARCHAR, max_length=6000,
                         enable_analyzer=True,
                         analyzer_params={"tokenizer": "jieba", "filter": ["cnalphanumonly"]})
        schema.add_field("created_at", DataType.INT64, nullable=True)
        schema.add_field("context_sparse", DataType.SPARSE_FLOAT_VECTOR)
        schema.add_field("context_dense", DataType.FLOAT_VECTOR, dim=DENSE_DIM)

        schema.add_function(Function(
            name="text_bm25_emb",
            input_field_names=["context_text"],
            output_field_names=["context_sparse"],
            function_type=FunctionType.BM25,
        ))

        index_params = self.client.prepare_index_params()
        index_params.add_index(field_name="context_sparse", index_type="SPARSE_INVERTED_INDEX",
                               metric_type="BM25")
        index_params.add_index(field_name="context_dense", index_type="AUTOINDEX", metric_type="IP")

        self.client.create_collection(self.collection_name, schema=schema, index_params=index_params)
        logger.info(f"Collection '{self.collection_name}' created")

    async def save_summary_vector(self, context_text: str, user_id: int = None,
                                   session_id: str = None, summary_id: str = None):
        if not context_text or not context_text.strip():
            return
        dense = embedding_model.embed_query(context_text)
        data = {
            "summary_id": summary_id, "user_id": user_id, "session_id": session_id,
            "context_text": context_text, "created_at": int(time.time()),
            "context_dense": dense,
        }
        self.client.insert(self.collection_name, [data])

    async def hybrid_search(self, query: str, session_id: str = None,
                            user_id: int = None, top_k: int = 5) -> List[Dict[str, Any]]:
        dense = embedding_model.embed_query(query)

        filters = []
        if session_id:
            filters.append(f'session_id == "{session_id}"')
        if user_id:
            filters.append(f"user_id == {user_id}")
        filter_expr = " and ".join(filters) if filters else ""

        sparse_req = AnnSearchRequest(data=[query], anns_field="context_sparse",
                                      param={"metric_type": "BM25"}, limit=top_k)
        dense_req = AnnSearchRequest(data=[dense], anns_field="context_dense",
                                     param={"metric_type": "IP"}, limit=top_k)

        kwargs = {
            "collection_name": self.collection_name,
            "reqs": [sparse_req, dense_req],
            "ranker": RRFRanker(), "limit": top_k,
            "output_fields": ["summary_id", "user_id", "session_id", "context_text", "created_at"],
        }
        if filter_expr:
            kwargs["filter"] = filter_expr

        results = self.client.hybrid_search(**kwargs)

        formatted = []
        for hits in results:
            for hit in hits:
                formatted.append({
                    "score": hit.get("distance", 0),
                    "session_id": hit.get("entity", {}).get("session_id"),
                    "created_at": hit.get("entity", {}).get("created_at", 0),
                    "context_text": hit.get("entity", {}).get("context_text", ""),
                    "summary_id": hit.get("entity", {}).get("summary_id"),
                })
        return formatted

    def get_collection_stats(self):
        return self.client.get_collection_stats(self.collection_name)


_instance: Optional[SummaryMilvusService] = None


def get_summary_milvus_service() -> SummaryMilvusService:
    global _instance
    if _instance is None:
        _instance = SummaryMilvusService()
    return _instance


async def check_milvus_connection() -> bool:
    try:
        svc = get_summary_milvus_service()
        svc.client.has_collection(svc.collection_name)
        logger.info("Milvus connection OK")
        return True
    except Exception as e:
        logger.error(f"Milvus connection failed: {e}")
        return False
