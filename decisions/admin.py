from django.apps import apps
from django.contrib import admin
from easy_select2 import select2_modelform

from parler.admin import TranslatableAdmin, TranslatableTabularInline

from decisions.models import Action, Content, Event, Membership, Organization, Person, Post


class PersonMembershipInline(TranslatableTabularInline):
    fields = ('organization', 'role', 'start_date', 'end_date')
    raw_id_fields = ('organization',)
    model = Membership
    extra = 0


class OrganizationMembershipInline(TranslatableTabularInline):
    fields = ('person', 'role', 'start_date', 'end_date')
    raw_id_fields = ('person',)
    model = Membership
    extra = 0


@admin.register(Person)
class PersonAdmin(TranslatableAdmin):
    inlines = (PersonMembershipInline,)
    search_fields = ('name',)


@admin.register(Organization)
class OrganizationAdmin(TranslatableAdmin):
    inlines = (OrganizationMembershipInline,)
    search_fields = ('name',)


EventForm = select2_modelform(Event)


@admin.register(Event)
class EventAdmin(TranslatableAdmin):
    form = EventForm
    ordering = ('-start_date',)


class ContentInline(TranslatableTabularInline):
    model = Content
    ordering = ('ordering',)
    fields = ('type', 'hypertext')
    extra = 0


@admin.register(Action)
class ActionAdmin(TranslatableAdmin):
    inlines = (ContentInline,)


@admin.register(Post)
class PostAdmin(TranslatableAdmin):
    model = Post
    raw_id_fields = ('organization',)


for model in apps.get_app_config("decisions").get_models():
    try:
        admin.site.register(model)
    except admin.sites.AlreadyRegistered:
        pass
