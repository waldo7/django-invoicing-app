from django.contrib import admin
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django.utils.html import format_html


# Register your models here.
from .models import (
    Client, MenuItem, Quotation, QuotationItem, Invoice, InvoiceItem, 
    Setting, Payment, Order, OrderItem
)
from solo.admin import SingletonModelAdmin # Import SoloAdmin


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
        'previous_version', 'revise_quotation_link', 'view_pdf_link'
        )
    fieldsets = (
        # Section 1: Core Info (No quotation_number here - it's read-only)
        (None, {
            'fields': ('client', 'title', 'status')
        }),
        ('Actions', {'fields': ('revise_quotation_link', 'view_pdf_link',)}),
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
         try:
             # Format as currency, you might need locale settings or a formatting library later
             return f"RM {obj.grand_total:,.2f}"
         except Exception:
             return "Error" # Handle potential calculation errors gracefully
    display_total.short_description = 'Total Amount' # Column header

    def revise_quotation_link(self, obj):
        """
        Generate a 'Revise' button link for the admin change page.
        Only show if the quotation exists and is in a state that can be revised (e.g., Sent, Accepted).
        """
        # Check if the object has been saved (has a PK) and its status allows revision
        if obj.pk and obj.status in [Quotation.Status.SENT, Quotation.Status.ACCEPTED, Quotation.Status.REJECTED]:
             # Generate the URL for our revise_quotation view using its name
             # Ensure 'documents' namespace is used if defined in core.urls include()
             url = reverse('documents:quotation_revise', args=[obj.pk])
             # Return HTML for a button-like link using admin styles
             return format_html('<a href="{}" class="button">Revise this Quotation</a>', url)
        # Return empty string or info message if revision isn't allowed
        return mark_safe("<em>(Cannot revise if Draft or Superseded)</em>") # Import mark_safe if needed
    revise_quotation_link.short_description = 'Revise' # Label for the fieldset section
    # revise_quotation_link.allow_tags = True # Deprecated in newer Django, format_html handles safety

    def view_pdf_link(self, obj):
        """Generate a 'View PDF' button link."""
        if obj.pk: # Check if the object has been saved
             # Generate URL for the PDF view
             url = reverse('documents:quotation_pdf', args=[obj.pk])
             # Return HTML for a link styled as button, opening in new tab
             return format_html('<a href="{}" class="button" target="_blank">View PDF</a>', url)
        return mark_safe("<em>(Save quotation first to view PDF)</em>")
    view_pdf_link.short_description = 'PDF' # Label for the fieldset

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
        'related_order'
        )
    fieldsets = (
        # Group fields logically in the edit view
        (None, {'fields': ('client', 'related_quotation', 'related_order', 'title', 'status')}),
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
         try: return f"RM {obj.grand_total:,.2f}"
         except Exception: return "Error"
    display_grand_total.short_description = 'Total Amount'

    # Need separate methods for readonly_fields as they often don't directly accept properties
    def display_grand_total_detail(self, obj):
         """Formats grand_total for detail view (readonly_fields)."""
         try: return f"RM {obj.grand_total:,.2f}"
         except Exception: return "Error"
    display_grand_total_detail.short_description = 'Grand Total' # Header in fieldset

    def display_amount_paid(self, obj):
         """Formats amount_paid for detail view."""
         try: return f"RM {obj.amount_paid:,.2f}"
         except Exception: return "Error"
    display_amount_paid.short_description = 'Amount Paid'

    def display_balance_due(self, obj):
         """Formats balance_due for list and detail view."""
         try: return f"RM {obj.balance_due:,.2f}"
         except Exception: return "Error"
    display_balance_due.short_description = 'Balance Due'

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
        'create_invoice_link'
    )
    fieldsets = (
        (None, {'fields': ('client', 'related_quotation', 'title', 'status')}),
        ('Actions', {'fields': ('create_invoice_link',)}),
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
         try: return f"RM {obj.grand_total:,.2f}"
         except Exception: return "Error"
    display_grand_total.short_description = 'Total Amount' # Header for list view

    def display_grand_total_detail(self, obj):
         """Formats grand_total for detail view."""
         try: return f"RM {obj.grand_total:,.2f}"
         except Exception: return "Error"
    display_grand_total_detail.short_description = 'Grand Total (Calc.)' # Header for detail view

    def display_subtotal(self, obj):
         """Formats subtotal for detail view."""
         try: return f"RM {obj.subtotal:,.2f}"
         except Exception: return "Error"
    display_subtotal.short_description = 'Subtotal (Calc.)'

    def display_discount_amount(self, obj):
         """Formats discount_amount for detail view."""
         try: return f"RM {obj.discount_amount:,.2f}"
         except Exception: return "Error"
    display_discount_amount.short_description = 'Discount Amount (Calc.)'

    def display_tax_amount(self, obj):
         """Formats tax_amount for detail view."""
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

    # Keep the Media class for JS auto-population
    class Media:
        js = ('documents/js/admin_inline_autofill.js',)

    class Media:
        # Use the SAME JavaScript file as Quote/Invoice inlines
        js = ('documents/js/admin_inline_autofill.js',)










