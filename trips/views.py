from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Project, ProjectPlace
from .serializers import (
    ProjectSerializer,
    ProjectListSerializer,
    ProjectPlaceSerializer,
    ProjectPlaceUpdateSerializer,
)
from .services import get_artwork


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list':
            return ProjectListSerializer
        return ProjectSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        if status_filter in (Project.STATUS_ACTIVE, Project.STATUS_COMPLETED):
            qs = qs.filter(status=status_filter)
        return qs

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        if project.places.filter(visited=True).exists():
            return Response(
                {'detail': 'Cannot delete a project that has visited places.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        project.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProjectPlaceViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    def get_project(self):
        return get_object_or_404(Project, pk=self.kwargs['project_pk'])

    def get_queryset(self):
        return ProjectPlace.objects.filter(project_id=self.kwargs['project_pk']).order_by('created_at')

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return ProjectPlaceUpdateSerializer
        return ProjectPlaceSerializer

    def create(self, request, *args, **kwargs):
        project = self.get_project()

        external_id = request.data.get('external_id')
        if external_id is None:
            return Response({'external_id': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)

        try:
            external_id = int(external_id)
        except (TypeError, ValueError):
            return Response({'external_id': ['Must be an integer.']}, status=status.HTTP_400_BAD_REQUEST)

        if project.places.count() >= 10:
            return Response(
                {'detail': 'A project can have at most 10 places.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if project.places.filter(external_id=external_id).exists():
            return Response(
                {'detail': 'This place is already in the project.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        artwork = get_artwork(external_id)
        place = ProjectPlace.objects.create(project=project, **artwork)
        return Response(ProjectPlaceSerializer(place).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        place = self.get_object()
        serializer = ProjectPlaceUpdateSerializer(place, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Auto-complete project if all places are visited
        place.project.refresh_status()

        return Response(ProjectPlaceSerializer(place).data)
