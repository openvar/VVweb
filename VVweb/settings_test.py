# VVweb/settings_test.py

from .settings import *  # import ALL real behaviour
import os

# ---------------------------------------------------------------------
# Ensure a consistent test environment
# ---------------------------------------------------------------------

os.environ.setdefault("ENVIRONMENT", "test")

# ---------------------------------------------------------------------
# DATABASE — REAL ENGINE, NEW DB
# ---------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "vvweb_test",
        "USER": "vvweb",
        "PASSWORD": "vvweb",
        "HOST": "localhost",
        "PORT": "5432",
        "TEST": {
            "NAME": "vvweb_test",
        },
    }
}


# ---------------------------------------------------------------------
# EMAIL — REAL TOKENS, NO REAL DELIVERY
# ---------------------------------------------------------------------

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ---------------------------------------------------------------------
# ALLAUTH — LOCK BEHAVIOUR
# ---------------------------------------------------------------------

ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_USERNAME_REQUIRED = False

LOGIN_REDIRECT_URL = "/verify/"
LOGOUT_REDIRECT_URL = "/"

# ---------------------------------------------------------------------
# SECURITY — TEST CONTEXT ONLY
# ---------------------------------------------------------------------

DEBUG = False
SECRET_KEY = "test-secret-key-never-used-in-prod"

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# ---------------------------------------------------------------------
# PERFORMANCE
# ---------------------------------------------------------------------

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# ---------------------------------------------------------------------
# ASYNC / TASKS
# ---------------------------------------------------------------------

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_IGNORE_RESULT = False
CELERY_TASK_STORE_EAGER_RESULT = True

# ---------------------------------------------------------------------
# TEST FLAG
# ---------------------------------------------------------------------

VVWEB_TEST_MODE = True

# ---------------------------------------------------------------------
# Disable reCAPTCHA validation in tests (django-recaptcha v2)
# ---------------------------------------------------------------------

RECAPTCHA_PUBLIC_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
RECAPTCHA_PRIVATE_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"

SILENCED_SYSTEM_CHECKS = ["captcha.recaptcha_test_key_error"]
