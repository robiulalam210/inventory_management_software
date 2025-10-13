from rest_framework import serializers
from .models import Expense, ExpenseHead, ExpenseSubHead

class ExpenseHeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseHead
        fields = ['id', 'name', 'company']  # ✅ include it!
        extra_kwargs = {
            'company': {'required': True}  # so we can set it manually in the view
        }

class ExpenseSubHeadSerializer(serializers.ModelSerializer):
    head = serializers.PrimaryKeyRelatedField(queryset=ExpenseHead.objects.all())
    class Meta:
        model = ExpenseSubHead
        fields = ['id', 'name', 'head', 'company']  # ✅ include it!

class ExpenseSerializer(serializers.ModelSerializer):

    head = serializers.PrimaryKeyRelatedField(queryset=ExpenseHead.objects.all())
    subhead = serializers.PrimaryKeyRelatedField(queryset=ExpenseSubHead.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Expense
        fields = [
            'id', 'company', 'head', 'subhead', 'description',
            'amount', 'payment_method', 'account', 'expense_date', 'note', 'created_at'
        ]