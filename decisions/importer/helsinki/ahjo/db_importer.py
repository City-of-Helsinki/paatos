from ....models import ImportedFile
from .importer import Importer


class DatabaseImporter(Importer):
    """
    Importer that imports from Ahjo to the database.
    """
    def __init__(self, data_source):
        self.data_source = data_source

    def get_imported_version(self, path):
        imported_file = ImportedFile.objects.filter(
            data_source=self.data_source, path=path).first()
        return imported_file.imported_version if imported_file else None

    def set_imported_version(self, path, version):
        (imported_file, created) = ImportedFile.objects.get_or_create(
            data_source=self.data_source, path=path, defaults={
                'imported_version': version})
        if not created:
            imported_file.imported_version = version
            imported_file.save(update_fields=['imported_version'])

    def handle_document_changed(self, doc_info):
        print("Updating data from {}".format(doc_info))
        doc = doc_info.get_document()
