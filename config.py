import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()  # take environment variables from .env.

openalex_data_to_ingest_path = os.getenv('OPENALEX_DATA_TO_INGEST_PATH')
elasticsearch_url = os.getenv('ELASTICSEARCH_URL')
elasticsearch_index = os.getenv('ELASTICSEARCH_INDEX')
elastic_password = os.getenv('ELASTIC_PASSWORD')
elastic_ca_certs_path = os.getenv('CA_CERTS_PATH')

ingested_files_index = os.getenv('INGESTED_FILES_INDEX')
nb_ingestion_processes = int(os.getenv('NB_INGESTION_PROCESSES'))

entities_to_ingest = [
    "authors",
    # "concepts",
    # "domains",
    # "fields",
    # "funders",
    # "institutions",
    # "publishers",
    # "sources",
    # "subfields",
    # "topics",
    # "works",
]

# Create the client instance
client = Elasticsearch(
    elasticsearch_url,
    ca_certs=os.path.join(elastic_ca_certs_path, "ca/ca.crt"),
    basic_auth=("elastic", elastic_password)
)