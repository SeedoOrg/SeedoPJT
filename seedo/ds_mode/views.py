from django.shortcuts import render
from django.http import HttpResponse

# Create your views here.
def index(request):
    return render(request, "ds_mode/ds_test.html")

def test(request):
    return HttpResponse('hello')
