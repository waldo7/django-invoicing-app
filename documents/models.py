from django.core.validators import MinValueValidator # To ensure amount is positive
from datetime import timedelta # Needed for adding days to a date
from django.db import models
from django.conf import settings # Needed for ForeignKey to User if we add created_by later
from django.utils import timezone # For default dates
from decimal import Decimal
from solo.models import SingletonModel
from django.apps import apps

# Create your models here.
class Client(models.Model):
    """Represents a client (customer)"""
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")

    #Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """String representation of the Client object"""
        return self.name
    

class MenuItem(models.Model):
    """
    Represents a menu item or service offered.
    Stores the default price; actual price might vary per quote/invoice line item.
    """
    class UnitType(models.TextChoices):
        PERSON = 'PERSON', 'Per Person'
        PACK = 'PACK', 'Per Pack'
        TRAY = 'TRAY', 'Per Tray'
        ITEM = 'ITEM', 'Per Item'
        FIXED = 'FIXED', 'Fixed Price'
        DAY = 'DAY', 'Per Day'
        EVENT = 'EVENT', 'Per Event'
        OTHER = 'OTHER', 'Other' # Fallback if needed

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    unit_price = models.DecimalField(
        max_digits=10,    # Max total digits allowed (e.g., 1,234,567.89)
        decimal_places=2  # Number of digits after the decimal point
    )
    unit = models.CharField(
        max_length=10, 
        choices = UnitType.choices,
        default = UnitType.ITEM,
        help_text="e.g., per person, per tray, per pack, fixed")
    is_active = models.BooleanField(default=True, help_text="Is this item currently offered?")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name'] # Order items alphabetically by name by default


class DiscountType(models.TextChoices):
    NONE = 'NONE', 'No Discount'
    PERCENTAGE = 'PERCENT', 'Percentage (%)'
    FIXED = 'FIXED', 'Fixed Amount (RM)'


