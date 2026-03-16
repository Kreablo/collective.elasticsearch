from collective.elasticsearch.indexes import EZCTextIndex
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.interfaces import IQueryAssembler, SortOrder
from collective.elasticsearch.combinator import Query
from collective.elasticsearch.utils import getESOnlyIndexes, sort_order_fields
from zope.interface import implementer
from collections.abc import Set, Mapping


_search_attributes: Set[str] = {
    "Subject",
    "contentType",
    "portal_type",
    "review_state",
    "plone-tags",
    "plone-webcontent"
}

_sort_attributes: Set[str] = {
    "sortable_title",
    "effective",
}


@implementer(IQueryAssembler)
class QueryAssembler:

    def __init__(self, request, es):
        self.es = es
        self.catalog = es.catalog
        self.request = request

    def normalize(self, query):  # NOQA R0201
        sort_on = []
        sort = query.pop("sort_on", None)
        # default plone is ascending
        sort_order = query.pop("sort_order", "asc")
        if sort_order in ("descending", "reverse", "desc"):
            sort_order = "desc"
        else:
            sort_order = "asc"

        if sort:
            for sort_str in sort.split(","):
                sort_on.append({sort_str: sort_order})
        sort_on.append("_score")
        if "b_size" in query:
            del query["b_size"]
        if "b_start" in query:
            del query["b_start"]
        if "sort_limit" in query:
            del query["sort_limit"]
        return query, sort_on


    def __call__(self, dquery: Query,
                 limits: Mapping[str, Set[str]], sort: SortOrder) -> Query:

        filters = []

        for limit in limits.keys():
            if limit not in _search_attributes:
                return None

            terms = limits.get(limit)

            if limit == 'plone-tags':
                limit = 'Subject'
            elif limit == 'plone-webcontent':
                if len(terms) != 1:
                    return None
                val = terms.pop()
                if val == '0':
                    del limits['plone-webcontent']
                    return None
                continue

            if terms is None:
                pass
            elif len(terms) > 1:
                filters.append({'terms': {limit: list(terms)}})
            elif len(terms) == 1:
                filters.append({'term': {limit: list(terms)[0]}})

        for s in sort_order_fields(sort):
            if s not in _sort_attributes:
                return None

        matches = []
        catalog = self.catalog._catalog
        idxs = catalog.indexes.keys()
        query = {"match_all": {}}
        es_only_indexes = getESOnlyIndexes()
        for key, value in dquery.items():
            if key not in idxs and key not in es_only_indexes:
                continue
            index = getIndex(catalog, key)
            if index is None and key in es_only_indexes:
                # deleted index for plone performance but still need on ES
                index = EZCTextIndex(catalog, key)
            qq = index.get_query(key, value)
            if qq is None:
                continue
            if index is not None and index.filter_query:
                if isinstance(qq, list):
                    filters.extend(qq)
                else:
                    filters.append(qq)
            else:
                if isinstance(qq, list):
                    matches.extend(qq)
                else:
                    matches.append(qq)

        if len(filters) == 0 and len(matches) == 0:
            return query
        query = {"bool": {}}
        if len(filters) > 0:
            query["bool"]["filter"] = filters

        if len(matches) > 0:
            query["bool"]["should"] = matches
            query["bool"]["minimum_should_match"] = 1

        return query
