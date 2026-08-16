#!/bin/bash
# Vercel static build: collect static assets into staticfiles_build/static.
set -e

python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

python3 manage.py collectstatic --noinput --clear
