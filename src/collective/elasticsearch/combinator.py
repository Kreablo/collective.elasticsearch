"""Combinator type for combining queries

The combinator module exports the class Query which is used to combine
queries using disjoint-max.

:var QT: QT is a type for dictionaries containing query data
:var QTD: QTD is the content type of QT
:var T: T is a type variable over QTD

"""
from copy import deepcopy
from typing import Dict, Set, Union, List, Type, TypeVar, Optional


QTD = Union[str, int, float, List[str], List["QT"], "QT"]
QT = Dict[str, QTD]

T = TypeVar("T", str, List[str], List["QT"], "QT")


def cast(v: QTD, t: Type[T]) -> T:
    """Cast a value of type QTD to the given type T"""
    return v  # type: ignore


def _index_filter_term(t: List[str], qt: QT | None = None) -> QT | None:
    qtfilter = deepcopy(qt._query['bool'].get('filter', None)) if qt._query is not None and 'bool' in qt._query else None

    if len(t) == 0:
        return qtfilter

    result = None if qtfilter is None else qtfilter if isinstance(qtfilter, list) else [qtfilter]

    if len(t) == 1:
        t = {
            "term": {
                "_index": t[0]
            }
        }
    else:
        t = {
            "terms": {
                "_index": t
            }
        }

    if result is None:
        return t

    result.append(t)
    return result

def _index_filter(indicies: Set[str], qt: QT | None = None) -> QT | None:
    term = _index_filter_term(list(indicies), qt)
    if term is None:
        return None

    return term

def _bool_must(q: QT) -> QT:
    if ("bool" in q.keys() and isinstance(q['bool'], dict) and "must" in q['bool'].keys()):
        return deepcopy(q)
    else:
        return {
            "bool": {
                "must": [q]
            }
        }

def _bool_must_query(q: "Query") -> QT | None:

    if q._query is None:
        return None

    must: dict = _bool_must(q._query)
    filter = _index_filter(q.indicies, q)

    if filter is not None:
        must['bool']['filter'] = filter
    return must

def _bool_should(q: QT) -> QT:
    if ("bool" in q.keys() and isinstance(q['bool'], dict) and "should" in q['bool'].keys()):
        return deepcopy(q)
    else:
        return {
            "bool": {
                "minimum_should_match": 1,
                "should": [q]
            }
        }

def _to_bool_should(q: "Query") -> QT | None:
    must = _bool_must_query(q)

    if must is None:
        return None

    return _bool_should(must)

def _to_dis_max(q: "Query") -> QT | None:
    if q._query is None:
        return None
    keys = q._query.keys()
    if "dis_max" in keys:
        return deepcopy(q._query)

    filter = q._index_filter()
    q0: dict
    if ("queries" in keys):
        q0 = q._query.copy()
        b = cast(q0["bool"], QT)
        if filter is not None:
            b["filter"] = filter
    else:
        q0 = {
            "bool": {
                "must": [q._query]
            }
        }
        if filter is not None:
            q0["bool"]["filter"] = filter

    return {
        "dis_max": {
            "queries": [
                q0
            ]
        }
    }


def _combine_bool_should(q1: "Query", q2: "Query") -> "Query":

    a: Optional[dict] = _to_bool_should(q1)
    b: Optional[dict] = _to_bool_should(q2)

    if a is None:
        return q2

    if b is None:
        return q1

    should = a["bool"]["should"] + b["bool"]["should"]

    a["bool"]["should"] = should

    return Query(a, q1.indicies | q2.indicies)


def _combine_dis_max(q1: "Query", q2: "Query") -> "Query":
    a = _to_dis_max(q1)
    b = _to_dis_max(q2)

    if a is None:
        return q2

    if b is None:
        return q1

    aq = cast(a["dis_max"], QT)
    bq = cast(b["dis_max"], QT)

    aqs = cast(aq["queries"], List[QT])
    bqs = cast(bq["queries"], List[QT])

    res = Query(
        {
            "dis_max": {
                "queries": aqs + bqs
            }
        },
        q1.indicies | q2.indicies,
    )

    return res


class Query:

    """Datatype for representing and combining queries."""

    def __init__(self, query: Optional[QT], indicies: Set[str]):
        self._query = query
        self._query_params = {}  # type: Dict[str, str]
        self._indicies = indicies
        self._track_total_hits = None

    @property
    def body(self) -> Optional[QT]:
        if self._query is None:
            return None
        q = self._query.copy()
        return {"query": q}

    @property
    def query_params(self) -> dict:
        return self._query_params

    @property
    def indicies(self) -> Set[str]:
        return self._indicies

    def index_name(self) -> str:
        return ",".join(self._indicies)

    def _index_filter(self) -> QT | None:
        return _index_filter(self.indicies)

    def __or__(self, other: "Query") -> "Query":
        if self._query is None:
            return other

        return _combine_bool_should(self, other)
