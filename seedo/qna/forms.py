from django import forms

from .models import QnA


# 문의 상세 내용 폼
class QnAForm(forms.ModelForm):
    file_upload = forms.FileField(label="파일 업로드", required=False)

    class Meta:
        model = QnA
        fields = ["title", "content", "file_upload"]
        labels = {"title": "제목", "content": "내용"}


# 댓글 폼
class CommentForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea, label="Comment")

    class Meta:
        model = QnA
        fields = ["content"]
