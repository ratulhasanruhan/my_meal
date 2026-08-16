#!/bin/bash
# Vercel static build: collect static assets into staticfiles_build/static.
set -e

# Vercel's build image ships a uv-managed Python that refuses a plain
# `pip install` (PEP 668), so install into an isolated virtualenv instead.
python3 -m venv .build_venv
.build_venv/bin/python -m pip install --upgrade pip
.build_venv/bin/python -m pip install -r requirements.txt

.build_venv/bin/python manage.py collectstatic --noinput --clear
