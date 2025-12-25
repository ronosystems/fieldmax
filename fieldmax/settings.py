"""
Django settings for fieldmax project - FIXED CLOUDINARY CONFIGURATION
"""
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
import os
import sys


# ============================================
# BASE DIRECTORY
# ============================================
BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================
# SECURITY SETTINGS
# ============================================
SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY environment variable is not set! "
        "Please set it in your Render environment variables."
    )

DEBUG = os.getenv("DEBUG", "False") == "True"

ALLOWED_HOSTS = [
    "newfieldmax.onrender.com",
    "127.0.0.1",
    "localhost",
]

# Security settings for production
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

APPEND_SLASH = True


# ============================================
# INSTALLED APPLICATIONS
# ============================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    
    # ✅ FIXED: Cloudinary MUST be before staticfiles
    'cloudinary_storage',
    'cloudinary',
    
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django_extensions',
    
    'rest_framework',
    'rest_framework.authtoken',
    
    'users.apps.UsersConfig',
    'website.apps.WebsiteConfig',
    'inventory.apps.InventoryConfig',
    'sales.apps.SalesConfig',
]


# ============================================
# MIDDLEWARE
# ============================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'website.middleware.DashboardSessionMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ============================================
# URL CONFIGURATION
# ============================================
ROOT_URLCONF = 'fieldmax.urls'


# ============================================
# TEMPLATES
# ============================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / "website" / "templates",
            BASE_DIR / "templates",
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'website.context_processors.dashboard_url',
            ],
        },
    },
]


# ============================================
# WSGI APPLICATION
# ============================================
WSGI_APPLICATION = 'fieldmax.wsgi.application'


# ============================================
# DATABASE CONFIGURATION
# ============================================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv("DB_NAME"),
        'USER': os.getenv("DB_USER"),
        'PASSWORD': os.getenv("DB_PASSWORD"),
        'HOST': os.getenv("DB_HOST"),
        'PORT': os.getenv("DB_PORT"),
        'CONN_MAX_AGE': 600,
    }
}


# ============================================
# PASSWORD VALIDATION
# ============================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ============================================
# INTERNATIONALIZATION
# ============================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_L10N = True
USE_TZ = True

USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ','
DECIMAL_SEPARATOR = '.'


# ============================================
# STATIC FILES (CSS, JavaScript, Images)
# ============================================
STATIC_URL = '/static/'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]


# ============================================
# ✅ FIXED: CLOUDINARY CONFIGURATION
# ============================================
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Cloudinary settings dictionary
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'API_SECRET': os.getenv('CLOUDINARY_API_SECRET')
}

# Configure cloudinary module directly
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True  # Use HTTPS
)

# ✅ ALWAYS use Cloudinary for media storage (production & development)
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# ============================================
# MEDIA FILES (User Uploads)
# ============================================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Maximum upload size (100MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600


# ============================================
# AUTHENTICATION & AUTHORIZATION
# ============================================
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

SESSION_COOKIE_AGE = 86400
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]


# ============================================
# REST FRAMEWORK CONFIGURATION
# ============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    
    'DEFAULT_FILTER_BACKENDS': [
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
    
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
    
    'DATETIME_FORMAT': '%Y-%m-%d %H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
    'TIME_FORMAT': '%H:%M:%S',
}


# ============================================
# INVENTORY MANAGEMENT CONFIGURATION
# ============================================
INVENTORY_CONFIG = {
    'LOW_STOCK_THRESHOLD': 5,
    'CRITICAL_STOCK_THRESHOLD': 2,
    
    'ENABLE_EMAIL_ALERTS': True,
    'ENABLE_SMS_ALERTS': False,
    'LOW_STOCK_ALERT_EMAILS': [
        'inventory@fieldmax.com',
    ],
    
    'ALLOW_NEGATIVE_STOCK': False,
    'AUTO_GENERATE_CODES': True,
    'REQUIRE_SKU_FOR_SINGLE_ITEMS': True,
    'REQUIRE_PURCHASE_ORDER_REFERENCE': False,
    
    'PRODUCT_CODE_LENGTH': 3,
    'PRODUCT_CODE_PREFIX_LENGTH': 4,
    
    'REQUIRE_STOCK_ENTRY_NOTES': False,
    'REQUIRE_STOCK_ENTRY_REFERENCE': True,
    'MAX_QUANTITY_PER_ENTRY': 10000,
    
    'STOCK_REPORT_DAYS': 30,
    'ENABLE_STOCK_ALERTS': True,
    'ALERT_CHECK_INTERVAL': 3600,
}


