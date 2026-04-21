# Django Project

This is a vanilla Django 5.2.6 starting project created for the WAT-2025 repository.

## Setup

The project is already configured and ready to run. The required dependencies are installed automatically when using the codespace.

## Running the Development Server

To start the Django development server:

```bash
cd "Django Project"
python manage.py runserver
```

The server will be available at http://localhost:8000 (or the forwarded port in codespaces).

## Project Structure

- `manage.py` - Django's command-line utility
- `myproject/` - Main Django project package
  - `settings.py` - Django settings
  - `urls.py` - URL configuration
  - `wsgi.py` - WSGI configuration for deployment
  - `asgi.py` - ASGI configuration for async deployment

## Database

The project uses SQLite by default. The database file `db.sqlite3` is created automatically when you run migrations.

Initial migrations have already been applied.