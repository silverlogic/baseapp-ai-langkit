from pathlib import Path

from django.utils.translation import gettext_lazy as _

from baseapp_ai_langkit.settings import *  # noqa

from .env import env

BASE_DIR = Path(__file__).resolve().parent.parent

APPS_DIR = BASE_DIR

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "secret-for-test-app"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ["*"]

MEDIA_ROOT = "/media/"
MEDIA_URL = "/media/"
STATIC_ROOT = "/static/"
STATIC_URL = "/static/"


# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_extensions",
    "pgtrigger",
    "rest_framework",
    "rest_framework.authtoken",
    "constance",
    "constance.backends.database",
    "adminsortable2",
    "baseapp_ai_langkit",
    "baseapp_ai_langkit.base",
    "baseapp_ai_langkit.chats",
    "baseapp_ai_langkit.executors",
    "baseapp_ai_langkit.runners",
    "baseapp_ai_langkit.vector_stores",
    "baseapp_ai_langkit.slack",
    "baseapp_ai_langkit.embeddings",
    "baseapp_mcp",
    "baseapp_mcp.logs",
    "baseapp_mcp.rate_limits",
    "testproject.apps.example",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "testproject.urls"

# Sites
URL = env("URL", "", required=False)
FRONT_URL = env("FRONT_URL", "", required=False)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(APPS_DIR / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database
# https://docs.djangoproject.com/en/3.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASS"),
        "HOST": env("DB_SERVICE"),
        "PORT": env("DB_PORT"),
        "ATOMIC_REQUESTS": True,
    }
}

# Password validation
# https://docs.djangoproject.com/en/3.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/3.2/topics/i18n/

LANGUAGE_CODE = "en-us"
LANGUAGES = [("en", _("English"))]

TIME_ZONE = "UTC"

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Celery
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

ADMIN_TIME_ZONE = "UTC"

# URL Shortening
URL_SHORTENING_PREFIX = "c"

# Constance
CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"

# Rest Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PAGINATION_CLASS": "testproject.api.pagination.DefaultPageNumberPagination",
    "PAGE_SIZE": 30,
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.NamespaceVersioning",
    "ORDERING_PARAM": "order_by",
    "SEARCH_PARAM": "q",
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "root": {"handlers": ["console"], "level": "DEBUG"},
    "formatters": {
        "simple": {"format": "[%(name)s] [%(levelname)s] %(message)s"},
        "simple_date": {
            "format": "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            "datefmt": "%Y/%m/%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "loggers": {},
}

BASEAPP_AI_LANGKIT_SLACK_SLASH_COMMANDS = [
    "testproject.extensions.baseapp_ai_langkit.slack.rest_framework.slash_commands.example.viewset.SlackExampleSlashCommandViewSet"
]
BASEAPP_AI_LANGKIT_SLACK_INTERACTIVE_ENDPOINT_HANDLERS = [
    "testproject.extensions.baseapp_ai_langkit.slack.rest_framework.slash_commands.example.viewset.SlackExampleInteractiveEndpointHandler"
]

# baseApp-ai-langkit.embeddings Settings
BASEAPP_AI_LANGKIT_EMBEDDINGS_EMBEDDING_MODEL_DIMENSIONS = 1024
BASEAPP_AI_LANGKIT_EMBEDDINGS_CHUNK_SIZE = 512
BASEAPP_AI_LANGKIT_EMBEDDINGS_CHUNK_OVERLAP = 64

# MCP Tools only, limit per user
MCP_ENABLE_TOOL_RATE_LIMITING = True
MCP_TOOL_RATE_LIMIT_PERIOD = 60  # seconds
MCP_TOOL_RATE_LIMIT_CALLS = 30  # max calls per period

# MCP Token Limits
MCP_ENABLE_MONTHLY_LIMITS = True
MCP_MONTHLY_TOKEN_LIMIT = 1000000
MCP_MONTHLY_TRANSFORMER_CALL_LIMIT = 1000000
