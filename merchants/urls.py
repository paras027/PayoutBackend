from django.contrib import admin
from django.urls import include, path
from .views import MerchantView

urlpatterns = [
    path('', MerchantView.as_view()),
    path('user/', MerchantView.as_view()),
]
