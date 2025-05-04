from django.urls import path
from . import views # Import views from the current app

# Define an app name for namespacing (optional but good practice)
app_name = 'documents'

urlpatterns = [
    path('api/menuitem/<int:pk>/', views.get_menu_item_details, name='get_menu_item_details'),
    path('quotation/<int:pk>/revise/', views.revise_quotation, name='quotation_revise'),
    path('order/<int:pk>/create-invoice/', views.create_invoice_from_order, name='order_create_invoice'),
]