from common.decorators import token_required
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import render
from django.urls import include, path


@token_required
def index(request):
    return render(request, "index.html", {"MEDIA_URL": settings.MEDIA_URL})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", index, name="home"),
    path("matching/", include("matching.urls")),
    path("record/", include("record.urls")),
    path("qna/", include("qna.urls")),
    path("sensor/", include("sensor.urls")),
    path("nav/", include("navigation.urls")),
    path("walking_mode/", include("walking_mode.urls")),
    path("ocr/", include("ocr.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
