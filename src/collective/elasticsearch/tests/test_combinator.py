
import unittest
from collective.elasticsearch.combinator import Query


class SomeTest(unittest.TestCase):
    def test_combine_query(self):
        a = Query({"match": "a"}, {"a"}, {"a"})
        b = Query({"match": "b"}, {"b", "b0"}, {"a"})

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

        self.assertEqual(c.body, {
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

        d = Query({"match": "d"}, {"d"}, {"d"})

        e = c | d

        self.assertEqual(e.body, {
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

