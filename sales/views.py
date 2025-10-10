from rest_framework import viewsets
from .models import Customer, Sale, SaleItem
from .serializers import CustomerSerializer, SaleSerializer, SaleItemSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum
from datetime import datetime

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().order_by('-date')
    serializer_class = SaleSerializer

    @action(detail=False, methods=['get'])
    def filter_by_customer(self, request):
        customer_id = request.query_params.get('customer_id')
        if not customer_id:
            return Response({'error': 'customer_id required'}, status=400)
        sales = self.queryset.filter(customer_id=customer_id)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def filter_by_date(self, request):
        date = request.query_params.get('date')
        if not date:
            return Response({'error': 'date required'}, status=400)
        sales = self.queryset.filter(date=date)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)


class SaleItemViewSet(viewsets.ModelViewSet):
    queryset = SaleItem.objects.all()
    serializer_class = SaleItemSerializer
