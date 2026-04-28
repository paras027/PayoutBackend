from django.contrib import admin
from django.urls import include, path
from .views import PayoutView

urlpatterns = [
    path('', PayoutView.as_view()),
]
