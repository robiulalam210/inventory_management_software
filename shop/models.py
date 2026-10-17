from decimal import Decimal

from django.db import models, transaction


class ShopOrder(models.Model):
    """কাস্টমারের অনলাইন অর্ডার।

    NOTE (পরে করতে হবে): এখন confirm করলে অর্ডার শুধু status বদলায়; আলাদা Sale / Customer / Money Receipt
    তৈরি হয় না। `sales/models.py` পেলে ShopOrder.change_status() এর CONFIRMED শাখায় অটো Sale বানানো যাবে।
    NOTE: stock অর্ডার দেওয়ার সময়ই কমে (stock_deducted=True), cancel করলে ফেরত আসে।
    """
    PENDING, CONFIRMED, DELIVERED, CANCELLED = 'pending', 'confirmed', 'delivered', 'cancelled'
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (CONFIRMED, 'Confirmed'),
        (DELIVERED, 'Delivered'),
        (CANCELLED, 'Cancelled'),
    ]

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='shop_orders')
    order_no = models.CharField(max_length=20, blank=True)
    customer_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    address = models.TextField()
    note = models.TextField(blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=PENDING)
    delivery_charge = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))  # আইটেম + delivery
    stock_deducted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['company', 'status'])]

    def __str__(self):
        return f"{self.order_no or self.pk} — {self.customer_name}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.order_no:
            self.order_no = f"WEB-{self.pk:05d}"
            super().save(update_fields=['order_no'])

    # ── stock ──
    def _locked_products(self):
        from products.models import Product
        ids = [i.product_id for i in self.items.all() if i.product_id]
        return {p.id: p for p in Product.objects.select_for_update().filter(id__in=ids)}

    def deduct_stock(self):
        """Confirm এর সময় — যথেষ্ট stock না থাকলে ValueError"""
        if self.stock_deducted:
            return
        items = list(self.items.all())
        products = self._locked_products()
        for it in items:
            p = products.get(it.product_id)
            if p is None:
                raise ValueError(f"'{it.product_name}' is no longer in the inventory.")
            if p.stock_qty < it.qty:
                raise ValueError(f"Not enough stock for '{it.product_name}' (in stock: {p.stock_qty}, ordered: {it.qty}).")
        for it in items:
            p = products[it.product_id]
            p.stock_qty -= it.qty
            p.save(update_fields=['stock_qty'])
        self.stock_deducted = True

    def restore_stock(self):
        """Confirm হওয়ার পর বাতিল হলে stock ফেরত"""
        if not self.stock_deducted:
            return
        products = self._locked_products()
        for it in self.items.all():
            p = products.get(it.product_id)
            if p is not None:
                p.stock_qty += it.qty
                p.save(update_fields=['stock_qty'])
        self.stock_deducted = False

    @transaction.atomic
    def change_status(self, new_status):
        order = ShopOrder.objects.select_for_update().get(pk=self.pk)
        allowed = {
            self.PENDING: {self.CONFIRMED, self.CANCELLED},
            self.CONFIRMED: {self.DELIVERED, self.CANCELLED},
        }
        if new_status not in allowed.get(order.status, set()):
            raise ValueError(f"Can't change an order from {order.status} to {new_status}.")
        if new_status == self.CONFIRMED:
            order.deduct_stock()
        elif new_status == self.CANCELLED:
            order.restore_stock()
        order.status = new_status
        order.save()
        return order


class ShopOrderItem(models.Model):
    order = models.ForeignKey(ShopOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    product_name = models.CharField(max_length=255)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    qty = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.product_name} × {self.qty}"


class ShopSettings(models.Model):
    """শপ পেজের তথ্য ও চেহারা — inventory এর Shop Settings পেজ থেকে অ্যাডমিন বদলাবে।"""
    company = models.OneToOneField('core.Company', on_delete=models.CASCADE, related_name='shop_settings')

    # কোম্পানি শনাক্ত: এই ডোমেইনে (যেমন shop.meherin.com) ঢুকলে এই কোম্পানির শপ দেখাবে
    domain = models.CharField(max_length=253, blank=True, null=True, unique=True,
                              help_text='Your shop address, e.g. shop.example.com (no https://). Leave empty if not used.')

    # সাধারণ
    is_open = models.BooleanField('Accept orders', default=True)
    shop_name = models.CharField(max_length=80, blank=True, help_text='Leave empty to use the company name.')
    tagline = models.CharField(max_length=140, blank=True)
    brand_color = models.CharField(max_length=7, default='#0f766e', help_text='Hex colour, e.g. #0f766e')
    THEME_CHOICES = [('auto', 'Follow the visitor\'s device'), ('light', 'Always light'), ('dark', 'Always dark')]
    default_theme = models.CharField(max_length=5, choices=THEME_CHOICES, default='auto',
                                     help_text='Visitors can still switch with the sun/moon button.')
    announcement = models.CharField('Top announcement', max_length=200, blank=True)

    # Hero ব্যানার
    hero_title = models.CharField(max_length=120, blank=True)
    hero_subtitle = models.CharField(max_length=240, blank=True)
    hero_button_text = models.CharField(max_length=30, default='Shop now')
    hero_image = models.ImageField(upload_to='shop-banners/', blank=True, null=True)

    # আমাদের সম্পর্কে
    about_title = models.CharField(max_length=80, blank=True)
    about_text = models.TextField(blank=True)

    # যোগাযোগ
    phone = models.CharField(max_length=30, blank=True)
    whatsapp = models.CharField('WhatsApp number', max_length=30, blank=True, help_text='With country code, digits only.')
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=240, blank=True)
    opening_hours = models.CharField(max_length=120, blank=True)
    facebook_url = models.URLField(blank=True)

    # ডেলিভারি ও পেমেন্ট
    delivery_charge = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    free_delivery_min = models.DecimalField('Free delivery above', max_digits=10, decimal_places=2, default=Decimal('0.00'),
                                            help_text='0 = no free delivery.')
    delivery_note = models.CharField(max_length=140, default='Delivery within 1–3 days', blank=True)
    payment_note = models.CharField(max_length=140, default='Cash on delivery', blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Shop settings'

    def __str__(self):
        return f"Shop settings — {self.company_id}"

    @classmethod
    def for_company(cls, company):
        obj, _ = cls.objects.get_or_create(company=company)
        return obj

    def public_url(self, request):
        """এই কোম্পানির শপের লিংক — ডোমেইন থাকলে সেটা, না থাকলে বর্তমান সাইটের হোম"""
        from django.urls import reverse
        if self.domain:
            return f"{'https' if request.is_secure() else 'http'}://{self.domain}/"
        return request.build_absolute_uri(reverse('shop:store', args=[self.company_id]))

    def delivery_for(self, subtotal):
        if self.free_delivery_min and subtotal >= self.free_delivery_min:
            return Decimal('0.00')
        return self.delivery_charge
