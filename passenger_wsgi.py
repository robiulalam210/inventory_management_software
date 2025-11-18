import os
import sys

# Add the project directory to the Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inventory_api.settings')

# Initialize Django application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()