from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Merchant
from .serializers import MerchantSerializer

# Create your views here.
class MerchantView(APIView):
    def get(self,request):

        merchant = Merchant.objects.all()
        serializer = MerchantSerializer(merchant, many=True)
        return Response(serializer.data)
    
    def post(self,request):
        serializer = MerchantSerializer(data = request.data)
        if(serializer.is_valid()):
            serializer.save()
            return Response(serializer.data)