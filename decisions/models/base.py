# -*- coding: UTF-8 -*-

from django.db import models
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslatableModel


class BaseModel(TranslatableModel):
    created_at = models.DateTimeField(auto_now_add=True, editable=False,
                                      help_text=_('The time at which the resource was created'))
    modified_at = models.DateTimeField(auto_now=True, editable=False,
                                       help_text=_('The time at which the resource was updated'))

    class Meta:
        abstract = True


class DataSource(BaseModel):
    identifier = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=255, help_text=_('Human-readable name'))

    def __str__(self):
        return self.identifier


class DataModel(BaseModel):
    data_source = models.ForeignKey(DataSource, blank=True, null=True, db_index=True)
    origin_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    class Meta:
        abstract = True
        unique_together = ('data_source', 'origin_id')
