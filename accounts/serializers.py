from rest_framework import serializers
from .models import Account

class AccountSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)
    ac_id = serializers.IntegerField(source='id', read_only=True)
    ac_name = serializers.CharField(source='name')
    ac_type = serializers.CharField()
    ac_number = serializers.CharField(source='number', allow_null=True, allow_blank=True)
    balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    bank_name = serializers.CharField(allow_null=True, allow_blank=True)
    branch = serializers.CharField(allow_null=True, allow_blank=True)
    opening_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    status = serializers.CharField(read_only=True)  # Add status field


    class Meta:
        model = Account
        fields = [
            'ac_id', 'ac_name', 'ac_type', 'ac_number', 'balance',
            'bank_name', 'branch', 'opening_balance', 'company', 'status',
        ]