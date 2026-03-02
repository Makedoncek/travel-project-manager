# Travel Project Manager API

REST API for managing travel projects and places, built with Django REST Framework. Users create travel projects, add places (validated against the [Art Institute of Chicago API](https://api.artic.edu/docs/)), attach notes, and mark places as visited.

## Quick Start

### Local

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows
# source .venv/bin/activate     # Linux/Mac

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Docker

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000/api/`.

## Authentication

All endpoints require **HTTP Basic Authentication**. Create a user first:

```bash
# Local
python manage.py createsuperuser

# Docker
docker compose exec web python manage.py createsuperuser
```

Then pass credentials with every request:

```bash
curl -u username:password http://localhost:8000/api/projects/
```

Or use the **Authorize** button in the Swagger UI.

## API Documentation

Interactive API docs are available once the server is running:

- **Swagger UI:** [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
- **ReDoc:** [http://localhost:8000/api/redoc/](http://localhost:8000/api/redoc/)
- **OpenAPI schema (JSON):** [http://localhost:8000/api/schema/](http://localhost:8000/api/schema/)

## API Endpoints

### Projects

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/projects/` | List all projects (paginated) |
| POST | `/api/projects/` | Create a project (optionally with places) |
| GET | `/api/projects/{id}/` | Get a single project with its places |
| PATCH | `/api/projects/{id}/` | Update project name, description, or start_date |
| DELETE | `/api/projects/{id}/` | Delete a project (blocked if any place is visited) |

**Filter by status:** `GET /api/projects/?status=active` or `?status=completed`

### Places (nested under a project)

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/projects/{id}/places/` | List all places in a project |
| POST | `/api/projects/{id}/places/` | Add a place to a project |
| GET | `/api/projects/{id}/places/{place_id}/` | Get a single place |
| PATCH | `/api/projects/{id}/places/{place_id}/` | Update notes or mark as visited |

## Example Requests

### Create a project with places

```bash
curl -u username:password -X POST http://localhost:8000/api/projects/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chicago Art Tour",
    "description": "Visit famous artworks",
    "start_date": "2026-06-01",
    "initial_places": [
      {"external_id": 27992},
      {"external_id": 129884}
    ]
  }'
```

### Add a place to an existing project

```bash
curl -u username:password -X POST http://localhost:8000/api/projects/1/places/ \
  -H "Content-Type: application/json" \
  -d '{"external_id": 28560}'
```

### Update notes and mark as visited

```bash
curl -u username:password -X PATCH http://localhost:8000/api/projects/1/places/1/ \
  -H "Content-Type: application/json" \
  -d '{"notes": "Amazing painting!", "visited": true}'
```

## Business Rules

- Each project can have **1 to 10 places**
- Places are validated against the Art Institute of Chicago API before being added
- The same artwork cannot be added to a project twice
- A project **cannot be deleted** if any of its places are marked as visited
- When **all places** in a project are marked as visited, the project status automatically changes to `completed`

## Postman Collection

Import `postman_collection.json` into Postman. Set the `username` and `password` variables to your superuser credentials. All endpoints are pre-configured with Basic Auth and example request bodies.

## Running Tests

```bash
# Local
python manage.py test trips

# Docker
docker compose exec web python manage.py test trips
```

## Tech Stack

- Python 3.12+ / Django 6 / Django REST Framework 3.16
- drf-spectacular for OpenAPI/Swagger documentation
- SQLite (default, no setup needed)
- Art Institute of Chicago API for place data and validation
