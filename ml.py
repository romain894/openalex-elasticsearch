import os
from sentence_transformers import SentenceTransformer
import torch
from dotenv import load_dotenv
from log_config import log

load_dotenv()  # take environment variables from .env.

text_encoding_model_name = os.getenv('TEXT_ENCODING_MODEL_NAME')

# Load or create a SentenceTransformer model.
model = SentenceTransformer(text_encoding_model_name)

if torch.cuda.is_available():
    model = model.to(torch.device("cuda"))
log.info(model.device)

def encode_text_document(document):
    embedding = model.encode(document, show_progress_bar=False)
    # log.debug(f"Vector dimension: {len(embedding)}")
    # print(document)
    return embedding