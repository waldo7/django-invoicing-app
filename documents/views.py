from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render # Helpful shortcut
from django.http import JsonResponse, Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string # To render template to string
from django.contrib import messages
from django.db import transaction
from django.urls import reverse

# Import WeasyPrint (will cause error if not installed)
try:
    import weasyprint
except ImportError:
    # Handle error gracefully if weasyprint isn't installed
    # You might want to log this or raise a configuration error
    weasyprint = None
    print("ERROR: WeasyPrint is not installed. PDF generation will not work.")
    print("Please install it: pip install WeasyPrint and required system dependencies.")

from .models import Order, MenuItem, Quotation, Setting, Invoice, Client
from .forms import QuotationForm, QuotationItemFormSet


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
  

@staff_member_required
def finalize_quotation(request, pk):
    """
    View to handle finalizing a DRAFT Quotation.
    Sets issue_date, calculates valid_until (if needed), and changes status to SENT.
    """
    quotation = get_object_or_404(Quotation, pk=pk)

    # Call the model method to finalize
    finalized_successfully = quotation.finalize() # This method now returns True/False

    if finalized_successfully:
        messages.success(
            request,
            f"Quotation {quotation.quotation_number} has been finalized. Status set to 'Sent', issue date set to {quotation.issue_date:%Y-%m-%d}."
        )
    else:
        messages.warning(
            request,
            f"Quotation {quotation.quotation_number} could not be finalized (status was likely not 'Draft')."
        )

    # Redirect back to the admin change page for this quotation
    redirect_url = reverse('admin:documents_quotation_change', args=[quotation.pk])
    return redirect(redirect_url)


@staff_member_required
def revert_quotation_to_draft(request, pk):
    """
    View to handle reverting a 'Sent' Quotation back to 'Draft'.
    """
    quotation = get_object_or_404(Quotation, pk=pk)

    # Call the model method to revert
    reverted_successfully = quotation.revert_to_draft()

    if reverted_successfully:
        messages.success(
            request,
            f"Quotation {quotation.quotation_number} has been reverted to Draft. Issue date and valid until date have been cleared."
        )
    else:
        messages.warning(
            request,
            f"Quotation {quotation.quotation_number} could not be reverted to draft (status was likely not 'Sent')."
        )

    # Redirect back to the admin change page for this quotation
    redirect_url = reverse('admin:documents_quotation_change', args=[quotation.pk])
    return redirect(redirect_url)


