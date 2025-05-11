from django.utils.html import format_html, mark_safe
from solo.admin import SingletonModelAdmin # Import SoloAdmin
from django.contrib import admin
from django.urls import reverse

# Register your models here.
from .models import (
    Client, MenuItem, Quotation, QuotationItem, Invoice, InvoiceItem, 
    Setting, Payment, Order, OrderItem, 
    DeliveryOrder, DeliveryOrderItem, DeliveryOrderStatus
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Configuration for the Client model in the Django admin interface"""
    list_display = ("name", "email", "phone", "created_at")
    search_fields = ("name", "email")
    list_filter = ("created_at",)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    """
    Configuration for the MenuItem model in the Django admin interface.
    """
    list_display = ('name', 'unit_price', 'unit', 'is_active', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'description', 'unit')
    list_editable = ('unit_price', 'unit', 'is_active') # Allows editing these directly in the list view


class QuotationItemInline(admin.TabularInline): # Or use admin.StackedInline for a different layout
    """
    Allows editing QuotationItems directly within the Quotation admin page.
    """
    model = QuotationItem
    extra = 1 # Number of empty item forms to show by default
    # We can add fields later to customize the inline form, e.g., readonly_fields
    readonly_fields = ('line_total',) # Display calculated total as read-only

    def line_total(self, obj):
        return obj.line_total 


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    """
    Configuration for the Quotation model in the Django admin interface.
    """
    list_display = ('quotation_number', 'client', 'title', 'status', 'version', 'issue_date', 'valid_until', 'display_total') # Removed placeholder 'total_amount' for now
    list_filter = ('status', 'client', 'issue_date', 'created_at')
    search_fields = ('quotation_number', 'client__name', 'title', 'items__menu_item__name')
    # Make auto-generated/timestamp fields read-only
    readonly_fields = (
        'quotation_number', 'version', 'created_at', 'updated_at', ''
        'previous_version', 
        'finalize_quotation_link',
        'revert_to_draft_link',
        'revise_quotation_link', 
        'preview_draft_pdf_link', 
        'view_final_pdf_link'
        )
    fieldsets = (
        # Section 1: Core Info (No quotation_number here - it's read-only)
        (None, {
            'fields': ('client', 'title', 'status')
        }),
        ('Actions', {'fields': (
            'finalize_quotation_link',
            'revert_to_draft_link',
            'revise_quotation_link', 
            'preview_draft_pdf_link', 
            'view_final_pdf_link',
            )}),
        # Section 2: Dates
        ('Dates', {
            'fields': ('issue_date', 'valid_until')
        }),
        # --- Add Discount Section ---
        ('Discount', {'fields': ('discount_type', 'discount_value')}),
        # Section 3: Versioning Info
        ('Versioning', {
            # Show read-only fields here if desired, or omit them from fieldsets
            'fields': ('version', 'previous_version') # previous_version is read-only
        }),
        # Section 4: Document Content
        ('Content', {
            'fields': ('terms_and_conditions', 'notes')
        }),
        # Section 5: Timestamps (Collapsible)
        ('Timestamps & Auto-Number', {
            'fields': ('quotation_number','created_at', 'updated_at'), # Show read-only number here
            'classes': ('collapse',)
        }),
    )

    # Embed the item editor within the quote page
    inlines = [QuotationItemInline]

    def display_total(self, obj):
         # Call the 'total' property from the Quotation model
         # Format it nicely for display (optional, but good)
         if not obj.pk: return "-"
         try:
             # Format as currency, you might need locale settings or a formatting library later
             return f"RM {obj.grand_total:,.2f}"
         except Exception:
             return "Error" # Handle potential calculation errors gracefully
    display_total.short_description = 'Total Amount' # Column header

    def finalize_quotation_link(self, obj):
        """Generate a 'Finalize' button link if status is Draft."""
        if obj.pk and obj.status == Quotation.Status.DRAFT:
            url = reverse('documents:quotation_finalize', args=[obj.pk])
            return format_html('<a href="{}" class="button">Finalize Quotation</a>', url)
        return mark_safe("<em>(Only Draft quotations can be finalized)</em>")
    finalize_quotation_link.short_description = 'Finalize Action'

    def revert_to_draft_link(self, obj):
        """Generate a 'Revert to Draft' button if status is Sent."""
        if obj.pk and obj.status == Quotation.Status.SENT:
            url = reverse('documents:quotation_revert_to_draft', args=[obj.pk])
            return format_html('<a href="{}" class="button">Revert to Draft</a>', url)
        return mark_safe("<em>(Only Sent quotations can be reverted to draft)</em>")
    revert_to_draft_link.short_description = 'Revert Action'

    def revise_quotation_link(self, obj):
        """
        Generate a 'Revise' button link for the admin change page.
        Only show if the quotation exists and is in a state that can be revised (e.g., Sent, Accepted).
        """
        allowed_statuses = [
            Quotation.Status.SENT, Quotation.Status.ACCEPTED, Quotation.Status.REJECTED
        ]

        # Check if the object has been saved (has a PK) and its status allows revision
        if obj.pk and obj.status in allowed_statuses:
             # Generate the URL for our revise_quotation view using its name
             # Ensure 'documents' namespace is used if defined in core.urls include()
             url = reverse('documents:quotation_revise', args=[obj.pk])
             # Return HTML for a button-like link using admin styles
             return format_html('<a href="{}" class="button">Revise this Quotation</a>', url)
        # Return empty string or info message if revision isn't allowed
        return mark_safe("<em>(Cannot revise if Draft or Superseded)</em>") # Import mark_safe if needed
    revise_quotation_link.short_description = 'Revise' # Label for the fieldset section
    # revise_quotation_link.allow_tags = True # Deprecated in newer Django, format_html handles safety

    def preview_draft_pdf_link(self, obj):
        if obj.pk and obj.status == Quotation.Status.DRAFT:
            url = reverse('documents:quotation_pdf', args=[obj.pk])
            return format_html('<a href="{}" class="button" target="_blank">Preview Draft PDF</a>', url)
        return "-" # Show dash if not applicable
    preview_draft_pdf_link.short_description = 'Draft PDF'

    def view_final_pdf_link(self, obj):
        # Define statuses for which a "final" PDF makes sense
        final_statuses = [
            Quotation.Status.SENT,
            Quotation.Status.ACCEPTED,
            Quotation.Status.REJECTED,
            Quotation.Status.SUPERSEDED,
            # Exclude DRAFT
        ]
        if obj.pk and obj.status in final_statuses:
            url = reverse('documents:quotation_pdf', args=[obj.pk])
            return format_html('<a href="{}" class="button" target="_blank">View Final PDF</a>', url)
        return "-" # Show dash if not applicable
    view_final_pdf_link.short_description = 'Final PDF'

    class Media:
        # List of JS files to include on the admin change/add pages
        # Path is relative to your STATIC files setup
        js = ('documents/js/admin_inline_autofill.js',) # Note the comma to make it a tuple


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1 # Show one blank row for adding items
    readonly_fields = ('line_total',) # Display calculated line total

    # Helper to display the property in readonly_fields
    def line_total(self, obj):
        return obj.line_total
    line_total.short_description = 'Line Total' # Column header


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'client', 'status', 'issue_date', 'due_date', 'display_grand_total', 'display_balance_due')
    list_filter = ('status', 'client', 'issue_date')
    search_fields = ('invoice_number', 'client__name', 'items__menu_item__name')
    # Make auto-generated fields read-only
    readonly_fields = (
        'invoice_number', 'created_at', 'updated_at', 
        'display_amount_paid', 'display_balance_due', 'display_grand_total_detail',
        'related_order',
        'finalize_invoice_link',
        'revert_to_draft_link',
        'preview_draft_pdf_link', 
        'view_final_pdf_link',
        )
    fieldsets = (
        # Group fields logically in the edit view
        (None, {'fields': ('client', 'related_quotation', 'related_order', 'title', 'status')}),
        ('Actions', {'fields': (
            'finalize_invoice_link', 
            'revert_to_draft_link',
            'preview_draft_pdf_link', 
            'view_final_pdf_link',
            )}),
        ('Dates', {'fields': ('issue_date', 'due_date')}),
        ('Payment Status', {'fields': ('display_grand_total_detail', 'display_amount_paid', 'display_balance_due')}),
        # --- Add Discount Section ---
        ('Discount', {'fields': ('discount_type', 'discount_value')}),
        ('Content', {'fields': ('terms_and_conditions', 'payment_details', 'notes')}),
        # Show read-only auto-generated fields in a collapsible section
        ('System Info', {
            'fields': ('invoice_number', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    # Embed the InvoiceItem editor
    inlines = [InvoiceItemInline]

    
    def display_grand_total(self, obj): # Renamed for list view
         """Formats grand_total for list display."""
         if not obj.pk: return "-"
         try: return f"RM {obj.grand_total:,.2f}"
         except Exception: return "Error"
    display_grand_total.short_description = 'Total Amount'

    # Need separate methods for readonly_fields as they often don't directly accept properties
    def display_grand_total_detail(self, obj):
         """Formats grand_total for detail view (readonly_fields)."""
         if not obj.pk: return "-"
         try: return f"RM {obj.grand_total:,.2f}"
         except Exception: return "Error"
    display_grand_total_detail.short_description = 'Grand Total' # Header in fieldset

    def display_amount_paid(self, obj):
         """Formats amount_paid for detail view."""
         if not obj.pk: return "-"
         try: return f"RM {obj.amount_paid:,.2f}"
         except Exception: return "Error"
    display_amount_paid.short_description = 'Amount Paid'

    def display_balance_due(self, obj):
         """Formats balance_due for list and detail view."""
         if not obj.pk: return "-"
         try: return f"RM {obj.balance_due:,.2f}"
         except Exception: return "Error"
    display_balance_due.short_description = 'Balance Due'

    def finalize_invoice_link(self, obj):
        """Generate a 'Finalize' button link if status is Draft."""
        if obj.pk and obj.status == Invoice.Status.DRAFT:
            url = reverse('documents:invoice_finalize', args=[obj.pk])
            return format_html('<a href="{}" class="button">Finalize Invoice</a>', url)
        return mark_safe("<em>(Only Draft invoices can be finalized)</em>")
    finalize_invoice_link.short_description = 'Finalize Action'

    def revert_to_draft_link(self, obj):
        """Generate a 'Revert to Draft' button if status is Sent."""
        if obj.pk and obj.status == Invoice.Status.SENT: # Only from SENT for now
            url = reverse('documents:invoice_revert_to_draft', args=[obj.pk])
            return format_html('<a href="{}" class="button">Revert to Draft</a>', url)
        return mark_safe("<em>(Only Sent invoices can be reverted to draft)</em>")
    revert_to_draft_link.short_description = 'Revert Action'

    def preview_draft_pdf_link(self, obj):
        if obj.pk and obj.status == Invoice.Status.DRAFT:
            url = reverse('documents:invoice_pdf', args=[obj.pk])
            return format_html('<a href="{}" class="button" target="_blank">Preview Draft PDF</a>', url)
        return "-"
    preview_draft_pdf_link.short_description = 'Draft PDF'

    def view_final_pdf_link(self, obj):
        # Define statuses for which a "final" PDF makes sense
        final_statuses = [
            Invoice.Status.SENT.value,
            Invoice.Status.PAID.value,
            Invoice.Status.PARTIALLY_PAID.value,
            # Exclude DRAFT, CANCELLED
        ]
        if obj.pk and obj.status in final_statuses:
            url = reverse('documents:invoice_pdf', args=[obj.pk])
            return format_html('<a href="{}" class="button" target="_blank">View Final PDF</a>', url)
        return "-"
    view_final_pdf_link.short_description = 'Final PDF'

    class Media:
        js = ('documents/js/admin_inline_autofill.js',) # Same JS file needed here too


@admin.register(Setting)
class SettingAdmin(SingletonModelAdmin):
    """Admin interface for the singleton Settings model."""
    # Optionally define fieldsets to organize the settings page
    fieldsets = (
        ('Company Information', {'fields': ('company_name', 'address', 'email', 'phone', 'tax_id', 'company_logo', 'logo_preview')}),
        ('Financial Settings', {'fields': ('currency_symbol', 'tax_enabled', 'tax_rate')}),
        ('Document Defaults', {'fields': (
            'default_payment_details', 
            'default_terms_conditions',
            'default_validity_days',
            'default_payment_terms_days',
            )}),
    )

    # Make the preview read-only
    readonly_fields = ('logo_preview',)

    def logo_preview(self, obj):
        if obj.company_logo:
            # Render an img tag - careful with large images in admin!
            return format_html('<img src="{}" style="max-height: 100px; max-width: 200px;" />', obj.company_logo.url)
        return mark_safe("<em>No logo uploaded.</em>")
    logo_preview.short_description = 'Logo Preview'
    # No list_display needed for SingletonAdmin


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for the Payment model."""
    list_display = ('get_invoice_number', 'payment_date', 'amount_display', 'payment_method', 'reference_number', 'created_at')
    list_filter = ('payment_date', 'payment_method', 'invoice__client')
    search_fields = ('invoice__invoice_number', 'invoice__client__name', 'reference_number', 'notes')
    list_select_related = ('invoice', 'invoice__client') # Performance optimization
    date_hierarchy = 'payment_date' # Adds date navigation
    readonly_fields = ('created_at', 'updated_at') # Timestamps shouldn't be editable
    list_per_page = 25 # Show more items per page if desired

    # Use methods to display related fields nicely and format currency
    def get_invoice_number(self, obj):
        if obj.invoice:
            # Optional: Link to the invoice change page
            # from django.urls import reverse
            # from django.utils.html import format_html
            # url = reverse('admin:documents_invoice_change', args=[obj.invoice.pk])
            # return format_html('<a href="{}">{}</a>', url, obj.invoice.invoice_number or f"Invoice PK {obj.invoice.pk}")
            return obj.invoice.invoice_number or f"Invoice PK {obj.invoice.pk}"
        return None
    get_invoice_number.short_description = 'Invoice' # Column header
    get_invoice_number.admin_order_field = 'invoice__invoice_number' # Allow sorting by invoice number

    def amount_display(self, obj):
        # Format amount with currency (assuming RM for now)
         try:
             # settings = Setting.get_solo() # Could fetch currency from settings later
             currency = "RM"
             return f"{currency} {obj.amount:,.2f}"
         except Exception:
             return obj.amount # Fallback
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount' # Allow sorting by amount

    # Customize the form fields layout if needed
    # fieldsets = ( ... )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1 # Show one empty row for adding items
    # Add readonly_fields for calculated properties later if needed (e.g., line_total)
    readonly_fields = ('line_total',)
    
    # Helper to display the property
    def line_total(self, obj):
        # Access the property we just added to the model
        return obj.line_total
    line_total.short_description = 'Line Total' # Column header


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'client', 'title', 'status', 'event_date', 'display_grand_total', 'created_at') # Added total display
    list_filter = ('status', 'client', 'event_date')
    search_fields = ('order_number', 'client__name', 'title', 'items__menu_item__name')
    list_select_related = ('client',)
    date_hierarchy = 'event_date'
    # Add display method names to readonly_fields
    readonly_fields = (
        'order_number', 'created_at', 'updated_at',
        'display_subtotal', 'display_discount_amount', 'display_tax_amount', 'display_grand_total_detail',
        'create_invoice_link',
        'view_pdf_link'
    )
    fieldsets = (
        (None, {'fields': ('client', 'related_quotation', 'title', 'status')}),
        ('Actions', {'fields': ('create_invoice_link', 'view_pdf_link',)}),
        ('Event Details', {'fields': ('event_date', 'delivery_address')}),
        ('Discount', {'fields': ('discount_type', 'discount_value')}),
        # --- Add Financial Summary section ---
        ('Financial Summary', {'fields': (
            'display_subtotal',
            'display_discount_amount',
            'display_tax_amount',
            'display_grand_total_detail'
        )}),
        ('Notes', {'fields': ('notes',)}),
        ('System Info', {
            'fields': ('order_number', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    inlines = [OrderItemInline]

    def display_grand_total(self, obj):
         """Formats grand_total for list display."""
         if not obj.pk: return "-"
         try: return f"RM {obj.grand_total:,.2f}"
         except Exception: return "Error"
    display_grand_total.short_description = 'Total Amount' # Header for list view

    def display_grand_total_detail(self, obj):
         """Formats grand_total for detail view."""
         if not obj.pk: return "-"
         try: return f"RM {obj.grand_total:,.2f}"
         except Exception: return "Error"
    display_grand_total_detail.short_description = 'Grand Total (Calc.)' # Header for detail view

    def display_subtotal(self, obj):
         """Formats subtotal for detail view."""
         if not obj.pk: return "-"
         try: return f"RM {obj.subtotal:,.2f}"
         except Exception: return "Error"
    display_subtotal.short_description = 'Subtotal (Calc.)'

    def display_discount_amount(self, obj):
         """Formats discount_amount for detail view."""
         if not obj.pk: return "-"
         try: return f"RM {obj.discount_amount:,.2f}"
         except Exception: return "Error"
    display_discount_amount.short_description = 'Discount Amount (Calc.)'

    def display_tax_amount(self, obj):
         """Formats tax_amount for detail view."""
         if not obj.pk: return "-"
         try: return f"RM {obj.tax_amount:,.2f}"
         except Exception: return "Error"
    display_tax_amount.short_description = 'Tax Amount (Calc.)'

    def create_invoice_link(self, obj):
        """
        Generate a 'Create Invoice' button link for the admin change page.
        Only show if the order exists, is in an appropriate status,
        AND if no invoices exist for it yet.
        """
        allowed_statuses = [Order.OrderStatus.CONFIRMED, Order.OrderStatus.IN_PROGRESS, Order.OrderStatus.COMPLETED]
        # --- Add check for existing invoices ---
        can_create_first_invoice = not obj.invoices.exists()
        # --- End Add check ---

        # Modify the condition to include the new check
        if obj.pk and obj.status in allowed_statuses and can_create_first_invoice:
            url = reverse('documents:order_create_invoice', args=[obj.pk])
            # Optional: Rename button text -> "Create Initial Full Invoice"?
            return format_html('<a href="{}" class="button">Create Invoice from this Order</a>', url)
        # --- Add this elif block ---
        elif obj.invoices.exists():
             # Show message if invoices already exist
             return mark_safe("<em>(Invoice(s) already exist for this Order. Create new invoices manually.)</em>")
        # --- End Add elif ---
        else: # Original status check failure
            return mark_safe(f"<em>(Cannot create invoice for status: {obj.get_status_display()})</em>")
    create_invoice_link.short_description = 'Invoice Actions'

    def view_pdf_link(self, obj):
        """Generate a 'View PDF' button link for the Order."""
        if obj.pk: # Check if the object has been saved
             url = reverse('documents:order_pdf', args=[obj.pk])
             return format_html('<a href="{}" class="button" target="_blank">View Order PDF</a>', url)
        # For new objects not yet saved, no PDF can be generated
        return mark_safe("<em>(Save Order first to view PDF)</em>")
    view_pdf_link.short_description = 'PDF Action'

    class Media:
        # Use the SAME JavaScript file as Quote/Invoice inlines
        js = ('documents/js/admin_inline_autofill.js',)

 
class DeliveryOrderItemInline(admin.TabularInline):
    model = DeliveryOrderItem
    extra = 1 # Show one empty row for adding items by default
    fields = ('order_item', 'quantity_delivered', 'notes')
    # autocomplete_fields = ['order_item'] # We can consider this later for usability
    # Note: The 'order_item' dropdown will currently show ALL OrderItems from ALL Orders.
    # We will address filtering this dropdown or adding validation in a future step.


@admin.register(DeliveryOrder)
class DeliveryOrderAdmin(admin.ModelAdmin):
    list_display = ('do_number', 'order_link', 'delivery_date', 'status', 'recipient_name', 'created_at')
    list_filter = ('status', 'delivery_date', 'order__client')
    search_fields = ('do_number', 'order__order_number', 'order__client__name', 'recipient_name', 'notes')
    list_select_related = ('order', 'order__client') # Performance optimization for list view
    date_hierarchy = 'delivery_date' # Adds date navigation
    readonly_fields = ('do_number', 'created_at', 'updated_at', 'view_pdf_link')


    fieldsets = (
        (None, {'fields': ('order', 'delivery_date', 'status')}),
        # --- Add Actions section if it makes sense, or add button to an existing one ---
        ('Actions', {'fields': ('view_pdf_link',)}),
        ('Recipient & Address', {'fields': ('recipient_name', 'delivery_address_override')}),
        ('Notes', {'fields': ('notes',)}),
        ('System Info', {
            'fields': ('do_number', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [DeliveryOrderItemInline] # Embed the DeliveryOrderItem editor

    def order_link(self, obj):
        """Creates a clickable link to the parent Order in the admin."""
        if obj.order:
            # Ensure you have imported 'reverse' and 'format_html'
            link = reverse("admin:documents_order_change", args=[obj.order.pk])
            return format_html('<a href="{}">{}</a>', link, obj.order.order_number or f"Order PK {obj.order.pk}")
        return None
    order_link.short_description = 'Parent Order' # Column header for the link
    order_link.admin_order_field = 'order__order_number' # Allow sorting by this field

    def view_pdf_link(self, obj):
        """Generate a 'View PDF' button link for the Delivery Order."""
        if obj.pk: # Check if the object has been saved
             url = reverse('documents:delivery_order_pdf', args=[obj.pk])
             return format_html('<a href="{}" class="button" target="_blank">View DO PDF</a>', url)
        return mark_safe("<em>(Save Delivery Order first to view PDF)</em>")
    view_pdf_link.short_description = 'PDF Action' # Label for the fieldset section