from django.urls import path
from .views import preview_template

urlpatterns = [
    path('preview/', preview_template, name='marketing-preview'),
]
