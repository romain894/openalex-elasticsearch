import sys

from config import *
from utils import reset_indexes, create_index, ingest_list_of_entities
from log_config import log



if __name__ == "__main__":
    if "--reset-indexes" in sys.argv:
        reset_indexes(entities_to_ingest)
    else:
        for entity in entities_to_ingest:
            if client.indices.exists(index=entity):
                log.info(f"Index {entity} already exists.")
            else:
                log.info(f"Index {entity} doesn't already exists.")
                create_index(entity)

    ingest_list_of_entities()


