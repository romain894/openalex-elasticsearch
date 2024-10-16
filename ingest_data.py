import os
from dotenv import load_dotenv
import gzip
import json

from log_config import log

load_dotenv()  # take environment variables from .env.

openalex_data_to_ingest_path = os.getenv('OPENALEX_DATA_TO_INGEST_PATH')

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

for entity in entities_to_ingest:
    log.info(f"Ingesting {entity}...")
    for updated_date_dir in os.listdir(os.path.join(openalex_data_to_ingest_path, entity)):
        if os.path.isdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
            for filename in os.listdir(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir)):
                log.debug(f"Ingesting {os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir, 
                                                    filename)}...")
                with gzip.open(os.path.join(openalex_data_to_ingest_path, entity, updated_date_dir, filename
                                            ),'r') as f:
                    for line in f:
                        print(json.loads(line))
