from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render # Helpful shortcut
from django.http import JsonResponse, Http404, HttpResponse
from django.contrib.auth.decorators import login_required
from django.template.loader import render_to_string # To render template to string
from django.urls import reverse, reverse_lazy
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import transaction

# Import WeasyPrint (will cause error if not installed)
try:
    import weasyprint
except ImportError:
    # Handle error gracefully if weasyprint isn't installed
    # You might want to log this or raise a configuration error
    weasyprint = None
    print("ERROR: WeasyPrint is not installed. PDF generation will not work.")
    print("Please install it: pip install WeasyPrint and required system dependencies.")

from .models import (
    Client, Quotation, QuotationItem, 
    Invoice, InvoiceItem, Payment,
    Order, OrderItem,
    DeliveryOrder, DeliveryOrderItem, # Ensure DeliveryOrder is imported
    Setting, MenuItem
)
from .forms import (
    QuotationForm, QuotationItemFormSet, 
    InvoiceForm, InvoiceItemFormSet,
    OrderForm, OrderItemFormSet,
    ClientForm
)


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
        redirect_url = reverse('documents:quotation_detail', args=[new_revision.pk])
        return redirect(redirect_url)
    else:
        # Add a warning message if revision couldn't be created
        messages.warning(request, f"Could not revise Quotation {original_quote.quotation_number}. Status might be Draft or already Superseded.")
        # Redirect back to the original quote's change page
        redirect_url = reverse('documents:quotation_detail', args=[original_quote.pk])
        return redirect(redirect_url)
  

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
    redirect_url = reverse('documents:quotation_detail', args=[quotation.pk])
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
    redirect_url = reverse('documents:quotation_detail', args=[quotation.pk])
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

    redirect_url = reverse('documents:invoice_detail', args=[invoice.pk])
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
        redirect_url = reverse('documents:invoice_detail', args=[new_invoice.pk])
    else:
        # Show warning message if invoice creation failed (e.g., due to order status)
        messages.warning(
            request,
            f"Could not create invoice from Order {order.order_number}. Order status might be '{order.get_status_display()}'."
        )
        # Redirect back to the original Order's change page
        redirect_url = reverse('documents:order_detail', args=[order.pk])

    return redirect(redirect_url)


@login_required
def generate_quotation_pdf(request, pk):
    """
    View to generate and return a PDF representation of a Quotation.
    """
    if not weasyprint:
        return HttpResponse("PDF generation library (WeasyPrint) is not installed correctly.", status=500)

    quotation = get_object_or_404(Quotation, pk=pk) # Moved outside try for redirect

    try:
        settings = Setting.get_solo()
        items = quotation.items.all()
        is_draft = (quotation.status == Quotation.Status.DRAFT)

        context = {
            'quotation': quotation,
            'items': items,
            'settings': settings,
            'is_draft': is_draft,
        }
        html_string = render_to_string('documents/pdf/quotation_pdf.html', context)
        html = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()

        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = f"Quotation-{quotation.quotation_number or quotation.pk}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except Setting.DoesNotExist:
        messages.error(request, "Application settings are not configured. PDF cannot be generated.")
        # Redirect to frontend quotation detail page
        return redirect(reverse('documents:quotation_detail', args=[pk]))
    except Exception as e:
        print(f"Error generating PDF for Quotation {pk}: {e}")
        messages.error(request, f"An error occurred while generating the PDF: {e}")
        # Redirect to frontend quotation detail page
        return redirect(reverse('documents:quotation_detail', args=[pk]))

