import os
from sentence_transformers import SentenceTransformer
import torch
from dotenv import load_dotenv
from log_config import log

load_dotenv()  # take environment variables from .env.

text_encoding_model_name = os.getenv('TEXT_ENCODING_MODEL_NAME')
text_encoding_torch_dtype = os.getenv('TEXT_ENCODING_TORCH_DTYPE')
# Load or create a SentenceTransformer model.
model = SentenceTransformer(text_encoding_model_name, model_kwargs={"torch_dtype": text_encoding_torch_dtype})

if torch.cuda.is_available():
    model = model.to(torch.device("cuda"))
log.debug(model.device)

def encode_text_document(document):
    """
    Infer a document or a list of documents.
    :param document: str | list[str]
    :return: str | list[str]
    """
    embedding = model.encode(document, show_progress_bar=False)
    # log.debug(f"Vector dimension: {len(embedding)}")
    # print(document)
    return embedding