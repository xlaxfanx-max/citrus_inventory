#!/bin/sh
set -eu

python manage.py check --deploy --fail-level ERROR
python manage.py migrate --noinput
python manage.py migrate --check
python manage.py setup_roles
# A model version bump blanks every board until predictions are rebuilt,
# so rebuild as part of the release rather than waiting for the nightly job.
python manage.py build_predictions
