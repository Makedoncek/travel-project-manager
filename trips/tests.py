from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework import status

from .models import Project, ProjectPlace
from .services import get_artwork


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ARTWORK_RESPONSE = {
    'external_id': 27992,
    'title': 'A Sunday on La Grande Jatte',
    'artist': 'Georges Seurat',
    'thumbnail_url': 'data:image/gif;base64,abc',
}

ARTWORK_RESPONSE_2 = {
    'external_id': 129884,
    'title': 'Starry Night and the Astronauts',
    'artist': 'Alma Thomas',
    'thumbnail_url': 'data:image/gif;base64,xyz',
}


def make_api_response(artwork_dict):
    """Return a mock requests.Response for a single artwork."""
    mock = MagicMock()
    mock.status_code = 200
    mock.ok = True
    mock.json.return_value = {
        'data': {
            'id': artwork_dict['external_id'],
            'title': artwork_dict['title'],
            'artist_display': artwork_dict['artist'],
            'thumbnail': {'lqip': artwork_dict['thumbnail_url']},
        }
    }
    return mock


def make_project(**kwargs):
    defaults = {'name': 'Test Project'}
    defaults.update(kwargs)
    return Project.objects.create(**defaults)


def make_place(project, external_id=27992, **kwargs):
    defaults = {
        'external_id': external_id,
        'title': 'Some Artwork',
        'artist': 'Some Artist',
    }
    defaults.update(kwargs)
    return ProjectPlace.objects.create(project=project, **defaults)


# ---------------------------------------------------------------------------
# Service layer tests
# ---------------------------------------------------------------------------

class GetArtworkServiceTest(TestCase):

    def setUp(self):
        cache.clear()

    @patch('trips.services.requests.get')
    def test_returns_parsed_artwork(self, mock_get):
        mock_get.return_value = make_api_response(ARTWORK_RESPONSE)
        result = get_artwork(27992)
        self.assertEqual(result['external_id'], 27992)
        self.assertEqual(result['title'], 'A Sunday on La Grande Jatte')
        self.assertEqual(result['artist'], 'Georges Seurat')

    @patch('trips.services.requests.get')
    def test_caches_result(self, mock_get):
        mock_get.return_value = make_api_response(ARTWORK_RESPONSE)
        get_artwork(27992)
        get_artwork(27992)
        self.assertEqual(mock_get.call_count, 1)

    @patch('trips.services.requests.get')
    def test_raises_validation_error_on_404(self, mock_get):
        mock = MagicMock()
        mock.status_code = 404
        mock.ok = False
        mock_get.return_value = mock
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            get_artwork(99999)

    @patch('trips.services.requests.get')
    def test_raises_validation_error_on_network_failure(self, mock_get):
        import requests as req
        mock_get.side_effect = req.RequestException('timeout')
        from rest_framework.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            get_artwork(1)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class ProjectModelTest(TestCase):

    def test_refresh_status_completes_when_all_visited(self):
        project = make_project()
        make_place(project, external_id=1, visited=True)
        make_place(project, external_id=2, visited=True)
        project.refresh_status()
        project.refresh_from_db()
        self.assertEqual(project.status, Project.STATUS_COMPLETED)

    def test_refresh_status_stays_active_when_some_not_visited(self):
        project = make_project()
        make_place(project, external_id=1, visited=True)
        make_place(project, external_id=2, visited=False)
        project.refresh_status()
        project.refresh_from_db()
        self.assertEqual(project.status, Project.STATUS_ACTIVE)

    def test_refresh_status_stays_active_when_no_places(self):
        project = make_project()
        project.refresh_status()
        project.refresh_from_db()
        self.assertEqual(project.status, Project.STATUS_ACTIVE)

    def test_unique_together_external_id_per_project(self):
        from django.db import IntegrityError
        project = make_project()
        make_place(project, external_id=1)
        with self.assertRaises(IntegrityError):
            make_place(project, external_id=1)


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------

class AuthenticationTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_unauthenticated_request_is_rejected(self):
        r = self.client.get('/api/projects/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_request_is_allowed(self):
        self.client.force_authenticate(user=self.user)
        r = self.client.get('/api/projects/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_basic_auth_credentials_accepted(self):
        self.client.credentials(HTTP_AUTHORIZATION='Basic dGVzdHVzZXI6dGVzdHBhc3M=')
        r = self.client.get('/api/projects/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_wrong_credentials_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION='Basic d3Jvbmc6d3Jvbmc=')
        r = self.client.get('/api/projects/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Project API tests
# ---------------------------------------------------------------------------

class ProjectListCreateAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)
        cache.clear()

    def test_list_empty(self):
        r = self.client.get('/api/projects/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 0)

    def test_create_project_minimal(self):
        r = self.client.post('/api/projects/', {'name': 'Rome Trip'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['name'], 'Rome Trip')
        self.assertEqual(r.data['status'], 'active')
        self.assertEqual(r.data['places'], [])

    def test_create_project_full_fields(self):
        r = self.client.post('/api/projects/', {
            'name': 'Paris Trip',
            'description': 'City of lights',
            'start_date': '2026-07-01',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['description'], 'City of lights')
        self.assertEqual(r.data['start_date'], '2026-07-01')

    def test_create_project_missing_name(self):
        r = self.client.post('/api/projects/', {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', r.data)

    @patch('trips.serializers.get_artwork')
    def test_create_project_with_initial_places(self, mock_get):
        mock_get.return_value = ARTWORK_RESPONSE
        r = self.client.post('/api/projects/', {
            'name': 'Art Tour',
            'initial_places': [{'external_id': 27992}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(r.data['places']), 1)
        self.assertEqual(r.data['places'][0]['external_id'], 27992)

    @patch('trips.serializers.get_artwork')
    def test_create_project_with_duplicate_initial_places_rejected(self, mock_get):
        mock_get.return_value = ARTWORK_RESPONSE
        r = self.client.post('/api/projects/', {
            'name': 'Art Tour',
            'initial_places': [{'external_id': 27992}, {'external_id': 27992}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('trips.serializers.get_artwork')
    def test_create_project_with_more_than_10_places_rejected(self, mock_get):
        mock_get.return_value = ARTWORK_RESPONSE
        r = self.client.post('/api/projects/', {
            'name': 'Too Many',
            'initial_places': [{'external_id': i} for i in range(11)],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('trips.serializers.get_artwork')
    def test_create_project_rolls_back_on_invalid_place(self, mock_get):
        from rest_framework.exceptions import ValidationError
        mock_get.side_effect = [ARTWORK_RESPONSE, ValidationError('Not found')]
        r = self.client.post('/api/projects/', {
            'name': 'Rollback Test',
            'initial_places': [{'external_id': 27992}, {'external_id': 99999}],
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Project.objects.count(), 0)

    def test_list_filters_by_status(self):
        make_project(name='Active', status='active')
        make_project(name='Done', status='completed')
        r = self.client.get('/api/projects/?status=active')
        self.assertEqual(r.data['count'], 1)
        self.assertEqual(r.data['results'][0]['name'], 'Active')

    def test_list_is_paginated(self):
        for i in range(12):
            make_project(name=f'Project {i}')
        r = self.client.get('/api/projects/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 12)
        self.assertEqual(len(r.data['results']), 10)


class ProjectDetailAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)
        self.project = make_project(name='My Trip')

    def test_retrieve(self):
        r = self.client.get(f'/api/projects/{self.project.pk}/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['name'], 'My Trip')

    def test_retrieve_not_found(self):
        r = self.client.get('/api/projects/9999/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_partial_update(self):
        r = self.client.patch(f'/api/projects/{self.project.pk}/', {
            'description': 'Updated'
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['description'], 'Updated')

    def test_delete_without_visited_places(self):
        make_place(self.project, external_id=1, visited=False)
        r = self.client.delete(f'/api/projects/{self.project.pk}/')
        self.assertEqual(r.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_delete_blocked_when_place_visited(self):
        make_place(self.project, external_id=1, visited=True)
        r = self.client.delete(f'/api/projects/{self.project.pk}/')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())


# ---------------------------------------------------------------------------
# Places API tests
# ---------------------------------------------------------------------------

class PlacesAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.force_authenticate(user=self.user)
        self.project = make_project()
        cache.clear()

    def _url(self, place_pk=None):
        base = f'/api/projects/{self.project.pk}/places/'
        return base if place_pk is None else f'{base}{place_pk}/'

    @patch('trips.views.get_artwork')
    def test_add_place(self, mock_get):
        mock_get.return_value = ARTWORK_RESPONSE
        r = self.client.post(self._url(), {'external_id': 27992}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.data['external_id'], 27992)
        self.assertEqual(r.data['title'], 'A Sunday on La Grande Jatte')
        self.assertFalse(r.data['visited'])

    def test_add_place_missing_external_id(self):
        r = self.client.post(self._url(), {}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('trips.views.get_artwork')
    def test_add_place_duplicate_rejected(self, mock_get):
        mock_get.return_value = ARTWORK_RESPONSE
        make_place(self.project, external_id=27992)
        r = self.client.post(self._url(), {'external_id': 27992}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already in the project', r.data['detail'])

    @patch('trips.views.get_artwork')
    def test_add_place_exceeds_limit(self, mock_get):
        mock_get.return_value = ARTWORK_RESPONSE
        for i in range(10):
            make_place(self.project, external_id=i)
        r = self.client.post(self._url(), {'external_id': 99}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('at most 10', r.data['detail'])

    @patch('trips.views.get_artwork')
    def test_add_place_invalid_external_id(self, mock_get):
        from rest_framework.exceptions import ValidationError
        mock_get.side_effect = ValidationError('Not found')
        r = self.client.post(self._url(), {'external_id': 99999}, format='json')
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_add_place_to_nonexistent_project(self):
        r = self.client.post('/api/projects/9999/places/', {'external_id': 1}, format='json')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_places(self):
        make_place(self.project, external_id=1)
        make_place(self.project, external_id=2)
        r = self.client.get(self._url())
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['count'], 2)

    def test_retrieve_place(self):
        place = make_place(self.project, external_id=1, title='Mona Lisa')
        r = self.client.get(self._url(place.pk))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['title'], 'Mona Lisa')

    def test_update_notes(self):
        place = make_place(self.project, external_id=1)
        r = self.client.patch(self._url(place.pk), {'notes': 'Breathtaking'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data['notes'], 'Breathtaking')

    def test_mark_visited(self):
        place = make_place(self.project, external_id=1)
        r = self.client.patch(self._url(place.pk), {'visited': True}, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(r.data['visited'])

    def test_mark_all_visited_completes_project(self):
        p1 = make_place(self.project, external_id=1)
        p2 = make_place(self.project, external_id=2)
        self.client.patch(self._url(p1.pk), {'visited': True}, format='json')
        self.client.patch(self._url(p2.pk), {'visited': True}, format='json')
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.STATUS_COMPLETED)

    def test_project_stays_active_until_all_visited(self):
        p1 = make_place(self.project, external_id=1)
        make_place(self.project, external_id=2)
        self.client.patch(self._url(p1.pk), {'visited': True}, format='json')
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, Project.STATUS_ACTIVE)
