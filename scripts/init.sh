#!/bin/sh
set -e

export PATH="/app/.venv/bin:$PATH"

echo "Running database migrations..."
python manage.py migrate --noinput

# puts defaults in the Setting DB table
echo "Initializing default settings..."
python manage.py metrics_service init-default-settings

# Initialize ServiceID for django-ansible-base
echo "Initializing django-ansible-base ServiceID..."
python manage.py metrics_service init-service-id

# puts TASK_GROUPS in the Task DB table
echo "Initializing system tasks..."
python manage.py metrics_service init-system-tasks
