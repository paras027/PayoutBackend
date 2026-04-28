from django.contrib import admin
from django.urls import include, path
from .views import LedgerView

urlpatterns = [
    path('', LedgerView.as_view()),
    path('details/', LedgerView.as_view()),
]
