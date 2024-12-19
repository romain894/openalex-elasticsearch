import os
from datetime import datetime
import gzip
import json
from multiprocessing import Process, Value
import time
import requests

from elasticsearch.helpers import streaming_bulk

import config
from config import client, inference_chunk_size
from log_config import log


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


def invert_abstract(inv_index):
    if inv_index is not None:
        l_inv = [(w, p) for w, pos in inv_index.items() for p in pos]
        return " ".join(map(lambda x: x[0], sorted(l_inv, key=lambda x: x[1])))


def format_entity_data(entity, data):
    # needed to avoid the error: BadRequestError(400, 'illegal_argument_exception', 'mapper
    # [summary_stats.2yr_mean_citedness] cannot be changed from type [long] to [float]')
    # this fix is needed for authors and concepts
    if entity == "authors" or entity == "concepts":
        data['summary_stats']['2yr_mean_citedness'] = float(data['summary_stats']['2yr_mean_citedness'])
    if entity == "concepts":
        data['summary_stats']['oa_percent'] = float(data['summary_stats']['oa_percent'])
    if entity == "works":
        data['abstract'] = invert_abstract(data['abstract_inverted_index'])
        # fix errors in OpenAlex dataset
        if 'topics' in data.keys():
            for topic in data['topics']:
                if 'subfield' in topic.keys() and type(topic['subfield']['id']) is not str:
                    log.warning(f"Fixing format of topic subfield ({topic['subfield']['id']}) from int to str")
                    topic['subfield']['id'] = "https://openalex.org/subfield/" + str(topic['subfield']['id'])
                if 'field' in topic.keys() and type(topic['field']['id']) is not str:
                    log.warning(f"Fixing format of topic field ({topic['field']['id']}) from int to str")
                    topic['field']['id'] = "https://openalex.org/field/" + str(topic['field']['id'])
                if 'domain' in topic.keys() and type(topic['domain']['id']) is not str:
                    log.warning(f"Fixing format of topic domain ({topic['domain']['id']}) from int to str")
                    topic['domain']['id'] = "https://openalex.org/domains/" + str(topic['domain']['id'])
        if 'primary_topic' in data.keys() and data['primary_topic'] is not None:
            if 'subfield' in data['primary_topic'].keys() and type(data['primary_topic']['subfield']['id']) is not str:
                log.warning(f"Fixing format of primary_topic subfield ({data['primary_topic']['subfield']['id']}) from int to str")
                data['primary_topic']['subfield']['id'] = "https://openalex.org/subfield/" + str(data['primary_topic']['subfield']['id'])
            if 'field' in data['primary_topic'].keys() and type(data['primary_topic']['field']['id']) is not str:
                log.warning(f"Fixing format of primary_topic field ({data['primary_topic']['field']['id']}) from int to str")
                data['primary_topic']['field']['id'] = "https://openalex.org/field/" + str(data['primary_topic']['field']['id'])
            if 'domain' in data['primary_topic'].keys() and type(data['primary_topic']['domain']['id']) is not str:
                log.warning(f"Fixing format of primary_topic domain ({data['primary_topic']['domain']['id']}) from int to str")
                data['primary_topic']['domain']['id'] = "https://openalex.org/domain/" + str(data['primary_topic']['domain']['id'])
        del data['abstract_inverted_index']
        # the embeddings are computed and added later
    return data


