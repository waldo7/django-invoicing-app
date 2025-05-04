from django.shortcuts import render

# Create your views here.
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404 # Helpful shortcut

from .models import MenuItem # Import your MenuItem model

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