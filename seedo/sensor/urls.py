# camera/urls.py
from common.decorators import token_required
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.urls import path

from .views import fall_recognition


@token_required
def index(request):
    return render(request, "sensor/index.html")


app_name = "sensor"

urlpatterns = [path("", index, name="get_sensor"), path("fall_recognition/", fall_recognition, name="fall_recognition")] + static(
    settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
)
