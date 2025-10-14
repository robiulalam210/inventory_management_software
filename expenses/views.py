from rest_framework import status, viewsets, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from core.utils import custom_response
from .models import Expense, ExpenseHead, ExpenseSubHead
from .serializers import ExpenseSerializer, ExpenseHeadSerializer, ExpenseSubHeadSerializer

class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Filters queryset by logged-in user's company"""
    company_field = 'company'  # override if needed

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            filter_kwargs = {self.company_field: user.company}
            return queryset.filter(**filter_kwargs)
        return queryset.none()

# ------------------------------
# Expense Head
# ------------------------------
class ExpenseHeadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            heads = ExpenseHead.objects.filter(company=company)
            serializer = ExpenseHeadSerializer(heads, many=True)
            return custom_response(
                success=True,
                message="Expense Heads fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            data = request.data.copy()
            data['company'] = company.id

            serializer = ExpenseHeadSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return custom_response(
                    success=True,
                    message="Expense Head created successfully.",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            return custom_response(
                success=False,
                message="Validation Error.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation Error.",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ------------------------------
# Expense SubHead
# ------------------------------
class ExpenseSubHeadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            subheads = ExpenseSubHead.objects.filter(company=company)
            serializer = ExpenseSubHeadSerializer(subheads, many=True)
            return custom_response(
                success=True,
                message="Expense SubHeads fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            data = request.data.copy()
            data['company'] = company.id
            serializer = ExpenseSubHeadSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return custom_response(
                    success=True,
                    message="Expense SubHead created successfully.",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            return custom_response(
                success=False,
                message="Validation Error.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation Error.",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# ------------------------------
# Expense
# ------------------------------
class ExpenseListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            start = request.GET.get('start')
            end = request.GET.get('end')
            expenses = Expense.objects.filter(company=company)
            if start and end:
                expenses = expenses.filter(expense_date__range=[start, end])

            serializer = ExpenseSerializer(expenses, many=True)
            return custom_response(
                success=True,
                message="Expenses fetched successfully.",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request):
        try:
            user = request.user
            company = getattr(user, 'company', None)
            if not company:
                return custom_response(
                    success=False,
                    message="User has no associated company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            data = request.data.copy()
            data['company'] = company.id  # attach company automatically

            serializer = ExpenseSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return custom_response(
                    success=True,
                    message="Expense created successfully.",
                    data=serializer.data,
                    status_code=status.HTTP_201_CREATED
                )
            return custom_response(
                success=False,
                message="Validation Error.",
                data=serializer.errors,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except serializers.ValidationError as e:
            return custom_response(
                success=False,
                message="Validation Error.",
                data=e.detail,
                status_code=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return custom_response(
                success=False,
                message=str(e),
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )