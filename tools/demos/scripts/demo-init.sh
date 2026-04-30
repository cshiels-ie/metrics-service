#!/bin/sh
# Demo environment initialisation.
# Extends the standard init.sh with demo-specific setup:
#   - Creates a demo superuser (demo_admin / demo_password)
#   - Creates a DRF token for the BI connector
#   - Enables the BI_CONNECTOR feature flag
set -e

export PATH="/app/.venv/bin:$PATH"

echo "=== Running database migrations ==="
python manage.py migrate --noinput

echo "=== Initialising default settings ==="
python manage.py metrics_service init-default-settings

echo "=== Initialising django-ansible-base ServiceID ==="
python manage.py metrics_service init-service-id

echo "=== Initialising system tasks ==="
python manage.py metrics_service init-system-tasks

echo "=== Creating demo superuser (demo_admin) ==="
python manage.py shell -c "
from apps.core.models import User
if not User.objects.filter(username='demo_admin').exists():
    User.objects.create_superuser('demo_admin', 'demo@example.com', 'demo_password')
    print('Created demo_admin superuser')
else:
    print('demo_admin already exists')
"

echo "=== Creating BI connector API token ==="
python manage.py shell -c "
from rest_framework.authtoken.models import Token
from apps.core.models import User
user = User.objects.get(username='demo_admin')
token, created = Token.objects.get_or_create(user=user)
print()
print('=== BI Connector Token ===')
print(f'  Authorization: Token {token.key}')
print()
print('  curl -H \"Authorization: Token ' + token.key + '\" http://localhost:8000/api/v1/bi/metrics/daily/')
print()
"

echo "=== Demo initialisation complete ==="
echo "   Metrics Service: http://localhost:8000"
echo "   API docs:        http://localhost:8000/api/docs/"
echo "   Grafana:         http://localhost:3000  (admin / admin)"
