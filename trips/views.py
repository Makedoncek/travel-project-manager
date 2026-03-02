from rest_framework import viewsets, mixins, status, serializers as drf_serializers
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter, inline_serializer

from .models import Project, ProjectPlace
from .serializers import (
    ProjectSerializer,
    ProjectListSerializer,
    ProjectPlaceSerializer,
    ProjectPlaceUpdateSerializer,
    ProjectPlaceAddSerializer,
)
from .services import get_artwork


@extend_schema_view(
    list=extend_schema(
        summary='List all projects',
        description='Returns a paginated list of travel projects. Optionally filter by status.',
        parameters=[
            OpenApiParameter(
                name='status',
                type=str,
                enum=['active', 'completed'],
                description='Filter projects by status.',
                required=False,
            ),
        ],
    ),
    create=extend_schema(
        summary='Create a project',
        description=(
            'Create a new travel project. Optionally include an `initial_places` array '
            'with external IDs to add places from the Art Institute of Chicago API in a single request.'
        ),
    ),
    retrieve=extend_schema(
        summary='Get a project',
        description='Retrieve a single project with all its places.',
    ),
    partial_update=extend_schema(
        summary='Update a project',
        description='Update project name, description, or start_date.',
    ),
    update=extend_schema(
        summary='Update a project (full)',
        description='Full update of project name, description, and start_date.',
    ),
    destroy=extend_schema(
        summary='Delete a project',
        description='Delete a project. Returns 400 if any place in the project is already marked as visited.',
        responses={
            204: None,
            400: inline_serializer('DeleteError', fields={
                'detail': drf_serializers.CharField(),
            }),
        },
    ),
)
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


@extend_schema_view(
    list=extend_schema(
        summary='List places in a project',
        parameters=[OpenApiParameter(name='project_pk', type=int, location=OpenApiParameter.PATH)],
        description='Returns a paginated list of all places belonging to the specified project.',
    ),
    create=extend_schema(
        summary='Add a place to a project',
        description=(
            'Add a place to an existing project by providing its Art Institute of Chicago external ID. '
            'The artwork is validated against the API before being stored. '
            'A project can have at most 10 places, and duplicate external IDs are rejected.'
        ),
        request=ProjectPlaceAddSerializer,
        responses={201: ProjectPlaceSerializer, 400: inline_serializer('PlaceAddError', fields={
            'detail': drf_serializers.CharField(),
        })},
    ),
    retrieve=extend_schema(
        summary='Get a place',
        description='Retrieve a single place within a project.',
        parameters=[OpenApiParameter(name='id', type=int, location=OpenApiParameter.PATH)],
    ),
    partial_update=extend_schema(
        summary='Update a place',
        description=(
            'Update a place\'s notes or mark it as visited. '
            'When all places in a project are marked as visited, the project status is automatically set to completed.'
        ),
        request=ProjectPlaceUpdateSerializer,
        responses={200: ProjectPlaceSerializer},
        parameters=[OpenApiParameter(name='id', type=int, location=OpenApiParameter.PATH)],
    ),
    update=extend_schema(
        summary='Update a place (full)',
        description='Full update of a place\'s notes and visited status.',
        request=ProjectPlaceUpdateSerializer,
        responses={200: ProjectPlaceSerializer},
        parameters=[OpenApiParameter(name='id', type=int, location=OpenApiParameter.PATH)],
    ),
)
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

        serializer = ProjectPlaceAddSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        external_id = serializer.validated_data['external_id']

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
