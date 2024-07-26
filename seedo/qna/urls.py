from django.urls import path

from .views import *

app_name = "qna"

urlpatterns = [
    # 문의게시판 첫 화면에 매핑
    path("", QnAListView.as_view(), name="qna-list"),
    # 문의 상세내용에 대해 매핑
    path("<int:pk>/", QnADetailView.as_view(), name="qna-detail"),
    # 문의 등록하는 화면에 매핑
    path("new/", QnACreateView.as_view(), name="qna-create"),
    # 문의 상세내용에서 수정 누르면 해당 url로 매핑
    path("<int:pk>/edit/", QnAUpdateView.as_view(), name="qna-update"),
    # 문의 상세내용에서 삭제 누르면 해당 url로 매핑
    path("<int:pk>/delete/", QnADeleteView.as_view(), name="qna-delete"),
    # 댓글 새로 작성 후 등록할 경우, 해당 url로 매핑
    path("<int:pk>/comment/new/", CommentCreateView.as_view(), name="comment-create"),
    # 댓글 수정할 경우, 해당 url로 매핑
    path("<int:pk>/comment/update/", comment_update, name="comment-update"),
    # 댓글 삭제할 경우, 해당 url로 매핑
    path("<int:pk>/comment/delete/", comment_delete, name="comment-delete"),
]
