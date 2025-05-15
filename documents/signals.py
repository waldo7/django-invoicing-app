from django.db.models.signals import post_save, post_delete 
from django.dispatch import receiver
from django.utils import timezone # Add this import
from django.apps import apps
from decimal import Decimal

from .models import (
    Quotation, Payment, Invoice, Order, DeliveryOrder, CreditNote
)




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


@receiver([post_save, post_delete], sender=Payment)
def update_invoice_status_on_payment_change(sender, instance, **kwargs):
    """
    Update the related Invoice status based on payment changes.
    """
    try:
        invoice = instance.invoice
        if not invoice:
             return
    except Invoice.DoesNotExist:
        return

    InvoiceStatus = apps.get_model('documents', 'Invoice').Status

    # Use the correct member name: PARTIALLY_PAID
    if invoice.status in [InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED]:
        return # Do nothing if Draft or Cancelled

    amount_paid = invoice.amount_paid
    grand_total = invoice.grand_total

    new_status = invoice.status

    # Use the correct member name: PARTIALLY_PAID
    if amount_paid <= 0:
        new_status = InvoiceStatus.SENT
    elif amount_paid < grand_total:
         new_status = InvoiceStatus.PARTIALLY_PAID # Corrected here
    # Note: The logic for PAID might need refinement later depending on exact grand_total behavior
    elif amount_paid >= grand_total and grand_total > 0:
         new_status = InvoiceStatus.PAID
    elif grand_total <= 0 and amount_paid >= grand_total:
         new_status = InvoiceStatus.PAID

    if new_status != invoice.status:
        invoice.status = new_status
        invoice.save(update_fields=['status'])


@receiver(post_save, sender=Order)
def generate_order_number(sender, instance, created, **kwargs):
    """
    Generate an order number automatically after an Order is first created.
    Format: ORD-YYYY-ID
    """
    if created and not instance.order_number:
        # Ensure created_at is available (should be due to auto_now_add)
        # Default to current year if created_at isn't set yet (unlikely)
        year = instance.created_at.year if instance.created_at else timezone.now().year
        pk = instance.pk
        # Format the number
        number = f"ORD-{year}-{pk}"
        # Assign it to the instance
        instance.order_number = number
        # Save the instance again, ONLY updating this field
        instance.save(update_fields=['order_number'])


@receiver(post_save, sender=DeliveryOrder)
def generate_do_number(sender, instance, created, **kwargs):
    """
    Generate a delivery order number automatically after a DeliveryOrder is first created.
    Format: DO-YYYY-ID
    """
    if created and not instance.do_number:
        # Ensure created_at is available (should be due to auto_now_add)
        # Default to current year if created_at isn't set yet (unlikely but safe)
        year = instance.created_at.year if instance.created_at else timezone.now().year
        pk = instance.pk
        # Format the number
        number = f"DO-{year}-{pk}"
        # Assign it to the instance
        instance.do_number = number
        # Save the instance again, ONLY updating this field
        instance.save(update_fields=['do_number'])


@receiver(post_save, sender=CreditNote)
def generate_cn_number(sender, instance, created, **kwargs):
    """
    Generate a credit note number automatically after a CreditNote is first created.
    Format: CN-YYYY-ID
    """
    if created and not instance.cn_number:
        year = instance.created_at.year if instance.created_at else timezone.now().year
        pk = instance.pk
        number = f"CN-{year}-{pk}"
        instance.cn_number = number
        instance.save(update_fields=['cn_number'])



