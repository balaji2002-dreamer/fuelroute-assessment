import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "development-only-change-me")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")]
ROOT_URLCONF = "config.urls"
INSTALLED_APPS = ["django.contrib.contenttypes", "django.contrib.staticfiles", "fuel"]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "django.middleware.common.CommonMiddleware"]
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [BASE_DIR / "templates"], "APP_DIRS": True, "OPTIONS": {"context_processors": []}}]
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
GEOCODER_URL = os.getenv("GEOCODER_URL", "https://nominatim.openstreetmap.org/search")
GEOCODER_USER_AGENT = os.getenv("GEOCODER_USER_AGENT", "FuelRouteAssessment/1.0 (configure-contact-email)")
ROUTER_URL = os.getenv("ROUTER_URL", "https://router.project-osrm.org/route/v1/driving")

