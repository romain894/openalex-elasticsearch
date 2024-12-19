def ingest_entity(entity: dict, entity_type: str):
    """
    Filter each entity to be ingested. Returns True is the entity is to be ingested.
    :param entity_type:
    :param entity:
    :return: whether the entity is to be ingested
    """
    if entity_type == "authors":
        return True
    if entity_type == "concepts":
        return True
    if entity_type == "domains":
        return True
    if entity_type == "fields":
        return True
    if entity_type == "funders":
        return True
    if entity_type == "institutions":
        return True
    if entity_type == "publishers":
        return True
    if entity_type == "sources":
        return True
    if entity_type == "subfields":
        return True
    if entity_type == "topics":
        return True
    if entity_type == "works":
        return True
    # return True if entity type unknown (aka filter is ignored)
    return True
