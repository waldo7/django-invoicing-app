from django.http import HttpResponse # For sending the PDF response
from django.template.loader import render_to_string # To render template to string

from django.shortcuts import render
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404, redirect # Helpful shortcut
from django.urls import reverse
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required

# Import WeasyPrint (will cause error if not installed)
try:
    import weasyprint
except ImportError:
    # Handle error gracefully if weasyprint isn't installed
    # You might want to log this or raise a configuration error
    weasyprint = None
    print("ERROR: WeasyPrint is not installed. PDF generation will not work.")
    print("Please install it: pip install WeasyPrint and required system dependencies.")

from .models import Order, MenuItem, Quotation, Setting, Invoice

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


@staff_member_required
def generate_quotation_pdf(request, pk):
    """
    View to generate and return a PDF representation of a Quotation.
    """
    if not weasyprint:
        # Handle case where WeasyPrint failed to import
        return HttpResponse("PDF generation library (WeasyPrint) is not installed correctly.", status=500)

    try:
        quotation = get_object_or_404(Quotation, pk=pk)
        settings = Setting.get_solo()
        items = quotation.items.all()

        # Prepare context for the template
        context = {
            'quotation': quotation,
            'items': items,
            'settings': settings,
        }

        # Render the HTML template to a string
        html_string = render_to_string('documents/pdf/quotation_pdf.html', context)

        # Generate PDF using WeasyPrint
        # base_url helps resolve relative paths for assets if needed (e.g., CSS)
        # Using request.build_absolute_uri('/') provides the site's base URL.
        html = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()

        # Create the HTTP response with PDF mime type
        response = HttpResponse(pdf_file, content_type='application/pdf')

        # Set Content-Disposition header to suggest a filename
        # 'inline' attempts to display PDF in browser, 'attachment' forces download
        filename = f"Quotation-{quotation.quotation_number or quotation.pk}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        # Alternatively, for forced download:
        # response['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Quotation.DoesNotExist:
        raise Http404("Quotation not found.")
    except Setting.DoesNotExist:
         # Handle case where settings haven't been configured in admin yet
         messages.error(request, "Application settings have not been configured in the admin.")
         # Redirect back to where they came from or a safe place
         # This requires getting the previous URL or redirecting to admin index
         # For simplicity now, let's return an error response
         return HttpResponse("Application settings not configured.", status=500)
    except Exception as e:
        # Handle other potential errors during PDF generation
        print(f"Error generating PDF for Quotation {pk}: {e}") # Log the error
        messages.error(request, f"An error occurred while generating the PDF: {e}")
        # Redirect back to the quotation detail page
        admin_url = reverse('admin:documents_quotation_change', args=[pk])
        return redirect(admin_url)


@staff_member_required
def generate_invoice_pdf(request, pk):
    """
    View to generate and return a PDF representation of an Invoice.
    """
    if not weasyprint:
        return HttpResponse("PDF generation library (WeasyPrint) is not installed correctly.", status=500)

    try:
        invoice = get_object_or_404(Invoice, pk=pk)
        settings = Setting.get_solo()
        items = invoice.items.all() # Use related_name 'items'

        # Prepare context for the template
        context = {
            'invoice': invoice,
            'items': items,
            'settings': settings,
        }

        # Render the HTML template to a string
        # Make sure this matches the template file path we created
        html_string = render_to_string('documents/pdf/invoice_pdf.html', context)

        # Generate PDF using WeasyPrint
        html = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()

        # Create the HTTP response
        response = HttpResponse(pdf_file, content_type='application/pdf')

        # Set filename
        filename = f"Invoice-{invoice.invoice_number or invoice.pk}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        return response

    except Invoice.DoesNotExist:
        raise Http404("Invoice not found.")
    except Setting.DoesNotExist:
         messages.error(request, "Application settings have not been configured in the admin.")
         # Redirect back to the invoice detail page if possible
         try:
             admin_url = reverse('admin:documents_invoice_change', args=[pk])
             return redirect(admin_url)
         except: # Fallback if pk doesn't exist or other error
             return redirect('admin:index') # Redirect to main admin page
    except Exception as e:
        print(f"Error generating PDF for Invoice {pk}: {e}") # Log the error
        messages.error(request, f"An error occurred while generating the PDF: {e}")
        # Redirect back to the invoice detail page
        admin_url = reverse('admin:documents_invoice_change', args=[pk])
        return redirect(admin_url)


