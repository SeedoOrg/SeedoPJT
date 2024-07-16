from django.urls import path

from .views import *

app_name = "record"

urlpatterns = [
    path("break/<int:request_id>/", broken_view, name="broken_list"),
    path("accident/<int:request_id>/", accident_view, name="accident_list"),
    path("accident/save_accident/", save_accident_view, name="save_accident_view"),
    path("break/save_break/", save_broken_view, name="save_broken_view"),
]
