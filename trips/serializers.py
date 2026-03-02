from django.db import transaction
from rest_framework import serializers
from .models import Project, ProjectPlace
from .services import get_artwork


class ProjectPlaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlace
        fields = ['id', 'external_id', 'title', 'artist', 'thumbnail_url', 'notes', 'visited', 'created_at', 'updated_at']
        read_only_fields = ['id', 'title', 'artist', 'thumbnail_url', 'created_at', 'updated_at']


class ProjectPlaceCreateSerializer(serializers.Serializer):
    """Used when creating a project with an initial list of places."""
    external_id = serializers.IntegerField()


class ProjectPlaceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectPlace
        fields = ['notes', 'visited']


class ProjectListSerializer(serializers.ModelSerializer):
    place_count = serializers.IntegerField(source='places.count', read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'start_date', 'status', 'place_count', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class ProjectSerializer(serializers.ModelSerializer):
    places = ProjectPlaceSerializer(many=True, read_only=True)
    initial_places = ProjectPlaceCreateSerializer(many=True, write_only=True, required=False)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'start_date', 'status', 'places', 'initial_places', 'created_at', 'updated_at']
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']

    def validate_initial_places(self, value):
        if len(value) > 10:
            raise serializers.ValidationError('A project can have at most 10 places.')
        ids = [p['external_id'] for p in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError('Duplicate external_id values in initial_places.')
        return value

    def create(self, validated_data):
        initial_places = validated_data.pop('initial_places', [])
        with transaction.atomic():
            project = Project.objects.create(**validated_data)
            for place_data in initial_places:
                artwork = get_artwork(place_data['external_id'])
                ProjectPlace.objects.create(project=project, **artwork)
        return project
