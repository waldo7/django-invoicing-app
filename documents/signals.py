from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Quotation, Invoice


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


@receiver(post_save, sender=Invoice)
def generate_invoice_number(sender, instance, created, **kwargs):
    """
    Generate an invoice number automatically after an Invoice is first created.
    Format: INV-YYYY-ID
    """
    if created and not instance.invoice_number:
        year = instance.created_at.year
        pk = instance.pk
        # Format the number
        number = f"INV-{year}-{pk}"
        # Assign it to the instance
        instance.invoice_number = number
        # Save the instance again, ONLY updating this field
        instance.save(update_fields=['invoice_number'])