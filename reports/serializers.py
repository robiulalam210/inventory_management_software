from rest_framework import serializers

# --------------------
# Sales Report Serializer
# --------------------
class SalesReportSerializer(serializers.Serializer):
    invoice_no = serializers.CharField()
    customer = serializers.CharField()
    total_amount = serializers.FloatField()
    total_discount = serializers.FloatField()
    total_vat = serializers.FloatField()
    net_amount = serializers.FloatField()
    date = serializers.DateField()

# --------------------
# Purchase Report Serializer
# --------------------
class PurchaseReportSerializer(serializers.Serializer):
    invoice_no = serializers.CharField()
    supplier = serializers.CharField()
    total_amount = serializers.FloatField()
    total_discount = serializers.FloatField()
    net_amount = serializers.FloatField()
    date = serializers.DateField()

# --------------------
# Profit & Loss Report Serializer
# --------------------
class ProfitLossReportSerializer(serializers.Serializer):
    total_sales = serializers.FloatField()
    total_purchase = serializers.FloatField()
    total_profit = serializers.FloatField()

class PurchaseReturnReportSerializer(serializers.Serializer):
    invoice_no = serializers.CharField()
    supplier = serializers.CharField()
    total_amount = serializers.FloatField()
    return_amount = serializers.FloatField()
    date = serializers.DateField()



class TopSoldProductsSerializer(serializers.Serializer):
    product_name = serializers.CharField()  # match the key from values()
    quantity_sold = serializers.IntegerField()
    total_sales = serializers.FloatField()

class LowStockSerializer(serializers.Serializer):
    product = serializers.CharField()
    stock_qty = serializers.IntegerField()


class BadStockReportSerializer(serializers.Serializer):
    product = serializers.CharField()
    quantity = serializers.IntegerField()
    reason = serializers.CharField()

class StockReportSerializer(serializers.Serializer):
    product = serializers.CharField()
    stock_qty = serializers.IntegerField()
