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
    path('quotations/', views.quotation_list_view, name='quotation_list'),
    path('invoice/<int:pk>/pdf/', views.generate_invoice_pdf, name='invoice_pdf'),
    path('invoice/<int:pk>/', views.invoice_detail_view, name='invoice_detail'),
    path('invoice/<int:pk>/finalize/', views.finalize_invoice, name='invoice_finalize'),
    path('invoices/', views.invoice_list_view, name='invoice_list'),
]