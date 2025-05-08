from django.urls import path
from . import views # Import views from the current app

# Define an app name for namespacing (optional but good practice)
app_name = 'documents'

urlpatterns = [
    path('api/menuitem/<int:pk>/', views.get_menu_item_details, name='get_menu_item_details'),
    path('quotation/<int:pk>/revise/', views.revise_quotation, name='quotation_revise'),
    path('order/<int:pk>/create-invoice/', views.create_invoice_from_order, name='order_create_invoice'),
    path('quotation/<int:pk>/pdf/', views.generate_quotation_pdf, name='quotation_pdf'),
    path('quotation/<int:pk>/', views.quotation_detail_view, name='quotation_detail'),
    path('quotation/<int:pk>/finalize/', views.finalize_quotation, name='quotation_finalize'),
    path('quotation/<int:pk>/revert-to-draft/', views.revert_quotation_to_draft, name='quotation_revert_to_draft'),
    path('quotations/', views.quotation_list_view, name='quotation_list'),
    path('quotations/new/', views.quotation_create_view, name='quotation_create'),
    path('quotation/<int:pk>/edit/', views.quotation_update_view, name='quotation_update'),
    path('invoice/<int:pk>/pdf/', views.generate_invoice_pdf, name='invoice_pdf'),
    path('invoice/<int:pk>/', views.invoice_detail_view, name='invoice_detail'),
    path('invoice/<int:pk>/finalize/', views.finalize_invoice, name='invoice_finalize'),
    path('invoice/<int:pk>/revert-to-draft/', views.revert_invoice_to_draft, name='invoice_revert_to_draft'),
    path('invoice/<int:pk>/edit/', views.invoice_update_view, name='invoice_update'),
    path('invoices/', views.invoice_list_view, name='invoice_list'),
    path('invoices/new/', views.invoice_create_view, name='invoice_create'),
    path('orders/', views.order_list_view, name='order_list'),
    path('order/<int:pk>/', views.order_detail_view, name='order_detail'),
    path('clients/', views.client_list_view, name='client_list'),
    path('client/<int:pk>/', views.client_detail_view, name='client_detail'),
]