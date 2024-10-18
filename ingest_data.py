import os
import sys
import gzip
import json
from multiprocessing import Pool, Value
from datetime import datetime

from dotenv import load_dotenv
from elasticsearch import Elasticsearch

from log_config import log

load_dotenv()  # take environment variables from .env.

openalex_data_to_ingest_path = os.getenv('OPENALEX_DATA_TO_INGEST_PATH')
elasticsearch_url = os.getenv('ELASTICSEARCH_URL')
elasticsearch_index = os.getenv('ELASTICSEARCH_INDEX')
elastic_password = os.getenv('ELASTIC_PASSWORD')
elastic_ca_certs_path = os.getenv('CA_CERTS_PATH')

ingested_files_index = os.getenv('INGESTED_FILES_INDEX')

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


def get_dataset_relative_file_path(path):
    # Split the path into a list of folders
    folders = path.split(os.sep)
    # Keep only the last 3 folders
    folders = folders[-3:]
    # Join the folders back into a path
    new_path = os.sep.join(folders)
    return new_path



def ingest_document(index, data):
    try:
        client.index(
            index=index,
            id=data['id'][21:],
            document=data
        )
    except Exception as e:
        log.error(e)
        raise RuntimeError


def ingest_file(index, file_path):
    log.debug(f"Ingesting {file_path}...")
    ingestion_started = datetime.now()
    try:
        with gzip.open(file_path,'r') as f:
            # for each document (one work, one institution...)
            for line in f:
                ingest_document(index, json.loads(line))
        ingestion_finished = datetime.now()

        doc_ingested_file = {
            'file': str(get_dataset_relative_file_path(file_path)),
            'ingestion_started': ingestion_started,
            'ingestion_finished': ingestion_finished,
            'ingestion_duration_seconds': (ingestion_finished - ingestion_started).total_seconds(),
        }
        client.index(index=ingested_files_index, document=doc_ingested_file)
        log.debug(f"Ingested {file_path}...")
    except Exception as e:
        log.error(f"Failed to ingest file {file_path}")
        log.error(e)


if __name__ == "__main__":
    if "--reset-indexes" in sys.argv:
        for entity in entities_to_ingest:
            log.info(f"Resetting index: {entity}...")
            if client.indices.exists(index=entity):
                client.indices.delete(index=entity)
                client.indices.create(index=entity)

        log.info(f"Resetting the index with the ingested files: {ingested_files_index}...")
        if client.indices.exists(index=ingested_files_index):
            client.indices.delete(index=ingested_files_index)
            client.indices.create(index=ingested_files_index)


    if client.indices.exists(index="institutions"):
        client.indices.put_settings(index="institutions", settings={"mapping.total_fields.limit": 2000})


    # for each entity (e.g. works, institutions...)
    for entity in entities_to_ingest:
        log.info(f"Ingesting {entity}...")
        # create an index for the documents if it doesn't already exist
        if not client.indices.exists(index=entity):
            client.indices.create(index=entity)
        nb_dir = len(os.listdir(os.path.join(openalex_data_to_ingest_path, entity)))
        log.info(f"{nb_dir} to ingest...")
        nb_dir_ingested = Value('i', 0)

        # for each updated date
        for updated_date_dir in os.listdir(os.path.join(openalex_data_to_ingest_path, entity)):
            log.debug(f"Ingesting directory: {entity}/{updated_date_dir}...")
            if os.path.isdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
                # for each gzip file
                for filename in os.listdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
                    ingest_file(entity, os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir, filename))
            with nb_dir_ingested.get_lock():
                nb_dir_ingested.value += 1
            log.debug(f"Done directory: {entity}/{updated_date_dir}.")
            log.info(f"Ingested {nb_dir_ingested.value} directories out of {nb_dir} ("
                     f"{nb_dir_ingested.value*100/nb_dir:.2f}%).")


        # with Pool(processes=1) as pool:
        #     results = pool.imap(ingest_dir, os.listdir(os.path.join(openalex_data_to_ingest_path, entity)))
        #     tuple(results)  # fetch the lazy results

        log.info(f"Done ingesting {entity}.")