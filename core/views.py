from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import User, Account
from .serializers import UserSerializer, AccountSerializer

# User API
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]


# Account API
class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]