class Quotation(models.Model):
    """
    Represents a quotation document header.
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SENT = 'SENT', 'Sent'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'
        SUPERSEDED = 'SUPERSEDED', 'Superseded'

    quotation_number = models.CharField(
        max_length=50, 
        unique=True,
        blank=True,
        null=True,
        editable=False
        )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='quotations')
    title = models.CharField(max_length=255, blank=True, default='')
    issue_date = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True) # Optional

    status = models.CharField(max_length=15, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1)
    # Link to previous version, if any. 'self' refers to the Quotation model itself.
    previous_version = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL, # Keep revision history even if previous is deleted (though unlikely)
        null=True, blank=True,
        related_name='next_versions' # How we can find V2 from V1 (V1.next_versions)
    )

    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices,
        default=DiscountType.NONE
    )

    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Enter percentage (e.g., 10.00 for 10%) or fixed amount."
    )

    terms_and_conditions = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='', help_text="Internal notes, not shown to client")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Quotation {self.quotation_number} ({self.client.name})"
    
    @property
    def subtotal(self):
        """Calculate sum of all line item totals before discounts/taxes."""
        return sum((item.line_total for item in self.items.all()), Decimal('0.00')).quantize(Decimal("0.01"))

    @property
    def discount_amount(self):
        """Calculate the discount amount based on type and value."""
        if self.discount_type == DiscountType.NONE or self.discount_value <= 0:
            return Decimal("0.00")

        sub = self.subtotal # Use the subtotal property
        if self.discount_type == DiscountType.PERCENTAGE:
            amount = (sub * (self.discount_value / Decimal(100))).quantize(Decimal("0.01"))
            return amount
        elif self.discount_type == DiscountType.FIXED:
            amount = min(sub, self.discount_value).quantize(Decimal("0.01"))
            return amount
        return Decimal("0.00")

    @property
    def total_before_tax(self):
        """Calculate total after discount but before tax."""
        return (self.subtotal - self.discount_amount).quantize(Decimal("0.01"))

    @property
    def tax_amount(self):
        """Calculate tax amount based on settings and total_before_tax."""
        Setting = apps.get_model('documents', 'Setting')
        settings = Setting.get_solo()
        if settings.tax_enabled and settings.tax_rate > 0:
            tax_rate = settings.tax_rate / Decimal(100) # e.g., 6.00 -> 0.06
            amount = (self.total_before_tax * tax_rate).quantize(Decimal("0.01"))
            return amount
        return Decimal("0.00")

    @property
    def grand_total(self):
        """Calculate the final total including discounts and tax."""
        return (self.total_before_tax + self.tax_amount).quantize(Decimal("0.01"))

    
    class Meta:
        ordering = ['-issue_date', '-created_at'] # Show newest quotes first by default

    
class QuotationItem(models.Model):
    """
    Represents a single line item on a Quotation.
    """
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name='quotation_items')
    description = models.TextField(blank=True, help_text="Defaults to menu item description, can be overridden.")
    quantity = models.DecimalField(max_digits=10, decimal_places=2) # e.g., 1.5 hours, 10 persons
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit for *this* quote line.")
    grouping_label = models.CharField(max_length=100, blank=True, default='', help_text="Optional label to group items (e.g., 'Day 1 - Lunch')")

    def __str__(self):
        return f"{self.quantity} x {self.menu_item.name} on {self.quotation.quotation_number}"


    @property
    def line_total(self):
        """Calculate the total for this line item."""
        if self.quantity is not None and self.unit_price is not None:
            return (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        return Decimal("0.00")


    class Meta:
        ordering = ['id'] # Order items by creation order within a quote


class Invoice(models.Model):
    """
    Represents an invoice document header.
    """
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SENT = 'SENT', 'Sent'
        PAID = 'PAID', 'Paid'
        PARTIALLY_PAID = 'PART_PAID', 'Partially Paid'
        CANCELLED = 'CANCELLED', 'Cancelled'
        # OVERDUE = 'OVERDUE', 'Overdue' # Maybe calculated later

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        blank=True, null=True, # Allow blank/null initially for auto-gen
        editable=False         # Not editable by user
    )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='invoices')
    # Link back to the source if applicable
    related_quotation = models.ForeignKey(
        Quotation,
        on_delete=models.SET_NULL, # Keep invoice if quote is deleted
        null=True, blank=True,
        related_name='invoices'
    )
    # We might add related_order later when that model exists

    title = models.CharField(max_length=255, blank=True, default='')
    issue_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices,
        default=DiscountType.NONE
    )

    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Enter percentage (e.g., 10.00 for 10%) or fixed amount."
    )

    terms_and_conditions = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='', help_text="Internal notes")
    payment_details = models.TextField(blank=True, default='', help_text="Info like bank account, payment terms")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def subtotal(self):
        """Calculate sum of all line item totals before discounts/taxes."""
        #return sum(item.line_total for item in self.items.all()).quantize(Decimal("0.01"))
        return sum((item.line_total for item in self.items.all()), Decimal('0.00')).quantize(Decimal("0.01"))


    @property
    def discount_amount(self):
        """Calculate the discount amount based on type and value."""
        if self.discount_type == DiscountType.NONE or self.discount_value <= 0:
            return Decimal("0.00")

        sub = self.subtotal # Use the subtotal property
        if self.discount_type == DiscountType.PERCENTAGE:
            amount = (sub * (self.discount_value / Decimal(100))).quantize(Decimal("0.01"))
            return amount
        elif self.discount_type == DiscountType.FIXED:
            amount = min(sub, self.discount_value).quantize(Decimal("0.01"))
            return amount
        return Decimal("0.00")

    @property
    def total_before_tax(self):
        """Calculate total after discount but before tax."""
        return (self.subtotal - self.discount_amount).quantize(Decimal("0.01"))

    @property
    def tax_amount(self):
        """Calculate tax amount based on settings and total_before_tax."""
        Setting = apps.get_model('documents', 'Setting')

        settings = Setting.get_solo()
        if settings.tax_enabled and settings.tax_rate > 0:
            tax_rate = settings.tax_rate / Decimal(100)
            amount = (self.total_before_tax * tax_rate).quantize(Decimal("0.01"))
            return amount
        return Decimal("0.00")

    @property
    def grand_total(self):
        """Calculate the final total including discounts and tax."""
        return (self.total_before_tax + self.tax_amount).quantize(Decimal("0.01"))

    def __str__(self):
        num = self.invoice_number if self.invoice_number else "Draft"
        return f"Invoice {num} ({self.client.name})"
    
    
    class Meta:
        ordering = ['-issue_date', '-created_at']


class InvoiceItem(models.Model):
    """
    Represents a single line item on an Invoice.
    """
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name='invoice_items')
    description = models.TextField(blank=True, help_text="Defaults to menu item description, can be overridden.")
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit for *this* invoice line.")
    grouping_label = models.CharField(max_length=100, blank=True, default='')

    @property
    def line_total(self):
        """Calculate the total for this line item."""
        # Re-using the same logic as QuotationItem
        if self.quantity is not None and self.unit_price is not None:
            return (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        return Decimal("0.00")

    def __str__(self):
        # Need to handle case where invoice number might not be generated yet if accessed early
        inv_num = self.invoice.invoice_number if self.invoice_id and self.invoice.invoice_number else "Draft Invoice"
        return f"{self.quantity} x {self.menu_item.name} on {inv_num}"

    class Meta:
        ordering = ['id']


class Setting(SingletonModel):
    """
    Singleton model to store global application settings.
    Accessed via Setting.get_solo()
    """
    company_name = models.CharField(max_length=255, default="Your Company Name")
    address = models.TextField(blank=True, default='')
    email = models.EmailField(blank=True, default='')
    phone = models.CharField(max_length=50, blank=True, default='')
    tax_id = models.CharField(max_length=100, blank=True, default='', verbose_name="Company Tax ID")

    company_logo = models.ImageField(
        upload_to='company_logos/', # Store logos in 'media/company_logos/' subdirectory
        null=True,  # Allow the field to be empty in the database
        blank=True, # Allow the field to be empty in forms/admin
        help_text="Optional company logo."
    )

    # Financial Settings
    currency_symbol = models.CharField(max_length=5, default="RM")
    tax_enabled = models.BooleanField(default=False, verbose_name="Enable Tax/SST Calculation")
    tax_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("6.00"), # e.g., 6.00 for 6%
        verbose_name="Tax/SST Rate (%)",
        help_text="Enter the rate as a percentage, e.g., 6.00 for 6%"
    )

    # Document Defaults
    default_payment_details = models.TextField(blank=True, default='', help_text="Default payment info shown on invoices (e.g., Bank Details)")
    default_terms_conditions = models.TextField(blank=True, default='', help_text="Default terms shown on quotes/invoices")
    default_validity_days = models.PositiveIntegerField(
        default=15, # Default to 15 days
        help_text="Default number of days a quote/invoice is valid from the issue date."
    )

    # Timestamps (inherited from SingletonModel perhaps, but good to have explicitly?)
    # Singleton model doesn't have these by default, let's add them.
    created_at = models.DateTimeField(auto_now_add=True, null=True) # Allow null for initial singleton creation if needed
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return "Application Settings"

    class Meta:
        verbose_name = "Application Setting" # Singular name in admin
        # verbose_name_plural = "Application Settings" # Not really needed for singleton


class PaymentMethod(models.TextChoices):
    BANK_TRANSFER = 'BANK', 'Bank Transfer'
    CASH = 'CASH', 'Cash'
    CHEQUE = 'CHEQUE', 'Cheque'
    CREDIT_CARD = 'CARD', 'Credit Card'
    ONLINE = 'ONLINE', 'Online Payment Gateway'
    OTHER = 'OTHER', 'Other'


class Payment(models.Model):
    """
    Represents a payment received for an Invoice.
    """
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT, # Prevent deleting invoice if payments exist? Or CASCADE? Let's use PROTECT.
        related_name='payments'
    )
    payment_date = models.DateField(default=timezone.now)
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))] # Ensure positive amount
    )
    payment_method = models.CharField(
        max_length=10,
        choices=PaymentMethod.choices,
        blank=True, null=True # Make method optional for flexibility
    )
    reference_number = models.CharField(
        max_length=100, blank=True, default='',
        help_text="E.g., Transaction ID, Cheque No."
    )
    notes = models.TextField(blank=True, default='', help_text="Internal notes about the payment")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # Try to show invoice number, default to PK if number not generated yet (unlikely here)
        inv_num = self.invoice.invoice_number if self.invoice_id and self.invoice.invoice_number else f"Invoice PK {self.invoice_id}"
        # Format amount using settings currency eventually? For now, hardcode RM.
        try:
             # settings = Setting.get_solo() # Could fetch settings here if needed
             currency = "RM" # Hardcode for now
        except:
             currency = ""
        return f"Payment of {currency} {self.amount} for Invoice {inv_num} on {self.payment_date}"

    class Meta:
        ordering = ['-payment_date', '-created_at']