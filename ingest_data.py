import sys

from config import *
from utils import reset_indexes, ingest_list_of_entities
from log_config import log



if __name__ == "__main__":
    if "--reset-indexes" in sys.argv:
        reset_indexes(entities_to_ingest)

    # we need to increase the number of fields in elasticsearch for institutions
    if client.indices.exists(index="institutions"):
        client.indices.put_settings(index="institutions", settings={"mapping.total_fields.limit": 2000})

    ingest_list_of_entities()


