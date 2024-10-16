import os
import sys
import gzip
import json
from multiprocessing import Pool

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

from log_config import log

load_dotenv()  # take environment variables from .env.

openalex_data_to_ingest_path = os.getenv('OPENALEX_DATA_TO_INGEST_PATH')
elasticsearch_url = os.getenv('ELASTICSEARCH_URL')
elasticsearch_index = os.getenv('ELASTICSEARCH_INDEX')
elastic_password = os.getenv('ELASTIC_PASSWORD')
elastic_ca_certs_path = os.getenv('CA_CERTS_PATH')

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
    "topics",
    # "works",
]


# Create the client instance
client = Elasticsearch(
    elasticsearch_url,
    ca_certs=os.path.join(elastic_ca_certs_path, "ca/ca.crt"),
    basic_auth=("elastic", elastic_password)
)

if "--reset-indexes" in sys.argv:
    for entity in entities_to_ingest:
        log.info(f"Resetting index: {entity}...")
        client.indices.delete(index=entity)
        client.indices.create(index=entity)


def ingest_single_document(iterator):
    index = iterator[0]
    data = iterator[1]
    client.index(
        index=index,
        id=data['id'][21:],
        document=data
    )

for entity in entities_to_ingest:
    log.info(f"Ingesting {entity}...")
    # create an index for the documents if it doesn't already exist
    if not client.indices.exists(index=entity):
        client.indices.create(index=entity)
    for updated_date_dir in os.listdir(os.path.join(openalex_data_to_ingest_path, entity)):
        if os.path.isdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
            for filename in os.listdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
                log.debug(f"Ingesting {os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir, 
                                                    filename)}...")
                with gzip.open(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir, filename
                                            ),'r') as f:
                    for line in f:
                        # print(json.loads(line))
                        ingest_single_document([entity, json.loads(line)])
    log.info(f"Done ingesting {entity}.")