def data_for_bulk_ingest(index, file_path):
    def yield_buff(buff):
        if len(buff) > 0:
            for k in range(len(buff)):
                yield {
                    "_index": index,
                    "_id":buff[k]['id'][21:],
                    # "_type": "doc",
                    "_source": buff[k]
                }

    def infer_chunk(buff):
        # infer the buffer before yielding it
        if index == "works":
            # create a list with the doc having an abstract to infer
            log.debug(f"Inferring {len(buff)} documents")
            buff_with_abstract = [doc for doc in inference_buff if doc['abstract'] is not None]
            log.debug(f"{len(buff_with_abstract)} documents with an abstract")
            # create a list with the doc not having an abstract to infer
            buff_without_abstract = [doc for doc in inference_buff if doc['abstract'] is None]
            log.debug(f"{len(buff_without_abstract)} documents without an abstract")
            # if there are abstracts to infer
            if len(buff_with_abstract) > 0:
                abstract_list = [doc['abstract'] for doc in buff_with_abstract]
                # infer the embeddings using the API
                abstracts_embeddings = requests.post(
                    url=config.api_create_embeddings_endpoint,
                    json=abstract_list
                ).json()
                abstracts_embeddings = [vec['vector'] for vec in abstracts_embeddings]
                # save the embeddings with the docs
                for j in range(len(buff_with_abstract)):
                    buff_with_abstract[j]['abstract_embeddings'] = abstracts_embeddings[j]
            # yield the data previously loaded and inferred
            yield from yield_buff(buff_with_abstract)
            yield from yield_buff(buff_without_abstract)
        else:
            yield from yield_buff(buff)

    with gzip.open(file_path,'r') as f:
        # we will read the file per inference chunk
        i_inferred = 0
        inference_buff = [None]*inference_chunk_size
        # for each document (one work, one institution...)
        i = 0 # counter of ingested documents
        ignored_doc = 0
        for line in f:
            # condition to start reading a new inference chunk
            if i_inferred <= i:
                i_inferred += inference_chunk_size
            # read the line from the json file and format the data
            entity = format_entity_data(index, json.loads(line))
            # check if the entity should be ingested based on the function written in the filter file specified in .env
            if config.ingestion_filter.ingest_entity(entity, index):
                # we index the entity
                # add the document in the buffer for later inference and increment the counter of ingested documents
                inference_buff[i%inference_chunk_size] = entity
                # if the buffer is full
                if i >= i_inferred - 1:
                    # infer the documents in the buffer
                    yield from infer_chunk(inference_buff)
                i += 1
            else:
                # we don't ingest the entity
                # we do nothing and don't increment the buffer counter of ingested documents
                ignored_doc += 1
        # crop the inference buff to keep only the last documents to infer
        inference_buff = [doc for j, doc in enumerate(inference_buff) if j <= i - 1]
        yield from infer_chunk(inference_buff)
        log.info(f"ingested {i} documents and ignored {ignored_doc} documents (based on the filter)")



