from django.contrib import admin
from django.utils.html import format_html, mark_safe


# Register your models here.
from .models import Client, MenuItem, Quotation, QuotationItem, Invoice, InvoiceItem, Setting
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
    readonly_fields = ('quotation_number', 'version', 'created_at', 'updated_at', 'previous_version')
    fieldsets = (
        # Section 1: Core Info (No quotation_number here - it's read-only)
        (None, {
            'fields': ('client', 'title', 'status')
        }),
        # Section 2: Dates
        ('Dates', {
            'fields': ('issue_date', 'valid_until')
        }),
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

    def display_total(self, obj):
         # Call the 'total' property from the Quotation model
         # Format it nicely for display (optional, but good)
         try:
             # Format as currency, you might need locale settings or a formatting library later
             return f"RM {obj.total:,.2f}"
         except Exception:
             return "Error" # Handle potential calculation errors gracefully
    display_total.short_description = 'Total Amount' # Column header

    # Embed the item editor within the quote page
    inlines = [QuotationItemInline]

# Note: We don't need a separate admin registration for QuotationItem
# because it's handled by the 'inlines' in QuotationAdmin

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
    list_display = ('invoice_number', 'client', 'status', 'issue_date', 'due_date', 'display_total') # Add display_total later
    list_filter = ('status', 'client', 'issue_date')
    search_fields = ('invoice_number', 'client__name', 'items__menu_item__name')
    # Make auto-generated fields read-only
    readonly_fields = ('invoice_number', 'created_at', 'updated_at')
    fieldsets = (
        # Group fields logically in the edit view
        (None, {'fields': ('client', 'related_quotation', 'title', 'status')}),
        ('Dates', {'fields': ('issue_date', 'due_date')}),
        ('Content', {'fields': ('terms_and_conditions', 'payment_details', 'notes')}),
        # Show read-only auto-generated fields in a collapsible section
        ('System Info', {
            'fields': ('invoice_number', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    # Embed the InvoiceItem editor
    inlines = [InvoiceItemInline]

    # We can add a display_total method here later similar to QuotationAdmin
    def display_total(self, obj):
         """Calculates and formats the total for display in admin list."""
         try:
             # Format as RM currency
             return f"RM {obj.total:,.2f}"
         except Exception:
             return "Error"
    display_total.short_description = 'Total Amount' # Sets the column header


@admin.register(Setting)
class SettingAdmin(SingletonModelAdmin):
    """Admin interface for the singleton Settings model."""
    # Optionally define fieldsets to organize the settings page
    fieldsets = (
        ('Company Information', {'fields': ('company_name', 'address', 'email', 'phone', 'tax_id', 'company_logo', 'logo_preview')}),
        ('Financial Settings', {'fields': ('currency_symbol', 'tax_enabled', 'tax_rate')}),
        ('Document Defaults', {'fields': ('default_payment_details', 'default_terms_conditions')}),
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