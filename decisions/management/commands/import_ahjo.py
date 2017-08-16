import sys

from django.core.management.base import BaseCommand
from decisions.importer.helsinki.ahjo import AhjoDocument


class Command(BaseCommand):
    help = 'Imports'

    def add_arguments(self, parser):
        pass
        # parser.add_argument('filename', type=str)

    def handle(self, *args, **options):
        for filename in sys.stdin:
            filename = filename.strip()
            print(filename)
            importer = AhjoDocument(filename)
            print(importer.json)
            print()
