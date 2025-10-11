from rest_framework import serializers
from .models import Account


class AccountSerializer(serializers.ModelSerializer):
    ac_id = serializers.IntegerField(source='id', read_only=True)
    ac_name = serializers.CharField(source='name')
    ac_number = serializers.CharField(source='number', allow_null=True, allow_blank=True)
    balance = serializers.DecimalField(source='balance', max_digits=14, decimal_places=2)


class Meta:
    model = Account
    fields = [
    'ac_id', 'ac_name', 'ac_type', 'ac_number', 'balance',
    'bank_name', 'branch', 'opening_balance',
    ]