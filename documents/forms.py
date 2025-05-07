from django import forms
from .models import Quotation, QuotationItem, Client, MenuItem, DiscountType

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