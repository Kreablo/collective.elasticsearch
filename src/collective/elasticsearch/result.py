from Acquisition import aq_base
from Acquisition import aq_get
from Acquisition import aq_parent
from collective.elasticsearch import interfaces
from collective.elasticsearch.interfaces import IBrainFactory
from collective.elasticsearch.interfaces import IQueryExtender
from collective.elasticsearch.interfaces import SortOrder
from functools import reduce
from Products.ZCatalog.interfaces import ICatalogBrain
from zope.component import getMultiAdapter
from zope.component import subscribers
from zope.globalrequest import getRequest
from zope.interface import implementer
from ZPublisher.BaseRequest import RequestContainer
from collections.abc import Iterable, Callable
import logging
logger = logging.getLogger(__name__)


@implementer(ICatalogBrain)
class ElasticSearchBrain:
    """A Brain containing only information indexed in ElasticSearch."""

    def __init__(self, record: dict, catalog, source):
        self._record = record
        self._catalog = catalog
        self._source = source

    def has_key(self, key):
        return key in self._record

    def __contains__(self, name):
        return name in self._record

    def __getattr__(self, name):
        if name == "EffectiveDate":
            name0 = "effective"
        elif name == "ModificationDate":
            name0 = "modified"
        else:
            name0 = name

        if not self.__contains__(name0):
            raise AttributeError(
                f"'ElasticSearchBrain' object has no attribute '{name}'"
            )
        return self._record[name0]

    def getPath(self):
        """Get the physical path for this record"""
        return self._record["path"]["path"]

    def getURL(self, relative=0):
        """Generate a URL for this record"""
        request = getRequest()
        return request.physicalPathToURL(self.getPath(), relative)

    def getObject(self, REQUEST=None):
        path = self.getPath().split("/")
        if not path:
            return None
        parent = aq_parent(self._catalog)
        if aq_get(parent, "REQUEST", None) is None:
            request = getRequest()
            if request is not None:
                # path should be absolute, starting at the physical root
                parent = self.getPhysicalRoot()
                request_container = RequestContainer(REQUEST=request)
                parent = aq_base(parent).__of__(request_container)
        if len(path) > 1:
            parent = parent.unrestrictedTraverse(path[:-1])

        obj = parent.restrictedTraverse(path[-1])

        return obj

    def getRID(self) -> int:
        """Return the record ID for this object."""
        return -1

@implementer(IBrainFactory)
class BrainFactory:
    def __init__(self, manager):
        self._manager = manager

    def __call__(self, result):
        manager = self._manager
        source = None
        if "fields" in result.keys():
            path = result.get("fields", {}).get("path.path", None)
        elif "_source" in result.keys():
            # source = result.get("_source")
            # path = source.get("path", {}).get("path")
            # All information is already in the source field, no need
            # to reload the record from ElasticSearch.  Instead, use
            # the _source field directly.
            brain = ElasticSearchBrain(record=result.get("_source"),
                                       catalog=manager.catalog,
                                       source=None)
            if manager.highlight and result.get("highlight"):
                fragments = []
                fraglen = 0
                for idx, i in enumerate(result["highlight"].get("SearchableText", [])):
                    fraglen += len(i)
                    if idx > 0 and fraglen > manager.highlight_threshold:
                        break
                    fragments.append(i)
                brain["Description"] = " ... ".join(fragments)
            return brain

        if type(path) in (list, tuple, set) and len(path) > 0:
            path = path[0]
        if path:
            result = manager.get_record_by_path(path)
            brain = ElasticSearchBrain(record=result, catalog=manager.catalog, source=source)
            if manager.highlight and result.get("highlight"):
                fragments = []
                fraglen = 0
                for idx, i in enumerate(result["highlight"].get("SearchableText", [])):
                    fraglen += len(i)
                    if idx > 0 and fraglen > manager.highlight_threshold:
                        break
                    fragments.append(i)
                brain["Description"] = " ... ".join(fragments)
            return brain
        # We should handle cases where there is no path in the ES response
        return None


class ElasticResult:
    def __init__(self, manager, query, limits, **query_params):
        assert "sort" not in query_params
        assert "start" not in query_params
        self.manager = manager
        self.bulk_size = manager.bulk_size
        qassembler = getMultiAdapter(
            (getRequest(), manager), interfaces.IQueryAssembler
        )
        dquery, sort = qassembler.normalize(query)
        q0 = interfaces.Query(qassembler(dquery, limits, sort),
                              {manager.index_name})

        qes = subscribers([q0], IQueryExtender)

        eqs = [et(dquery, limits, sort) for et in qes]

        self.sort: SortOrder = reduce(lambda s, eq: eq.transform_sort(s),
                                      filter(lambda eq: callable(
                                          getattr(eq, 'transform_sort', None)),
                                             qes),
                                      sort)

        self.query = reduce(lambda q1, q2: q1 | q2, eqs, q0)
        if self.query.body is None:
            self.no_applicable_index = True
            result = {
                "hits": {
                    "hits": [],
                    "total": {
                        "value": 0,
                        "relation": "eq"
                    }
                }
            }
        else:
            # self.query = eqs[0]

            # results are stored in a dictionary, keyed
            # but the start index of the bulk size for the
            # results it holds. This way we can skip around
            # for result data in a result object
            result = manager._search(self.query,
                                     sort=self.sort,
                                     **query_params)
        hits = result["hits"]
        self.aggregations = result.get("aggregations", None)
        self.results = {0: hits["hits"]}
        self.count = hits["total"]["value"]
        self.count_relation = hits["total"]["relation"]
        self.query_params = query_params

    def __len__(self):
        return self.count

    def __getitem__(self, key):
        """
        Lazy loading es results with negative index support.
        We store the results in buckets of what the bulk size is.
        This is so you can skip around in the indexes without needing
        to load all the data.
        Example(all zero based indexing here remember):
            (525 results with bulk size 50)
            - self[0]: 0 bucket, 0 item
            - self[10]: 0 bucket, 10 item
            - self[50]: 50 bucket: 0 item
            - self[55]: 50 bucket: 5 item
            - self[352]: 350 bucket: 2 item
            - self[-1]: 500 bucket: 24 item
            - self[-2]: 500 bucket: 23 item
            - self[-55]: 450 bucket: 19 item
        """
        bulk_size = self.bulk_size
        count = self.count
        if isinstance(key, slice):
            return [self[i] for i in range(key.start, key.end)]
        if key + 1 > count:
            raise IndexError
        if key < 0 and abs(key) > count:
            raise IndexError
        if key >= 0:
            result_key = int(key / bulk_size) * bulk_size
            start = result_key
            result_index = key % bulk_size
        elif key < 0:
            last_key = int(count / bulk_size) * bulk_size
            last_key = last_key if last_key else count
            start = result_key = int(last_key - ((abs(key) / bulk_size) * bulk_size))
            if last_key == result_key:
                result_index = key
            else:
                result_index = (key % bulk_size) - (bulk_size - (count % last_key))
        if result_key not in self.results:
            results = self.manager._search(
                self.query, sort=self.sort, start=start, **self.query_params
            )
            aggregations = results.get("aggregations", None)
            if aggregations is not None:
                self.aggregations = aggregations
            self.results[result_key] = results["hits"]["hits"]
        return self.results[result_key][result_index]
