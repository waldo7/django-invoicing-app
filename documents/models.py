from django.core.validators import MinValueValidator # To ensure amount is positive
from django.core.exceptions import ValidationError
from solo.models import SingletonModel
from django.utils import timezone # For default dates
from django.db import transaction
from django.db.models import Sum
from django.conf import settings # Needed for ForeignKey to User if we add created_by later
from django.urls import reverse
from datetime import timedelta # Needed for adding days to a date
from django.db import models
from django.apps import apps
from decimal import Decimal

# Create your models here.
class Client(models.Model):
    """Represents a client (customer)"""
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    tax_id = models.CharField(
        max_length=50,  # Adjust max_length as needed
        blank=True,     # Make it optional
        default='',
        verbose_name="Client Tax ID"
    )
    #Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_admin_url(self):
        """
        Returns the URL to the admin change page for this client instance.
        """
        return reverse('admin:documents_client_change', args=[self.pk])

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
    
    def get_admin_url(self):
        """
        Returns the URL to the admin change page for this quotation instance.
        """
        # Uses the standard admin URL naming convention: admin:<app_label>_<model_name>_change
        return reverse('admin:documents_quotation_change', args=[self.pk])
    
    @transaction.atomic
    def finalize(self):
        """
        Finalizes a DRAFT quotation:
        - Sets issue_date if not already set.
        - Calculates valid_until if not already set, based on issue_date and settings.
        - Changes status to SENT.
        Returns True if successful, False otherwise.
        """
        if self.status != self.Status.DRAFT:
            print(f"Warning: Quotation {self.quotation_number} is not a DRAFT. Cannot finalize.")
            return False

        # Set issue_date if it's not already set
        if not self.issue_date:
            self.issue_date = timezone.now().date()

        # Set valid_until if it's not already set AND issue_date is now available
        if not self.valid_until and self.issue_date:
            try:
                Setting = apps.get_model('documents', 'Setting')
                settings = Setting.get_solo()
                validity_days = getattr(settings, 'default_validity_days', 0)
                if validity_days > 0:
                    self.valid_until = self.issue_date + timedelta(days=validity_days)
            except Setting.DoesNotExist:
                # Settings not configured, proceed without default valid_until
                print("Warning: Settings object not found, cannot set default valid_until for Quotation.")
                pass

        self.status = self.Status.SENT
        # Define which fields to update
        fields_to_update = ['status']
        if self.issue_date: # Only add to update_fields if it was potentially changed
            fields_to_update.append('issue_date')
        if self.valid_until: # Only add to update_fields if it was potentially changed
            fields_to_update.append('valid_until')

        self.save(update_fields=fields_to_update)
        return True
    
    @transaction.atomic
    def revert_to_draft(self):
        """
        Reverts a 'Sent' Quotation back to 'Draft' status.
        - Clears issue_date and valid_until.
        - Changes status to DRAFT.
        Returns True if successful, False otherwise (e.g., if not in 'Sent' status).
        """
        # For now, let's only allow reverting from SENT.
        # We could expand this later to allow reverting from ACCEPTED/REJECTED
        # if the business logic requires it, but that might have other implications.
        if self.status != self.Status.SENT:
            print(f"Warning: Quotation {self.quotation_number} is not 'Sent'. Current status: {self.get_status_display()}. Cannot revert to draft.")
            return False

        self.status = self.Status.DRAFT
        self.issue_date = None
        self.valid_until = None

        # Define which fields to update
        fields_to_update = ['status', 'issue_date', 'valid_until']
        self.save(update_fields=fields_to_update)
        return True

    def __str__(self):
        return f"Quotation {self.quotation_number} ({self.client.name})"
    
    class Meta:
        ordering = ['-issue_date', '-created_at'] # Show newest quotes first by default

    @transaction.atomic # Ensure all operations succeed or fail together
    def create_revision(self):
        """
        Creates a new draft revision of the current quotation.
        - Copies fields and line items.
        - Increments version number.
        - Links new version back to this one.
        - Sets current quotation status to Superseded.
        Returns the new draft quotation instance.
        """
        # Optional: Prevent revising already superseded or draft quotes?
        if self.status == self.Status.SUPERSEDED:
            # Or raise an exception
            print(f"Warning: Quotation {self.quotation_number} is already superseded.")
            return None
        if self.status == self.Status.DRAFT:
            print(f"Warning: Cannot revise a draft quotation {self.quotation_number}.")
            return None # Or maybe just return self?

        # Get related items before changing self
        original_items = list(self.items.all()) # Evaluate queryset now

        # Create a new instance (don't save yet)
        # Exclude fields that should not be copied directly
        excluded_fields = {'id', 'pk', '_state', 'quotation_number', 'status', 'version', 'previous_version', 'created_at', 'updated_at'}
        new_quote_data = {}
        for field in self._meta.get_fields():
            if field.name not in excluded_fields and hasattr(self, field.name):
                # Handle ManyToMany later if needed
                if not field.one_to_many and not field.many_to_many:
                     new_quote_data[field.name] = getattr(self, field.name)

        # Set new version details
        new_quote_data['version'] = self.version + 1
        new_quote_data['status'] = self.Status.DRAFT
        new_quote_data['previous_version'] = self
        new_quote_data['issue_date'] = None # Drafts don't have issue date yet
        new_quote_data['valid_until'] = None

        # Create the new quote header (will trigger auto-numbering via signals)
        new_quote = Quotation.objects.create(**new_quote_data)

        # Copy line items
        new_items = []
        for item in original_items:
            new_items.append(QuotationItem(
                quotation=new_quote, # Link to the new quote
                menu_item=item.menu_item,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price, # Copy the exact price from old quote
                grouping_label=item.grouping_label
            ))

        # Use bulk_create for efficiency if there can be many items
        if new_items:
            QuotationItem.objects.bulk_create(new_items)

        # Update status of the original quote
        self.status = self.Status.SUPERSEDED
        self.save(update_fields=['status']) # Only save the status field

        return new_quote

    
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


