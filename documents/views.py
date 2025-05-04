from django.shortcuts import render
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect # Helpful shortcut
from django.urls import reverse
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required

from .models import Order, MenuItem, Quotation 

# Create your views here.
def get_menu_item_details(request, pk):
    """
    API endpoint to fetch unit_price and description for a given MenuItem pk.
    Called via JavaScript from the admin inline forms.
    """
    # Ensure this is accessed only when needed, maybe check user permissions later if necessary
    # For now, just check if the user is authenticated and staff
    if not request.user.is_authenticated or not request.user.is_staff:
         return JsonResponse({'error': 'Not authorized'}, status=403)

    try:
        # Use get_object_or_404 to handle item not found cleanly
        menu_item = get_object_or_404(MenuItem, pk=pk)

        # Prepare data to return as JSON
        data = {
            'unit_price': str(menu_item.unit_price), # Convert Decimal to string for JSON
            'description': menu_item.description,
        }
        return JsonResponse(data)
    except Exception as e:
        # Basic error handling
        return JsonResponse({'error': str(e)}, status=500)
    
    
@staff_member_required # Ensure only logged-in staff can access this
def revise_quotation(request, pk):
    """
    View to handle the creation of a new revision for a Quotation.
    """
    # Get the quotation we want to revise
    original_quote = get_object_or_404(Quotation, pk=pk)

    # Call the model method to create the revision
    new_revision = original_quote.create_revision()

    # Check if revision was successful (it returns None if status was Draft/Superseded)
    if new_revision:
        # Add a success message for the user
        messages.success(request, f"Successfully created revision V{new_revision.version} ({new_revision.quotation_number}) from {original_quote.quotation_number}. You are now editing the new draft.")
        # Redirect the user to the admin change page for the NEW revision
        admin_url = reverse('admin:documents_quotation_change', args=[new_revision.pk])
        return redirect(admin_url)
    else:
        # Add a warning message if revision couldn't be created
        messages.warning(request, f"Could not revise Quotation {original_quote.quotation_number}. Status might be Draft or already Superseded.")
        # Redirect back to the original quote's change page
        admin_url = reverse('admin:documents_quotation_change', args=[original_quote.pk])
        return redirect(admin_url)
  

@staff_member_required # Ensure only logged-in staff can access this
def create_invoice_from_order(request, pk):
    """
    View to handle creating a draft Invoice from a specific Order.
    """
    order = get_object_or_404(Order, pk=pk)

    # Call the model method we created and tested
    new_invoice = order.create_invoice()

    if new_invoice:
        # Show success message
        messages.success(
            request,
            f"Successfully created draft Invoice {new_invoice.invoice_number} from Order {order.order_number}. You are now editing the new draft."
        )
        # Redirect to the change page of the new Invoice
        redirect_url = reverse('admin:documents_invoice_change', args=[new_invoice.pk])
    else:
        # Show warning message if invoice creation failed (e.g., due to order status)
        messages.warning(
            request,
            f"Could not create invoice from Order {order.order_number}. Order status might be '{order.get_status_display()}'."
        )
        # Redirect back to the original Order's change page
        redirect_url = reverse('admin:documents_order_change', args=[order.pk])

    return redirect(redirect_url)




