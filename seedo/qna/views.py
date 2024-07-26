from common.decorators import token_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.views.generic.edit import FormView

from .forms import CommentForm, QnAForm
from .models import QnA


# 문의내용들을 최신순으로 나열해서 전달하는 view
@method_decorator(token_required, name="dispatch")
class QnAListView(LoginRequiredMixin, ListView):
    model = QnA
    template_name = "qna/qna_list.html"
    context_object_name = "questions"

    def get_queryset(self):
        if self.request.user.is_superuser:
            queryset = QnA.objects.all().order_by("-created_at")
        else:
            queryset = QnA.objects.filter(Q(author=self.request.user) | Q(author__is_superuser=True)).order_by("-created_at")

        filter_type = self.request.GET.get("filter")
        if filter_type == "answered":
            queryset = queryset.exclude(Q(comments__exact="") | Q(comments__isnull=True))
        elif filter_type == "unanswered":
            queryset = queryset.filter(Q(comments__exact="") | Q(comments__isnull=True))

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_type"] = self.request.GET.get("filter", "")
        context["superuser"] = self.request.user.is_superuser
        return context


# 문의에 대한 정보를 전부 갖고와서, post 방식으로 전달하는 view
@method_decorator(token_required, name="dispatch")
class QnADetailView(View):

    def get(self, request, pk):
        question = get_object_or_404(QnA, pk=pk)
        comment_form = CommentForm()
        comments_list = question.comments if question.comments else []
        context = {"question": question, "comment_form": comment_form, "comments_list": comments_list}
        return render(request, "qna/qna_detail.html", context)

    def post(self, request, pk):
        question = get_object_or_404(QnA, pk=pk)
        form = CommentForm(request.POST)

        if form.is_valid():
            comment = form.cleaned_data["content"]

            question.comments = comment
            question.save()

        return redirect("qna:qna-detail", pk=pk)


# 댓글 폼에 작성되면 내용 전달해주는 함수
@token_required
def comment_update(request, pk):
    question = get_object_or_404(QnA, pk=pk)

    if request.method == "POST":
        comment_content = request.POST["content"]
        question.comments = comment_content
        question.save()

    return redirect("qna:qna-detail", pk=pk)


# 댓글 삭제 요청을 처리하는 함수
@token_required
def comment_delete(request, pk):
    question = get_object_or_404(QnA, pk=pk)

    if request.method == "POST":
        question.comments = ""
        question.save()
        return redirect("qna:qna-detail", pk=pk)

    return redirect("qna:qna-detail", pk=pk)


# 문의 내용 작성 폼을 처리하는 view
@method_decorator(token_required, name="dispatch")
class QnACreateView(LoginRequiredMixin, CreateView):
    model = QnA
    form_class = QnAForm
    template_name = "qna/qna_form.html"
    success_url = "/qna/"

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["view"] = "form"
        return context


# 문의 내용 수정 요청을 처리하는 view
@method_decorator(token_required, name="dispatch")
class QnAUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = QnA
    form_class = QnAForm
    template_name = "qna/qna_form.html"
    success_url = "/qna/"

    def test_func(self):
        question = self.get_object()
        return self.request.user.is_superuser or self.request.user == question.author

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["view"] = "form"
        return context


# 문의 내용에 대해 삭제요청을 처리하는 view
@method_decorator(token_required, name="dispatch")
class QnADeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = QnA
    success_url = reverse_lazy("qna:qna-list")

    def test_func(self):
        question = self.get_object()
        return self.request.user.is_superuser or self.request.user == question.author


# 댓글작성을 처리하는 view
@method_decorator(token_required, name="dispatch")
class CommentCreateView(FormView):
    template_name = "qna/qna_detail.html"
    form_class = CommentForm

    def form_valid(self, form):
        question = get_object_or_404(QnA, pk=self.kwargs["pk"])

        question.comments = form.cleaned_data["content"]
        question.save()

        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("qna:qna-detail", kwargs={"pk": self.kwargs["pk"]})
