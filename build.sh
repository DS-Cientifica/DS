#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput

# Free Render web services do not run preDeployCommand. Keep migrations as the
# final build step so a migration failure prevents the new release from going live.
python manage.py migrate --noinput
