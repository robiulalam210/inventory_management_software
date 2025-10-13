from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Expense, ExpenseHead, ExpenseSubHead
from .serializers import ExpenseSerializer, ExpenseHeadSerializer, ExpenseSubHeadSerializer

# List and create Expense Heads
class ExpenseHeadListView(APIView):
    def get(self, request):
        company_id = request.GET.get('company')
        heads = ExpenseHead.objects.all()
        if company_id:
            heads = heads.filter(company_id=company_id)
        serializer = ExpenseHeadSerializer(heads, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ExpenseHeadSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# List and create Expense SubHeads
class ExpenseSubHeadListView(APIView):
    def get(self, request):
        company_id = request.GET.get('company')
        subheads = ExpenseSubHead.objects.all()
        if company_id:
            subheads = subheads.filter(company_id=company_id)
        serializer = ExpenseSubHeadSerializer(subheads, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ExpenseSubHeadSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# List and create Expenses
class ExpenseListView(APIView):
    def get(self, request):
        company_id = request.GET.get('company')
        start = request.GET.get('start')
        end = request.GET.get('end')

        expenses = Expense.objects.all()
        if company_id:
            expenses = expenses.filter(company_id=company_id)
        if start and end:
            expenses = expenses.filter(expense_date__range=[start, end])

        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ExpenseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
