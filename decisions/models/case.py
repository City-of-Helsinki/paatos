# -*- coding: UTF-8 -*-
from django.contrib.gis.db import models
from django.utils.translation import ugettext_lazy as _
from parler.models import TranslatedFields

from .base import DataModel


class Function(DataModel):
    translations = TranslatedFields(
        name=models.CharField(max_length=255, help_text=_('Name of this function'))
    )
    function_id = models.CharField(max_length=32, help_text=_('Original identifier of this function'))
    parent = models.ForeignKey('self', help_text=_('Parent function of this function'), blank=True, null=True)

    def __str__(self):
        return '%s / %s' % (self.parent, self.name) if self.parent else self.name


class CaseGeometry(DataModel):
    ADDRESS = 'address'
    PLAN = 'plan'
    DISTRICT = 'district'

    TYPE_CHOICES = (
        ('address', 'Address'),
        ('plan', 'Plan'),
        ('district', 'District'),
    )
    translations = TranslatedFields(
        name=models.CharField(max_length=100, db_index=True)
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    geometry = models.GeometryField()

    def __str__(self):
        return '%s (%s, %s)' % (self.name, self.type, self.geometry.geom_type)


class Case(DataModel):
    translations = TranslatedFields(
        title=models.CharField(max_length=255, help_text=_('Descriptive compact title for this case'))
    )
    register_id = models.CharField(max_length=255, help_text=_('Register ID of this case'), unique=True, db_index=True)
    attachments = models.ManyToManyField('Attachment', related_name='cases')
    function = models.ForeignKey(Function, related_name='cases',
                                 help_text=_('Function this case belongs to ("tehtäväluokka")'))
    geometries = models.ManyToManyField(CaseGeometry, related_name='cases', blank=True,
                                        help_text=_('Geometries related to this case'))

    def __str__(self):
        return self.title


class Action(DataModel):
    translations = TranslatedFields(
        title=models.CharField(max_length=255, help_text=_('Title of the action')),
        resolution=models.CharField(max_length=255, blank=True,
                                    help_text="Resolution taken in this action (like tabled, decided...)")
    )
    case = models.ForeignKey(Case, related_name='actions', help_text=_('Case this action is related to'), blank=True,
                             null=True)
    ordering = models.IntegerField(help_text=_('Ordering of this action within a meeting'))
    article_number = models.CharField(max_length=255, blank=True,
                                      help_text=_('The article number given to this action after decision'))
    post = models.ForeignKey('Post', related_name='actions', blank=True, null=True, help_text=_(
        'If this decision was delegated, this field will be filled and refers to the post that made the decision'))
    event = models.ForeignKey('Event', related_name='actions', help_text=_('Event this action is related to'),
                              null=True, blank=True)

    def __str__(self):
        return self.title


class Content(DataModel):
    ordering = models.IntegerField(help_text=_('Ordering of this content within the larger context (like action)'))
    translations = TranslatedFields(
        title=models.CharField(max_length=255, help_text=_('Title of this content'), blank=True),
        type=models.CharField(max_length=255, help_text=_(
            'Type of this content (options include: decision, proposal, proceedings...)')),
        hypertext=models.TextField(help_text=_(
            'Content formatted with pseudo-HTML. Only a very restricted set of tags is allowed. '
            'These are: first and second level headings (P+H1+H2) and table (more may be added, '
            'but start from a minimal set)'))
    )
    action = models.ForeignKey(Action, related_name='contents', help_text=_('Action that this content describes'))

    def __str__(self):
        return '%s %s' % (self.action, self.ordering)


class Attachment(DataModel):
    # file = models.FileField()  # TODO
    translations = TranslatedFields(
        name=models.CharField(max_length=400, blank=True, help_text='Short name of this attachment'),
        confidentiality_reason=models.CharField(max_length=100, help_text=_(
            'Reason for keeping this attachment confidential'), blank=True)
    )
    url = models.URLField(help_text=_('URL of the content of this attachment'))
    action = models.ForeignKey(Action, help_text=_('The action this attachment is related to'),
                               related_name='attachments')
    number = models.PositiveIntegerField(help_text='Index number of this attachment')
    public = models.BooleanField(default=False, help_text=_('Is this attachment public?'))

    def __str__(self):
        return '%s %s' % (self.name, self.action)

    class Meta:
        ordering = ('number',)
