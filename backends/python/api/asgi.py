import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from otel import setup_otel
setup_otel()

application = get_asgi_application()
