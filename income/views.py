from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from core.utils import custom_response
from .models import Income, IncomeHead
from .serializers import IncomeSerializer, IncomeHeadSerializer, IncomeCreateSerializer

class IncomeHeadListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return custom_response(False, "User has no associated company.", None, status.HTTP_400_BAD_REQUEST)
        heads = IncomeHead.objects.filter(company=company)
        serializer = IncomeHeadSerializer(heads, many=True)
        return custom_response(True, "Income heads fetched successfully.", serializer.data, status.HTTP_200_OK)

    def post(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return custom_response(False, "User has no associated company.", None, status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data['company'] = company.id
        serializer = IncomeHeadSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return custom_response(True, "Income head created successfully.", serializer.data, status.HTTP_201_CREATED)
        return custom_response(False, "Validation Error.", serializer.errors, status.HTTP_400_BAD_REQUEST)

class IncomeHeadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        company = getattr(request.user, 'company', None)
        head = IncomeHead.objects.filter(id=pk, company=company).first()
        if not head:
            return custom_response(False, "Income head not found.", None, status.HTTP_404_NOT_FOUND)
        serializer = IncomeHeadSerializer(head)
        return custom_response(True, "Income head fetched successfully.", serializer.data, status.HTTP_200_OK)

    def patch(self, request, pk):
        company = getattr(request.user, 'company', None)
        head = IncomeHead.objects.filter(id=pk, company=company).first()
        if not head:
            return custom_response(False, "Income head not found.", None, status.HTTP_404_NOT_FOUND)
        serializer = IncomeHeadSerializer(head, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return custom_response(True, "Income head updated successfully.", serializer.data, status.HTTP_200_OK)
        return custom_response(False, "Validation error.", serializer.errors, status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        company = getattr(request.user, 'company', None)
        head = IncomeHead.objects.filter(id=pk, company=company).first()
        if not head:
            return custom_response(False, "Income head not found.", None, status.HTTP_404_NOT_FOUND)
        head.delete()
        return custom_response(True, "Income head deleted successfully.", None, status.HTTP_204_NO_CONTENT)

class IncomeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return custom_response(False, "User has no associated company.", None, status.HTTP_400_BAD_REQUEST)
        # Pagination/filtering: add as needed
        incomes = Income.objects.filter(company=company)
        serializer = IncomeSerializer(incomes, many=True)
        return custom_response(True, "Income fetched successfully.", serializer.data, status.HTTP_200_OK)

    def post(self, request):
        company = getattr(request.user, 'company', None)
        if not company:
            return custom_response(False, "User has no associated company.", None, status.HTTP_400_BAD_REQUEST)
        data = request.data.copy()
        data['company'] = company.id
        serializer = IncomeCreateSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            income = serializer.save(created_by=request.user)
            return custom_response(True, "Income created successfully.", IncomeSerializer(income).data, status.HTTP_201_CREATED)
        return custom_response(False, "Validation Error.", serializer.errors, status.HTTP_400_BAD_REQUEST)