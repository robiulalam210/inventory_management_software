# accounts/serializers.py
from rest_framework import serializers
from .models import Account

class AccountSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    ac_id = serializers.IntegerField(source='id', read_only=True)
    ac_name = serializers.CharField(source='name')
    ac_type = serializers.CharField()
    ac_number = serializers.CharField(source='number', required=False, allow_null=True, allow_blank=True)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)  # Make read-only
    bank_name = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    branch = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    opening_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = Account
        fields = [
            'ac_id', 'ac_name', 'ac_type', 'ac_number', 'balance',
            'bank_name', 'branch', 'opening_balance', 'company', 'status',
        ]

    def validate(self, data):
        """
        Custom validation for account data
        """
        ac_type = data.get('ac_type')
        number = data.get('number')
        bank_name = data.get('bank_name')
        branch = data.get('branch')

        # Validate account number based on type
        if ac_type in [Account.TYPE_BANK, Account.TYPE_MOBILE]:
            if not number or number.strip() == '':
                raise serializers.ValidationError({
                    'ac_number': 'Account number is required for Bank and Mobile banking accounts.'
                })

        # Validate bank details for bank accounts
        if ac_type == Account.TYPE_BANK:
            if not bank_name or bank_name.strip() == '':
                raise serializers.ValidationError({
                    'bank_name': 'Bank name is required for Bank accounts.'
                })
            if not branch or branch.strip() == '':
                raise serializers.ValidationError({
                    'branch': 'Branch name is required for Bank accounts.'
                })

        # For Cash and Other accounts, ensure number is None
        if ac_type in [Account.TYPE_CASH, Account.TYPE_OTHER]:
            data['number'] = None
            data['bank_name'] = None
            data['branch'] = None

        return data

    def create(self, validated_data):
        # Set balance from opening_balance for new accounts
        validated_data['balance'] = validated_data.get('opening_balance', 0)
        return super().create(validated_data)