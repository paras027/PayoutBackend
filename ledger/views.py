from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Ledger
from .serializers import LedgerSerializer

class LedgerView(APIView):
    def get(self, request):
        qs = Ledger.objects.all().order_by('-created_at')
        merchant_id = request.query_params.get('merchant')
        if merchant_id:
            qs = qs.filter(merchant_id=merchant_id)
        serializer = LedgerSerializer(qs, many=True)
        return Response(serializer.data, status=200)

    def post(self,request):
        serializer = LedgerSerializer(data = request.data)
        if(serializer.is_valid()):
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=400)
    
