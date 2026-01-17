from rest_framework import serializers
from rest_framework.relations import PrimaryKeyRelatedField
from .models import SalesReturn, PurchaseReturn, BadStock, SalesReturnItem, PurchaseReturnItem
from accounts.models import Account, Company
from products.models import Product


class CompanyProductRelatedField(PrimaryKeyRelatedField):
    """
    PrimaryKeyRelatedField that scopes Product lookups to the request user's company
    and provides a clearer error message when the product is not found / not accessible.
    """
    def get_queryset(self):
        request = getattr(self, 'context', {}).get('request', None)
        if request and hasattr(request.user, 'company') and request.user.company:
            return Product.objects.filter(company=request.user.company)
        return Product.objects.all()

    def to_internal_value(self, data):
        try:
            return super().to_internal_value(data)
        except serializers.ValidationError:
            raise serializers.ValidationError(f"Product with id {data} not found or not available for your company.")


class SalesReturnItemSerializer(serializers.ModelSerializer):
    # Use a company-scoped related field for safety
    product_id = CompanyProductRelatedField(source='product', write_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SalesReturnItem
        fields = ['id', 'product_id', 'product_name', 'quantity', 'damage_quantity',
                  'unit_price', 'discount', 'discount_type', 'total']
        read_only_fields = ['sales_return']

    def validate(self, data):
        """Validate item data"""
        if 'damage_quantity' in data and 'quantity' in data:
            if data['damage_quantity'] > data['quantity']:
                raise serializers.ValidationError(
                    {"damage_quantity": "Damage quantity cannot exceed total quantity"}
                )
        return data


class SalesReturnSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )
    items = SalesReturnItemSerializer(many=True)
    return_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    created_by = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = SalesReturn
        fields = ['id', 'receipt_no', 'customer_name', 'return_date',
                  'account_id', 'payment_method', 'reason', 'return_charge',
                  'return_charge_type', 'return_amount', 'status', 'company_id',
                  'items', 'created_at', 'created_by']
        read_only_fields = ['receipt_no', 'return_amount', 'status', 'created_at']

    def __init__(self, *args, **kwargs):
        """
        Ensure nested `items` serializer has the same context (so CompanyProductRelatedField
        can access request.user.company).
        """
        super().__init__(*args, **kwargs)
        if 'items' in self.fields:
            try:
                # ListSerializer -> .child is the actual item serializer
                child = self.fields['items'].child
                # update child's context with parent context
                child.context.update(self.context or {})
            except Exception:
                pass

    def validate(self, data):
        """Validate return data"""
        if not data.get('items'):
            raise serializers.ValidationError({"items": "At least one item is required"})
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        company = validated_data.get('company')

        # Generate receipt number if not provided
        if not validated_data.get('receipt_no'):
            last_return = SalesReturn.objects.filter(company=company).order_by('-id').first()
            if last_return and last_return.receipt_no:
                try:
                    parts = last_return.receipt_no.split('-')
                    last_number = int(parts[-1]) if parts[-1].isdigit() else 0
                    new_number = last_number + 1
                    validated_data['receipt_no'] = f"SR-{new_number:04d}"
                except Exception:
                    validated_data['receipt_no'] = f"SR-0001"
            else:
                validated_data['receipt_no'] = f"SR-0001"

        sales_return = SalesReturn.objects.create(**validated_data)

        total_amount = 0
        for item_data in items_data:
            # item_data['product'] is a Product instance thanks to CompanyProductRelatedField
            item = SalesReturnItem.objects.create(sales_return=sales_return, **item_data)
            total_amount += item.total

        # Calculate final return amount with return charge
        if sales_return.return_charge_type == 'percentage' and (sales_return.return_charge or 0) > 0:
            return_charge_amount = (total_amount * sales_return.return_charge) / 100
        else:
            return_charge_amount = sales_return.return_charge or 0

        sales_return.return_amount = total_amount + return_charge_amount
        sales_return.save()

        return sales_return

    def update(self, instance, validated_data):
        """Update sales return - only allow if pending"""
        if instance.status != 'pending':
            raise serializers.ValidationError(
                {"status": f"Cannot update {instance.status} return"}
            )

        items_data = validated_data.pop('items', [])

        # Update instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Replace items
        instance.items.all().delete()
        total_amount = 0

        for item_data in items_data:
            item = SalesReturnItem.objects.create(sales_return=instance, **item_data)
            total_amount += item.total

        # Recalculate return amount
        if instance.return_charge_type == 'percentage' and (instance.return_charge or 0) > 0:
            return_charge_amount = (total_amount * instance.return_charge) / 100
        else:
            return_charge_amount = instance.return_charge or 0

        instance.return_amount = total_amount + return_charge_amount
        instance.save()

        return instance


