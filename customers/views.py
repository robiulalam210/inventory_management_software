import logging
from rest_framework import viewsets, status, filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum, F, Case, When, Value, DecimalField
from core.utils import custom_response
from core.pagination import CustomPageNumberPagination
from .models import Customer
from .serializers import CustomerSerializer
from decimal import Decimal

logger = logging.getLogger(__name__)

class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    search_fields = ['name', 'phone', 'email', 'address']
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'client_no', 'date_created']
    ordering = ['client_no']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by company
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            return Customer.objects.none()
        
        # Apply custom filters
        queryset = self.apply_custom_filters(queryset)
        
        # Optimize queryset with annotations for better performance
        queryset = queryset.annotate(
            sales_count=Count('sale', distinct=True),
            total_paid_amount=Sum('sale__paid_amount'),
            total_grand_total=Sum('sale__grand_total'),
            basic_due_amount=Case(
                When(
                    total_grand_total__isnull=True,
                    then=Value(0)
                ),
                default=F('total_grand_total') - F('total_paid_amount'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            net_due_amount=Case(
                When(
                    advance_balance__gte=F('basic_due_amount'),
                    then=Value(0)
                ),
                default=F('basic_due_amount') - F('advance_balance'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            remaining_advance=Case(
                When(
                    advance_balance__gt=F('basic_due_amount'),
                    then=F('advance_balance') - F('basic_due_amount')
                ),
                default=Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
        
        return queryset

    def apply_custom_filters(self, queryset):
        params = self.request.GET
        
        # Search filter
        search = params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(phone__icontains=search) |
                Q(email__icontains=search) |
                Q(address__icontains=search)
            )
        
        # Status filter
        status_filter = params.get('status')
        if status_filter:
            if status_filter.lower() == 'active':
                queryset = queryset.filter(is_active=True)
            elif status_filter.lower() == 'inactive':
                queryset = queryset.filter(is_active=False)
        
        # Amount type filter (advance/due/paid)
        amount_type = params.get('amount_type')
        if amount_type:
            if amount_type.lower() == 'advance':
                queryset = queryset.filter(advance_balance__gt=0)
            elif amount_type.lower() == 'due':
                # Customers with net due amount > 0
                queryset = queryset.annotate(
                    temp_net_due=Case(
                        When(
                            total_grand_total__isnull=True,
                            then=Value(0)
                        ),
                        default=Case(
                            When(
                                advance_balance__gte=F('total_grand_total') - F('total_paid_amount'),
                                then=Value(0)
                            ),
                            default=F('total_grand_total') - F('total_paid_amount') - F('advance_balance'),
                            output_field=DecimalField(max_digits=12, decimal_places=2)
                        ),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                ).filter(temp_net_due__gt=0)
            elif amount_type.lower() == 'paid':
                # Customers with no due and no advance
                queryset = queryset.annotate(
                    temp_net_due=Case(
                        When(
                            total_grand_total__isnull=True,
                            then=Value(0)
                        ),
                        default=Case(
                            When(
                                advance_balance__gte=F('total_grand_total') - F('total_paid_amount'),
                                then=Value(0)
                            ),
                            default=F('total_grand_total') - F('total_paid_amount') - F('advance_balance'),
                            output_field=DecimalField(max_digits=12, decimal_places=2)
                        ),
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    )
                ).filter(temp_net_due=0, advance_balance=0)
        
        # Date range filter
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(date_created__date__range=[start_date, end_date])
        
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Apply pagination
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            
            # If no pagination, return all results
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} customers",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error in CustomerViewSet list: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error fetching customers: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def payment_details(self, request, pk=None):
        """Get detailed payment information for a customer including advance, due, paid"""
        try:
            customer = self.get_object()
            breakdown = customer.get_detailed_payment_breakdown()
            
            return custom_response(
                success=True,
                message="Payment details fetched successfully",
                data=breakdown,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching payment details for customer {pk}: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error fetching payment details: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary of all customers' payment status"""
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # Calculate totals using annotations
            total_customers = queryset.count()
            
            # Calculate summary from annotations
            summary_data = queryset.aggregate(
                total_advance=Sum('advance_balance'),
                total_net_due=Sum('net_due_amount'),
                total_paid=Sum('total_paid_amount'),
                total_grand=Sum('total_grand_total')
            )
            
            # Count by status
            advance_count = queryset.filter(advance_balance__gt=0).count()
            due_count = queryset.filter(net_due_amount__gt=0).count()
            paid_count = queryset.filter(net_due_amount=0, advance_balance=0).count()
            
            summary = {
                'total_customers': total_customers,
                'financial_summary': {
                    'total_advance': float(summary_data['total_advance'] or 0),
                    'total_due': float(summary_data['total_net_due'] or 0),
                    'total_paid': float(summary_data['total_paid'] or 0),
                    'total_sales': float(summary_data['total_grand'] or 0)
                },
                'status_counts': {
                    'advance_customers': advance_count,
                    'due_customers': due_count,
                    'paid_customers': paid_count
                }
            }
            
            return custom_response(
                success=True,
                message="Customer summary fetched successfully",
                data=summary,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error fetching customer summary: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error fetching customer summary: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def add_advance(self, request, pk=None):
        """Add advance payment to customer"""
        try:
            customer = self.get_object()
            amount = request.data.get('amount')
            
            if not amount or float(amount) <= 0:
                return custom_response(
                    success=False,
                    message="Amount must be greater than 0",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            new_balance = customer.add_advance_direct(float(amount), created_by=request.user)
            
            return custom_response(
                success=True,
                message=f"Advance of {amount} added successfully",
                data={
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'new_advance_balance': float(new_balance),
                    'added_amount': float(amount)
                },
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error adding advance to customer {pk}: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error adding advance: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def use_advance(self, request, pk=None):
        """Use advance balance for payment"""
        try:
            customer = self.get_object()
            amount = request.data.get('amount')
            
            if not amount or float(amount) <= 0:
                return custom_response(
                    success=False,
                    message="Amount must be greater than 0",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            new_balance = customer.use_advance_payment(float(amount))
            
            return custom_response(
                success=True,
                message=f"Advance of {amount} used successfully",
                data={
                    'customer_id': customer.id,
                    'customer_name': customer.name,
                    'new_advance_balance': float(new_balance),
                    'used_amount': float(amount)
                },
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error using advance for customer {pk}: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error using advance: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def sync_advance(self, request, pk=None):
        """Sync customer's advance balance with actual receipts and sales"""
        try:
            customer = self.get_object()
            sync_result = customer.sync_advance_balance()
            
            if sync_result['synced']:
                message = f"Advance balance synced from {sync_result['old_value']} to {sync_result['new_value']}"
            else:
                message = f"Advance balance is already correct: {sync_result['current_value']}"
            
            return custom_response(
                success=True,
                message=message,
                data=sync_result,
                status_code=status.HTTP_200_OK
            )
        except Exception as e:
            logger.error(f"Error syncing advance for customer {pk}: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error syncing advance: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def check_receipts(self, request, pk=None):
        """Debug endpoint to check all money receipts for a customer"""
        try:
            customer = self.get_object()
            
            try:
                from money_receipts.models import MoneyReceipt
                
                # Get all money receipts for this customer
                all_receipts = MoneyReceipt.objects.filter(
                    customer=customer,
                    company=customer.company
                )
                
                receipts_data = []
                for receipt in all_receipts:
                    receipt_info = {
                        'id': receipt.id,
                        'receipt_no': receipt.receipt_no,
                        'amount': float(receipt.amount) if receipt.amount else 0,
                        'payment_date': receipt.payment_date,
                        'customer_id': receipt.customer_id,
                        'company_id': receipt.company_id,
                        'payment_type': receipt.payment_type if hasattr(receipt, 'payment_type') else None,
                        'specific_invoice': receipt.specific_invoice if hasattr(receipt, 'specific_invoice') else None,
                        'sale_id': receipt.sale_id if hasattr(receipt, 'sale') and receipt.sale else None,
                        'sale_invoice_no': receipt.sale_invoice_no if hasattr(receipt, 'sale_invoice_no') else None,
                    }
                    
                    # Check for advance-related fields
                    if hasattr(receipt, 'is_advance_payment'):
                        receipt_info['is_advance_payment'] = receipt.is_advance_payment
                    if hasattr(receipt, 'advance_amount'):
                        receipt_info['advance_amount'] = float(receipt.advance_amount) if receipt.advance_amount else 0
                    
                    # Determine if it should be treated as advance using the new logic
                    is_advance, advance_type = customer.is_advance_receipt(receipt)
                    receipt_info['should_be_advance'] = is_advance
                    receipt_info['advance_type'] = advance_type
                    
                    receipts_data.append(receipt_info)
                
                # Check customer's sales
                from sales.models import Sale
                sales = Sale.objects.filter(customer=customer, company=customer.company)
                sales_data = []
                for sale in sales:
                    sales_data.append({
                        'id': sale.id,
                        'invoice_no': sale.invoice_no,
                        'grand_total': float(sale.grand_total),
                        'paid_amount': float(sale.paid_amount),
                        'due_amount': float(sale.due_amount),
                        'overpayment': float(max(Decimal('0'), sale.paid_amount - sale.grand_total))
                    })
                
                # Calculate what advance should be
                sales_overpayment = max(0.0, sum(s['paid_amount'] for s in sales_data) - sum(s['grand_total'] for s in sales_data))
                advance_receipts_total = sum(r['amount'] for r in receipts_data if r['should_be_advance'])
                total_advance_should_be = sales_overpayment + advance_receipts_total
                
                return custom_response(
                    success=True,
                    message="Money receipts and sales checked",
                    data={
                        'customer_id': customer.id,
                        'customer_name': customer.name,
                        'stored_advance_balance': float(customer.advance_balance),
                        'total_money_receipts': len(receipts_data),
                        'money_receipts': receipts_data,
                        'advance_receipts': [r for r in receipts_data if r['should_be_advance']],
                        'non_advance_receipts': [r for r in receipts_data if not r['should_be_advance']],
                        'total_sales': len(sales_data),
                        'sales': sales_data,
                        'calculated_advance': {
                            'sales_overpayment': sales_overpayment,
                            'advance_receipts_total': advance_receipts_total,
                            'total_advance_should_be': total_advance_should_be
                        },
                        'advance_logic': {
                            'rules': [
                                'Rule 1: is_advance_payment = True',
                                'Rule 2: advance_amount > 0',
                                'Rule 3: payment_type = "advance"',
                                'Rule 4: payment_type = "overall" and no sale linked',
                                'Rule 5: No sale linked (generic payment)'
                            ]
                        }
                    },
                    status_code=status.HTTP_200_OK
                )
                
            except ImportError as e:
                return custom_response(
                    success=False,
                    message=f"Cannot import MoneyReceipt model: {str(e)}",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Error checking receipts for customer {pk}: {str(e)}")
            return custom_response(
                success=False,
                message=f"Error checking receipts: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        from rest_framework import serializers
        
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            user = self.request.user
            company = getattr(user, 'company', None)

            if not company:
                return custom_response(
                    success=False,
                    message="User must belong to a company.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            # Check for duplicate phone number
            phone = serializer.validated_data.get('phone')
            if phone and Customer.objects.filter(company=company, phone=phone).exists():
                return custom_response(
                    success=False,
                    message="A customer with this phone number already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )

            instance = serializer.save(company=company, created_by=user)
            return custom_response(
                success=True,
                message="Customer created successfully.",
                data=self.get_serializer(instance).data,
                status_code=status.HTTP_201_CREATED
            )
        except serializers.ValidationError as e:
            # Safely get the first error message
            if isinstance(e.detail, list) and e.detail:
                message = str(e.detail[0])
            elif isinstance(e.detail, dict) and e.detail:
                # Get first field error
                first_field = next(iter(e.detail.values()))
                if isinstance(first_field, list) and first_field:
                    message = str(first_field[0])
                else:
                    message = str(first_field)
            else:
                message = str(e.detail)
            
            return custom_response(
                success=False,
                message=message,
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

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            
            # Check for duplicate phone number (excluding current instance)
            phone = serializer.validated_data.get('phone')
            if phone and Customer.objects.filter(company=instance.company, phone=phone).exclude(id=instance.id).exists():
                return custom_response(
                    success=False,
                    message="A customer with this phone number already exists.",
                    data=None,
                    status_code=status.HTTP_400_BAD_REQUEST
                )
            
            self.perform_update(serializer)
            return custom_response(
                success=True,
                message="Customer updated successfully.",
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

    def destroy(self, request, *args, **kwargs):
        """
        Delete a customer - Only allow if no related records exist
        """
        try:
            instance = self.get_object()
            customer_name = instance.name
            
            # Check all possible relationships that might prevent deletion
            blocking_relationships = []
            
            def check_relationship(relationship_name, check_function):
                """Helper function to check relationships safely"""
                try:
                    count = check_function()
                    if count > 0:
                        blocking_relationships.append(f"{count} {relationship_name}")
                    return count
                except Exception as e:
                    logger.debug(f"Could not check {relationship_name}: {e}")
                    return 0
            
            # 1. Check sales
            sales_count = check_relationship("sales", lambda: 
                getattr(instance, 'sales').count() if hasattr(instance, 'sales') else
                getattr(instance, 'sale_set').count() if hasattr(instance, 'sale_set') else 0
            )
            
            # 2. Check money receipts
            money_receipts_count = check_relationship("money receipts", lambda: 
                getattr(instance, 'money_receipts').count() if hasattr(instance, 'money_receipts') else
                getattr(instance, 'moneyreceipt_set').count() if hasattr(instance, 'moneyreceipt_set') else 0
            )
            
            # 3. Direct database queries for common models
            # Sales
            if sales_count == 0:
                try:
                    from sales.models import Sale
                    sales_count = check_relationship("sales", 
                        lambda: Sale.objects.filter(customer=instance).count()
                    )
                except ImportError:
                    pass
            
            # Money Receipts
            if money_receipts_count == 0:
                try:
                    from money_receipts.models import MoneyReceipt
                    money_receipts_count = check_relationship("money receipts", 
                        lambda: MoneyReceipt.objects.filter(customer=instance).count()
                    )
                except ImportError:
                    pass
            
            # 4. Check other possible customer relationships
            # Due Collections
            try:
                from due_collections.models import DueCollection
                check_relationship("due collections",
                    lambda: DueCollection.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # Invoices
            try:
                from invoices.models import Invoice
                check_relationship("invoices",
                    lambda: Invoice.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # Customer Payments
            try:
                from customer_payments.models import CustomerPayment
                check_relationship("customer payments",
                    lambda: CustomerPayment.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # Customer Statements
            try:
                from accounting.models import CustomerStatement
                check_relationship("customer statements",
                    lambda: CustomerStatement.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # Customer Ledger
            try:
                from ledger.models import CustomerLedger
                check_relationship("ledger entries",
                    lambda: CustomerLedger.objects.filter(customer=instance).count()
                )
            except ImportError:
                pass
            
            # 5. Generic check using Django's related objects
            try:
                for related_object in instance._meta.related_objects:
                    related_name = related_object.get_accessor_name()
                    try:
                        related_manager = getattr(instance, related_name)
                        if hasattr(related_manager, 'count'):
                            count = related_manager.count()
                            if count > 0:
                                # Only include if not already counted and it's a meaningful relationship
                                rel_name = related_name.replace('_set', '').replace('_', ' ')
                                if (not any(rel_name in rel for rel in blocking_relationships) and 
                                    any(keyword in related_name for keyword in ['sale', 'receipt', 'payment', 'invoice', 'due', 'ledger'])):
                                    blocking_relationships.append(f"{count} {rel_name}")
                    except Exception as e:
                        logger.debug(f"Could not check related object {related_name}: {e}")
            except Exception as e:
                logger.debug(f"Error checking generic related objects: {e}")
            
            # If any blocking relationships exist, mark as inactive instead of deleting
            if blocking_relationships:
                instance.is_active = False
                instance.save(update_fields=['is_active'])
                
                # Create detailed message
                relationships_text = ", ".join(blocking_relationships)
                message = f"Customer cannot be deleted as it has transaction history ({relationships_text}). It has been marked as inactive instead."
                
                logger.warning(f"Customer deletion blocked for '{customer_name}'. Reasons: {blocking_relationships}")
                
                return custom_response(
                    success=True,
                    message=message,
                    data={
                        'is_active': instance.is_active,
                        'deletion_blocked': True,
                        'blocking_relationships': blocking_relationships,
                        'customer_id': instance.id,
                        'customer_name': customer_name
                    },
                    status_code=status.HTTP_200_OK
                )
            
            # If no blocking relationships, proceed with actual deletion
            self.perform_destroy(instance)
            
            logger.info(f"Customer deleted successfully: {customer_name} (ID: {instance.id})")
            
            return custom_response(
                success=True,
                message=f"Customer '{customer_name}' deleted successfully.",
                data={
                    'deletion_successful': True,
                    'customer_name': customer_name
                },
                status_code=status.HTTP_200_OK
            )
                
        except Exception as e:
            logger.error(f"Error deleting customer: {str(e)}", exc_info=True)
            return custom_response(
                success=False,
                message="Internal server error",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CustomerNonPaginationViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    pagination_class = None
    
    search_fields = ['name', 'phone', 'email', 'address']
    ordering_fields = ['name', 'date_created']
    ordering = ['name']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by company only (no active/inactive filter)
        user = self.request.user
        if hasattr(user, 'company') and user.company:
            queryset = queryset.filter(company=user.company)
        else:
            return Customer.objects.none()
        
        # Optimize queryset with annotations
        queryset = queryset.annotate(
            sales_count=Count('sale', distinct=True),
            total_paid_amount=Sum('sale__paid_amount'),
            total_grand_total=Sum('sale__grand_total')
        )
        
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            
            # No pagination - return all results
            serializer = self.get_serializer(queryset, many=True)
            return custom_response(
                success=True,
                message=f"Found {queryset.count()} customers",
                data=serializer.data,
                status_code=status.HTTP_200_OK
            )
            
        except Exception as e:
            return custom_response(
                success=False,
                message=f"Error fetching customers: {str(e)}",
                data=None,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )