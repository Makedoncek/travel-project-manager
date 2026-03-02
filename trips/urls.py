from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet, ProjectPlaceViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')

project_places_router = DefaultRouter()
project_places_router.register(r'places', ProjectPlaceViewSet, basename='project-place')

urlpatterns = [
    path('', include(router.urls)),
    path('projects/<int:project_pk>/', include(project_places_router.urls)),
]
