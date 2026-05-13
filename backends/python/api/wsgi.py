import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from otel import setup_otel
setup_otel()

application = get_wsgi_application()