class PurchaseReturnItemSerializer(serializers.ModelSerializer):
    product_id = CompanyProductRelatedField(source='product', write_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseReturnItem
        fields = ['id', 'product_id', 'product_name', 'quantity', 'unit_price',
                  'discount', 'discount_type', 'total']
        read_only_fields = ['purchase_return']


class PurchaseReturnSerializer(serializers.ModelSerializer):
    account_id = serializers.PrimaryKeyRelatedField(
        queryset=Account.objects.all(), source='account', allow_null=True, required=False
    )
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )
    items = PurchaseReturnItemSerializer(many=True)
    return_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    created_by = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = PurchaseReturn
        fields = ['id', 'supplier', 'invoice_no', 'return_date',
                  'account_id', 'payment_method', 'return_charge', 'return_charge_type',
                  'return_amount', 'reason', 'status', 'company_id', 'items',
                  'created_at', 'created_by']
        read_only_fields = ['return_amount', 'status', 'created_at']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'items' in self.fields:
            try:
                child = self.fields['items'].child
                child.context.update(self.context or {})
            except Exception:
                pass

    def validate(self, data):
        """Validate purchase return data"""
        if not data.get('items'):
            raise serializers.ValidationError({"items": "At least one item is required"})
        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items', [])
        company = validated_data.get('company')

        # Generate invoice number if not provided
        if not validated_data.get('invoice_no'):
            last_return = PurchaseReturn.objects.filter(company=company).order_by('-id').first()
            if last_return and last_return.invoice_no:
                try:
                    parts = last_return.invoice_no.split('-')
                    last_number = int(parts[-1]) if parts[-1].isdigit() else 0
                    new_number = last_number + 1
                    validated_data['invoice_no'] = f"PR-{new_number:04d}"
                except Exception:
                    validated_data['invoice_no'] = f"PR-0001"
            else:
                validated_data['invoice_no'] = f"PR-0001"

        purchase_return = PurchaseReturn.objects.create(**validated_data)

        total_amount = 0
        for item_data in items_data:
            item = PurchaseReturnItem.objects.create(purchase_return=purchase_return, **item_data)
            total_amount += item.total

        # Calculate final return amount (minus return charge)
        if purchase_return.return_charge_type == 'percentage' and (purchase_return.return_charge or 0) > 0:
            return_charge_amount = (total_amount * purchase_return.return_charge) / 100
        else:
            return_charge_amount = purchase_return.return_charge or 0

        purchase_return.return_amount = total_amount - return_charge_amount
        purchase_return.save()

        return purchase_return

    def update(self, instance, validated_data):
        """Update purchase return - only allow if pending"""
        if instance.status != 'pending':
            raise serializers.ValidationError(
                {"status": f"Cannot update {instance.status} return"}
            )

        items_data = validated_data.pop('items', [])

        # Update instance fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Replace items
        instance.items.all().delete()
        total_amount = 0

        for item_data in items_data:
            item = PurchaseReturnItem.objects.create(purchase_return=instance, **item_data)
            total_amount += item.total

        # Recalculate return amount
        if instance.return_charge_type == 'percentage' and (instance.return_charge or 0) > 0:
            return_charge_amount = (total_amount * instance.return_charge) / 100
        else:
            return_charge_amount = instance.return_charge or 0

        instance.return_amount = total_amount - return_charge_amount
        instance.save()

        return instance


class BadStockSerializer(serializers.ModelSerializer):
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), source='company', allow_null=True, required=False
    )
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_code = serializers.CharField(source='product.code', read_only=True, allow_null=True)

    class Meta:
        model = BadStock
        fields = ['id', 'product', 'product_name', 'product_code', 'quantity',
                  'company_id', 'reason', 'date', 'reference_type', 'reference_id']
        read_only_fields = ['date']