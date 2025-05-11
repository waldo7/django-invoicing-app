from decimal import Decimal
from django import forms

from .models import (
    Quotation, QuotationItem, Client, MenuItem, DiscountType, 
    Invoice, InvoiceItem, Order, OrderItem,
    Client, DeliveryOrderItem, OrderItem, Order
    )

class QuotationForm(forms.ModelForm):
    # Add custom DateInput widgets to get nice date pickers in most browsers
    issue_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False # Will be set on finalize
    )
    valid_until = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False # Will be calculated or manually set
    )

    class Meta:
        model = Quotation
        fields = [
            'client', 'title', 'issue_date', 'valid_until',
            'discount_type', 'discount_value',
            'terms_and_conditions', 'notes'
        ]
        # Exclude: quotation_number (auto), status (default Draft), version (default 1), previous_version (for revise)
        widgets = {
            'terms_and_conditions': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            # Client will be a dropdown by default
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to form fields
        for field_name, field in self.fields.items():
            # Check if field has a widget and if it has an 'attrs' attribute
            if hasattr(field.widget, 'attrs'):
                current_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{current_class} form-control form-control-sm'.strip()
                if isinstance(field.widget, forms.CheckboxInput):
                     field.widget.attrs['class'] = 'form-check-input' # Specific class for checkbox
                elif isinstance(field.widget, forms.Select):
                     field.widget.attrs['class'] = 'form-select form-select-sm' # Specific class for select
            # Special handling for client select due to ModelChoiceField
            if field_name == 'client':
                field.widget.attrs['class'] = 'form-select form-select-sm'


class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ['menu_item', 'description', 'quantity', 'unit_price', 'grouping_label']
        # Exclude: quotation (set by formset)
        widgets = {
            'description': forms.Textarea(attrs={'rows': 1}),
            'grouping_label': forms.TextInput(attrs={'placeholder': 'e.g., Day 1 - Lunch'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                current_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{current_class} form-control form-control-sm'.strip()
                if isinstance(field.widget, forms.Select):
                     field.widget.attrs['class'] = 'form-select form-select-sm'


# Create an InlineFormSet for QuotationItems
QuotationItemFormSet = forms.inlineformset_factory(
    Quotation,  # Parent model
    QuotationItem, # Child model
    form=QuotationItemForm, # Form to use for each item
    extra=1,  # Number of empty forms to display
    can_delete=True, # Allow deleting items
    can_delete_extra=True, # Allows deleting even the 'extra' forms if not filled
    min_num=0 # Allow zero items initially if desired (default 0)
)


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['menu_item', 'description', 'quantity', 'unit_price', 'grouping_label']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 1}),
            'grouping_label': forms.TextInput(attrs={'placeholder': 'e.g., Service Fee'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                current_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{current_class} form-control form-control-sm'.strip()
                if isinstance(field.widget, forms.Select):
                     field.widget.attrs['class'] = 'form-select form-select-sm'


class InvoiceForm(forms.ModelForm):
    issue_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False # Set by finalize action
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False # Optional / Set by finalize action
    )

    class Meta:
        model = Invoice
        fields = [
            'client', 'title', 'related_quotation', 'related_order',
            'issue_date', 'due_date', 'discount_type', 'discount_value',
            'terms_and_conditions', 'notes', 'payment_details'
        ]
        # Exclude: invoice_number (auto), status (default Draft)
        widgets = {
            'terms_and_conditions': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'payment_details': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                current_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{current_class} form-control form-control-sm'.strip()
                if isinstance(field.widget, forms.CheckboxInput):
                     field.widget.attrs['class'] = 'form-check-input'
                elif isinstance(field.widget, forms.Select):
                     field.widget.attrs['class'] = 'form-select form-select-sm'
            # Special handling for FK selects
            if field_name in ['client', 'related_quotation', 'related_order']:
                field.widget.attrs['class'] = 'form-select form-select-sm'
                # Make relation fields optional if appropriate (model already allows null/blank)
                # field.required = False # Keep required based on model unless explicitly overriding


# Create an InlineFormSet for InvoiceItems
InvoiceItemFormSet = forms.inlineformset_factory(
    Invoice,    # Parent model
    InvoiceItem,# Child model
    form=InvoiceItemForm, # Form for child
    extra=1,
    can_delete=True,
    can_delete_extra=True,
    min_num=0
)


class OrderItemForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ['menu_item', 'description', 'quantity', 'unit_price', 'grouping_label']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 1}),
            'grouping_label': forms.TextInput(attrs={'placeholder': 'e.g., Buffet Station'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                current_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{current_class} form-control form-control-sm'.strip()
                if isinstance(field.widget, forms.Select):
                     field.widget.attrs['class'] = 'form-select form-select-sm'


class OrderForm(forms.ModelForm):
    # Use DateInput widget for nice picker
    event_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        required=False # Make optional in form if model allows null/blank
    )

    class Meta:
        model = Order
        fields = [
            'client', 'title', 'related_quotation', 'event_date',
            'delivery_address', 'discount_type', 'discount_value', 'notes'
        ]
        # Exclude: order_number (auto), status (default Confirmed)
        widgets = {
            'delivery_address': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        for field_name, field in self.fields.items():
             # Make relation fields optional in the form if model allows (reduces errors if user doesn't select)
            if field_name in ['related_quotation']:
                field.required = False

            if hasattr(field.widget, 'attrs'):
                current_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{current_class} form-control form-control-sm'.strip()
                if isinstance(field.widget, forms.CheckboxInput):
                     field.widget.attrs['class'] = 'form-check-input'
                elif isinstance(field.widget, forms.Select):
                     field.widget.attrs['class'] = 'form-select form-select-sm'
            # Special handling for FK selects
            if field_name in ['client', 'related_quotation']:
                field.widget.attrs['class'] = 'form-select form-select-sm'


# Create an InlineFormSet for OrderItems
OrderItemFormSet = forms.inlineformset_factory(
    Order,      # Parent model
    OrderItem,  # Child model
    form=OrderItemForm, # Form for child
    extra=1,    # Show 1 empty form
    can_delete=True,
    can_delete_extra=True,
    min_num=0
)


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'address', 'email', 'phone', 'tax_id'] # Add all fields you want on the form
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            # Add any other widget customizations if needed
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes to form fields
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                current_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{current_class} form-control form-control-sm'.strip()
                if isinstance(field.widget, forms.CheckboxInput):
                     field.widget.attrs['class'] = 'form-check-input'
                elif isinstance(field.widget, forms.Select): # Though ClientForm might not have Selects by default
                     field.widget.attrs['class'] = 'form-select form-select-sm'


class DeliveryOrderItemForm(forms.ModelForm):
    class Meta:
        model = DeliveryOrderItem
        fields = ['order_item', 'quantity_delivered', 'notes']
        # Add any widgets if needed, e.g., for notes
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 1}),
        }

    def __init__(self, *args, **kwargs):
        # Pop 'parent_order' kwarg, passed from DeliveryOrderAdmin
        parent_order = kwargs.pop('parent_order', None)
        super().__init__(*args, **kwargs)

        # Add Bootstrap classes (optional, but good for consistency if used elsewhere)
        for field_name, field in self.fields.items():
            if hasattr(field.widget, 'attrs'):
                current_class = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{current_class} form-control form-control-sm'.strip()
                if isinstance(field.widget, forms.Select):
                     field.widget.attrs['class'] = 'form-select form-select-sm'

        # Filter the 'order_item' queryset if a parent_order is provided
        if parent_order:
            self.fields['order_item'].queryset = OrderItem.objects.filter(order=parent_order)
        elif self.instance and self.instance.pk and hasattr(self.instance, 'delivery_order') and self.instance.delivery_order:
            # If editing an existing item, parent_order might not be passed explicitly,
            # but we can infer it from the instance.
            self.fields['order_item'].queryset = OrderItem.objects.filter(order=self.instance.delivery_order.order)
        else:
            # For new, unbound forms (e.g., initial load of "add" page before parent DO is saved),
            # show no items or items from a sensible default if possible.
            # Showing none is safer to prevent selection before parent Order is known.
            self.fields['order_item'].queryset = OrderItem.objects.none()

                     