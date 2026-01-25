# sales/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
from decimal import Decimal, ROUND_HALF_UP
import logging

logger = logging.getLogger(__name__)


class Sale(models.Model):
    SALE_TYPE_CHOICES = [('retail', 'Retail'), ('wholesale', 'Wholesale')]
    CUSTOMER_TYPE_CHOICES = [('walk_in', 'Walk-in'), ('saved_customer', 'Saved Customer')]
    MONEY_RECEIPT_CHOICES = [('Yes', 'Yes'), ('No', 'No')]
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
    ]

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_created')
    sale_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales_made')
    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey('customers.Customer', on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=100, blank=True, null=True)

    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='retail')
    invoice_no = models.CharField(max_length=20, blank=True, null=True)
    sale_date = models.DateTimeField(auto_now_add=True)

    customer_type = models.CharField(max_length=20, choices=CUSTOMER_TYPE_CHOICES, default='walk_in')
    with_money_receipt = models.CharField(max_length=3, choices=MONEY_RECEIPT_CHOICES, default='No')
    remark = models.TextField(blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    gross_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    net_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    payable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    due_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    overall_discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_discount_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)

    overall_delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_delivery_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)

    overall_service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_service_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)

    overall_vat_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    overall_vat_type = models.CharField(max_length=10, choices=(('fixed','Fixed'),('percent','Percent')), blank=True, null=True)

    payment_method = models.CharField(max_length=100, blank=True, null=True)
    account = models.ForeignKey('accounts.Account', on_delete=models.SET_NULL, blank=True, null=True, related_name='sales')

    class Meta:
        ordering = ['-sale_date', '-id']
        indexes = [
            models.Index(fields=['company', 'sale_date']),
            models.Index(fields=['customer', 'sale_date']),
            models.Index(fields=['invoice_no']),
        ]

    def __str__(self):
        return f"{self.invoice_no} - {self.get_customer_display()}"

    def get_customer_display(self):
        if self.customer_type == 'walk_in':
            return self.customer_name or "Walk-in Customer"
        elif self.customer:
            return self.customer.name
        return "Unknown Customer"

    def save(self, *args, **kwargs):
        """Safe save with recursion prevention"""
        if getattr(self, '_saving', False):
            return super().save(*args, **kwargs)

        self._saving = True
        try:
            is_new = self.pk is None

            # Auto-assign company based on created_by if not present
            if not self.company and hasattr(self, 'created_by') and self.created_by:
                if hasattr(self.created_by, 'company') and self.created_by.company:
                    self.company = self.created_by.company

            if not self.company:
                raise ValidationError("Sale must be associated with a company.")

            # Handle customer/walk-in logic
            if self.customer_type == 'walk_in':
                if not self.customer_name:
                    self.customer_name = 'Walk-in Customer'
                self.customer = None
            elif self.customer_type == 'saved_customer' and self.customer:
                if self.customer.company and self.company and self.customer.company != self.company:
                    raise ValidationError('Customer must belong to the same company.')

            # Generate invoice for new sales
            if is_new and not self.invoice_no:
                self.invoice_no = self._generate_invoice_no()

            # Validate account company match if provided
            if self.account and self.account.company and self.company and self.account.company != self.company:
                self.account = None

            # Save to get pk
            super().save(*args, **kwargs)

            # Recalculate totals and handle payment processing
            self.calculate_totals()
            self._handle_payment_processing(is_new)

        except Exception as e:
            logger.exception("Error saving sale")
            raise
        finally:
            self._saving = False

    def _generate_invoice_no(self):
        if not self.company:
            return f"SL-{int(timezone.now().timestamp())}"
        try:
            last_sale = Sale.objects.filter(
                company=self.company,
                invoice_no__regex=r'^SL-\d+$'
            ).order_by('-invoice_no').first()
            if last_sale and last_sale.invoice_no:
                try:
                    last_number = int(last_sale.invoice_no.split('-')[1])
                    new_number = last_number + 1
                except (ValueError, IndexError):
                    existing_count = Sale.objects.filter(company=self.company).count()
                    new_number = 1001 + existing_count
            else:
                existing_count = Sale.objects.filter(company=self.company).count()
                new_number = 1001 + existing_count
            return f"SL-{new_number}"
        except Exception:
            logger.exception("Error generating invoice number")
            return f"SL-{int(timezone.now().timestamp())}"

    def calculate_totals(self):
        """Compute gross/net/payable/grand totals, due/change and update payment status."""
        try:
            # Calculate total from items
            items_total = sum(item.subtotal() for item in self.items.all())
            self.gross_total = self._round_decimal(items_total)
            self.net_total = self.gross_total

            # Calculate charges using the actual stored values
            vat_amount = self._calculate_charge(
                self.overall_vat_amount, 
                self.overall_vat_type, 
                self.net_total
            )
            service_amount = self._calculate_charge(
                self.overall_service_charge, 
                self.overall_service_type, 
                self.net_total
            )
            delivery_amount = self._calculate_charge(
                self.overall_delivery_charge, 
                self.overall_delivery_type, 
                self.net_total
            )
            overall_discount_amount = self._calculate_charge(
                self.overall_discount, 
                self.overall_discount_type, 
                self.net_total
            )

            total_charges = vat_amount + service_amount + delivery_amount
            self.payable_amount = self.net_total + total_charges - overall_discount_amount
            
            if self.payable_amount < Decimal('0.00'):
                self.payable_amount = Decimal('0.00')

            self.grand_total = self.payable_amount
            self.due_amount = max(Decimal('0.00'), self.grand_total - self.paid_amount)
            self.change_amount = max(Decimal('0.00'), self.paid_amount - self.grand_total)

            self._update_payment_status()

            # Save calculated fields
            update_fields = [
                'gross_total', 'net_total', 'payable_amount', 'grand_total',
                'due_amount', 'change_amount', 'payment_status'
            ]
            
            # Avoid recursion by using super().save()
            super(Sale, self).save(update_fields=update_fields)
            
            logger.info(f"Sale {self.invoice_no} totals calculated: "
                       f"Gross={self.gross_total}, "
                       f"VAT={vat_amount}, "
                       f"Service={service_amount}, "
                       f"Delivery={delivery_amount}, "
                       f"GrandTotal={self.grand_total}")
            
        except Exception as e:
            logger.exception("Error calculating totals")
            raise

    def _calculate_charge(self, amount, charge_type, base_amount):
        """Calculate charge amount based on type (fixed or percent)"""
        if not amount or amount <= 0:
            return Decimal('0.00')
        if charge_type == 'percent':
            return self._round_decimal(base_amount * (amount / Decimal('100.00')))
        return self._round_decimal(amount)

    def _round_decimal(self, value):
        """Helper to round decimals safely"""
        try:
            if value is None:
                return Decimal('0.00')
            if isinstance(value, (int, float)):
                value = Decimal(str(value))
            return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal('0.00')

    def _update_payment_status(self):
        """Update payment status based on paid amount"""
        try:
            if self.paid_amount >= self.grand_total:
                self.payment_status = 'paid'
            elif self.paid_amount > Decimal('0.00'):
                self.payment_status = 'partial'
            else:
                self.payment_status = 'pending'
        except Exception:
            logger.exception("Error updating payment status")
            self.payment_status = 'pending'

    def _handle_payment_processing(self, is_new):
        """If paid_amount > 0, update account and create transaction/receipt."""
        if self.paid_amount <= 0:
            return

        if self.account:
            try:
                self.account.balance += self.paid_amount
                self.account.save(update_fields=['balance'])
                logger.info(f"Account {self.account.name} balance updated: +{self.paid_amount}")
            except Exception:
                logger.exception("Error updating account balance")

        if self.with_money_receipt == 'Yes':
            self.create_money_receipt()
        else:
            self.create_transaction()

    def create_transaction(self):
        """Create transaction for the sale"""
        try:
            from transactions.models import Transaction
            existing_transaction = Transaction.objects.filter(
                reference_model='sale',
                reference_id=self.id
            ).first()
            if existing_transaction:
                return existing_transaction
            if self.paid_amount > 0 and self.account:
                transaction = Transaction(
                    company=self.company,
                    account=self.account,
                    amount=self.paid_amount,
                    transaction_type='credit',
                    reference_model='sale',
                    reference_id=self.id,
                    date=timezone.now(),
                    description=f"Sale {self.invoice_no}",
                    created_by=self.created_by
                )
                transaction.save()
                return transaction
        except Exception:
            logger.exception("Error creating transaction")
        return None

    def create_money_receipt(self):
        """Create money receipt for the sale"""
        if self.paid_amount <= 0:
            return None
        try:
            from money_receipts.models import MoneyReceipt
            existing_receipt = MoneyReceipt.objects.filter(sale=self).first()
            if existing_receipt:
                if existing_receipt.amount != self.paid_amount:
                    existing_receipt.amount = self.paid_amount
                    existing_receipt.save()
                return existing_receipt
            money_receipt = MoneyReceipt(
                company=self.company,
                customer=self.customer if self.customer_type == 'saved_customer' else None,
                sale=self,
                amount=self.paid_amount,
                payment_method=self.payment_method or 'Cash',
                payment_date=timezone.now(),
                remark=f"Auto receipt for {self.invoice_no}",
                seller=self.sale_by,
                account=self.account,
                created_by=self.created_by
            )
            money_receipt.save()
            return money_receipt
        except Exception:
            logger.exception("Error creating money receipt")
            return None

    def clean(self):
        """Validate sale data"""
        super().clean()
        if not self.company:
            raise ValidationError({'company': 'Sale must be associated with a company.'})
        if self.due_amount < 0:
            raise ValidationError({'due_amount': 'Due amount cannot be negative.'})
        if self.customer_type == 'saved_customer' and not self.customer:
            raise ValidationError({'customer': 'Saved customer must have a customer record.'})
        if self.paid_amount > 0 and not self.payment_method:
            raise ValidationError({'payment_method': 'Payment method is required when payment is made.'})

    def add_payment(self, amount, payment_method=None, account=None):
        """Add payment to existing sale"""
        if amount <= 0:
            raise ValueError("Payment amount must be greater than 0")
        if payment_method:
            self.payment_method = payment_method
        if account:
            self.account = account
        self.paid_amount += amount
        self.save()
        return self.paid_amount

    def get_payment_summary(self):
        """Get payment summary"""
        return {
            'invoice_no': self.invoice_no,
            'grand_total': float(self.grand_total),
            'paid_amount': float(self.paid_amount),
            'due_amount': float(self.due_amount),
            'change_amount': float(self.change_amount),
            'payment_status': self.payment_status,
            'payment_method': self.payment_method,
        }

    def can_add_payment(self):
        """Check if payment can be added"""
        return self.due_amount > 0 and self.payment_status in ['pending', 'partial']

    @classmethod
    def get_sales_summary(cls, company, start_date=None, end_date=None):
        """Get sales summary for a company"""
        queryset = cls.objects.filter(company=company)
        if start_date:
            queryset = queryset.filter(sale_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(sale_date__lte=end_date)
        return queryset.aggregate(
            total_sales=models.Count('id'),
            total_amount=models.Sum('grand_total'),
            total_paid=models.Sum('paid_amount'),
            total_due=models.Sum('due_amount')
        )


class SaleItem(models.Model):
    sale = models.ForeignKey('Sale', related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    
    # Multi-mode system fields
    sale_mode = models.ForeignKey(
        'products.SaleMode', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        help_text="Sale mode used for this item (KG, GRAM, BOSTA, etc.)"
    )
    
    quantity = models.DecimalField(
        max_digits=12, 
        decimal_places=3,
        default=Decimal('1.00'),
        help_text="Quantity"
    )
    
    base_quantity = models.DecimalField(
        max_digits=12, 
        decimal_places=3,
        default=Decimal('1.00'),
        help_text="Quantity converted to base unit"
    )
    
    # Price fields
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    price_type = models.CharField(
        max_length=10, 
        choices=[
            ('unit', 'Unit Price'),
            ('flat', 'Flat Price'),
            ('tier', 'Tier Price'),
            ('normal', 'Normal Price')
        ], 
        default='unit'
    )
    flat_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # Discount fields
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    discount_type = models.CharField(
        max_length=10, 
        choices=(('fixed','Fixed'),('percent','Percent')), 
        default='fixed'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['id']
        verbose_name = "Sale Item"
        verbose_name_plural = "Sale Items"
    
    def __str__(self):
        if self.sale_mode:
            return f"{self.product.name} - {self.quantity} {self.sale_mode.name}"
        return f"{self.product.name} - {self.quantity} {self.product.unit.name if self.product.unit else 'units'}"
    
    @property
    def sale_quantity(self):
        return self.quantity
    
    @sale_quantity.setter
    def sale_quantity(self, value):
        self.quantity = value
    
    def save(self, *args, **kwargs):
        """Save sale item with multi-mode support"""
        is_new = self.pk is None
        
        # If sale_mode is provided, calculate base quantity
        if self.sale_mode and hasattr(self.sale_mode, 'convert_to_base'):
            try:
                self.base_quantity = self.sale_mode.convert_to_base(self.quantity)
                self.price_type = self.sale_mode.price_type
            except:
                self.base_quantity = self.quantity
                self.price_type = 'unit'
        else:
            self.base_quantity = self.quantity
            self.price_type = 'normal'
        
        # Get or calculate unit price
        if not self.unit_price:
            if self.sale_mode:
                try:
                    from products.models import ProductSaleMode
                    product_sale_mode = ProductSaleMode.objects.get(
                        product=self.product,
                        sale_mode=self.sale_mode,
                        is_active=True
                    )
                    
                    if self.sale_mode.price_type == 'flat' and product_sale_mode.flat_price:
                        self.flat_price = product_sale_mode.flat_price
                        self.unit_price = product_sale_mode.flat_price / self.quantity if self.quantity else Decimal('0.00')
                    elif self.sale_mode.price_type == 'tier':
                        self.unit_price = product_sale_mode.get_tier_price(self.base_quantity)
                    else:
                        self.unit_price = product_sale_mode.get_unit_price()
                except ProductSaleMode.DoesNotExist:
                    self.unit_price = self.product.selling_price
            else:
                self.unit_price = self.product.selling_price
        
        # Validate stock before saving
        if is_new:
            base_quantity_decimal = Decimal(str(self.base_quantity))
            product_stock = Decimal(str(self.product.stock_qty))
            
            if base_quantity_decimal > product_stock:
                raise ValidationError(
                    f"Not enough stock for {self.product.name}. "
                    f"Available: {product_stock} {self.product.unit.name if self.product.unit else 'units'}, "
                    f"Requested: {self.quantity} {self.sale_mode.name if self.sale_mode else self.product.unit.name if self.product.unit else 'units'}"
                )
        
        super().save(*args, **kwargs)
        
        # Update product stock if new item
        if is_new:
            try:
                self.product.stock_qty -= float(self.base_quantity)
                self.product.save(update_fields=['stock_qty', 'updated_at'])
            except Exception as e:
                logger.exception(f"Error updating product stock for {self.product.name}: {e}")
        
        # Recalculate sale totals
        try:
            self.sale.calculate_totals()
        except Exception as e:
            logger.exception(f"Error updating sale totals: {e}")
    
    def subtotal(self):
        """Calculate subtotal with multi-mode pricing"""
        try:
            if self.price_type == 'flat' and self.flat_price:
                total = self.flat_price
            else:
                total = Decimal(str(self.base_quantity)) * Decimal(str(self.unit_price))
            
            # Apply discount
            discount_amount = Decimal('0.00')
            if self.discount_type == 'percent' and self.discount > 0:
                discount_amount = total * (Decimal(str(self.discount)) / Decimal('100.00'))
            elif self.discount_type == 'fixed' and self.discount > 0:
                discount_amount = min(Decimal(str(self.discount)), total)
            
            final_total = max(Decimal('0.00'), total - discount_amount)
            return final_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception as e:
            logger.exception(f"Error calculating subtotal for item {self.id}: {e}")
            return Decimal('0.00')
    
    def get_item_details(self):
        """Get detailed item information"""
        return {
            'id': self.id,
            'product_id': self.product.id,
            'product_name': self.product.name,
            'product_sku': self.product.sku,
            'sale_mode_id': self.sale_mode.id if self.sale_mode else None,
            'sale_mode_name': self.sale_mode.name if self.sale_mode else self.product.unit.name if self.product.unit else 'Unit',
            'quantity': float(self.quantity),
            'sale_quantity': float(self.quantity),
            'base_quantity': float(self.base_quantity),
            'unit_price': float(self.unit_price),
            'price_type': self.price_type,
            'flat_price': float(self.flat_price) if self.flat_price else None,
            'discount': float(self.discount),
            'discount_type': self.discount_type,
            'subtotal': float(self.subtotal()),
            'stock_deducted': float(self.base_quantity)
        }
    
    def delete(self, *args, **kwargs):
        """Override delete to return stock"""
        # Return stock to product
        try:
            self.product.stock_qty += float(self.base_quantity)
            self.product.save(update_fields=['stock_qty', 'updated_at'])
        except Exception as e:
            logger.exception(f"Error returning stock for {self.product.name}: {e}")
        
        # Delete the item
        sale = self.sale
        super().delete(*args, **kwargs)
        
        # Recalculate sale totals
        try:
            sale.calculate_totals()
        except Exception:
            pass