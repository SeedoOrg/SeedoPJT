from django.urls import path

from .views import *

app_name = "record"

urlpatterns = [
    # 유저 id를 전달받아서 해당 유저의 파손기록에 접근하도록 매핑
    path("break/<int:request_id>/", broken_view, name="broken_list"),
    # 유저 id를 전달받아서 해당 유저의 사고기록에 접근하도록 매핑
    path("accident/<int:request_id>/", accident_view, name="accident_list"),
    # DB에 사고기록 저장하는 url로 매핑
    path("accident/save_accident/", save_accident_view, name="save_accident_view"),
    # DB에 파손기록 저장하는 url로 매핑
    path("break/save_break/", save_broken_view, name="save_broken_view"),
]
