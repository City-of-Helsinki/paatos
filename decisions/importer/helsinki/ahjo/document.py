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


class Document:
    @staticmethod
    def clean_html(raw):
        # TODO
        return ''.join([str(etree.tostring(el)) for el in raw])

    @staticmethod
    def parse_funcid(raw):
        if raw is None:
            return (None, None)

        match = re.fullmatch(r'((?:\d\d ){0,}\d\d) (.*)', raw)
        return (match.group(1), match.group(2))

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

        attrs = ['current_action']

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

    def gt(self, parent, el_name, log=lambda x: None, format=None):
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
                if name is not None and name.text:
                    a_attrs['name'] = Document.parse_name(name.text)
                else:
                    self.warning("Attendee doesn't have a name")
                    continue

                opts = attendee.find('OsallistujaOptiot')
                if opts is not None:
                    a_attrs['role'] = self.gt(opts, 'Rooli')
                else:
                    a_attrs['role'] = None

                a_attrs['title'] = self.gt(attendee, 'Titteli')

                if group_name is not None:
                    try:
                        a_attrs['category'] = ATTENDEE_MAP[group_name.lower()]
                    except KeyError:
                        continue
                else:
                    a_attrs['category'] = 'participant'

                ret.append(a_attrs)

        return ret

    def import_event(self, data1, data2):
        attrs = {}

        if data1 is not None:
            lasnaolotiedot = data1.find('Lasnaolotiedot')
            attrs['attendees'] = self.import_attendees(lasnaolotiedot)

            kokoustiedot = data1.find('Kokoustiedot')
            attrs['location'] = self.gt(kokoustiedot, 'Kokouspaikka')

            # format: dd.mm.yyyy hh:mm - hh:mm, extra stuff
            time_raw = self.gt(kokoustiedot, 'Kokousaika').split(',')[0]

            try:
                date = time_raw.split(' - ')[0].strip()
                endtime = time_raw.split(' - ')[1].strip()

                start_date = LOCAL_TZ.localize(datetime.strptime(date, '%d.%m.%Y %H:%M'))
                attrs['start_date'] = start_date

                try:
                    end_date = datetime.strptime(endtime, '%H:%M')
                except ValueError:
                    # there's one document with a . instead of : ...
                    end_date = datetime.strptime(endtime, '%H.%M')

                attrs['end_date'] = start_date.replace(hour=end_date.hour, minute=end_date.minute)
            except:
                attrs['start_date'] = None
                attrs['end_date'] = None
        else:
            attrs.update({
                'attendees': None,
                'location': None,
                'start_date': None,
                'end_date': None
            })

        if data2 is not None:
            attrs['name'] = '{} {}'.format(self.gt(data2, 'Paattaja'), self.gt(data2, 'Asiakirjatunnus'))
        else:
            attrs['name'] = None

        return attrs

    def import_content(self, content):
        if content is None:
            return None

        s = ""

        for section in content:
            heading = self.gt(section, 'SisaltoOtsikko')
            if heading is not None:
                s += '<h2>{}</h2>\n'.format(heading)

            mystery = section.find('TekstiSektio/taso1')
            if mystery is not None:
                for el in mystery:
                    if el.tag == 'Kappale':
                        s += '<p>{}</p>\n'.format(self.gt(el, 'KappaleTeksti'))
                    elif el.tag == 'Otsikko':
                        s += '<h3>{}<h3>\n'.format(el.text)
                    elif el.tag == 'XHTML':
                        s += Document.clean_html(el)

            return s

    def import_action(self, action):
        attrs = {}

        metadata = action.find('KuvailutiedotOpenDocument')

        vakiopaatos = False
        asktieto = self.gt(metadata, 'AsiakirjallinenTieto')
        if asktieto is not None and 'vakiopäätös' in asktieto:
            vakiopaatos = True

        attrs['title'] = self.gt(metadata, 'Otsikko', self.warning)
        self.current_action = attrs['title']

        attrs['function_id'] = self.parse_funcid(self.gt(metadata, 'Tehtavaluokka', self.warning))[0]

        attrs['case_guid'] = Document.parse_guid(self.gt(metadata, 'AsiaGuid'))
        if attrs['case_guid'] is None and not vakiopaatos:
            self.error("Action doesn't have an associated case")

        attrs['date'] = Document.parse_datetime(self.gt(metadata, 'Paatospaiva', self.error))
        attrs['article_number'] = self.gt(metadata, 'Pykala', self.error, format=int)

        attrs['dnro'] = self.gt(metadata, 'Dnro/DnroLyhyt')
        if attrs['dnro'] is None and not vakiopaatos:
            self.error("Action doesn't have a journal number (diaarinumero)")

        resolution_el = metadata.find('Asiakirjantila')

        if resolution_el is not None:
            try:
                attrs['resolution'] = RESOLUTION_MAP[resolution_el.text.lower()]
            except KeyError:
                self.warning("Unknown resolution type: {}".format(resolution_el.text))
        else:
            self.warning("Action doesn't have a resolution")

        content = action.find('SisaltoSektioToisto')
        attrs['content'] = self.import_content(content)

        keywords = action.findall('Asiasana')
        attrs['keywords'] = [{'name': kw.text} for kw in keywords]

        return attrs

    def import_document(self, root):
        attrs = {}

        event_metadata = root.find('PkKansilehtiSektio/KansilehtiToisto')
        event_metadata2 = root.find('YlatunnisteSektio')

        actions = root.find('Paatokset')

        attrs['event'] = self.import_event(event_metadata, event_metadata2)

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

    def __init__(self, source, except_treshold=logging.CRITICAL):
        self.logger = logging.getLogger(__name__)
        self.errors = []

        self.filename = source if isinstance(source, str) else source.name
        self.except_treshold = except_treshold

        self.current_action = None

        xml = etree.parse(source)
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
