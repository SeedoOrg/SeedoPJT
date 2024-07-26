import os
from datetime import timedelta
from pathlib import Path

import environ

# 프로젝트 내부에서의 경로구성: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
# 환경 설정 읽기
env = environ.Env(
    # 타입 설정, 기본값
    DEBUG=(bool, False)
)
env_path = BASE_DIR.parent / ".env"
environ.Env.read_env(env_file=env_path)

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = True

ALLOWED_HOSTS = ["*"]
# 이메일 설정
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.naver.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
# 내비 설정
TMAP_API_KEY = env("TMAP_API_KEY")

# 어플리케이션 정의
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "common",
    "accounts",
    "matching",
    "record",
    "qna",
    "sensor",
    "navigation",
    "walking_mode",
    "storages",
    "ocr",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

AUTH_USER_MODEL = "accounts.CustomUser"

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"

# JWT 관련 설정
JWT_SECRET_KEY = env("JWT_SECRET_KEY")
JWT_REFRESH_SECRET_KEY = env("JWT_REFRESH_SECRET_KEY")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRATION = timedelta(minutes=1)
JWT_REFRESH_TOKEN_EXPIRATION = timedelta(days=30)

# 개발 환경 설정
DJANGO_ENVIRONMENT = env("DJANGO_ENVIRONMENT")

if DJANGO_ENVIRONMENT == "development":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

else :
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",  # 고정
            "NAME": env("DATABASE_NAME"),  # DB 이름
            "USER": env("DATABASE_USER"),  # 계정
            "PASSWORD": env("DATABASE_PW"),  # 암호
            "HOST": env("DATABASE_HOST"),  # IP
            "PORT": "3306",  # default
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True

if DJANGO_ENVIRONMENT == "development":
    MEDIA_ROOT = os.path.join(BASE_DIR, "media")
    MEDIA_URL = "/media/"

else:
    # S3 Settings for Media Files
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME")

    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_MEDIA_LOCATION = "media"

    DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/{AWS_MEDIA_LOCATION}/"


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")  # collectstatic으로 모아놓을 디렉토리
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
    os.path.join(BASE_DIR, "accounts", "static"),
    os.path.join(BASE_DIR, "record", "static"),
    os.path.join(BASE_DIR, "qna", "static"),
    os.path.join(BASE_DIR, "navigation", "static"),
    os.path.join(BASE_DIR, "walking_mode", "static"),
    os.path.join(BASE_DIR, "ocr", "static"),
]  # 프로젝트 수준의 static 디렉토리


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
