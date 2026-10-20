import os
import sys

project_home = os.path.dirname(os.path.abspath(__file__))
if project_home not in sys.path:
    sys.path.insert(0, project_home)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_api.settings')

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
