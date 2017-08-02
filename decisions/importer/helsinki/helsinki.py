# -*- coding: utf-8 -*-
# Based heavily on https://github.com/City-of-Helsinki/openahjo/blob/4bcb003d5db932ca28ea6851d76a20a4ee6eef54/decisions/importer/helsinki.py  # noqa

import json

from enum import Enum
from dateutil.parser import parse as dateutil_parse
from django.db import transaction
from django.utils.text import slugify

from decisions.models import DataSource, Person, OrganizationClass

from .base import Importer


class Org(Enum):
    COUNCIL = 1
    BOARD = 2
    EXECUTIVE_BOARD = 3
    BOARD_DIVISION = 4
    COMMITTEE = 5
    COMMON = 6
    FIELD = 7
    DEPARTMENT = 8
    DIVISION = 9
    INTRODUCER = 10
    INTRODUCER_FIELD = 11
    OFFICE_HOLDER = 12
    CITY = 13
    UNIT = 14
    WORKING_GROUP = 15
    SCHOOL_BOARDS = 16
    PACKAGED_SERVICE = 17
    PACKAGED_INTRODUCER_SERVICE = 18
    TRUSTEE = 19


NAME_MAP = {
    Org.COUNCIL: ('Valtuusto', None, 'Council'),
    Org.BOARD: ('Hallitus', None, 'Board'),
    Org.EXECUTIVE_BOARD: ('Johtajisto', None, 'Executive board'),
    Org.BOARD_DIVISION: ('Jaosto', None, 'Board division'),
    Org.COMMITTEE: ('Lautakunta', None, 'Committee'),
    Org.COMMON: ('Yleinen', None, 'Common'),
    Org.FIELD: ('Toimiala', None, 'Field'),
    Org.DEPARTMENT: ('Virasto', None, 'Department'),
    Org.DIVISION: ('Osasto', None, 'Division'),
    Org.INTRODUCER: ('Esittelijä', None, 'Introducer'),
    Org.INTRODUCER_FIELD: ('Esittelijä (toimiala)', None, 'Introducer field'),
    Org.OFFICE_HOLDER: ('Viranhaltija', None, 'Office holder'),
    Org.CITY: ('Kaupunki', None, 'City'),
    Org.UNIT: ('Yksikkö', None, 'Unit'),
    Org.WORKING_GROUP: ('Toimikunta', None, 'Working group'),
    Org.SCHOOL_BOARDS: ('Koulujen johtokunnat', None, 'School boards'),
    Org.PACKAGED_SERVICE: ('Palvelukokonaisuus', None, 'Packaged service'),
    Org.PACKAGED_INTRODUCER_SERVICE: ('Esittelijäpalvelukokonaisuus', None, 'Packaged introducer service'),
    Org.TRUSTEE: ('Luottamushenkilö', None, 'Trustee')
}


PARENT_OVERRIDES = {
    'Kiinteistövirasto': '100',  # Kaupunkisuunnittelu- ja kiinteistötoimi'
    'Kaupunginhallituksen konsernijaosto': '00400',   # Kaupunginhallitus
    'Opetusvirasto': '301',  # Sivistystoimi,
    'Kaupunkisuunnitteluvirasto': '100',  # Kaupunkisuunnittelu- ja kiinteistötoimi'
    'Sosiaali- ja terveysvirasto': '400',  # Sosiaali- ja terveystoimi
    'Kaupunginkanslia': '00001',  # Helsingin kaupunki
}