@staff_member_required
def finalize_invoice(request, pk):
    """
    View to handle finalizing a DRAFT Invoice.
    Sets issue_date, calculates due_date (if needed), and changes status to SENT.
    """
    invoice = get_object_or_404(Invoice, pk=pk)

    # Call the model method to finalize
    finalized_successfully = invoice.finalize() # This method returns True/False

    if finalized_successfully:
        # Use f-string for better readability if issue_date might be None (though finalize sets it)
        issue_date_str = f"{invoice.issue_date:%Y-%m-%d}" if invoice.issue_date else "not set"
        messages.success(
            request,
            f"Invoice {invoice.invoice_number} has been finalized. Status set to 'Sent', issue date set to {issue_date_str}."
        )
    else:
        messages.warning(
            request,
            f"Invoice {invoice.invoice_number} could not be finalized (status was likely not 'Draft')."
        )

    # Redirect back to the admin change page for this invoice
    redirect_url = reverse('admin:documents_invoice_change', args=[invoice.pk])
    return redirect(redirect_url)


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

        is_draft = (quotation.status == Quotation.Status.DRAFT)

        # Prepare context for the template
        context = {
            'quotation': quotation,
            'items': items,
            'settings': settings,
            'is_draft': is_draft,
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

        is_draft = (invoice.status == Invoice.Status.DRAFT)

        # Prepare context for the template
        context = {
            'invoice': invoice,
            'items': items,
            'settings': settings,
            'is_draft': is_draft,
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


@login_required # Ensures only logged-in users can access this view
def quotation_list_view(request):
    """
    Display a list of all quotations.
    """
    quotations = Quotation.objects.select_related('client').all() # Fetch all quotations, optimize client access
    settings = Setting.get_solo() # Get settings for currency symbol etc.

    context = {
        'quotations': quotations,
        'settings': settings, # Pass settings to template
    }
    # Render the template we just created
    return render(request, 'documents/quotation_list.html', context)


@login_required
def invoice_list_view(request):
    """
    Display a list of all invoices.
    """
    invoices = Invoice.objects.select_related('client').all() # Fetch all invoices
    settings = Setting.get_solo() # Get settings for currency symbol etc.

    context = {
        'invoices': invoices,
        'settings': settings,
    }
    # Point to the new template we will create
    return render(request, 'documents/invoice_list.html', context)


@login_required
def quotation_detail_view(request, pk):
    """
    Display the details of a single quotation.
    """
    # Fetch the specific quotation, ensuring client data is fetched efficiently
    quotation = get_object_or_404(Quotation.objects.select_related('client'), pk=pk)
    # Fetch related items, also getting linked menu_item efficiently
    items = quotation.items.select_related('menu_item').all()
    settings = Setting.get_solo()

    context = {
        'quotation': quotation,
        'items': items,
        'settings': settings,
    }
    return render(request, 'documents/quotation_detail.html', context)


@login_required
def invoice_detail_view(request, pk):
    """
    Display the details of a single invoice.
    """
    invoice = get_object_or_404(Invoice.objects.select_related('client', 'related_order', 'related_quotation'), pk=pk)
    items = invoice.items.select_related('menu_item').all()
    settings = Setting.get_solo()

    context = {
        'invoice': invoice,
        'items': items,
        'settings': settings,
    }
    return render(request, 'documents/invoice_detail.html', context)


@staff_member_required
def revert_invoice_to_draft(request, pk):
    """
    View to handle reverting a 'Sent' Invoice back to 'Draft'.
    """
    invoice = get_object_or_404(Invoice, pk=pk)

    # Call the model method to revert
    reverted_successfully = invoice.revert_to_draft()

    if reverted_successfully:
        messages.success(
            request,
            f"Invoice {invoice.invoice_number} has been reverted to Draft. Issue date and due date have been cleared."
        )
    else:
        messages.warning(
            request,
            f"Invoice {invoice.invoice_number} could not be reverted to draft (status was likely not 'Sent')."
        )

    # Redirect back to the admin change page for this invoice
    redirect_url = reverse('admin:documents_invoice_change', args=[invoice.pk])
    return redirect(redirect_url)

@login_required
def order_list_view(request):
    """
    Display a list of all orders.
    """
    # Order by event_date (most recent first), then by creation date
    orders = Order.objects.select_related('client').all().order_by('-event_date', '-created_at')
    settings = Setting.get_solo()

    context = {
        'orders': orders,
        'settings': settings,
    }
    return render(request, 'documents/order_list.html', context)


@login_required
def order_detail_view(request, pk):
    """
    Display the details of a single order.
    """
    order = get_object_or_404(
        Order.objects.select_related('client', 'related_quotation'), pk=pk
    )
    items = order.items.select_related('menu_item').all()
    settings = Setting.get_solo()

    context = {
        'order': order,
        'items': items,
        'settings': settings,
    }
    return render(request, 'documents/order_detail.html', context)


@login_required
def client_list_view(request):
    """
    Display a list of all clients.
    """
    clients = Client.objects.all().order_by('name') # Order by name
    settings = Setting.get_solo() # For currency or other settings if needed in template later

    context = {
        'clients': clients,
        'settings': settings, # Though not strictly needed for client list yet
    }
    return render(request, 'documents/client_list.html', context)


@login_required
def client_detail_view(request, pk):
    """
    Display the details of a single client and their related documents.
    """
    client = get_object_or_404(Client, pk=pk)
    settings = Setting.get_solo()

    # Fetch related documents
    # Using prefetch_related for M2M or reverse FKs if needed,
    # but direct related manager access is fine for now given separate queries are likely
    quotations = client.quotations.all().order_by('-issue_date', '-created_at')[:10] # Get latest 10
    orders = client.orders.all().order_by('-event_date', '-created_at')[:10]
    invoices = client.invoices.all().order_by('-issue_date', '-created_at')[:10]

    context = {
        'client': client,
        'settings': settings,
        'quotations': quotations,
        'orders': orders,
        'invoices': invoices,
    }
    return render(request, 'documents/client_detail.html', context)


@login_required
@transaction.atomic # Ensures all database operations are run together or rolled back on error
def quotation_create_view(request):
    """
    View to handle creating a new Quotation with its line items.
    """
    page_title = "Create New Quotation"

    if request.method == 'POST':
        # If data is being submitted
        form = QuotationForm(request.POST)
        # 'prefix="items"' must match the prefix used when rendering the formset in the template
        item_formset = QuotationItemFormSet(request.POST, prefix='items')

        if form.is_valid() and item_formset.is_valid():
            # Save the main Quotation form (but don't commit to DB yet if further processing needed)
            quotation = form.save(commit=False)
            # Set any fields not on the form automatically
            # quotation.created_by = request.user # Example if you had this field
            quotation.status = Quotation.Status.DRAFT # New quotes start as Draft
            quotation.version = 1 # First version
            # issue_date and valid_until are intentionally left blank for drafts
            quotation.save() # Save the Quotation header (this will trigger auto-numbering)

            # Now link the item_formset to the saved quotation instance
            item_formset.instance = quotation
            item_formset.save() # Save the line items

            messages.success(request, f"Quotation {quotation.quotation_number} created successfully as Draft.")
            # Redirect to the detail page of the newly created quotation
            return redirect(reverse('documents:quotation_detail', args=[quotation.pk]))
        else:
            # If forms are not valid, display errors
            messages.error(request, "Please correct the errors below.")
    else:
        # If it's a GET request, display a blank form
        form = QuotationForm()
        item_formset = QuotationItemFormSet(prefix='items')

    context = {
        'form': form,
        'item_formset': item_formset,
        'page_title': page_title,
    }
    return render(request, 'documents/quotation_form.html', context)



