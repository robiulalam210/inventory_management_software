from rest_framework import serializers
from .models import Account
from decimal import Decimal


class AccountSerializer(serializers.ModelSerializer):
    ac_number = serializers.CharField(source='number', required=False, allow_blank=True, allow_null=True)
    status = serializers.SerializerMethodField()
    
    class Meta:
        model = Account
        fields = [
            'id', 'name', 'ac_type', 'ac_number', 'balance', 
            'bank_name', 'branch', 'opening_balance', 'company', 
            'status', 'ac_no', 'is_active', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'balance': {'read_only': True},
            'ac_no': {'read_only': True},
            'company': {'read_only': True},
            'created_at': {'read_only': True},
            'updated_at': {'read_only': True},
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
    
    def validate(self, data):
        """Validate the entire data set"""
        request = self.context.get('request')
        company = request.user.company if request and hasattr(request.user, 'company') else None
        
        # Get the actual number value from the source mapping
        if 'number' in data:
            if data['number'] == '' or data['number'] is None:
                data['number'] = None
        
        # Get account type
        ac_type = data.get('ac_type', self.instance.ac_type if self.instance else None)
        number = data.get('number', self.instance.number if self.instance else None)
        
        # Bank and Mobile banking must have numbers
        if ac_type in [Account.TYPE_BANK, Account.TYPE_MOBILE]:
            if not number:
                raise serializers.ValidationError({
                    'ac_number': f"{ac_type} accounts must have an account number."
                })
            
            # Check for duplicates
            if company and number:
                queryset = Account.objects.filter(
                    company=company,
                    ac_type=ac_type,
                    number=number
                )
                if self.instance:
                    queryset = queryset.exclude(pk=self.instance.pk)
                
                if queryset.exists():
                    raise serializers.ValidationError({
                        'ac_number': f"A {ac_type} account with this number already exists."
                    })
        
        # Ensure opening_balance is included and valid
        opening_balance = data.get('opening_balance', Decimal('0.00'))
        if opening_balance is None:
            data['opening_balance'] = Decimal('0.00')
        
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user if request else None
        company = user.company if user and hasattr(user, 'company') else None

        if not company:
            raise serializers.ValidationError({"company": "User must be associated with a company."})

        # Extract data
        ac_type = validated_data.get('ac_type')
        name = validated_data.get('name')
        number = validated_data.get('number')
        opening_balance = validated_data.get('opening_balance', Decimal('0.00'))

        # For Bank/Mobile banking, ensure number exists
        if ac_type in [Account.TYPE_BANK, Account.TYPE_MOBILE] and not number:
            raise serializers.ValidationError({
                'ac_number': f"{ac_type} accounts must have an account number."
            })

        # Check for duplicates for Bank/Mobile banking
        if ac_type in [Account.TYPE_BANK, Account.TYPE_MOBILE] and number:
            if Account.objects.filter(company=company, ac_type=ac_type, number=number).exists():
                raise serializers.ValidationError({
                    'ac_number': "An account with this type and number already exists."
                })

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
            is_active=True,
            created_by=user
        )

        # Validate and save
        account.full_clean()
        account.save(creating_user=user)
        return account