class Order(models.Model):
    """
    Represents a confirmed order or event booking, potentially linked from a Quotation.
    Acts as the source for generating Invoices and Delivery Orders.
    """

    class OrderStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending Confirmation' # Maybe if created directly
        CONFIRMED = 'CONFIRMED', 'Confirmed'       # Likely status after quote accepted or direct order
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'   # Event happening
        COMPLETED = 'COMPLETED', 'Completed'         # Event finished
        CANCELLED = 'CANCELLED', 'Cancelled'         # Order cancelled   

    order_number = models.CharField(
        max_length=50, unique=True,
        blank=True, null=True, # For auto-generation later
        editable=False
    )
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name='orders')
    # Link back to the source quotation if applicable
    related_quotation = models.ForeignKey(
        Quotation,
        on_delete=models.SET_NULL, # Keep order even if original quote is deleted
        null=True, blank=True,
        related_name='orders'
    )
    title = models.CharField(max_length=255, blank=True, default='', help_text="e.g., Wedding Catering June 15th")
    status = models.CharField(max_length=15, choices=OrderStatus.choices, default=OrderStatus.CONFIRMED)
    event_date = models.DateField(null=True, blank=True, help_text="Primary date of the event/order")
    # Add more dates later if needed e.g., event_start_datetime, event_end_datetime

    # Delivery/Venue address might differ from client's main address
    delivery_address = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='', help_text="Internal notes about the order/event")

    # --- Add Discount Fields ---
    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices, # Reuse choices defined earlier
        default=DiscountType.NONE
    )
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00"),
        help_text="Enter percentage (e.g., 10.00 for 10%) or fixed amount for overall order discount."
    )

    @property
    def subtotal(self):
        """Calculate sum of all line item totals before discounts/taxes."""
        # Use the related_name 'items' from OrderItem's ForeignKey
        return sum((item.line_total for item in self.items.all()), Decimal('0.00')).quantize(Decimal("0.01"))

    @property
    def discount_amount(self):
        """Calculate the discount amount based on type and value."""
        # Reuse the logic from Quote/Invoice
        if self.discount_type == DiscountType.NONE or self.discount_value <= 0:
            return Decimal("0.00")

        sub = self.subtotal # Use the subtotal property we just defined
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
        # Use dynamic model loading for Setting
        Setting = apps.get_model('documents', 'Setting')
        try:
            settings = Setting.get_solo()
            if settings.tax_enabled and settings.tax_rate > 0:
                tax_rate = settings.tax_rate / Decimal(100)
                amount = (self.total_before_tax * tax_rate).quantize(Decimal("0.01"))
                return amount
        except Setting.DoesNotExist:
            pass # Settings not created yet
        return Decimal("0.00")

    @property
    def grand_total(self):
        """Calculate the final total including discounts and tax."""
        return (self.total_before_tax + self.tax_amount).quantize(Decimal("0.01"))

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        num = self.order_number if self.order_number else "Draft Order"
        return f"Order {num} ({self.client.name})"

    class Meta:
        ordering = ['-event_date', '-created_at']

    @transaction.atomic
    def create_invoice(self):
        """
        Creates a new draft Invoice based on this Order.
        Copies details and all line items.
        Returns the newly created Invoice instance or None if creation is not allowed.
        """
        # Get related models safely
        Invoice = apps.get_model('documents', 'Invoice')
        InvoiceItem = apps.get_model('documents', 'InvoiceItem')
        OrderStatus = self.__class__.OrderStatus

        # Prevent creating invoice from Pending or Cancelled orders
        if self.status in [OrderStatus.PENDING, OrderStatus.CANCELLED]:
            print(f"Warning: Cannot create invoice for Order {self.order_number} with status {self.status}.")
            return None

        # Check if an invoice already exists for this order?
        # For now, allow multiple invoices from one order to support partial billing later.
        # We might add logic here later if needed.

        # Prepare data for the new Invoice
        # Fields to copy directly from Order: client, title, discount_type, discount_value, related_quotation
        # Fields to potentially copy later if added to Order: terms_and_conditions, payment_details
        invoice_data = {
            'client': self.client,
            'related_order': self, # Link back to this order
            'related_quotation': self.related_quotation, # Carry over link from order
            'title': self.title or f"Invoice for Order {self.order_number or self.pk}",
            'status': Invoice.Status.DRAFT, # New invoices start as Draft
            'discount_type': self.discount_type,
            'discount_value': self.discount_value,
            'issue_date': None, # To be set when sent
            'due_date': None,   # To be set when sent/based on issue_date
            # Copy other fields if they exist on both models
            'terms_and_conditions': getattr(self, 'terms_and_conditions', ''),
            'payment_details': getattr(self, 'payment_details', ''),
            'notes': getattr(self, 'notes', ''), # Copy internal notes? Maybe not? Let's copy for now.
        }

        # Create the main Invoice record (triggers auto-numbering)
        new_invoice = Invoice.objects.create(**invoice_data)

        # Copy line items from OrderItem to InvoiceItem
        new_invoice_items = []
        for order_item in self.items.all():
            new_invoice_items.append(InvoiceItem(
                invoice=new_invoice,
                menu_item=order_item.menu_item,
                description=order_item.description, # Copy specific description
                quantity=order_item.quantity,
                unit_price=order_item.unit_price, # Copy specific agreed price
                grouping_label=order_item.grouping_label
            ))

        if new_invoice_items:
            InvoiceItem.objects.bulk_create(new_invoice_items)

        return new_invoice
    
    def get_admin_url(self):
        """
        Returns the URL to the admin change page for this order instance.
        """
        return reverse('admin:documents_order_change', args=[self.pk])

    def clean(self):
        """
        Add validation rules for the Order.
        - Ensure client matches related_quotation.client if quote is linked.
        """
        super().clean() # Call parent's clean method

        # Check client consistency if a related quotation is selected
        if self.related_quotation_id and self.client_id: # Check if both are set
            # Avoid fetching full objects if possible, compare IDs
            # Or fetch the quote client ID if needed
            try:
                # Fetch the client ID directly associated with the related quotation
                quote_client_id = Quotation.objects.values_list('client_id', flat=True).get(pk=self.related_quotation_id)
                if self.client_id != quote_client_id:
                    raise ValidationError({
                        'client': 'Client does not match the client on the selected Quotation.',
                        'related_quotation': 'Client on this Quotation does not match the Order client.'
                    })
            except Quotation.DoesNotExist:
                # This shouldn't happen due to FK constraints but handle defensively
                raise ValidationError("Related quotation not found.")


