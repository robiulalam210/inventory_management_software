from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Expense, ExpenseHead, ExpenseSubHead
from .serializers import ExpenseSerializer, ExpenseHeadSerializer, ExpenseSubHeadSerializer


# ------------------------------
# Expense Head
# ------------------------------
class ExpenseHeadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)

        heads = ExpenseHead.objects.filter(company=company)
        serializer = ExpenseHeadSerializer(heads, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        company = getattr(user, 'company', None)
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)

        data = request.data.copy()
        data['company'] = company.id

        serializer = ExpenseHeadSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# ------------------------------
# Expense SubHead
# ------------------------------
class ExpenseSubHeadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)

        subheads = ExpenseSubHead.objects.filter(company=company)
        serializer = ExpenseSubHeadSerializer(subheads, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        company = getattr(user, 'company', None)
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)

        data = request.data.copy()
        data['company'] = company.id

        serializer = ExpenseSubHeadSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ------------------------------
# Expense
# ------------------------------
class ExpenseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        company = getattr(user, 'company', None)
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)

        start = request.GET.get('start')
        end = request.GET.get('end')

        expenses = Expense.objects.filter(company=company)

        if start and end:
            expenses = expenses.filter(expense_date__range=[start, end])

        serializer = ExpenseSerializer(expenses, many=True)
        return Response(serializer.data)

    def post(self, request):
        user = request.user
        company = getattr(user, 'company', None)
        if not company:
            return Response({"detail": "User has no associated company"}, status=400)

        data = request.data.copy()
        data['company'] = company.id  # attach company automatically

        serializer = ExpenseSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
