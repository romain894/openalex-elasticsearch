import os
from datetime import datetime
import gzip
import json
from multiprocessing import Process, Value
import time

import config
from config import client
from log_config import log
from elasticsearch.helpers import streaming_bulk


def get_dataset_relative_file_path(path):
    # Split the path into a list of folders
    folders = path.split(os.sep)
    # Keep only the last 3 folders
    folders = folders[-3:]
    # Join the folders back into a path
    new_path = os.sep.join(folders)
    return new_path


def get_if_file_already_ingested(file_path: str):
    resp = client.search(
        index=config.ingested_files_index,
        query={
            "match": {
                "file": file_path
            }
        },
    )
    if resp['hits']['total']['value'] == 0:
        return False
    elif resp['hits']['total']['value'] > 1:
        log.error(f"The file {file_path} was ingested multiple times ({resp['hits']['total']['value']})")
    return True


def format_entity_data(entity, data):
    # needed to avoid the error: BadRequestError(400, 'illegal_argument_exception', 'mapper
    # [summary_stats.2yr_mean_citedness] cannot be changed from type [long] to [float]')
    if entity == "authors":
        data['summary_stats']['2yr_mean_citedness'] = float(data['summary_stats']['2yr_mean_citedness'])
    return data


def data_for_bulk_ingest(index, file_path):
    with gzip.open(file_path,'r') as f:
        # for each document (one work, one institution...)
        for line in f:
            data = format_entity_data(index, json.loads(line))
            yield {
                "_index": index,
                "_id":data['id'][21:],
                # "_type": "doc",
                "_source": data
            }


def ingest_file_bulk(index, file_path, nb_running_processes = None):
    if get_if_file_already_ingested(str(get_dataset_relative_file_path(file_path))):
        log.info(f"File already ingested: {str(get_dataset_relative_file_path(file_path))}")
    else:
        log.debug(f"Ingesting {file_path}...")
        ingestion_started = datetime.now()
        successes = 0
        for status_ok, response in streaming_bulk(
            client=client,
            actions=data_for_bulk_ingest(index, file_path),
            # max_retries=5,
            chunk_size=200,
            request_timeout=1000,
        ):
            successes += status_ok
            if not status_ok:
                print(response)
        # warning : this doesn't display the number of failed document ingestion
        log.info("Indexed %d documents (%s)." % (successes, index))
        ingestion_finished = datetime.now()

        doc_ingested_file = {
            'file': str(get_dataset_relative_file_path(file_path)),
            'ingestion_started': ingestion_started,
            'ingestion_finished': ingestion_finished,
            'ingestion_duration_seconds': (ingestion_finished - ingestion_started).total_seconds(),
        }
        client.index(index=config.ingested_files_index, document=doc_ingested_file)
        log.debug(f"Ingested {file_path}...")
    try:
        pass
    except Exception as e:
        log.error(f"Failed to ingest file {file_path}")
        log.error(e)
    finally:
        if nb_running_processes is not None:
            # increment the number of running processes
            with nb_running_processes.get_lock():
                nb_running_processes.value -= 1


def ingest_list_of_entities(
        entities_to_ingest: list[str] = config.entities_to_ingest,
        openalex_data_to_ingest_path: str = config.openalex_data_to_ingest_path
    ):
    """
    Ingest a list of entities into an Elasticsearch database. This optimized to use multiprocessing, you can configure
    the number of processes (threads) to use with the environment variables defined in the file .env.

    :param entities_to_ingest: List of the entities to ingest into the Elasticsearch database. The entities strings must
    correspond to their folder names
    :param openalex_data_to_ingest_path: Path where the compressed (zipped) data to ingest is located. This path must
    correspond to the folder where you can find the folders of each entity (Works, Institutions...)
    :return:
    """
    nb_running_processes = Value('i', 0)

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
            with nb_dir_ingested.get_lock():
                nb_dir_ingested.value += 1
            log.debug(f"Staring ingesting directory: {entity}/{updated_date_dir}.")
            log.info(f"Staring ingesting the directory {nb_dir_ingested.value} out of {nb_dir} ("
                     f"{nb_dir_ingested.value*100/nb_dir:.2f}%).")
            if os.path.isdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
                # for each gzip file
                for filename in os.listdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
                    # wait if too many processes are already running
                    while nb_running_processes.value >= config.nb_ingestion_processes:
                        time.sleep(0.01)
                    # increment the number of running processes
                    with nb_running_processes.get_lock():
                        nb_running_processes.value += 1
                    # start the process
                    Process(target=ingest_file_bulk, args=(
                        entity,
                        os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir, filename),
                        nb_running_processes,
                    )).start()


        while nb_running_processes.value > 0:
            time.sleep(0.1)


def reset_indexes(
        entities_list: list[str] = config.entities_to_ingest,
        reset_ingested_files_index: bool = True
    ):
    """
    Reset the indexes (if they exist) storing the entities in the Elasticsearch database. By default, the index storing
    the indexed files (the zipped files in the raw dataset from OpenAlex) will be deleted.
    :param entities_list: List of indexed entities to reset.
    :param reset_ingested_files_index: Set to False to not reset the index storing the indexed files.
    :return:
    """
    for entity in entities_list:
        log.info(f"Resetting index: {entity}...")
        if client.indices.exists(index=entity):
            client.indices.delete(index=entity)
            if entity == "authors":
                with open("authors_template.json") as f:
                    authors_mapping = json.load(f)['template']['mappings']
                print(authors_mapping)
                resp = client.indices.create(
                    index=entity,
                    mappings=authors_mapping,
                )
                print(resp)
            else:
                client.indices.create(index=entity)

    if reset_ingested_files_index:
        log.info(f"Resetting the index with the ingested files: {config.ingested_files_index}...")
        if client.indices.exists(index=config.ingested_files_index):
            client.indices.delete(index=config.ingested_files_index)
            # as the file paths contain special characters and as we want to be able to match the exact string, we set
            # the analyzer to keyword for the field file.
            resp = client.indices.create(
                index=config.ingested_files_index,
                mappings={
                    "properties": {
                        "file": {
                            "type": "text",
                            "analyzer": "keyword"
                        }
                    }
                },
            )
