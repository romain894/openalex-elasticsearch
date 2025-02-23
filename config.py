import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
import importlib

load_dotenv()  # take environment variables from .env.

openalex_data_to_ingest_path = os.getenv('OPENALEX_DATA_TO_INGEST_PATH')
elasticsearch_url = os.getenv('ELASTICSEARCH_URL')
elasticsearch_index = os.getenv('ELASTICSEARCH_INDEX')
elastic_password = os.getenv('ELASTIC_PASSWORD')
elastic_ca_certs_path = os.getenv('CA_CERTS_PATH')
inference_chunk_size = int(os.getenv('INFERENCE_CHUNK_SIZE'))
ingestion_chunk_size = int(os.getenv('INGESTION_CHUNK_SIZE'))
ingestion_request_timeout = int(os.getenv('INGESTION_REQUEST_TIMEOUT'))

ingested_files_index = os.getenv('INGESTED_FILES_INDEX')
nb_ingestion_processes = int(os.getenv('NB_INGESTION_PROCESSES'))

api_create_embeddings_endpoint = os.getenv('API_CREATE_EMBEDDINGS_ENDPOINT')
ingestion_filter_file_path = os.getenv('INGESTION_FILTER_FILE_PATH')

ingestion_filter = importlib.import_module(ingestion_filter_file_path)

entities_to_ingest = [
    # "authors",
    # "concepts",
    # "domains",
    # "fields",
    # "funders",
    # "institutions",
    # "publishers",
    # "sources",
    # "subfields",
    # "topics",
    "works",
]

# Create the client instance
client = Elasticsearch(
    elasticsearch_url,
    ca_certs=os.path.join(elastic_ca_certs_path, "ca/ca.crt"),
    basic_auth=("elastic", elastic_password),
    # retry_on_status=[408, 502, 503, 504], # https://elasticsearch-py.readthedocs.io/en/7.x/connection.html
)