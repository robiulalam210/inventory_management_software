from rest_framework import serializers
from .models import User, Account

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role']

class AccountSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)  # nested user info
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), source='user', write_only=True
    )

    class Meta:
        model = Account
        fields = ['id', 'user', 'user_id', 'account_number', 'balance']