@login_required
def generate_invoice_pdf(request, pk):
    """
    View to generate and return a PDF representation of an Invoice.
    """
    if not weasyprint:
        return HttpResponse("PDF generation library (WeasyPrint) is not installed correctly.", status=500)

    invoice = get_object_or_404(Invoice, pk=pk) # Moved outside try for redirect

    try:
        settings = Setting.get_solo()
        items = invoice.items.all()
        is_draft = (invoice.status == Invoice.Status.DRAFT)

        context = {
            'invoice': invoice,
            'items': items,
            'settings': settings,
            'is_draft': is_draft,
        }
        html_string = render_to_string('documents/pdf/invoice_pdf.html', context)
        html = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()

        response = HttpResponse(pdf_file, content_type='application/pdf')
        filename = f"Invoice-{invoice.invoice_number or invoice.pk}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except Setting.DoesNotExist:
         messages.error(request, "Application settings are not configured. PDF cannot be generated.")
         # Redirect to frontend invoice detail page
         return redirect(reverse('documents:invoice_detail', args=[pk]))
    except Exception as e:
        print(f"Error generating PDF for Invoice {pk}: {e}")
        messages.error(request, f"An error occurred while generating the PDF: {e}")
        # Redirect to frontend invoice detail page
        return redirect(reverse('documents:invoice_detail', args=[pk]))


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
    quotation = get_object_or_404(Quotation.objects.select_related('client', 'previous_version'), pk=pk)
    items = quotation.items.select_related('menu_item').all()
    settings = Setting.get_solo()

    # --- Add this line to fetch linked orders ---
    # Uses the related_name 'orders' from Order.related_quotation
    # Limit to 5 most recent for now, can add pagination later
    linked_orders = quotation.orders.all().order_by('-created_at')[:5]
    # --- End Add ---

    context = {
        'quotation': quotation,
        'items': items,
        'settings': settings,
        'linked_orders': linked_orders, # --- Add this to context ---
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
    redirect_url = reverse('documents:invoice_detail', args=[invoice.pk])
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


@login_required
@transaction.atomic # Ensure all database operations succeed or fail together
def invoice_create_view(request):
    """
    View to handle creating a new Invoice with its line items.
    """
    page_title = "Create New Invoice"

    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        item_formset = InvoiceItemFormSet(request.POST, prefix='items') # Use same prefix

        if form.is_valid() and item_formset.is_valid():
            invoice = form.save(commit=False)
            invoice.status = Invoice.Status.DRAFT # New invoices start as Draft
            # issue_date and due_date are left blank until finalized
            invoice.save() # Save Invoice header (triggers auto-numbering)

            # Link formset to the saved invoice and save items
            item_formset.instance = invoice
            item_formset.save()

            messages.success(request, f"Invoice {invoice.invoice_number} created successfully as Draft.")
            # Redirect to the detail page of the new invoice
            return redirect(reverse('documents:invoice_detail', args=[invoice.pk]))
        else:
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        form = InvoiceForm()
        item_formset = InvoiceItemFormSet(prefix='items')

    context = {
        'form': form,
        'item_formset': item_formset,
        'page_title': page_title,
    }
    # We need to create this template file next
    return render(request, 'documents/invoice_form.html', context)


@login_required
@transaction.atomic
def quotation_update_view(request, pk):
    """
    View to handle editing an existing Quotation and its line items.
    Only allows editing if the quotation is in DRAFT status.
    """
    quotation = get_object_or_404(Quotation, pk=pk)
    page_title = f"Edit Quotation {quotation.quotation_number or 'Draft'}"

    # --- IMPORTANT: Prevent editing finalized quotations ---
    if quotation.status != Quotation.Status.DRAFT:
        messages.error(request, "Only DRAFT quotations can be edited.")
        return redirect(reverse('documents:quotation_detail', args=[quotation.pk]))

    if request.method == 'POST':
        # Pass instance for update
        form = QuotationForm(request.POST, instance=quotation)
        item_formset = QuotationItemFormSet(request.POST, instance=quotation, prefix='items')

        if form.is_valid() and item_formset.is_valid():
            form.save() # Saves changes to the main quotation instance
            item_formset.save() # Saves changes to items (adds new, updates existing, deletes marked)

            messages.success(request, f"Quotation {quotation.quotation_number} updated successfully.")
            # Redirect to the detail page of the updated quotation
            return redirect(reverse('documents:quotation_detail', args=[quotation.pk]))
        else:
            # If forms are not valid, display errors
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        # Populate forms with existing instance data
        form = QuotationForm(instance=quotation)
        item_formset = QuotationItemFormSet(instance=quotation, prefix='items')

    context = {
        'form': form,
        'item_formset': item_formset,
        'page_title': page_title,
        'quotation': quotation, # Pass quotation for context if needed in template
    }
    # Reuse the same template as the create view
    return render(request, 'documents/quotation_form.html', context)


@login_required
@transaction.atomic
def invoice_update_view(request, pk):
    """
    View to handle editing an existing Invoice and its line items.
    Only allows editing if the invoice is in DRAFT status.
    """
    invoice = get_object_or_404(Invoice, pk=pk)
    page_title = f"Edit Invoice {invoice.invoice_number or 'Draft'}"

    # --- IMPORTANT: Prevent editing finalized invoices ---
    if invoice.status != Invoice.Status.DRAFT:
        messages.error(request, "Only DRAFT invoices can be edited.")
        return redirect(reverse('documents:invoice_detail', args=[invoice.pk]))

    if request.method == 'POST':
        # Pass instance for update
        form = InvoiceForm(request.POST, instance=invoice)
        item_formset = InvoiceItemFormSet(request.POST, instance=invoice, prefix='items')

        if form.is_valid() and item_formset.is_valid():
            form.save() # Saves changes to the main invoice instance
            item_formset.save() # Saves changes to items

            messages.success(request, f"Invoice {invoice.invoice_number} updated successfully.")
            # Redirect to the detail page of the updated invoice
            return redirect(reverse('documents:invoice_detail', args=[invoice.pk]))
        else:
            # If forms are not valid, display errors
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        # Populate forms with existing instance data
        form = InvoiceForm(instance=invoice)
        item_formset = InvoiceItemFormSet(instance=invoice, prefix='items')

    context = {
        'form': form,
        'item_formset': item_formset,
        'page_title': page_title,
        'invoice': invoice, # Pass invoice for context if needed in template title etc.
    }
    # Reuse the same template as the create view
    return render(request, 'documents/invoice_form.html', context)


@login_required
@transaction.atomic
def order_create_view(request):
    """
    View to handle creating a new Order with its line items.
    """
    page_title = "Create New Order/Event"

    if request.method == 'POST':
        form = OrderForm(request.POST)
        # Use 'items' prefix consistent with other formsets
        item_formset = OrderItemFormSet(request.POST, prefix='items')

        if form.is_valid() and item_formset.is_valid():
            order = form.save(commit=False)
            # Status defaults to CONFIRMED in the model, no need to set here explicitly
            order.save() # Save Order header (triggers auto-numbering)

            # Link formset to the saved order and save items
            item_formset.instance = order
            item_formset.save()

            messages.success(request, f"Order {order.order_number} created successfully.")
            # Redirect to the detail page of the newly created order
            return redirect(reverse('documents:order_detail', args=[order.pk]))
        else:
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        form = OrderForm()
        item_formset = OrderItemFormSet(prefix='items')

    context = {
        'form': form,
        'item_formset': item_formset,
        'page_title': page_title,
    }
    # We need to create this template file next
    return render(request, 'documents/order_form.html', context)


@login_required
@transaction.atomic
def order_update_view(request, pk):
    """
    View to handle editing an existing Order and its line items.
    Only allows editing if the order is in a suitable status (e.g., not completed/cancelled).
    """
    order = get_object_or_404(Order.objects.select_related('client'), pk=pk)
    page_title = f"Edit Order {order.order_number or 'Draft_ORD'}" # Use order_number if available

    # Define statuses that are NOT editable
    non_editable_statuses = [Order.OrderStatus.COMPLETED, Order.OrderStatus.CANCELLED]

    if order.status in non_editable_statuses:
        messages.error(request, f"Order cannot be edited when status is '{order.get_status_display()}'.")
        return redirect(reverse('documents:order_detail', args=[order.pk]))

    if request.method == 'POST':
        form = OrderForm(request.POST, instance=order)
        # Remember the prefix used when rendering the formset
        item_formset = OrderItemFormSet(request.POST, instance=order, prefix='items')

        if form.is_valid() and item_formset.is_valid():
            form.save() # Saves changes to the main order instance
            item_formset.save() # Saves changes to items (adds new, updates existing, deletes marked)

            messages.success(request, f"Order {order.order_number} updated successfully.")
            # Redirect to the detail page of the updated order
            return redirect(reverse('documents:order_detail', args=[order.pk]))
        else:
            # If forms are not valid, display errors
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        # Populate forms with existing instance data
        form = OrderForm(instance=order)
        item_formset = OrderItemFormSet(instance=order, prefix='items')

    context = {
        'form': form,
        'item_formset': item_formset,
        'page_title': page_title,
        'order': order, # Pass order for context
    }
    # Reuse the create template
    return render(request, 'documents/order_form.html', context)


@login_required
def client_create_view(request):
    """
    View to handle creating a new Client.
    """
    page_title = "Add New Client"

    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save() # Save the new client instance
            messages.success(request, f"Client '{client.name}' created successfully.")
            # Redirect to the detail page of the newly created client
            return redirect(reverse('documents:client_detail', args=[client.pk]))
        else:
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        form = ClientForm()

    context = {
        'form': form,
        'page_title': page_title,
    }
    # We will create this template file next
    return render(request, 'documents/client_form.html', context)


@login_required
@transaction.atomic # Good practice for views that save data
def client_update_view(request, pk):
    """
    View to handle editing an existing Client.
    """
    client = get_object_or_404(Client, pk=pk)
    page_title = f"Edit Client: {client.name}"

    if request.method == 'POST':
        # Pass instance to pre-fill the form and to update this specific client
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            form.save() # Saves changes to the existing client instance
            messages.success(request, f"Client '{client.name}' updated successfully.")
            # Redirect to the detail page of the updated client
            return redirect(reverse('documents:client_detail', args=[client.pk]))
        else:
            messages.error(request, "Please correct the errors below.")
    else: # GET request
        # Populate form with existing instance data
        form = ClientForm(instance=client)

    context = {
        'form': form,
        'page_title': page_title,
        'client': client, # Pass client for context if template uses it (e.g., in breadcrumbs)
    }
    # Reuse the same template as the create view
    return render(request, 'documents/client_form.html', context)


@login_required
def generate_delivery_order_pdf(request, pk):
    """
    View to generate and return a PDF representation of a DeliveryOrder.
    """
    if not weasyprint:
        return HttpResponse("PDF generation library (WeasyPrint) is not installed correctly.", status=500)

    # Use select_related to optimize fetching related Order and its Client
    delivery_order = get_object_or_404(
        DeliveryOrder.objects.select_related('order', 'order__client'),
        pk=pk
    )

    try:
        settings = Setting.get_solo()
        # Use select_related to optimize fetching related OrderItem and its MenuItem
        items = delivery_order.items.select_related('order_item__menu_item').all()

        # Prepare context for the template
        context = {
            'delivery_order': delivery_order,
            'items': items,
            'settings': settings,
            # No 'is_draft' needed for DOs unless you introduce a draft status for them
        }

        # Render the HTML template to a string
        html_string = render_to_string('documents/pdf/delivery_order_pdf.html', context)

        # Generate PDF using WeasyPrint
        html = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()

        # Create the HTTP response
        response = HttpResponse(pdf_file, content_type='application/pdf')

        # Set filename
        filename = f"DO-{delivery_order.do_number or delivery_order.pk}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        return response

    except DeliveryOrder.DoesNotExist: # Should be caught by get_object_or_404
        raise Http404("Delivery Order not found.")
    except Setting.DoesNotExist:
         messages.error(request, "Application settings have not been configured in the admin.")
         # Redirect back to the DO detail page if we create one, or admin change page
         # For now, let's try redirecting to admin DO change page
         try:
             admin_url = reverse('admin:documents_deliveryorder_change', args=[pk])
             return redirect(admin_url)
         except: # Fallback
             return redirect('admin:index')
    except Exception as e:
        print(f"Error generating PDF for Delivery Order {pk}: {e}") # Log the error
        messages.error(request, f"An error occurred while generating the PDF: {e}")
        # Redirect back to the DO detail page
        try:
            admin_url = reverse('admin:documents_deliveryorder_change', args=[pk])
            return redirect(admin_url)
        except: # Fallback
             return redirect('admin:index')


@login_required # Changed from @staff_member_required for consistency with other frontend PDF views
def generate_order_pdf(request, pk):
    """
    View to generate and return a PDF representation of an Order.
    """
    if not weasyprint:
        return HttpResponse("PDF generation library (WeasyPrint) is not installed correctly.", status=500)

    # Use select_related to optimize fetching related data
    order = get_object_or_404(
        Order.objects.select_related('client', 'related_quotation'),
        pk=pk
    )

    try:
        settings = Setting.get_solo()
        # Use select_related for OrderItem's MenuItem
        items = order.items.select_related('menu_item').all()

        # Prepare context for the template
        context = {
            'order': order,
            'items': items,
            'settings': settings,
        }

        # Render the HTML template to a string
        html_string = render_to_string('documents/pdf/order_pdf.html', context)

        # Generate PDF using WeasyPrint
        html = weasyprint.HTML(string=html_string, base_url=request.build_absolute_uri('/'))
        pdf_file = html.write_pdf()

        # Create the HTTP response
        response = HttpResponse(pdf_file, content_type='application/pdf')

        # Set filename
        filename = f"Order-{order.order_number or order.pk}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'

        return response

    except Order.DoesNotExist: # Should be caught by get_object_or_404
        raise Http404("Order not found.")
    except Setting.DoesNotExist:
         messages.error(request, "Application settings have not been configured in the admin.")
         # Redirect to the Order detail page as we have one now
         return redirect(reverse('documents:order_detail', args=[pk]))
    except Exception as e:
        print(f"Error generating PDF for Order {pk}: {e}") # Log the error
        messages.error(request, f"An error occurred while generating the PDF: {e}")
        # Redirect to the Order detail page
        return redirect(reverse('documents:order_detail', args=[pk]))
    

@login_required # Or @staff_member_required if this button will only be in admin
def create_order_from_quotation(request, pk):
    """
    View to handle creating a new Order from an ACCEPTED Quotation.
    """
    quotation = get_object_or_404(Quotation, pk=pk)

    # Call the model method to create the order
    new_order = quotation.create_order() # This method returns the new Order or None

    if new_order:
        messages.success(
            request,
            f"Order {new_order.order_number} created successfully from Quotation {quotation.quotation_number}."
        )
        # Redirect to the detail page of the newly created order
        redirect_url = reverse('documents:order_detail', args=[new_order.pk])
    else:
        # The create_order method on the model handles printing warnings for specific failure reasons
        messages.warning(
            request,
            f"Could not create Order from Quotation {quotation.quotation_number}. "
            "Ensure the quotation is 'Accepted' and an order doesn't already exist for it."
        )
        # Redirect back to the quotation's detail page
        redirect_url = reverse('documents:quotation_detail', args=[quotation.pk])

    return redirect(redirect_url)


@login_required
def delivery_order_list_view(request):
    """
    Display a list of all Delivery Orders with pagination.
    """
    delivery_order_list = DeliveryOrder.objects.select_related(
        'order', 'order__client'
    ).all().order_by('-delivery_date', '-created_at') # Order by delivery date, then creation

    paginator = Paginator(delivery_order_list, 10) # Show 10 delivery orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'title': 'Delivery Orders'
    }
    return render(request, 'documents/delivery_order_list.html', context)


@login_required
def delivery_order_detail_view(request, pk):
    """
    Display the details of a single Delivery Order.
    """
    delivery_order = get_object_or_404(
        DeliveryOrder.objects.select_related(
            'order',
            'order__client',
            'order__related_quotation' # If you want to show quote ref
        ),
        pk=pk
    )
    # Fetch related items, also getting linked order_item and its menu_item efficiently
    items = delivery_order.items.select_related(
        'order_item__menu_item', # Access menu_item name via order_item
        'order_item__order' # Access original order if needed from item level
    ).all()
    settings = Setting.get_solo()

    context = {
        'delivery_order': delivery_order,
        'items': items,
        'settings': settings, # For currency symbol, company info etc.
        'title': f"Delivery Order {delivery_order.do_number or delivery_order.pk}"
    }
    return render(request, 'documents/delivery_order_detail.html', context)


    

