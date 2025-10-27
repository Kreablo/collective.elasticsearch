from collective.elasticsearch.compat import indices_create
from collective.elasticsearch.indexes import getIndex
from collective.elasticsearch.interfaces import IMappingProvider
from zope.interface import implementer


@implementer(IMappingProvider)
class MappingAdapter:
    _default_mapping = {
        "SearchableText": {"store": False, "type": "text", "index": True},
        "Title": {"store": True, "type": "text", "index": True},
        "Description": {"store": True, "type": "text", "index": True},
        "allowedRolesAndUsers": {"store": True, "type": "keyword", "index": True},
        "portal_type": {"store": True, "type": "keyword", "index": True},
    }

    _search_attributes = [
        "Title",
        "Description",
        "Subject",
        "contentType",
        "created",
        "modified",
        "effective",
        "hasImage",
        "is_folderish",
        "portal_type",
        "review_state",
        "path.path",
    ]

    def __init__(self, request, manager):
        self.request = request
        self.manager = manager
        self.catalog = manager.catalog._catalog

    def get_index_creation_body(self):  # NOQA E0211
        return {}

    def __call__(self):
        properties = self._default_mapping.copy()
        for name in self.catalog.indexes.keys():
            index = getIndex(self.catalog, name)
            if index is not None:
                properties[name] = index.create_mapping(name)
            else:
                raise Exception(f"Can not locate index for {name}")

        for key in properties:
            if key in self._search_attributes:
                properties[key]["store"] = True

        properties["attachments"] = {
            "properties": {
                "data": {"type": "binary"},
                "filename": {"type": "text"},
                "fieldname": {"type": "text"},
            }
        }

        return {"properties": properties}
