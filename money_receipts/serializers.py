from rest_framework import serializers
from decimal import Decimal, InvalidOperation
from .models import MoneyReceipt
from sales.models import Sale
from customers.models import Customer
from accounts.models import Account
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class MoneyReceiptSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, allow_null=True)
    seller_name = serializers.CharField(source='seller.username', read_only=True, allow_null=True)
    sale_invoice_no = serializers.SerializerMethodField(read_only=True)
    account_name = serializers.CharField(source='account.name', read_only=True, allow_null=True)
    payment_summary = serializers.SerializerMethodField()
    company_name = serializers.CharField(source='company.name', read_only=True)
    
    # FIXED: Use DecimalField instead of CharField for amount
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=True,
        coerce_to_string=True  # This will handle string input properly
    )
    
    # Writeable fields
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.all(), 
        source='customer',
        write_only=True,
        required=False,
        allow_null=True
    )
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(),
        source='account', 
        write_only=True,
        required=False,
        allow_null=True
    )
    sale_id = serializers.PrimaryKeyRelatedField(
        queryset=Sale.objects.all(),
        source='sale',
        write_only=True,
        required=False,
        allow_null=True
    )
    seller_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='seller',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = MoneyReceipt
        fields = [
            'id', 'mr_no', 'company', 'company_name',
            'customer', 'customer_id', 'customer_name', 'customer_phone',
            'payment_type', 'specific_invoice', 'is_advance_payment', 
            'sale', 'sale_id', 'sale_invoice_no',
            'amount', 'payment_method', 'payment_date', 'remark', 
            'account', 'account_id', 'account_name', 
            'seller', 'seller_id', 'seller_name',
            'cheque_status', 'cheque_id', 'payment_status', 
            'created_at', 'updated_at', 'payment_summary'
        ]
        read_only_fields = [
            'id', 'mr_no', 'customer_name', 'customer_phone', 'sale_invoice_no', 
            'seller_name', 'account_name', 'company', 'company_name', 
            'created_at', 'updated_at', 'payment_summary',
            'payment_type', 'specific_invoice'
        ]

    def __init__(self, *args, **kwargs):
        """Initialize with company-filtered querysets - FIXED"""
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        
        if request and hasattr(request, 'user'):
            user = request.user
            if hasattr(user, 'company') and user.company:
                company = user.company
                
                # Filter querysets by company - SAFELY
                try:
                    self.fields['customer_id'].queryset = Customer.objects.filter(company=company)
                except Exception as e:
                    logger.warning(f"Error filtering customers: {e}")
                
                try:
                    self.fields['account_id'].queryset = Account.objects.filter(company=company, is_active=True)
                except Exception as e:
                    logger.warning(f"Error filtering accounts: {e}")
                
                try:
                    self.fields['sale_id'].queryset = Sale.objects.filter(company=company)
                except Exception as e:
                    logger.warning(f"Error filtering sales: {e}")
                
                try:
                    self.fields['seller_id'].queryset = User.objects.filter(company=company)
                except Exception as e:
                    logger.warning(f"Error filtering sellers: {e}")

    def validate_amount(self, value):
        """Validate amount field specifically"""
        try:
            # Convert to Decimal if it's a string
            if isinstance(value, str):
                # Remove commas if present
                value = value.replace(',', '')
                decimal_value = Decimal(value)
            elif isinstance(value, (int, float)):
                decimal_value = Decimal(str(value))
            else:
                decimal_value = value
            
            # Validate it's greater than 0
            if decimal_value <= Decimal('0'):
                raise serializers.ValidationError("Payment amount must be greater than 0.")
            
            return decimal_value
        except (InvalidOperation, ValueError, TypeError) as e:
            raise serializers.ValidationError(f"Invalid amount format: {str(e)}")

    def validate(self, attrs):
        """Enhanced validation with company checks - FIXED"""
        request = self.context.get('request')
        company = getattr(request.user, 'company', None) if request else None
        
        # Amount is already validated in validate_amount and is now a Decimal
        # No need to validate amount here again
        
        customer = attrs.get('customer')
        sale = attrs.get('sale')
        account = attrs.get('account')
        is_advance_payment = attrs.get('is_advance_payment', False)
        payment_type = attrs.get('payment_type', 'overall')

        # Validate company consistency
        if company:
            if customer and hasattr(customer, 'company') and customer.company != company:
                raise serializers.ValidationError({
                    "customer": "Customer must belong to your company."
                })
            
            if sale and hasattr(sale, 'company') and sale.company != company:
                raise serializers.ValidationError({
                    "sale": "Sale must belong to your company."
                })
            
            if account and hasattr(account, 'company') and account.company != company:
                raise serializers.ValidationError({
                    "account": "Account must belong to your company."
                })

        # Validate customer requirements
        if is_advance_payment and not customer:
            raise serializers.ValidationError({
                "customer": "Customer is required for advance payments."
            })

        if payment_type == 'specific' and not sale:
            raise serializers.ValidationError({
                "sale": "Sale is required for specific invoice payments."
            })

        if payment_type == 'overall' and not customer:
            raise serializers.ValidationError({
                "customer": "Customer is required for overall payments."
            })

        return attrs

    def create(self, validated_data):
        """Create money receipt with proper context - FIXED"""
        request = self.context.get('request')
        
        if not request:
            raise serializers.ValidationError("Request context is required.")
        
        if not hasattr(request.user, 'company') or not request.user.company:
            raise serializers.ValidationError("User must be associated with a company.")
        
        # Set company from request user
        validated_data['company'] = request.user.company
        
        # Set seller and created_by from request user if not provided
        if 'seller' not in validated_data or not validated_data['seller']:
            validated_data['seller'] = request.user
        if 'created_by' not in validated_data or not validated_data['created_by']:
            validated_data['created_by'] = request.user
        
        # Set default payment method if not provided
        if 'payment_method' not in validated_data or not validated_data['payment_method']:
            validated_data['payment_method'] = 'cash'
        
        # Ensure payment status
        if 'payment_status' not in validated_data:
            validated_data['payment_status'] = 'completed'
        
        try:
            # Create the money receipt
            receipt = MoneyReceipt.objects.create(**validated_data)
            return receipt
        except Exception as e:
            logger.error(f"Error creating money receipt: {e}")
            raise serializers.ValidationError(f"Error creating money receipt: {str(e)}")

    def get_sale_invoice_no(self, obj):
        """Get sale invoice number safely"""
        if obj.sale:
            return obj.sale.invoice_no
        elif obj.sale_invoice_no:
            return obj.sale_invoice_no
        return None

    def get_payment_summary(self, obj):
        """Get payment summary from model method - SAFELY"""
        try:
            return obj.get_payment_summary()
        except Exception as e:
            logger.error(f"Error getting payment summary for {obj.mr_no}: {e}")
            return {
                'mr_no': obj.mr_no,
                'amount': float(obj.amount),
                'payment_type': obj.payment_type,
                'error': 'Could not generate full summary'
            }