"""
Django settings for fieldmax project - PRODUCTION READY
Optimized for Render deployment with PostgreSQL database
"""

import dj_database_url
import sys
import secrets
from pathlib import Path
import os

# ============================================
# LOAD ENVIRONMENT VARIABLES
# ============================================
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed

# ============================================
# BASE DIRECTORY
# ============================================
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# DEBUG SETTING (MUST BE DEFINED EARLY)
# ============================================
DEBUG = os.getenv("DEBUG", "False").lower() in ('true', '1', 't')

# ============================================
# SECURITY SETTINGS - RENDER OPTIMIZED
# ============================================
SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    if DEBUG:
        # Development fallback
        SECRET_KEY = 'django-insecure-dev-key-for-local-testing-only'
        print("⚠️  WARNING: Using development SECRET_KEY. Set SECRET_KEY in Render environment variables for production.")
    else:
        # In production, generate a secure key if not set (won't raise error)
        SECRET_KEY = 'django-insecure-' + secrets.token_urlsafe(32)
        print("⚠️  WARNING: Generated SECRET_KEY for this session. Set SECRET_KEY in Render environment variables.")

# Render specific configuration
RENDER_EXTERNAL_HOSTNAME = os.getenv('RENDER_EXTERNAL_HOSTNAME')

if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = [
        RENDER_EXTERNAL_HOSTNAME,
        'localhost',
        '127.0.0.1',
    ]
else:
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# ✅ CRITICAL: CSRF Trusted Origins for Render
CSRF_TRUSTED_ORIGINS = [
    f"https://{RENDER_EXTERNAL_HOSTNAME}",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
] if RENDER_EXTERNAL_HOSTNAME else [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# ✅ CRITICAL: Proxy SSL Header for Render
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

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
    
    # Cloudinary storage (conditional)
    'cloudinary_storage',
    'cloudinary',
    
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Django extensions
    'django_extensions',
    
    # REST framework
    'rest_framework',
    'rest_framework.authtoken',
    
    # Your apps
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
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ✅ WhiteNoise for static files
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

                # ✅ CUSTOM CONTEXT PROCESSORS
                'website.context_processors.categories_processor',
                'website.context_processors.dashboard_url',
                'website.context_processors.cart_data',
                'inventory.context_processors.categories',
            ],
        },
    },
]

# ============================================
# WSGI APPLICATION
# ============================================
WSGI_APPLICATION = 'fieldmax.wsgi.application'

# ============================================
# DATABASE CONFIGURATION - RENDER OPTIMIZED
# ============================================
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # ✅ Render provides PostgreSQL URLs that may start with postgres://
    # dj_database_url handles the conversion to postgresql://
    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,  # Enable connection health checks
            ssl_require=True  # Render requires SSL
        )
    }
    print(f"🔗 Using PostgreSQL database from DATABASE_URL")
elif all([os.getenv('DB_NAME'), os.getenv('DB_USER'), os.getenv('DB_PASSWORD'), os.getenv('DB_HOST')]):
    # Use individual database credentials
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME'),
            'USER': os.getenv('DB_USER'),
            'PASSWORD': os.getenv('DB_PASSWORD'),
            'HOST': os.getenv('DB_HOST'),
            'PORT': os.getenv('DB_PORT', '5432'),
            'OPTIONS': {
                'sslmode': 'require',
            },
            'CONN_MAX_AGE': 600,
            'CONN_HEALTH_CHECKS': True,
        }
    }
    print(f"🔗 Using PostgreSQL database: {os.getenv('DB_NAME')} on {os.getenv('DB_HOST')}")
else:
    # Development or fallback - SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
    print(f"🔧 {'Development' if DEBUG else 'Production'} mode - using SQLite database")

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
# STORAGE CONFIGURATION - RENDER OPTIMIZED
# ============================================
# ✅ Use simple StaticFilesStorage to avoid CSS map errors
STATICFILES_STORAGE = 'whitenoise.storage.StaticFilesStorage'

# Modern Django storage configuration
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.StaticFilesStorage",
    },
}

# Whitenoise configuration
WHITENOISE_KEEP_ONLY_HASHED_FILES = False  # Set to False to avoid issues
WHITENOISE_AUTOREFRESH = DEBUG
WHITENOISE_MAX_AGE = 31536000 if not DEBUG else 0

# ============================================
# STATIC FILES (CSS, JavaScript, Images)
# ============================================
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / "static",
]

STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

# ============================================
# CLOUDINARY CONFIGURATION (OPTIONAL)
# ============================================
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

if all([CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET]):
    try:
        import cloudinary
        import cloudinary.uploader
        import cloudinary.api
        
        cloudinary.config(
            cloud_name=CLOUDINARY_CLOUD_NAME,
            api_key=CLOUDINARY_API_KEY,
            api_secret=CLOUDINARY_API_SECRET,
            secure=True
        )
        print(f"☁️  Cloudinary configured: {CLOUDINARY_CLOUD_NAME}")
    except ImportError:
        print("⚠️  Cloudinary packages not installed. Media uploads disabled.")
else:
    # Fallback to local file storage
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
    print("⚠️  Cloudinary credentials missing. Using local file storage.")

# ============================================
# MEDIA FILES
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
        'fieldmaxlimited@gmail.com',
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
FIELDMAX_EMAIL = "fieldmaxlimited@gmail.com"
FIELDMAX_WEBSITE = "www.fieldmax.co.ke"
FIELDMAX_PIN = "--------"
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
    print("📧 Development mode - using console email backend")
else:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
    EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
    EMAIL_USE_TLS = True
    EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
    EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
    DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@fieldmax.co.ke')
    SERVER_EMAIL = DEFAULT_FROM_EMAIL
    
    if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
        print(f"📧 Email configured: {EMAIL_HOST_USER}")
    else:
        print("⚠️  Email credentials missing. Email functionality disabled.")

# ============================================
# LOGGING CONFIGURATION
# ============================================
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

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
        'render': {
            'format': '{asctime} [{levelname}] {message}',
            'style': '{',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    },
    
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'render',
            'level': 'INFO',
        },
    },
    
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'inventory': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'sales': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# ============================================
# CACHING
# ============================================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'fieldmax-cache',
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
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
# SIMPLIFIED SETTINGS VALIDATION
# ============================================
def validate_settings():
    """Validate critical settings on startup"""
    
    warnings = []
    
    # Check Render environment
    if not RENDER_EXTERNAL_HOSTNAME and not DEBUG:
        warnings.append("⚠️  RENDER_EXTERNAL_HOSTNAME not set. This should be automatically set by Render.")
    
    # Check Cloudinary credentials
    cloudinary_vars = {
        'CLOUDINARY_CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
        'CLOUDINARY_API_KEY': os.getenv('CLOUDINARY_API_KEY'),
        'CLOUDINARY_API_SECRET': os.getenv('CLOUDINARY_API_SECRET')
    }
    
    missing_cloudinary = [name for name, val in cloudinary_vars.items() if not val]
    
    if missing_cloudinary:
        warnings.append("⚠️  Cloudinary credentials not fully configured!")
    
    # Check SECRET_KEY warning (not error)
    if not DEBUG and SECRET_KEY.startswith('django-insecure-'):
        warnings.append("⚠️  Generated SECRET_KEY in use. Set SECRET_KEY in Render environment variables.")
    
    if warnings:
        print("\n" + "="*70)
        print("⚠️  SETTINGS WARNINGS:")
        for warning in warnings:
            print(f"   {warning}")
        print("="*70 + "\n")
    else:
        print("\n✅ Settings validated successfully!\n")

# ============================================
# RUN VALIDATION ONLY ONCE (Fix for duplicate output)
# ============================================
if os.environ.get('RUN_MAIN') == 'true' or 'runserver' not in sys.argv:
    # Run validation on startup
    if 'runserver' in sys.argv or 'migrate' in sys.argv or 'collectstatic' in sys.argv:
        validate_settings()
    
    # ============================================
    # FINAL STARTUP MESSAGE
    # ============================================
    print(f"\n🚀 FieldMax initialized successfully!")
    print(f"   Environment: {'DEVELOPMENT' if DEBUG else 'PRODUCTION'}")
    print(f"   Platform: {'Render' if RENDER_EXTERNAL_HOSTNAME else 'Local'}")
    print(f"   Database: {DATABASES['default']['ENGINE']}")
    print(f"   Allowed Hosts: {ALLOWED_HOSTS}")
    print("="*50 + "\n")