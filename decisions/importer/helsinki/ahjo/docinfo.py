import logging
import re
import zipfile

from django.utils.functional import cached_property

from .document import AhjoDocument
from .http_file import HttpFetchedFile
from .parse_dirlist import parse_file_path

LOG = logging.getLogger(__name__)


class _DocumentInfoDataProperty(object):
    def __init__(self, name):
        self.name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return instance._data[self.name]


class DocumentInfo(object):
    def __init__(self, dir_entry, base_url, tz):
        """
        Initialize document info from directory entry.

        :type dir_entry: .parse_dirlist.DirEntry
        :type base_url: str
        :type tz: pytz.tzinfo.DstTzInfo|pytz.tzinfo.StaticTzInfo
        """
        self.dir_entry = dir_entry
        self.base_url = base_url
        self.tz = tz
        self.path = dir_entry.href
        self.url = base_url + self.path
        self._data = self._parse_path(self.path)

    def _parse_path(self, path):
        data = parse_file_path(path)
        if not data:
            raise ValueError("Invalid filename: {}".format(path))
        if not data.get('language'):
            LOG.debug("Language field missing in %s", path)
            data['language'] = 'Su'
        return data

    def __repr__(self):
        return '<DocumentInfo: {}>'.format(self.path)

    org = _DocumentInfoDataProperty('org')
    date = _DocumentInfoDataProperty('date')
    policymaker = _DocumentInfoDataProperty('policymaker')
    meeting_nr = _DocumentInfoDataProperty('meeting_nr')
    doc_type_id = _DocumentInfoDataProperty('doc_type_id')
    language = _DocumentInfoDataProperty('language')
    year = _DocumentInfoDataProperty('year')
    policymaker_id = _DocumentInfoDataProperty('policymaker_id')
    policymaker_abbr = _DocumentInfoDataProperty('policymaker_abbr')
    doc_type = _DocumentInfoDataProperty('doc_type')
    origin_id = _DocumentInfoDataProperty('origin_id')

    @cached_property
    def last_modified(self):
        return self.tz.localize(self.dir_entry.mtime)

    @property
    def mtime_text(self):
        return self.dir_entry.mtime_text

    def get_document(self):
        """
        Get the parsed Ahjo document of this document info.

        :rtype: AhjoDocument
        """
        with self._open_remote_xml_file() as xml_file:
            document = AhjoDocument(xml_file)
        return document

    def _open_remote_xml_file(self):
        remote_file = HttpFetchedFile(self.url)
        zipf = zipfile.ZipFile(remote_file)
        name_list = zipf.namelist()
        xml_names = [x for x in name_list if x.endswith('.xml')]
        if len(xml_names) == 0:
            # FIXME: Workaround for a silly bug
            xml_names = [x for x in name_list if re.match(r'\w+\d+xml_', x)]
            if len(xml_names) != 1:
                raise IOError("No XML file in ZIP: {}".format(self.url))
        if len(xml_names) > 1:
            raise IOError("Too many XML files in ZIP: {}".format(self.url))
        return zipf.open(xml_names[0])
