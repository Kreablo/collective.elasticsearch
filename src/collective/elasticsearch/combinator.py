"""Combinator type for combining queries

The combinator module exports the class Query which is used to combine
queries using disjoint-max.

:var QT: QT is a type for dictionaries containing query data
:var QTD: QTD is the content type of QT
:var T: T is a type variable over QTD

"""
from copy import deepcopy
from typing import Dict, Set, Union, List, Type, TypeVar


QTD = Union[str, int, float, List[str], List["QT"], "QT"]
QT = Dict[str, QTD]

T = TypeVar("T", str, List[str], List["QT"], "QT")


def cast(v: QTD, t: Type[T]) -> T:
    """Cast a value of type QTD to the given type T"""
    return v  # type: ignore


def _index_filter_term(t: str) -> QT:
    return {
        "term": {
            "_index": t
        }
    }


def _index_filter(indicies: Set[str]) -> QT:
    f = list(map(_index_filter_term, indicies))
    if len(f) == 0:
        return {}
    if len(f) == 1:
        return f[0]
    return {
        "bool": {
            "should": f
        }
    }


def _to_bool(q: QT) -> QT:
    if ("bool" in q.keys()):
        return q
    else:
        return {
            "bool": {
                "must": [q]
            }
        }


def _to_dis_max(q: "Query") -> QT:
    keys = q._query.keys()
    if "dis_max" in keys:
        return deepcopy(q._query)

    if ("queries" in keys):
        q0 = q._query.copy()
        b = cast(q0["bool"], QT)
        b["filter"] = q._index_filter()
    else:
        q0 = {
            "bool": {
                "must": [q._query],
                "filter": q._index_filter()
            }
        }

    return {
        "dis_max": {
            "queries": [
                q0
            ]
        }
    }


def _combine_dis_max(q1: "Query", q2: "Query") -> "Query":
    a = _to_dis_max(q1)
    b = _to_dis_max(q2)

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

    def __init__(self, query: QT, indicies: Set[str]):
        self._query = query
        self._query_params = {}  # type: Dict[str, str]
        self._indicies = indicies

    @property
    def body(self) -> QT:
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

    def _index_filter(self) -> QT:
        return _index_filter(self.indicies)

    def __or__(self, other: "Query") -> "Query":
        return _combine_dis_max(self, other)