class HelsinkiImporter(Importer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data_source, created = DataSource.objects.get_or_create(
            identifier='helsinki',
            defaults={'name': 'Helsinki'}
        )
        if created:
            self.logger.debug('Created new data source "helsinki"')

    @transaction.atomic()
    def _import_organization(self, info):
        org_type = Org(info['type'])
        org = dict(origin_id=info['id'])
        org['classification'] = OrganizationClass.objects.get(id=org_type.value)

        if org_type in [Org.INTRODUCER, Org.INTRODUCER_FIELD, Org.PACKAGED_INTRODUCER_SERVICE]:
            self.skip_orgs.add(org['origin_id'])
            return

        # TODO change when model translations are in
        """
        org['name'] = {'fi': info['name_fin'], 'sv': info['name_swe']}
        """
        org['name'] = info['name_fin']

        if info['shortname']:
            org['abbreviation'] = info['shortname']

        # FIXME: Use maybe sometime
        """
        DUPLICATE_ABBREVS = [
            'AoOp', 'Vakaj', 'Talk', 'KIT', 'HTA', 'Ryj', 'Pj', 'Sotep', 'Hp',
            'Kesvlk siht', 'Kulttj', 'HVI', 'Sostap', 'KOT',
            'Lsp', 'Kj', 'KYT', 'AST', 'Sote', 'Vp', 'HHE', 'Tj', 'HAKE', 'Ko'
        ]
        """

        if org_type in (Org.COUNCIL, Org.COMMITTEE, Org.BOARD_DIVISION, Org.BOARD):
            org['slug'] = slugify(org['abbreviation'])
        else:
            org['slug'] = slugify(org['origin_id'])

        org['founding_date'] = None
        if info['start_time']:
            d = dateutil_parse(info['start_time'])
            # 2009-01-01 means "no data"
            if not (d.year == 2009 and d.month == 1 and d.day == 1):
                org['founding_date'] = d.date().strftime('%Y-%m-%d')

        org['dissolution_date'] = None
        if info['end_time']:
            d = dateutil_parse(info['end_time'])
            org['dissolution_date'] = d.date().strftime('%Y-%m-%d')

        org['contact_details'] = []
        if info['visitaddress_street'] or info['visitaddress_zip']:
            cd = {'type': 'address'}
            cd['value'] = info.get('visitaddress_street', '')
            z = info.get('visitaddress_zip', '')
            if z and len(z) == 2:
                z = "00%s0" % z
            cd['postcode'] = z
            org['contact_details'].append(cd)
        org['modified_at'] = dateutil_parse(info['modified_time'])

        parents = []
        if org['name'] in PARENT_OVERRIDES:
            parent = PARENT_OVERRIDES[org['name']]
        else:
            parent = None
            if info['parents'] is not None:
                parents = info['parents']
                try:
                    parent = parents[0]
                except IndexError:
                    pass

        if parent not in self.skip_orgs:
            if len(parents) > 1:
                self.logger.warning('Org %s has multiple parents %s, choosing the first one' % (org['name'], parents))
            org['parent'] = parent

        org['memberships'] = []
        if self.options['include_people']:
            for person_info in info['people']:
                person = dict(
                    origin_id=person_info['id'],
                    given_name=person_info['first_name'],
                    family_name=person_info['last_name'],
                    name='{} {}'.format(person_info['first_name'], person_info['last_name'])
                )
                org['memberships'].append(dict(
                    person=person,
                    start_date=person_info['start_time'],
                    end_date=person_info['end_time'],
                    role=person_info['role'],
                ))

        if org_type in [Org.OFFICE_HOLDER, Org.TRUSTEE]:
            self.save_post(org)
        else:
            self.save_organization(org)

    def import_organizations(self, filename):
        self.logger.info('Updating organization class definitions...')
        for enum, names in NAME_MAP.items():
            values = {
                'id': enum.value,
                'name': names[0]
            }
            klass, updated = OrganizationClass.objects.update_or_create(id=values['id'], defaults=values)

        self.logger.info('Importing organizations...')

        with open(filename, 'r') as org_file:
            org_list = json.load(org_file)

        if not self.options['include_people']:
            Person.objects.all().delete()

        self.skip_orgs = set()

        self.org_dict = {org['id']: org for org in org_list}
        ordered = []
        # Start import from the root orgs, move down level by level.
        while len(ordered) != len(org_list):
            for org in org_list:
                if 'added' in org:
                    continue
                if not org['parents']:
                    org['added'] = True
                    ordered.append(org)
                    continue
                for p in org['parents']:
                    if 'added' not in self.org_dict[p]:
                        break
                else:
                    org['added'] = True
                    ordered.append(org)

        for i, org in enumerate(ordered):
            self.logger.info('Processing organization {} / {}'.format(i + 1, len(ordered)))
            self._import_organization(org)

        self.logger.info('Import done!')
