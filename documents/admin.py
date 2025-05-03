from django.contrib import admin

# Register your models here.
from .models import Client
from .models import MenuItem

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    """Configuration for the Client model in the Django admin interface"""
    list_display = ("name", "email", "phone", "created_at")
    search_fields = ("name", "email")
    list_filter = ("created_at",)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    """
    Configuration for the MenuItem model in the Django admin interface.
    """
    list_display = ('name', 'unit_price', 'unit', 'is_active', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('name', 'description', 'unit')
    list_editable = ('unit_price', 'unit', 'is_active') # Allows editing these directly in the list view