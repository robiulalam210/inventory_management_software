from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import IntegrityError
from rest_framework import status, viewsets, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from core.utils import custom_response
from .models import Expense, ExpenseHead, ExpenseSubHead
from .serializers import ExpenseSerializer, ExpenseHeadSerializer, ExpenseSubHeadSerializer, ExpenseCreateSerializer, ExpenseUpdateSerializer   
from core.pagination import CustomPageNumberPagination
from django.db.models import Q 

 # Add this import

import logging

logger = logging.getLogger(__name__)
class BaseCompanyViewSet(viewsets.ModelViewSet):
    """Filters queryset by logged-in user's company"""
    company_field = 'company'

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
            company = getattr(request.user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company.", None, status.HTTP_400_BAD_REQUEST)

            heads = ExpenseHead.objects.filter(company=company)
            serializer = ExpenseHeadSerializer(heads, many=True)
            return custom_response(True, "Expense heads fetched successfully.", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return custom_response(False, f"Server Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            company = getattr(request.user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company.", None, status.HTTP_400_BAD_REQUEST)

            data = request.data.copy()
            data['company'] = company.id
            serializer = ExpenseHeadSerializer(data=data)

            if serializer.is_valid():
                serializer.save(created_by=request.user)  # ✅ Set created_by
                return custom_response(True, "Expense head created successfully.", serializer.data, status.HTTP_201_CREATED)
            return custom_response(False, "Validation error.", serializer.errors, status.HTTP_400_BAD_REQUEST)

        except IntegrityError as e:
            return custom_response(False, f"Database integrity error: {str(e)}", None, status.HTTP_400_BAD_REQUEST)
        except ValidationError as e:
            return custom_response(False, f"Validation error: {e.message}", None, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return custom_response(False, f"Unexpected error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExpenseHeadDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            head = ExpenseHead.objects.filter(id=pk, company=company).first()
            if not head:
                return custom_response(False, "Expense head not found.", None, status.HTTP_404_NOT_FOUND)
            
            serializer = ExpenseHeadSerializer(head)
            return custom_response(True, "Expense head fetched successfully.", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return custom_response(False, f"Server Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            head = ExpenseHead.objects.filter(id=pk, company=company).first()
            if not head:
                return custom_response(False, "Expense head not found.", None, status.HTTP_404_NOT_FOUND)
                
            serializer = ExpenseHeadSerializer(head, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return custom_response(True, "Expense head updated successfully.", serializer.data, status.HTTP_200_OK)
            return custom_response(False, "Validation error.", serializer.errors, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return custom_response(False, f"Update failed: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            head = ExpenseHead.objects.filter(id=pk, company=company).first()
            if not head:
                return custom_response(False, "Expense head not found.", None, status.HTTP_404_NOT_FOUND)
                
            # Check if head has any subheads before deleting
            if head.subheads.exists():
                return custom_response(False, "Cannot delete expense head that has subheads.", None, status.HTTP_400_BAD_REQUEST)
                
            head.delete()
            return custom_response(True, "Expense head deleted successfully.", None, status.HTTP_204_NO_CONTENT)
        except IntegrityError as e:
            return custom_response(False, f"Cannot delete: {str(e)}", None, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return custom_response(False, f"Delete failed: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------------------
# Expense SubHead
# ------------------------------
class ExpenseSubHeadListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            company = getattr(request.user, 'company', None)
            subheads = ExpenseSubHead.objects.filter(company=company).select_related('head')
            serializer = ExpenseSubHeadSerializer(subheads, many=True)
            return custom_response(True, "Expense SubHeads fetched successfully.", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return custom_response(False, f"Server Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        try:
            company = getattr(request.user, 'company', None)
            data = request.data.copy()
            data['company'] = company.id
            
            # Validate that head exists and belongs to company
            head_id = data.get('head')
            if head_id:
                head_exists = ExpenseHead.objects.filter(id=head_id, company=company).exists()
                if not head_exists:
                    return custom_response(False, "Expense Head not found or doesn't belong to your company.", None, status.HTTP_400_BAD_REQUEST)
            
            serializer = ExpenseSubHeadSerializer(data=data)
            if serializer.is_valid():
                serializer.save(created_by=request.user)  # ✅ Set created_by
                return custom_response(True, "Expense SubHead created successfully.", serializer.data, status.HTTP_201_CREATED)
            return custom_response(False, "Validation Error.", serializer.errors, status.HTTP_400_BAD_REQUEST)
        except IntegrityError as e:
            return custom_response(False, f"Database integrity error: {str(e)}", None, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return custom_response(False, f"Unexpected error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExpenseSubHeadDetailView(APIView):
    permission_classes = [IsAuthenticated]


    def get(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            subhead = ExpenseSubHead.objects.filter(id=pk, company=company).first()
            if not subhead:
                return custom_response(False, "Expense SubHead not found.", None, status.HTTP_404_NOT_FOUND)
            
            serializer = ExpenseSubHeadSerializer(subhead)
            return custom_response(True, "Expense SubHead fetched successfully.", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return custom_response(False, f"Server Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            subhead = ExpenseSubHead.objects.filter(id=pk, company=company).first()
            if not subhead:
                return custom_response(False, "Expense SubHead not found.", None, status.HTTP_404_NOT_FOUND)
            
            # Validate head if provided in update
            head_id = request.data.get('head')
            if head_id:
                head_exists = ExpenseHead.objects.filter(id=head_id, company=company).exists()
                if not head_exists:
                    return custom_response(False, "Expense Head not found or doesn't belong to your company.", None, status.HTTP_400_BAD_REQUEST)
            
            serializer = ExpenseSubHeadSerializer(subhead, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return custom_response(True, "Expense SubHead updated successfully.", serializer.data, status.HTTP_200_OK)
            return custom_response(False, "Validation Error.", serializer.errors, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return custom_response(False, f"Update failed: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            subhead = ExpenseSubHead.objects.filter(id=pk, company=company).first()
            if not subhead:
                return custom_response(False, "Expense SubHead not found.", None, status.HTTP_404_NOT_FOUND)
            
            # Check if subhead has any expenses before deleting
            if subhead.expense_set.exists():
                return custom_response(False, "Cannot delete expense subhead that has expenses.", None, status.HTTP_400_BAD_REQUEST)
                
            subhead.delete()
            return custom_response(True, "Expense SubHead deleted successfully.", None, status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return custom_response(False, f"Delete failed: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


# ------------------------------
# Expense
# ------------------------------


class ExpenseListView(APIView):
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get(self, request):
        try:
            company = getattr(request.user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company.", None, status.HTTP_400_BAD_REQUEST)

            # Get query parameters
            page = request.GET.get('page', 1)
            page_size = request.GET.get('page_size', 10)
            search = request.GET.get('search', '')
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            head_id = request.GET.get('head_id')
            subhead_id = request.GET.get('subhead_id')
            payment_method = request.GET.get('payment_method')
            sort_by = request.GET.get('sort_by', 'date_created')
            sort_order = request.GET.get('sort_order', 'desc')

            # Base queryset
            expenses = Expense.objects.filter(company=company).select_related('head', 'subhead', 'account')

            # Apply search filter
            if search:
                expenses = expenses.filter(
                    Q(note__icontains=search) |
                    Q(invoice_number__icontains=search) |
                    Q(head__name__icontains=search) |
                    Q(subhead__name__icontains=search) |
                    Q(payment_method__icontains=search)
                )
                
                # Handle numeric search for amount separately
                try:
                    amount_value = float(search)
                    expenses = expenses.filter(amount=amount_value)
                except (ValueError, TypeError):
                    pass

            # Date range filter
            if start_date and end_date:
                expenses = expenses.filter(expense_date__range=[start_date, end_date])
            elif start_date:
                expenses = expenses.filter(expense_date__gte=start_date)
            elif end_date:
                expenses = expenses.filter(expense_date__lte=end_date)

            # Head and subhead filters
            if head_id:
                expenses = expenses.filter(head_id=head_id)
            if subhead_id:
                expenses = expenses.filter(subhead_id=subhead_id)

            # Payment method filter
            if payment_method:
                expenses = expenses.filter(payment_method__iexact=payment_method)

            # Handle sorting
            valid_sort_fields = [
                'id', 'date_created', 'expense_date', 'amount', 'invoice_number',
                'head__name', 'subhead__name', 'payment_method'
            ]
            
            # Default sorting
            order_by_field = '-date_created'
            
            if sort_by:
                clean_sort_by = sort_by.lstrip('-')
                if clean_sort_by in valid_sort_fields:
                    if sort_order.lower() == 'desc':
                        order_by_field = f'-{clean_sort_by}'
                    else:
                        order_by_field = clean_sort_by
                else:
                    order_by_field = '-date_created'

            expenses = expenses.order_by(order_by_field)

            # Paginate results
            paginator = self.pagination_class()
            paginator.page_size = page_size
            
            try:
                page_number = int(page)
                if page_number < 1:
                    page_number = 1
            except (ValueError, TypeError):
                page_number = 1

            paginated_expenses = paginator.paginate_queryset(expenses, request, view=self)
            
            serializer = ExpenseSerializer(paginated_expenses, many=True)
            
            return paginator.get_paginated_response(serializer.data, "Expenses fetched successfully.")
            
        except Exception as e:
            logger.error(f"Error in ExpenseListView GET: {str(e)}", exc_info=True)
            return custom_response(False, f"Server Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def post(self, request):
        """Handle expense creation - FIXED: Use ExpenseCreateSerializer"""
        try:
            company = getattr(request.user, 'company', None)
            if not company:
                return custom_response(False, "User has no associated company.", None, status.HTTP_400_BAD_REQUEST)

            data = request.data.copy()
            data['company'] = company.id
            
            # Validate head and subhead
            head_id = data.get('head')
            if head_id:
                head_exists = ExpenseHead.objects.filter(id=head_id, company=company).exists()
                if not head_exists:
                    return custom_response(False, "Expense Head not found.", None, status.HTTP_400_BAD_REQUEST)
            
            subhead_id = data.get('subhead')
            if subhead_id:
                subhead_exists = ExpenseSubHead.objects.filter(id=subhead_id, company=company).exists()
                if not subhead_exists:
                    return custom_response(False, "Expense SubHead not found.", None, status.HTTP_400_BAD_REQUEST)
            
            # Validate account if provided
            account_id = data.get('account')
            if account_id:
                from accounts.models import Account
                account_exists = Account.objects.filter(id=account_id, company=company).exists()
                if not account_exists:
                    return custom_response(False, "Account not found.", None, status.HTTP_400_BAD_REQUEST)
            
            # Use ExpenseCreateSerializer for POST
            serializer = ExpenseCreateSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                expense = serializer.save()
                # Return the full expense data using ExpenseSerializer
                response_serializer = ExpenseSerializer(expense)
                return custom_response(True, "Expense created successfully.", response_serializer.data, status.HTTP_201_CREATED)
            
            return custom_response(False, "Validation Error.", serializer.errors, status.HTTP_400_BAD_REQUEST)
            
        except serializers.ValidationError as e:
            return custom_response(False, "Validation Error.", e.detail, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in ExpenseListView POST: {str(e)}", exc_info=True)
            return custom_response(False, f"Unexpected error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)


class ExpenseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            expense = Expense.objects.filter(pk=pk, company=company).first()
            if not expense:
                return custom_response(False, "Expense not found.", None, status.HTTP_404_NOT_FOUND)
            
            serializer = ExpenseSerializer(expense)
            return custom_response(True, "Expense fetched successfully.", serializer.data, status.HTTP_200_OK)
        except Exception as e:
            return custom_response(False, f"Server Error: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            expense = Expense.objects.filter(pk=pk, company=company).first()
            if not expense:
                return custom_response(False, "Expense not found.", None, status.HTTP_404_NOT_FOUND)

            # Validate head and subhead if provided
            head_id = request.data.get('head')
            if head_id:
                head_exists = ExpenseHead.objects.filter(id=head_id, company=company).exists()
                if not head_exists:
                    return custom_response(False, "Expense Head not found.", None, status.HTTP_400_BAD_REQUEST)
            
            subhead_id = request.data.get('subhead')
            if subhead_id:
                subhead_exists = ExpenseSubHead.objects.filter(id=subhead_id, company=company).exists()
                if not subhead_exists:
                    return custom_response(False, "Expense SubHead not found.", None, status.HTTP_400_BAD_REQUEST)

            # Use ExpenseUpdateSerializer for PATCH
            serializer = ExpenseUpdateSerializer(expense, data=request.data, partial=True, context={'request': request})
            if serializer.is_valid():
                updated_expense = serializer.save()
                # Return the full updated expense data
                response_serializer = ExpenseSerializer(updated_expense)
                return custom_response(True, "Expense updated successfully.", response_serializer.data, status.HTTP_200_OK)
            return custom_response(False, "Validation Error.", serializer.errors, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error in ExpenseDetailView PATCH: {str(e)}", exc_info=True)
            return custom_response(False, f"Update failed: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, request, pk):
        try:
            company = getattr(request.user, 'company', None)
            expense = Expense.objects.filter(pk=pk, company=company).first()
            if not expense:
                return custom_response(False, "Expense not found.", None, status.HTTP_404_NOT_FOUND)
            
            # Store expense info for logging before deletion
            expense_info = f"{expense.invoice_number} - {expense.amount}"
            expense.delete()
            
            logger.info(f"Expense deleted: {expense_info}")
            return custom_response(True, "Expense deleted successfully.", None, status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error in ExpenseDetailView DELETE: {str(e)}", exc_info=True)
            return custom_response(False, f"Delete failed: {str(e)}", None, status.HTTP_500_INTERNAL_SERVER_ERROR)