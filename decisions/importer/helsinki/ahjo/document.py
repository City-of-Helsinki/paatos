import datetime
import json

from .schema_validated import SchemaValidated


class Document(SchemaValidated):
    schema_file = 'document-schema.yaml'

    def __init__(self, data=None, errors=None):
        self._data = data or {}
        self._errors = errors or []
        super(Document, self).__init__()

    def as_dict(self):
        return {
            'document': self._data,
            'errors': self._errors,
        }

    def as_json(self):
        # https://stackoverflow.com/a/22238613

        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""

            if isinstance(obj, (datetime.datetime, datetime.date)):
                serial = obj.isoformat()
                return serial
            raise TypeError("Type %s not serializable" % type(obj))

        ret = self.as_dict()

        return json.dumps(ret, indent=4, ensure_ascii=False, default=json_serial)
