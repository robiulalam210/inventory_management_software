# branch_warehouse/admin.py
from django.contrib import admin
from .models import Supplier, Purchase, PurchaseItem

admin.site.register(Supplier) 
admin.site.register(Purchase)
admin.site.register(PurchaseItem)
