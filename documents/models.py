from django.db import models

# Create your models here.
class Client(models.Model):
    """Represents a client (customer)"""
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True, default="")
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")

    #Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        """String representation of the Client object"""
        return self.name
    

class MenuItem(models.Model):
    """
    Represents a menu item or service offered.
    Stores the default price; actual price might vary per quote/invoice line item.
    """
    class UnitType(models.TextChoices):
        PERSON = 'PERSON', 'Per Person'
        PACK = 'PACK', 'Per Pack'
        TRAY = 'TRAY', 'Per Tray'
        ITEM = 'ITEM', 'Per Item'
        FIXED = 'FIXED', 'Fixed Price'
        DAY = 'DAY', 'Per Day'
        EVENT = 'EVENT', 'Per Event'
        OTHER = 'OTHER', 'Other' # Fallback if needed

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    unit_price = models.DecimalField(
        max_digits=10,    # Max total digits allowed (e.g., 1,234,567.89)
        decimal_places=2  # Number of digits after the decimal point
    )
    unit = models.CharField(
        max_length=10, 
        choices = UnitType.choices,
        default = UnitType.ITEM,
        help_text="e.g., per person, per tray, per pack, fixed")
    is_active = models.BooleanField(default=True, help_text="Is this item currently offered?")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name'] # Order items alphabetically by name by default
