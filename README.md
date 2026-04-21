## Django Project
A vanilla Django 5.2.6 starting project ready for development.

### Quick Start

1. Open this repository in a GitHub Codespace (recommended) or local development environment
2. The Python/Django environment will be automatically configured
3. Navigate to the Django Project folder:
   ```bash
   cd "Django Project"
   ```
4. Run the requirements file:
   ```bash
   pip install -r requirements
   ```
5. Run migrations:
    ```bash
   python manage.py migrate
   ```
6. Load initial data:
   ```bash
    python manage.py loaddata supply_chain/fixtures/users.json supply_chain/fixtures/councils.json supply_chain/fixtures/contractor.json supply_chain/fixtures/project.json supply_chain/fixtures/package.json supply_chain/fixtures/bid.json supply_chain/fixtures/team.json supply_chain/fixtures/activity.json
    ```
7. Start the development server:
    ```bash
   python manage.py runserver
   ```
8. Access the Django application at the forwarded port (typically port 8000)

### Default Credentials

**Admin Panel:**
-Username: admin
-Password: django123

**#Council User:**
-Username: council1
-Password: django123

**#Contractor User:**
-Username: contractor1
-Password: django123

### Dependencies

- Python 3.12
- Django 5.2.6 (latest version)
- All dependencies are listed in `requirements.txt`

The development environment is pre-configured with VS Code extensions for Python and Django development.
