from django.db import models
from django.conf import settings # Needed for ForeignKey to User if we add created_by later
from django.utils import timezone # For default dates
from decimal import Decimal

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
    issue_date = models.DateField(default=timezone.now)
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

    terms_and_conditions = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='', help_text="Internal notes, not shown to client")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Quotation {self.quotation_number} ({self.client.name})"
    
    @property
    def total(self):
        """Calculate the total sum of all line item totals for this quotation."""
        # Use the related_name 'items' we defined in QuotationItem's ForeignKey
        # Sum the 'line_total' property of each item
        total_sum = sum(item.line_total for item in self.items.all())
        # Ensure it's a Decimal with 2 places
        return total_sum.quantize(Decimal("0.01"))

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

    # We will add logic later to auto-fill description/unit_price from menu_item
    # and a property/method to calculate line_total (quantity * unit_price)
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
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)

    terms_and_conditions = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='', help_text="Internal notes")
    payment_details = models.TextField(blank=True, default='', help_text="Info like bank account, payment terms")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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

# We will also need to add a property 'total' to the Invoice model later,
# similar to the Quotation model, to sum the InvoiceItem line totals.