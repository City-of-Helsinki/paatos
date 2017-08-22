# -*- coding: UTF-8 -*-

from django.db import models
from parler.models import TranslatableModel, TranslatedFields
from django.utils.translation import ugettext_lazy as _

from .base import DataModel


class OrganizationClass(TranslatableModel):
    translations = TranslatedFields(
        name=models.CharField(max_length=255, null=True)
    )


class Organization(DataModel):
    classification = models.ForeignKey(
        OrganizationClass,
        help_text=_('An organization category, e.g. committee'),
        on_delete=models.PROTECT,
    )
    translations = TranslatedFields(
        name=models.CharField(max_length=255, help_text=_('A primary name, e.g. a legally recognized name'))
    )
    founding_date = models.DateField(help_text=_('A date of founding'), blank=True, null=True)
    dissolution_date = models.DateField(help_text=_('A date of dissolution'), blank=True, null=True)
    parent = models.ForeignKey('self', help_text=_('The organizations that contain this organization'), null=True,
                               blank=True)

    def __str__(self):
        if self.parent:
            return '%s / %s' % (self.parent, self.name)  # TODO cache
        else:
            return self.name


class Post(DataModel):
    translations = TranslatedFields(
        label=models.CharField(max_length=255, help_text=_('A label describing the post'))
    )
    organization = models.ForeignKey(Organization, related_name='posts',
                                     help_text=_('The organization in which the post is held'))
    start_date = models.DateField(help_text=_('The date on which the post was created'), null=True, blank=True)
    end_date = models.DateField(help_text=_('The date on which the post was eliminated'), null=True, blank=True)

    def __str__(self):
        return '%s / %s' % (self.organization, self.label)  # TODO cache
