from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('api/v1/merchants/', include('merchants.urls')),
    path('api/v1/ledger/', include('ledger.urls')),
    path('api/v1/payouts/', include('payouts.urls')),
]