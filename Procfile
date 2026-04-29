web: python manage.py migrate && python manage.py seed && gunicorn PlaytoPayout.wsgi:application --bind 0.0.0.0:8000
worker: celery -A PlaytoPayout worker --loglevel=info --without-heartbeat --without-gossip --without-mingle
