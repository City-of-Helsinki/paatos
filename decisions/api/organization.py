from rest_framework import serializers, viewsets
from parler_rest.serializers import TranslatableModelSerializer  # , TranslatedFieldsField

from decisions.models import Event, OrganizationClass, Organization, Post

from .base import DataModelSerializer


class OrganizationClassSerializer(TranslatableModelSerializer):
    class Meta:
        model = OrganizationClass
        fields = '__all__'


class OrganizationSerializer(DataModelSerializer):
    events = serializers.HyperlinkedRelatedField(queryset=Event.objects.all(), view_name='event-detail', many=True)
    posts = serializers.HyperlinkedRelatedField(queryset=Post.objects.all(), view_name='post-detail', many=True)
    classification = OrganizationClassSerializer()

    class Meta:
        model = Organization
        fields = '__all__'


class OrganizationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Organization.objects.select_related('data_source').prefetch_related('events', 'posts')
    serializer_class = OrganizationSerializer