class OrderItem(models.Model):
    """
    Represents a single line item confirmed for an Order/Event.
    These details are typically locked in from the accepted Quotation or final agreement.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name='order_items')
    description = models.TextField(blank=True, help_text="Specific details for this item on this order.")
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, help_text="Price per unit agreed for this order.")
    grouping_label = models.CharField(max_length=100, blank=True, default='', help_text="Optional label (e.g., 'Day 1 - Lunch')")

    # We will add properties like line_total later

    def __str__(self):
        order_num = self.order.order_number if self.order_id and self.order.order_number else f"Order PK {self.order_id}"
        # Add "Order " before {order_num}
        return f"{self.quantity} x {self.menu_item.name} on Order {order_num}"
    
    @property
    def line_total(self):
        """Calculate the total for this line item."""
        # Same logic as QuotationItem/InvoiceItem
        if self.quantity is not None and self.unit_price is not None:
            return (self.quantity * self.unit_price).quantize(Decimal("0.01"))
        return Decimal("0.00")

    class Meta:
        ordering = ['id'] # Order items by creation order within an order


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
        related_name='invoices_from_quote'
    )
    
    related_order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL, # Keep invoice even if order is deleted? Or PROTECT? Let's use SET_NULL.
        null=True, blank=True,
        related_name='invoices' # An order can have multiple invoices (for partial billing later)
    )

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
    
    def get_admin_url(self):
        """
        Returns the URL to the admin change page for this invoice instance.
        """
        return reverse('admin:documents_invoice_change', args=[self.pk])

    def __str__(self):
        num = self.invoice_number if self.invoice_number else "Draft"
        return f"Invoice {num} ({self.client.name})"
    
    
    @property
    def amount_paid(self):
        """Calculate the total amount paid towards this invoice."""
        # Sum the 'amount' field of all related Payment objects
        # Use aggregate and handle None if no payments exist
        paid_sum = self.payments.aggregate(total_paid=Sum('amount'))['total_paid']
        return (paid_sum or Decimal('0.00')).quantize(Decimal("0.01"))

    @property
    def balance_due(self):
        """Calculate the remaining balance due for this invoice."""
        # Use grand_total property we defined earlier
        balance = self.grand_total - self.amount_paid
        return balance.quantize(Decimal("0.01"))

    @transaction.atomic
    def finalize(self):
        """
        Finalizes a DRAFT invoice:
        - Sets issue_date if not already set.
        - Calculates due_date if not already set, based on issue_date and settings.
        - Changes status to SENT.
        Returns True if successful, False otherwise.
        """
        if self.status != self.Status.DRAFT:
            print(f"Warning: Invoice {self.invoice_number} is not a DRAFT. Cannot finalize.")
            return False

        # Set issue_date if it's not already set
        if not self.issue_date:
            self.issue_date = timezone.now().date()

        # Set due_date if it's not already set AND issue_date is now available
        if not self.due_date and self.issue_date:
            try:
                Setting = apps.get_model('documents', 'Setting')
                settings = Setting.get_solo()
                # Use the new setting for payment terms
                payment_terms_days = getattr(settings, 'default_payment_terms_days', 0)
                if payment_terms_days > 0:
                    self.due_date = self.issue_date + timedelta(days=payment_terms_days)
            except Setting.DoesNotExist:
                print("Warning: Settings object not found, cannot set default due_date for Invoice.")
                pass # Proceed without default due_date

        self.status = self.Status.SENT
        # Define which fields to update
        fields_to_update = ['status']
        if self.issue_date: # Only add to update_fields if it was potentially changed/set
            fields_to_update.append('issue_date')
        if self.due_date:   # Only add to update_fields if it was potentially changed/set
            fields_to_update.append('due_date')

        self.save(update_fields=fields_to_update)
        return True
    
    @transaction.atomic
    def revert_to_draft(self):
        """
        Reverts a 'Sent' Invoice back to 'Draft' status.
        - Clears issue_date and due_date.
        - Changes status to DRAFT.
        Returns True if successful, False otherwise (e.g., if not in 'Sent' status).
        """
        # Only allow reverting from SENT. Reverting PAID or PARTIALLY_PAID
        # would have implications for recorded payments and should likely
        # be handled by credit notes or other accounting adjustments.
        if self.status != self.Status.SENT:
            print(f"Warning: Invoice {self.invoice_number} is not 'Sent'. Current status: {self.get_status_display()}. Cannot revert to draft.")
            return False

        self.status = self.Status.DRAFT
        self.issue_date = None
        self.due_date = None

        # Define which fields to update
        fields_to_update = ['status', 'issue_date', 'due_date']
        self.save(update_fields=fields_to_update)
        return True
    
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

    default_payment_terms_days = models.PositiveIntegerField(
        default=30, # Default to 30 days for invoice payment
        help_text="Default number of days until an invoice payment is due from the issue date."
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

    def clean(self):
        """
        Add validation to prevent payments against Draft or Cancelled invoices.
        """
        super().clean() # Call parent's clean method first

        # Check if invoice is linked and has a status that shouldn't allow payments
        if self.invoice_id: # Check if invoice is linked (self.invoice might not be loaded yet)
            InvoiceStatus = apps.get_model('documents', 'Invoice').Status # Get status choices safely
            # Fetch the invoice's current status
            try:
                # Fetch status directly to avoid loading the whole invoice object if not needed
                invoice_status = Invoice.objects.values_list('status', flat=True).get(pk=self.invoice_id)
                if invoice_status in [InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]:
                    raise ValidationError(
                        f"Payments cannot be recorded for Invoices with status: {invoice_status}."
                    )
            except Invoice.DoesNotExist:
                # Should not happen if FK constraint is working, but good practice
                raise ValidationError("Cannot find the associated Invoice.")
            

class DeliveryOrderStatus(models.TextChoices):
    PLANNED = 'PLANNED', 'Planned'
    DISPATCHED = 'DISPATCHED', 'Dispatched'
    DELIVERED = 'DELIVERED', 'Delivered'
    CANCELLED = 'CANCELLED', 'Cancelled'


class DeliveryOrder(models.Model):
    """
    Represents a delivery of items for a specific Order.
    An Order can have multiple DeliveryOrders (e.g., for phased delivery).
    """
    do_number = models.CharField(
        max_length=50, unique=True,
        blank=True, null=True, # For auto-generation later
        editable=False
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE, # If Order is deleted, DOs are deleted
        related_name='delivery_orders'
    )
    delivery_date = models.DateField(help_text="Date of scheduled/actual delivery")
    status = models.CharField(
        max_length=15,
        choices=DeliveryOrderStatus.choices,
        default=DeliveryOrderStatus.PLANNED
    )
    recipient_name = models.CharField(max_length=200, blank=True, default='', help_text="Name of person receiving the delivery, if different from client contact.")
    # Delivery address can default from Order.delivery_address but be overrideable.
    # For now, we'll just store it. Logic for defaulting can be added in forms/views.
    delivery_address_override = models.TextField(blank=True, default='', help_text="Specific delivery address for this DO, if different from Order's address.")
    notes = models.TextField(blank=True, default='', help_text="Internal notes or instructions for this delivery.")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        num = self.do_number if self.do_number else "Draft DO"
        return f"Delivery Order {num} for Order {self.order.order_number or self.order.pk}"

    class Meta:
        ordering = ['-delivery_date', '-created_at']
        verbose_name = "Delivery Order"
        verbose_name_plural = "Delivery Orders"


class DeliveryOrderItem(models.Model):
    """
    Represents a specific item and quantity being delivered in a DeliveryOrder.
    Links back to an OrderItem to track against the original order.
    """
    delivery_order = models.ForeignKey(
        DeliveryOrder,
        on_delete=models.CASCADE,
        related_name='items'
    )
    # Crucial link: Which item from the main Order is this delivery for?
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.PROTECT, # Don't delete an OrderItem if it's on a DO
        related_name='delivered_items'
    )
    # Quantity being delivered *in this specific DO*
    quantity_delivered = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))] # Must deliver a positive quantity
    )
    notes = models.TextField(blank=True, default='', help_text="Notes specific to this delivered item (e.g., substitution).")

    # No unit_price or description here, as those are fixed on the OrderItem.
    # The DO is just about quantity delivered.

    def __str__(self):
        do_num = self.delivery_order.do_number if self.delivery_order_id and self.delivery_order.do_number else f"DO PK {self.delivery_order_id}"
        return f"{self.quantity_delivered} x {self.order_item.menu_item.name} on {do_num}"

    class Meta:
        ordering = ['id']
        verbose_name = "Delivery Order Item"
        verbose_name_plural = "Delivery Order Items"

    # Potential future validation in clean():
    # Ensure quantity_delivered <= order_item.quantity - sum(other delivered_items for this order_item)


    def clean(self):
        """
        Custom validation for DeliveryOrderItem:
        1. Ensure the selected OrderItem belongs to the DeliveryOrder's parent Order.
        2. Ensure quantity_delivered does not exceed the OrderItem's original quantity.
           (Note: This simple check doesn't account for previous deliveries of the same OrderItem yet.
            That's a more complex validation we can add later if needed for partial deliveries on multiple DOs.)
        """
        super().clean() # Call parent's clean method first

        # Validation 1: Check if order_item belongs to the correct parent Order
        # We check for existence of both delivery_order and order_item first,
        # as this method can be called before they are fully assigned (e.g., in forms).
        if hasattr(self, 'delivery_order') and self.delivery_order and \
           hasattr(self, 'order_item') and self.order_item:

            # Ensure both related objects are fully loaded if they are just IDs
            # This can happen if the instance is not fully saved or is being constructed
            # For robustness, it's better to compare IDs if possible or ensure instances are loaded
            # Let's assume delivery_order and order_item are instances or will be when clean is called by a form

            if self.delivery_order.order_id != self.order_item.order_id:
                raise ValidationError({
                    'order_item': f"This item does not belong to the parent Order ({self.delivery_order.order}). "
                                  f"It belongs to Order {self.order_item.order}."
                })

            # Validation 2: Check quantity_delivered against order_item.quantity
            # This is a simple check for now. A more advanced check would sum up
            # all existing delivery_order_items for this order_item.
            if self.quantity_delivered is not None and self.order_item.quantity is not None:
                if self.quantity_delivered > self.order_item.quantity:
                    raise ValidationError({
                        'quantity_delivered': f"Cannot deliver more than ordered. "
                                              f"Ordered: {self.order_item.quantity}, "
                                              f"Attempting to deliver: {self.quantity_delivered}."
                    })
        # Handle cases where fields might not be set yet (e.g. before first save in some scenarios)
        elif not hasattr(self, 'delivery_order') or not self.delivery_order:
             pass # Cannot validate if delivery_order is not set
        elif not hasattr(self, 'order_item') or not self.order_item:
             pass # Cannot validate if order_item is not set



