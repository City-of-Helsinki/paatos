import json
import os

import jsonschema
import yaml


class SchemaValidated(object):
    def __init__(self, *args, **kwargs):
        self._schema = None
        self.validate()
        super(SchemaValidated, self).__init__(*args, **kwargs)

    def validate(self):
        jsonschema.validate(json.loads(self.as_json()), self.schema)

    @property
    def schema(self):
        if self._schema is None:
            with open(self.schema_file_full_path, 'rb') as fp:
                self._schema = yaml.load(fp.read())
        return self._schema

    @property
    def schema_file_full_path(self):
        directory = os.path.dirname(__file__)
        return os.path.join(directory, self.schema_file)
