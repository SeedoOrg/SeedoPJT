from common.decorators import token_required
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.urls import path

from .views import ImageUploadView


@token_required
def index(request):
    return render(request, "walking_mode/index.html")


app_name = "walking_mode"

urlpatterns = [path("test/", ImageUploadView.as_view(), name="test"), path("", index, name="index")]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
