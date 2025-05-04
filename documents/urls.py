from django.urls import path
from . import views # Import views from the current app

# Define an app name for namespacing (optional but good practice)
app_name = 'documents'

urlpatterns = [
    path('api/menuitem/<int:pk>/', views.get_menu_item_details, name='get_menu_item_details'),
    # Add other app-specific URLs here later
]