import requests
from django.conf import settings
from django.core.cache import cache
from rest_framework.exceptions import ValidationError

ARTWORK_FIELDS = 'id,title,artist_display,thumbnail'


def get_artwork(external_id: int) -> dict:
    cache_key = f'artwork_{external_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = f'{settings.ART_INSTITUTE_API_BASE}/artworks/{external_id}'
    try:
        response = requests.get(url, params={'fields': ARTWORK_FIELDS}, timeout=10)
    except requests.RequestException as exc:
        raise ValidationError(
            f'Failed to reach the Art Institute API: {exc}'
        )

    if response.status_code == 404:
        raise ValidationError(
            f'Artwork with id {external_id} does not exist in the Art Institute of Chicago API.'
        )
    if not response.ok:
        raise ValidationError(
            f'Art Institute API returned status {response.status_code}.'
        )

    data = response.json().get('data', {})
    result = {
        'external_id': data.get('id'),
        'title': data.get('title') or '',
        'artist': data.get('artist_display') or '',
        'thumbnail_url': _extract_thumbnail(data),
    }
    cache.set(cache_key, result)
    return result


def _extract_thumbnail(data: dict) -> str:
    thumbnail = data.get('thumbnail') or {}
    return thumbnail.get('lqip') or ''
