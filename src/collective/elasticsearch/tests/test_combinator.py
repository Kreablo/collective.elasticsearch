
import unittest
from collective.elasticsearch.combinator import Query
from copy import deepcopy


class SomeTest(unittest.TestCase):
    def test_combine_query(self):
        a = Query({"match": "a"}, {"a"})
        b = Query({"match": "b"}, {"b", "b0"})

        c = a | b

        self.assertEqual(c.indicies, {"a", "b", "b0"})

        self.assertEqual(a.body, {
            "query": {
                "match": "a"
            }
        })

        self.assertEqual(b.body, {
            "query": {
                "match": "b"
            }
        })

        self.maxDiff = None

        # The indicies are sets so we must sort the list for the test
        # to succeed consistently.  The order in the query should not
        # matter, so we only sort the list for the test.

        cbody = deepcopy(c.body)
        s = cbody["query"]["dis_max"]["queries"][1]["bool"]["filter"]["bool"]["should"]
        s = sorted(s, key=lambda t: t["term"]["_index"])
        cbody["query"]["dis_max"]["queries"][1]["bool"]["filter"]["bool"]["should"] = s

        self.assertEqual(cbody, {
            "query": {
                "dis_max": {
                    "queries": [
                        {
                            "bool": {
                                "must": [{"match": "a"}],
                                "filter": {"term": {"_index": "a"}}
                            }
                        },
                        {
                            "bool": {
                                "must": [{"match": "b"}],
                                "filter": {
                                    "bool": {
                                        "should": [
                                            {"term": {"_index": "b"}},
                                            {"term": {"_index": "b0"}}
                                        ]}
                                    }
                            }
                        }
                    ]
                }
            }
        })

        d = Query({"match": "d"}, {"d"})

        e = c | d

        ebody = deepcopy(e.body)
        s = ebody["query"]["dis_max"]["queries"][1]["bool"]["filter"]["bool"]["should"]
        s = sorted(s, key=lambda t: t["term"]["_index"])
        ebody["query"]["dis_max"]["queries"][1]["bool"]["filter"]["bool"]["should"] = s

        self.assertEqual(ebody, {
            "query": {
                "dis_max": {
                    "queries": [
                        {
                            "bool": {
                                "must": [{"match": "a"}],
                                "filter": {"term": {"_index": "a"}}
                            }
                        },
                        {
                            "bool": {
                                "must": [{"match": "b"}],
                                "filter": {
                                    "bool": {
                                        "should": [
                                            {"term": {"_index": "b"}},
                                            {"term": {"_index": "b0"}}
                                        ]}
                                    }
                            }
                        },
                        {
                            "bool": {
                                "must": [{"match": "d"}],
                                "filter": {"term": {"_index": "d"}}
                            }
                        },
                    ]
                }
            }
        })

        self.assertEqual(e.indicies, {"a", "b", "b0", "d"})
