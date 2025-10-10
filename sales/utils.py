# from decimal import Decimal
# from django.db import transaction
# from .models import Sale, SaleItem, Customer
# from products.models import Product

# def create_sale(data):
#     with transaction.atomic():
#         if data.get("customer"):
#             customer = Customer.objects.get(id=data["customer"])
#         else:
#             customer, _ = Customer.objects.get_or_create(name="Walk-in Customer")

#         sale = Sale.objects.create(
#             customer=customer,
#             sale_type=data.get("sale_type", "retail"),
#             sale_date=data.get("sale_date"),
#             sale_by=data.get("sale_by", ""),
#             gross_total=Decimal(data.get("gross_total", 0)),
#             net_total=Decimal(data.get("net_total", 0)),
#             overall_discount=Decimal(data.get("overall_discount", 0)),
#             overall_discount_type=data.get("overall_discount_type"),
#             overall_delivery_charge=Decimal(data.get("overall_delivery_charge", 0)),
#             overall_delivery_charge_type=data.get("overall_delivery_charge_type"),
#             overall_service_charge=Decimal(data.get("overall_service_charge", 0)),
#             overall_vat_amount=Decimal(data.get("overall_vat_amount", 0)),
#             overall_vat_type=data.get("overall_vat_type"),
#             payable_amount=Decimal(data.get("payable_amount", 0)),
#             change_amount=Decimal(data.get("change_amount", 0)),
#             payment_method=data.get("payment_method", "cash")
#         )

#         for item in data.get("items", []):
#             product = Product.objects.get(id=item["product_id"])
#             quantity = int(item["quantity"])
#             unit_price = Decimal(item["unit_price"])
#             discount = Decimal(item.get("discount", 0))
#             discount_type = item.get("discount_type", "fixed")

#             SaleItem.objects.create(
#                 sale=sale,
#                 product=product,
#                 quantity=quantity,
#                 unit_price=unit_price,
#                 discount=discount,
#                 discount_type=discount_type
#             )

#             # স্টক হ্রাস
#             product.stock_qty -= quantity
#             product.save()

#         return sale
