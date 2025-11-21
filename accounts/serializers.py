# accounts/serializers.py
from rest_framework import serializers
from .models import Account
from decimal import Decimal

class AccountSerializer(serializers.ModelSerializer):
    ac_name = serializers.CharField(source='name')
    ac_number = serializers.CharField(source='number', required=False, allow_blank=True, allow_null=True)
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = Account
        fields = ['id', 'ac_name', 'ac_type', 'ac_number', 'balance', 'bank_name', 'branch', 'opening_balance', 'company', 'status', 'ac_no']
        extra_kwargs = {
            'opening_balance': {'read_only': True},
            'balance': {'read_only': True},
        }
    
    def get_status(self, obj):
        return "Active" if obj.is_active else "Inactive"
    
    def validate_opening_balance(self, value):
        """Ensure opening_balance is a valid decimal"""
        if isinstance(value, str):
            try:
                if value.strip() == '' or value == '00':
                    return Decimal('0.00')
                return Decimal(value)
            except (ValueError, TypeError):
                raise serializers.ValidationError("Enter a valid decimal number.")
        return value
    
    # NO validation that prevents Cash/Other accounts from having numbers

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        company = user.company if user and hasattr(user, 'company') else None

        if not company:
            raise serializers.ValidationError("User must be associated with a company.")

        # Extract the data
        ac_type = validated_data.get('ac_type')
        number = validated_data.get('number')
        name = validated_data.get('name')
        opening_balance = validated_data.get('opening_balance', Decimal('0.00'))

        # Handle empty string as None
        if number == '':
            number = None

        # Check for duplicates
        if number:
            if Account.objects.filter(company=company, ac_type=ac_type, number=number).exists():
                raise serializers.ValidationError("An account with this type and number already exists.")
        else:
            if Account.objects.filter(company=company, ac_type=ac_type, number__isnull=True).exists():
                raise serializers.ValidationError(f"A {ac_type} account without a number already exists. Please provide a unique account number.")

        # Create the account
        account = Account(
            company=company,
            name=name,
            ac_type=ac_type,
            number=number,
            bank_name=validated_data.get('bank_name'),
            branch=validated_data.get('branch'),
            opening_balance=opening_balance,
            balance=opening_balance,
            is_active=True
        )

        # Save with the creating user
        account.save(creating_user=user)
        return account