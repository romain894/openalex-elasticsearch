#from cuml.manifold import UMAP # for NVIDIA GPU, needs CUDA drivers with CUDA capability 7.0 (RTX 20xx) or newer
from umap import UMAP
from elasticsearch.helpers import streaming_bulk
from rich.progress import Progress

from config import client
import config
from log_config import log
from utils import get_full_index

index = "works"

# get the embeddings from ElasticSearch
df = get_full_index(index=index, fields_to_export=['id', 'abstract_embeddings'])
df = df.dropna()
embeddings = df['abstract_embeddings'].to_list()
log.info(f"Number of embeddings for the dimensionality reduction: {len(embeddings)}")

# Reduce the dimensionality of the embeddings
log.info("Starting dimensionality reduction...")
umap_model = UMAP(n_components=2, n_neighbors=15, random_state=42, metric="cosine", verbose=True)
reduced_embeddings_2d = umap_model.fit_transform(embeddings)
log.info("Finished dimensionality reduction.")

log.info("Saving abstract_embeddings_2d to ElasticSearch...")
df['abstract_embeddings_2d'] = reduced_embeddings_2d.tolist()
# keep only id and abstract_embeddings_2d for ingestion into ElasticSearch
df = df[['id', 'abstract_embeddings_2d']]

def yield_data():
    with Progress(expand=True) as progress:
        task = progress.add_task(f"Ingesting abstract_embeddings_2d...", total=len(df.index))
        for row in df.to_dict(orient="records"):
            progress.update(task, advance=1)
            yield {
                "_index": index,
                "_id":row['id'][21:],
                # "_type": "doc",
                "_source": {'doc': row},
                "_op_type": "update"
            }

successes = 0
errors = 0
for status_ok, response in streaming_bulk(
    client=client,
    actions=yield_data(),
    raise_on_error=False,
    raise_on_exception=False,
    # max_retries=5,
    chunk_size=config.ingestion_chunk_size,
    # request_timeout=config.ingestion_request_timeout, # DeprecationWarning: Passing transport options in the API
                                                        # method is deprecated. Use 'Elasticsearch.options()' instead.
):
    successes += status_ok
    if not status_ok:
        log.error(response)
        errors += 1
# warning : this doesn't display the number of failed document ingestion
log.info(f"Successfully indexed {successes} {index} documents with {errors} errors.")
