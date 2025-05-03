from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Quotation

@receiver(post_save, sender=Quotation)
def generate_quotation_number(sender, instance, created, **kwargs):
    """
    Generate a quotation number automatically after a Quotation is first created.
    Format: Q-YYYY-ID
    """
    # Check if this is a new instance (created=True) and
    # if the quotation_number hasn't already been set somehow.
    if created and not instance.quotation_number:
        year = instance.created_at.year
        pk = instance.pk
        # Format the number
        number = f"Q-{year}-{pk}"
        # Assign it to the instance
        instance.quotation_number = number
        # Save the instance again, ONLY updating this field to avoid recursion
        instance.save(update_fields=['quotation_number'])