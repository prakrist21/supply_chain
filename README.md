[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DCR5jlI8)
[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/p2vSntpM)
# WAT-2025

## PRAKRIST MAHARJAN

This repository contains two main folders:

## Portfolio
A folder for portfolio-related projects and files. 
Using the following:
```bash
   python my_test_web_server.py
```
Will run a simple webserver which will set the portfolio directory as root.

## Django Project
A vanilla Django 5.2.6 starting project ready for development.

### Quick Start

1. Open this repository in a GitHub Codespace (recommended) or local development environment
2. The Python/Django environment will be automatically configured
3. Navigate to the Django Project folder:
   ```bash
   cd "Django Project"
   ```
4. Run migrations:
    ```bash
   python manage.py migrate
   ```
5. Load initial data:
   ```bash
    python manage.py loaddata supply_chain/fixtures/users.json supply_chain/fixtures/councils.json supply_chain/fixtures/contractor.json supply_chain/fixtures/project.json supply_chain/fixtures/package.json supply_chain/fixtures/bid.json supply_chain/fixtures/team.json supply_chain/fixtures/activity.json
    ```
6. Start the development server:
    ```bash
   python manage.py runserver
   ```
7. Access the Django application at the forwarded port (typically port 8000)

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