def ingest_file_bulk(index, file_path, nb_running_processes = None):
    try:
        if get_if_file_already_ingested(str(get_dataset_relative_file_path(file_path))): # redundant now
            log.info(f"File already ingested: {str(get_dataset_relative_file_path(file_path))}")
        else:
            log.debug(f"Ingesting {file_path}...")
            ingestion_started = datetime.now()
            successes = 0
            errors = 0
            for status_ok, response in streaming_bulk(
                client=client,
                actions=data_for_bulk_ingest(index, file_path),
                raise_on_error=False,
                raise_on_exception=False,
                # max_retries=5,
                chunk_size=config.ingestion_chunk_size,
                request_timeout=config.ingestion_request_timeout,
            ):
                successes += status_ok
                if not status_ok:
                    log.error(response)
                    errors += 1
            # warning : this doesn't display the number of failed document ingestion
            log.info(f"Successfully indexed {successes} {index} documents with {errors} errors.")
            ingestion_finished = datetime.now()

            doc_ingested_file = {
                'file': str(get_dataset_relative_file_path(file_path)),
                'ingestion_started': ingestion_started,
                'ingestion_finished': ingestion_finished,
                'ingestion_duration_seconds': (ingestion_finished - ingestion_started).total_seconds(),
                'nb_successes': successes,
                'nb_errors': errors,
            }
            client.index(index=config.ingested_files_index, document=doc_ingested_file)
            log.debug(f"Ingested {file_path}...")
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
    the number of processes (threads) to use with the environment variables defined in the file .env. If the indexes
    don't already exist, they will be created

    :param entities_to_ingest: List of the entities to ingest into the Elasticsearch database. The entities strings must
    correspond to their folder names
    :param openalex_data_to_ingest_path: Path where the compressed (zipped) data to ingest is located. This path must
    correspond to the folder where you can find the folders of each entity (Works, Institutions...)
    :return:
    """
    # create the index for the ingested files if it doesn't already exist
    if not client.indices.exists(index=config.ingested_files_index):
        create_ingested_files_index()

    nb_running_processes = Value('i', 0)

    # for each entity (e.g. works, institutions...)
    for entity in entities_to_ingest:
        log.info(f"Ingesting {entity}...")
        # create an index for the documents if it doesn't already exist
        if not client.indices.exists(index=entity):
            create_index(entity)
        nb_dir = len(os.listdir(os.path.join(openalex_data_to_ingest_path, entity)))
        log.info(f"{nb_dir} to ingest...")
        nb_dir_ingested = Value('i', 0)

        # for each updated date, from the oldest to the most recent date
        for updated_date_dir in sorted(os.listdir(os.path.join(openalex_data_to_ingest_path, entity))):
            with nb_dir_ingested.get_lock():
                nb_dir_ingested.value += 1
            log.info(f"Staring ingesting directory: {entity}/{updated_date_dir} ({nb_dir_ingested.value} "
                     f"out of {nb_dir}) {nb_dir_ingested.value*100/nb_dir:.2f}%")
            if os.path.isdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
                # for each gzip file
                for filename in os.listdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
                    file_path = os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir, filename)
                    # skip if file already ingested (avoid starting the process)
                    if get_if_file_already_ingested(str(get_dataset_relative_file_path(file_path))):
                        log.info(f"File already ingested: {str(get_dataset_relative_file_path(file_path))}")
                    else:
                        # wait if too many processes are already running
                        while nb_running_processes.value >= config.nb_ingestion_processes:
                            time.sleep(0.01)
                        # increment the number of running processes
                        with nb_running_processes.get_lock():
                            nb_running_processes.value += 1
                        # start the process
                        Process(target=ingest_file_bulk, args=(
                            entity,
                            file_path,
                            nb_running_processes,
                        )).start()
            log.debug(f"Finished ingesting directory: {entity}/{updated_date_dir}.")
            # We need to ingest each date one by one to correctly ingest updated works in future dates
            while nb_running_processes.value > 0:
                time.sleep(0.1)


def create_index(index):
    if index == "authors":
        with open("authors_template.json") as f:
            authors_mapping = json.load(f)['template']['mappings']
        print(authors_mapping)
        client.indices.create(
            index=index,
            mappings=authors_mapping,
        )
    elif index == "works":
        with open("works_template.json") as f:
            works_template = json.load(f)['template']
            works_mapping = works_template['mappings']
            works_settings = works_template['settings']
        client.indices.create(
            index=index,
            settings=works_settings,
            mappings=works_mapping,
            request_timeout=100
        )
    else:
        client.indices.create(index=index)
    # we need to increase the number of fields in elasticsearch for institutions and concepts
    if index == "institutions" or index == "concepts":
        client.indices.put_settings(index=index, settings={"mapping.total_fields.limit": 2000})
    log.info(f"Created index: {index}.")


def create_ingested_files_index():
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
    log.info(f"Created index: {config.ingested_files_index}.")


def reset_indexes(
        entities_list: list[str] = config.entities_to_ingest,
        reset_ingested_files_index: bool = True
    ):
    """
    Reset the indexes (if they exist) storing the entities in the Elasticsearch database. By default, the index storing
    the indexed files (the zipped files in the raw dataset from OpenAlex) will be deleted.
    :param entities_list: List of indexed entities to reset.
    :param reset_ingested_files_index: Set to True to reset the index storing the indexed files (default is False).
    :return:
    """
    # TODO : fix reset_ingested_files_index
    for entity in entities_list:
        log.info(f"Resetting index: {entity}...")
        if client.indices.exists(index=entity):
            client.indices.delete(index=entity)
            log.info(f"Deleted index: {entity}.")
        create_index(entity)

    if reset_ingested_files_index:
        log.info(f"Resetting the index with the ingested files: {config.ingested_files_index}...")
        if client.indices.exists(index=config.ingested_files_index):
            client.indices.delete(index=config.ingested_files_index)
            log.info(f"Deleted index: {config.ingested_files_index}.")
        create_ingested_files_index()