# ============================================
# COMPANY INFORMATION
# ============================================
FIELDMAX_COMPANY_NAME = "FIELDMAX SUPPLIERS LTD"
FIELDMAX_COMPANY_SHORT_NAME = "FIELDMAX"
FIELDMAX_ADDRESS = "Nairobi, Kenya"
FIELDMAX_TEL = "+254722558544"
FIELDMAX_EMAIL = "info@fieldmax.co.ke"
FIELDMAX_WEBSITE = "www.fieldmax.co.ke"
FIELDMAX_PIN = "-"
FIELDMAX_VAT_RATE = 0.16

FIELDMAX_RECEIPT_PREFIX = "RCT"
FIELDMAX_INVOICE_PREFIX = "INV"
FIELDMAX_PURCHASE_ORDER_PREFIX = "PO"
FIELDMAX_RETURN_PREFIX = "RET"

FIELDMAX_BUSINESS_HOURS = {
    'Monday': '08:00-18:00',
    'Tuesday': '08:00-18:00',
    'Wednesday': '08:00-18:00',
    'Thursday': '08:00-18:00',
    'Friday': '08:00-18:00',
    'Saturday': '09:00-17:00',
    'Sunday': 'Closed',
}


# ============================================
# EMAIL CONFIGURATION
# ============================================
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@fieldmax.co.ke')
    SERVER_EMAIL = DEFAULT_FROM_EMAIL


# ============================================
# LOGGING CONFIGURATION
# ============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {process:d} {thread:d} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '[{levelname}] {asctime} - {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'level': 'INFO',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'inventory_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'inventory.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'sales_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'sales.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'INFO',
        },
        'error_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'errors.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
            'level': 'ERROR',
        },
    },
    
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'inventory': {
            'handlers': ['console', 'inventory_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'sales': {
            'handlers': ['console', 'sales_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)


# ============================================
# CACHING
# ============================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}


# ============================================
# DEFAULT PRIMARY KEY FIELD TYPE
# ============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ============================================
# ADMIN CUSTOMIZATION
# ============================================
ADMIN_SITE_HEADER = "FIELDMAX Administration"
ADMIN_SITE_TITLE = "FIELDMAX Admin Portal"
ADMIN_INDEX_TITLE = "Welcome to FIELDMAX Administration"


# ============================================
# CUSTOM SETTINGS VALIDATION
# ============================================
def validate_settings():
    """Validate critical settings on startup"""
    import sys
    
    errors = []
    warnings = []
    
    # Check logs directory
    if not LOGS_DIR.exists():
        try:
            LOGS_DIR.mkdir(parents=True)
        except Exception as e:
            errors.append(f"Cannot create logs directory: {e}")
    
    # Check Cloudinary credentials
    if not all([
        os.getenv('CLOUDINARY_CLOUD_NAME'),
        os.getenv('CLOUDINARY_API_KEY'),
        os.getenv('CLOUDINARY_API_SECRET')
    ]):
        warnings.append("⚠️  Cloudinary credentials not set! Media uploads will fail.")
        warnings.append("   Set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET")
    else:
        print("✅ Cloudinary configured successfully")
    
    if errors:
        print("\n❌ SETTINGS VALIDATION ERRORS:")
        for error in errors:
            print(f"   - {error}")
        print()
    
    if warnings:
        print("\n⚠️  SETTINGS WARNINGS:")
        for warning in warnings:
            print(f"   {warning}")
        print()

# Run validation
if 'runserver' in sys.argv or 'migrate' in sys.argv:
    validate_settings()