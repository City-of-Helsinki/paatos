import pytz
import re
import logging
import json

from lxml import etree
from datetime import datetime, date

RESOLUTION_MAP = {
    'hyväksytty': 'accepted'
}

ATTENDEE_MAP = {
    'jäsenet': 'participant',
    'ledamöter': 'participant',

    'asiantuntija': 'expert',
    'asiantuntijat': 'expert',

    'muut': 'other',
    'övriga': 'other'
}

LOCAL_TZ = pytz.timezone('Europe/Helsinki')


class ParseError(Exception):
    pass


class AhjoDocument:
    @staticmethod
    def parse_name(name):
        if ', ' in name:
            name = name.split(', ')
            name = '{} {}'.format(name[1], name[0])

        return name

    @staticmethod
    def parse_guid(raw):
        if raw is None:
            return None

        guid_match = re.fullmatch(r'\{([A-F0-9]{8}-(?:[A-F0-9]{4}-){3}[A-F0-9]{12})\}', raw)
        if guid_match is not None:
            return guid_match.group(1).lower()
        else:
            raise ParseError("Invalid GUID format")

    @staticmethod
    def parse_datetime(raw):
        if raw is None:
            return None

        date = None

        # it's important here that the 12h versions are before 24h versions
        formats = [
            '%m/%d/%Y %I:%M:%S %p',
            '%m/%d/%Y %H:%M:%S',

            '%d.%m.%Y %I:%M:%S %p',
            '%d.%m.%Y %H:%M:%S',
        ]

        for fmt in formats:
            try:
                date = datetime.strptime(raw, fmt)
                break
            except ValueError as r:
                pass

        if date is None:
            raise ParseError('Unknown timestamp')

        return LOCAL_TZ.localize(date)

    def log(self, severity, msg):
        human_readable = '{} (File: {}, Action: {})'.format(msg, self.filename, self.current_action)
        self.logger.log(severity, human_readable)

        attrs = ['current_document', 'current_action']

        state = {attr: getattr(self, attr) for attr in attrs}
        state['filename'] = self.filename

        self.errors.append({
            'msg': msg,
            'severity': severity,
            'state': state
        })

        if severity >= self.except_treshold:
            raise ParseError(msg)

    def critical(self, msg):
        self.log(logging.CRITICAL, msg)

    def error(self, msg):
        self.log(logging.ERROR, msg)

    def warning(self, msg):
        self.log(logging.WARNING, msg)

    def info(self, msg):
        self.log(logging.INFO, msg)

    def debug(self, msg):
        self.log(logging.DEBUG, msg)

    def gt(self, parent, el_name, log, format=None):
        el = parent.find(el_name)
        if el is None:
            log("Element {} not found".format(el_name))
            return None
        else:
            content = el.text
            if content is None:
                log("Element {} is empty".format(el_name))
                return content

            if format is not None:
                return format(content)
            else:
                return content

    def import_attendees(self, lasnaolotiedot):
        ret = []

        attendee_group_els = lasnaolotiedot.findall('.//Osallistujaryhma')

        for attendee_group_el in attendee_group_els:
            group_name = self.gt(attendee_group_el, 'OsallistujaryhmaOtsikko', self.error)
            attendees = attendee_group_el.findall('Osallistujat')

            for attendee in attendees:
                a_attrs = {}

                name = attendee.find('Nimi')
                if name is not None:
                    a_attrs['name'] = AhjoDocument.parse_name(name.text)
                else:
                    self.warning("Attendee doesn't have a name")
                    continue

                opts = attendee.find('OsallistujaOptiot')
                if opts is not None:
                    role = opts.find('Rooli')
                    if role is not None:
                        a_attrs['role'] = role.text

                title = attendee.find('Titteli')
                if title is not None:
                    a_attrs['title'] = title.text

                if group_name is not None:
                    a_attrs['category'] = ATTENDEE_MAP[group_name.lower()]
                else:
                    a_attrs['category'] = 'participant'

                ret.append(a_attrs)

        return ret

    def import_event(self, event_data):
        attrs = {}

        date_el = event_data.find('Paivays')
        date = datetime.strptime(date_el.text, '%Y-%m-%d')
        attrs['start_date'] = date
        attrs['end_date'] = date

        return attrs

    def import_content(self, content):
        chapters = content.findall('.//Kappale')
        if chapters is not None:
            text = ''
            for chapter in chapters:
                chapter_text = chapter.find('KappaleTeksti')
                if chapter_text is not None:
                    text += '<p>{}</p>\n'.format(chapter_text.text)
        else:
            self.error("Content doesn't have chapters")

        attrs = {
            'hypertext': text
        }

        return attrs

    def import_action(self, action):
        attrs = {}

        metadata = action.find('KuvailutiedotOpenDocument')

        attrs['title'] = self.gt(metadata, 'Otsikko', self.warning)
        self.current_action = attrs['title']

        attrs['action_class'] = self.gt(metadata, 'AsiakirjallinenTieto', self.warning)
        if attrs['action_class'] is not None:
            attrs['action_class'] = attrs['action_class'].split(' ')

        attrs['case_guid'] = AhjoDocument.parse_guid(self.gt(metadata, 'AsiaGuid', lambda x: None))
        if attrs['case_guid'] is None and \
           attrs['action_class'] is not None and \
           attrs['action_class'][-1].lower() != 'vakiopäätös':
            self.error("Action doesn't have an associated case")

        attrs['date'] = AhjoDocument.parse_datetime(self.gt(metadata, 'Paatospaiva', self.error))

        attrs['article_number'] = self.gt(metadata, 'Pykala', self.error, format=int)

        attrs['dnro'] = self.gt(metadata, 'Dnro/DnroLyhyt', self.warning)

        resolution_el = metadata.find('Asiakirjantila')

        if resolution_el is not None:
            try:
                attrs['resolution'] = RESOLUTION_MAP[resolution_el.text.lower()]
            except KeyError:
                self.warning("Unknown resolution type: {}".format(resolution_el.text))
        else:
            self.warning("Action doesn't have a resolution")

        content = action.find('SisaltoSektioToisto')
        attrs['content'] = [self.import_content(cs) for cs in content]

        return attrs

    def import_document(self, root):
        attrs = {}

        actions = root.find('Paatokset')
        metadata = root.find('Kuvailutiedot')

        guid_el = metadata.find('DhId')
        attrs['guid'] = AhjoDocument.parse_guid(guid_el.text)
        self.current_document = attrs['guid']

        event_data = root.find('YlatunnisteSektio')
        event_metadata = root.find('PkKansilehtiSektio')

        if event_data is not None:
            attrs['event'] = self.import_event(event_data)
            if event_metadata is not None:
                lasnaolotiedot = event_metadata.find('KansilehtiToisto/Lasnaolotiedot')
                attrs['event']['attendees'] = self.import_attendees(lasnaolotiedot)
        else:
            self.critical("No event data")

        attrs['event']['actions'] = [self.import_action(ac) for ac in actions]

        # vain viranhaltijan päätöksissä?
        signatures = root.find('SahkoinenAllekirjoitusSektio')
        if signatures is None:
            signatures = root.find('AllekirjoitusSektio')
            chairman = signatures.find('PuheenjohtajaSektio').find('PuheenjohtajaToisto')
            attrs['chairman'] = chairman.find('Puheenjohtajanimi').text

        return attrs

    def import_esityslista(self, root):
        pass
        # attrs = {}

        # actions = root.find('KasiteltavatAsiat')

    def __init__(self, filename, except_treshold=logging.CRITICAL):
        self.logger = logging.getLogger(__name__)
        self.errors = []

        self.filename = filename
        self.except_treshold = except_treshold

        self.current_document = None
        self.current_action = None

        xml = etree.parse(filename)
        root = xml.getroot()

        if root.tag == 'Poytakirja':
            self.document = self.import_document(root)

        if root.tag == 'Esityslista':
            self.document = self.import_esityslista(root)

    @property
    def json(self):
        # https://stackoverflow.com/a/22238613

        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""

            if isinstance(obj, (datetime, date)):
                serial = obj.isoformat()
                return serial
            raise TypeError("Type %s not serializable" % type(obj))

        ret = {
            'document': self.document,
            'errors': self.errors
        }

        return json.dumps(ret, indent=4, ensure_ascii=False, default=json_serial)
