web: gunicorn lifelink.wsgi:application --bind 0.0.0.0:$PORT
worker: celery -A lifelink worker --loglevel=info
