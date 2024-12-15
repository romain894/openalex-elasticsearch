import config
from config import client, inference_chunk_size
from log_config import log
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ml import encode_text_document


class Embedding(BaseModel):
    vector: list[float]


app = FastAPI()

origins = [
    # "http://localhost",
    # "http://localhost:5173",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/vector_knn_search")
def vector_knn_search(embedding: Embedding):
    """
    Retrieve the nearest neighbors of an embedding with a KNN search (fast but approximate).
    :param embedding: The embedding for the search.
    :return: The nearest embeddings.
    """
    resp = client.search(
        index="works",
        knn={
            "field": "abstract_embeddings",
            "query_vector": embedding.vector,
            "k": 10,
            "num_candidates": 5000
        }
    )
    res = [{
        "id": w["_source"]["id"],
        "display_name": w["_source"]["display_name"],
        "abstract": w["_source"]["abstract"],
    } for w in resp["hits"]["hits"]]
    return res


@app.post("/text_knn_search")
def text_knn_search(text: str):
    """
    Retrieve the similar abstracts with a KNN search (fast but approximate).
    :param text: The text for the search.
    :return: The similar abstracts.
    """
    text_embedding = Embedding(vector=encode_text_document(text))
    res = vector_knn_search(text_embedding)
    return res
