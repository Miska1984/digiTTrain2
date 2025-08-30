# core/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

def hello_world(request):
    return render(request, 'core/index.html')

@login_required
def main_page(request):
    return render(request, 'core/main_page.html')