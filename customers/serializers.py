from rest_framework import serializers

from .models import Customer

# -----------------------------
# Customer Serializer
# -----------------------------
class CustomerSerializer(serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Customer
        fields = '__all__'
