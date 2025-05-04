from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

# Create your tests here.
from .models import Payment, PaymentMethod, Client, MenuItem, Quotation, QuotationItem, Invoice, InvoiceItem, Setting, DiscountType


class ClientModelTests(TestCase):
    def test_client_creation_minimal(self):
        """Test creating a client with only the required name field."""
        client = Client.objects.create(name="Test Client Ltd.")
        self.assertEqual(client.name, "Test Client Ltd.")
        self.assertEqual(client.address, "")
        self.assertEqual(client.email, "")
        self.assertEqual(client.phone, "")
        

    def test_client_creation_all_fields(self):
        """Test creating a client with all fields populated."""
        client = Client.objects.create(  
            name="Full Details Inc.",
            address="123 Main St\nAnytown",
            email="contact@fulldetails.com",
            phone="555-1234"
        )
        self.assertEqual(client.name, "Full Details Inc.") 
        self.assertEqual(client.address, "123 Main St\nAnytown") 
        self.assertEqual(client.email, "contact@fulldetails.com") 
        self.assertEqual(client.phone, "555-1234")  

    def test_client_str_representation(self):
        client = Client.objects.create(name="String Rep Co.") 
        self.assertEqual(str(client), "String Rep Co.") 


class MenuItemModelTests(TestCase):

    def test_menu_item_creation(self):
        """
        Test creating a menu item with required and optional fields.
        """
        item = MenuItem.objects.create(
            name="Nasi Lemak",
            description="Fragrant rice with sambal, anchovies, egg",
            unit_price=Decimal("8.50"), # Use Decimal for prices
            unit="PACK"
        )
        self.assertEqual(item.name, "Nasi Lemak")
        self.assertEqual(item.description, "Fragrant rice with sambal, anchovies, egg")
        self.assertEqual(item.unit_price, Decimal("8.50"))
        self.assertEqual(item.unit, "PACK")
        self.assertTrue(item.is_active) # Should default to Truepython manage.py migrate documents

    def test_menu_item_str_representation(self):
        """
        Test the string representation (__str__) of the menu item.
        """
        item = MenuItem.objects.create(
            name="Teh Tarik",
            unit_price=Decimal("2.50")
        )
        self.assertEqual(str(item), "Teh Tarik")

    def test_menu_item_default_is_active(self):
        """
        Test that a new menu item is active by default.
        """
        item = MenuItem.objects.create(name="Default Active", unit_price=Decimal("10.00"))
        self.assertTrue(item.is_active)


class QuotationModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create a client once for all tests in this class
        cls.db_client = Client.objects.create(name="Test Client for Quotes")

    def test_quotation_creation(self):
        """Test creating a basic quotation and auto-generating number."""
        today = timezone.now().date()
        quote = Quotation.objects.create(
            client=self.db_client,
            issue_date=today
        )
        quote.refresh_from_db() # <-- Add this line to get the latest data

        expected_number = f"Q-{quote.created_at.year}-{quote.pk}"
        self.assertEqual(quote.quotation_number, expected_number) # Now check
        self.assertEqual(quote.client, self.db_client)
        self.assertEqual(quote.issue_date, today)
        self.assertEqual(quote.version, 1)
        self.assertEqual(quote.status, 'DRAFT')
        self.assertIsNone(quote.previous_version)

    def test_quotation_versioning_fields(self):
        """Test setting versioning fields."""
        today = timezone.now().date()
        quote_v1 = Quotation.objects.create(
            client=self.db_client, issue_date=today, version=1, status='SUPERSEDED'
        )
        quote_v1.refresh_from_db() # <-- Add this line

        # Manually assign number for clarity in test setup if needed
        # (though the signal should handle it anyway)
        # if not quote_v1.quotation_number: # Check if signal didn't run fast enough (unlikely here)
        #    quote_v1.quotation_number = f"Q-{quote_v1.created_at.year}-{quote_v1.pk}"
        #    quote_v1.save(update_fields=['quotation_number'])

        quote_v2 = Quotation.objects.create(
            client=self.db_client, issue_date=today, version=2, status='DRAFT', previous_version=quote_v1
        )
        quote_v2.refresh_from_db() # <-- Add this line

        expected_v2_number = f"Q-{quote_v2.created_at.year}-{quote_v2.pk}"
        self.assertEqual(quote_v2.quotation_number, expected_v2_number) # Now check
        self.assertEqual(quote_v2.version, 2)
        self.assertEqual(quote_v2.previous_version, quote_v1)
        # Refresh v1 just in case its status was somehow modified by v2 creation signals (unlikely)
        quote_v1.refresh_from_db()
        self.assertEqual(quote_v1.status, 'SUPERSEDED')

    def test_quotation_str_representation(self):
        """Test the string representation."""
        quote = Quotation.objects.create(client=self.db_client, issue_date=timezone.now().date())
        quote.refresh_from_db() # <-- Add this line

        # The __str__ method needs the number, which is generated automatically
        expected_str = f"Quotation {quote.quotation_number} ({self.db_client.name})"
        self.assertEqual(str(quote), expected_str) # Now check

    

    def test_quotation_subtotal_and_discount(self):
        """Test subtotal and discount amount calculations."""
        quote = Quotation.objects.create(client=self.db_client, issue_date=timezone.now().date())
        menu_item = MenuItem.objects.create(name="Item for Disc Test", unit_price=Decimal("50.00"))
        # Add items: 2 * 50 = 100, 1 * 60 = 60. Subtotal = 160.00
        QuotationItem.objects.create(quotation=quote, menu_item=menu_item, quantity=2, unit_price=Decimal("50.00"))
        QuotationItem.objects.create(quotation=quote, menu_item=menu_item, quantity=1, unit_price=Decimal("60.00"))

        # Test subtotal
        self.assertEqual(quote.subtotal, Decimal("160.00"))

        # Test No Discount
        quote.discount_type = DiscountType.NONE
        quote.discount_value = Decimal("10.00") # Value ignored
        quote.save()
        self.assertEqual(quote.discount_amount, Decimal("0.00"))

        # Test Percentage Discount (10% of 160 = 16.00)
        quote.discount_type = DiscountType.PERCENTAGE
        quote.discount_value = Decimal("10.00")
        quote.save()
        self.assertEqual(quote.discount_amount, Decimal("16.00"))

        # Test Fixed Discount (RM 25.00)
        quote.discount_type = DiscountType.FIXED
        quote.discount_value = Decimal("25.00")
        quote.save()
        self.assertEqual(quote.discount_amount, Decimal("25.00"))

        # Test Fixed Discount exceeding subtotal
        quote.discount_type = DiscountType.FIXED
        quote.discount_value = Decimal("200.00")
        quote.save()
        self.assertEqual(quote.discount_amount, Decimal("160.00")) # Should cap at subtotal

    def test_quotation_tax_and_grand_total(self):
        """Test tax amount and grand total calculations."""
        # --- Setup ---
        quote = Quotation.objects.create(client=self.db_client, issue_date=timezone.now().date())
        menu_item = MenuItem.objects.create(name="Item for Tax Test", unit_price=Decimal("100.00"))
        # Add items: Subtotal = 100.00
        QuotationItem.objects.create(quotation=quote, menu_item=menu_item, quantity=1, unit_price=Decimal("100.00"))

        # Add Discount: 10% = 10.00 discount. Total before tax = 90.00
        quote.discount_type = DiscountType.PERCENTAGE
        quote.discount_value = Decimal("10.00")
        quote.save() # Save discount settings

        settings = Setting.get_solo() # Get settings instance

        # --- Test Case 1: Tax Disabled ---
        settings.tax_enabled = False
        settings.tax_rate = Decimal("6.00") # Rate doesn't matter if disabled
        settings.save()

        self.assertEqual(quote.total_before_tax, Decimal("90.00")) # Subtotal - Discount
        self.assertEqual(quote.tax_amount, Decimal("0.00"))     # Tax should be 0
        self.assertEqual(quote.grand_total, Decimal("90.00"))   # Grand total = total before tax

        # --- Test Case 2: Tax Enabled (6% of 90.00 = 5.40) ---
        settings.tax_enabled = True
        settings.tax_rate = Decimal("6.00")
        settings.save()

        # Need to reload quote maybe? Or does property re-fetch settings? Let's assume it fetches.
        self.assertEqual(quote.total_before_tax, Decimal("90.00")) # Should be unchanged
        self.assertEqual(quote.tax_amount, Decimal("5.40"))      # 6% tax on 90.00
        self.assertEqual(quote.grand_total, Decimal("95.40"))    # 90.00 + 5.40

    
class QuotationItemModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create common objects needed for item tests
        cls.db_client = Client.objects.create(name="Test Client for Items")
        cls.menu_item = MenuItem.objects.create(name="Test Menu Item", unit_price=Decimal("10.00"), unit='ITEM')
        cls.quote = Quotation.objects.create(quotation_number="Q-ITEM-TEST", client=cls.db_client, issue_date=timezone.now().date())

    def test_quotation_item_creation(self):
        """Test creating a quotation line item."""
        item = QuotationItem.objects.create(
            quotation=self.quote,
            menu_item=self.menu_item,
            quantity=Decimal("2.0"),
            unit_price=Decimal("11.00"), # Price specific to this quote line
            description="Overridden description",
            grouping_label="Group A"
        )
        self.assertEqual(item.quotation, self.quote)
        self.assertEqual(item.menu_item, self.menu_item)
        self.assertEqual(item.quantity, Decimal("2.0"))
        self.assertEqual(item.unit_price, Decimal("11.00")) # Check overridden price
        self.assertEqual(item.description, "Overridden description") # Check overridden description
        self.assertEqual(item.grouping_label, "Group A")

    # We might add tests later for default description/price copying once we implement that logic.
    # For now, we test setting the fields directly.

    def test_quotation_item_line_total(self):
        """Test the line_total calculation property."""
        # This test will fail until the line_total property exists
        item = QuotationItem.objects.create(
            quotation=self.quote,
            menu_item=self.menu_item,
            quantity=Decimal("3.0"),
            unit_price=Decimal("10.50") # 3 * 10.50 = 31.50
        )
        self.assertEqual(item.line_total, Decimal("31.50"))


class InvoiceModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.db_client = Client.objects.create(name="Test Client for Invoices")
        # Optional: create a quote to link to
        cls.quote = Quotation.objects.create(client=cls.db_client, issue_date=timezone.now().date())
        cls.quote.refresh_from_db() # Get the generated number if needed elsewhere
        cls.invoice = Invoice.objects.create(client=cls.db_client, issue_date=timezone.now().date())
        cls.invoice.refresh_from_db() # Refresh to get its number too

    def test_invoice_creation(self):
        """Test creating a basic invoice."""
        # This test will fail until Invoice model exists & auto-numbering works
        today = timezone.now().date()
        due = today + timezone.timedelta(days=30)

        inv = Invoice.objects.create(
            client=self.db_client,
            related_quotation=self.quote,
            title="Test Invoice Title",
            issue_date=today,
            due_date=due,
            terms_and_conditions="Pay up!",
            notes="Internal note",
            payment_details="Bank ABC 12345"
        )
        inv.refresh_from_db() # Need to refresh after signal runs

        expected_number = f"INV-{inv.created_at.year}-{inv.pk}"
        self.assertEqual(inv.invoice_number, expected_number)
        self.assertEqual(inv.client, self.db_client)
        self.assertEqual(inv.related_quotation, self.quote)
        self.assertEqual(inv.title, "Test Invoice Title")
        self.assertEqual(inv.issue_date, today)
        self.assertEqual(inv.due_date, due)
        self.assertEqual(inv.status, 'DRAFT') # Default status
        self.assertEqual(inv.terms_and_conditions, "Pay up!")
        self.assertEqual(inv.notes, "Internal note")
        self.assertEqual(inv.payment_details, "Bank ABC 12345")

    def test_invoice_str_representation(self):
        """Test the string representation."""
        # This test will fail until Invoice model exists & auto-numbering works
        expected_str = f"Invoice {self.invoice.invoice_number} ({self.db_client.name})"
        self.assertEqual(str(self.invoice), expected_str)

    

    def test_invoice_subtotal_and_discount(self):
        """Test subtotal and discount amount calculations for invoice."""
        # Use self.invoice created in setUpTestData
        menu_item = MenuItem.objects.create(name="Item for Inv Disc Test", unit_price=Decimal("30.00"))
        # Add items: 3 * 30 = 90, 1 * 10 = 10. Subtotal = 100.00
        InvoiceItem.objects.create(invoice=self.invoice, menu_item=menu_item, quantity=3, unit_price=Decimal("30.00"))
        InvoiceItem.objects.create(invoice=self.invoice, menu_item=menu_item, quantity=1, unit_price=Decimal("10.00"))

        # Test subtotal
        self.assertEqual(self.invoice.subtotal, Decimal("100.00"))

        # Test No Discount
        self.invoice.discount_type = DiscountType.NONE
        self.invoice.discount_value = Decimal("5.00")
        self.invoice.save()
        self.assertEqual(self.invoice.discount_amount, Decimal("0.00"))

        # Test Percentage Discount (20% of 100 = 20.00)
        self.invoice.discount_type = DiscountType.PERCENTAGE
        self.invoice.discount_value = Decimal("20.00")
        self.invoice.save()
        self.assertEqual(self.invoice.discount_amount, Decimal("20.00"))

        # Test Fixed Discount (RM 15.00)
        self.invoice.discount_type = DiscountType.FIXED
        self.invoice.discount_value = Decimal("15.00")
        self.invoice.save()
        self.assertEqual(self.invoice.discount_amount, Decimal("15.00"))

    def test_invoice_tax_and_grand_total(self):
        """Test tax amount and grand total calculations for invoice."""
        # --- Setup ---

        # --- Add Invoice Items first! ---
        # Need items that sum to 100.00 for the assertions below to make sense.
        menu_item = MenuItem.objects.create(name="Item for Inv Tax Test", unit_price=Decimal("50.00"))
        InvoiceItem.objects.create(invoice=self.invoice, menu_item=menu_item, quantity=1, unit_price=Decimal("60.00")) # 60.00
        InvoiceItem.objects.create(invoice=self.invoice, menu_item=menu_item, quantity=2, unit_price=Decimal("20.00")) # 40.00
        # Subtotal should now be 100.00 for self.invoice

        # Now apply discount: Fixed RM 15.00. Total before tax = 85.00
        self.invoice.discount_type = DiscountType.FIXED
        self.invoice.discount_value = Decimal("15.00")
        self.invoice.save()

        settings = Setting.get_solo()

        # --- Test Case 1: Tax Disabled ---
        settings.tax_enabled = False
        settings.tax_rate = Decimal("8.00") # Rate doesn't matter
        settings.save()

        # Refresh invoice object IF discount save might affect calculated properties? Unlikely needed but safe.
        # self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.total_before_tax, Decimal("85.00")) # 100 - 15
        self.assertEqual(self.invoice.tax_amount, Decimal("0.00"))
        self.assertEqual(self.invoice.grand_total, Decimal("85.00"))

        # --- Test Case 2: Tax Enabled (8% of 85.00 = 6.80) ---
        settings.tax_enabled = True
        settings.tax_rate = Decimal("8.00")
        settings.save()

        # Refreshing invoice again might be needed if property caching is complex, but try without first.
        # self.invoice.refresh_from_db()

        self.assertEqual(self.invoice.total_before_tax, Decimal("85.00")) # Should still be 85.00
        self.assertEqual(self.invoice.tax_amount, Decimal("6.80")) # 8% tax on 85.00
        self.assertEqual(self.invoice.grand_total, Decimal("91.80")) # 85.00 + 6.80

    def test_invoice_payment_calculations(self):
        """Test amount_paid and balance_due properties."""
        # --- Setup ---
        # We use self.invoice created in setUpTestData
        # Let's assume its grand_total needs calculating based on items & settings
        # Add items to give it a non-zero total (Subtotal=100)
        menu_item = MenuItem.objects.create(name="Item for Payment Calc", unit_price=Decimal("50.00"))
        InvoiceItem.objects.create(invoice=self.invoice, menu_item=menu_item, quantity=2, unit_price=Decimal("50.00"))

        # Assume no discount, tax disabled for simplicity here (or set them)
        settings = Setting.get_solo()
        settings.tax_enabled = False
        settings.save()
        self.invoice.discount_type = DiscountType.NONE
        self.invoice.save()

        # Expected grand_total = 100.00
        self.assertEqual(self.invoice.grand_total, Decimal("100.00"))

        # --- Test Case 1: No Payments ---
        self.assertEqual(self.invoice.amount_paid, Decimal("0.00"))
        self.assertEqual(self.invoice.balance_due, Decimal("100.00")) # 100 - 0

        # --- Test Case 2: One Payment ---
        Payment.objects.create(invoice=self.invoice, amount=Decimal("40.00"))
        self.assertEqual(self.invoice.amount_paid, Decimal("40.00"))
        self.assertEqual(self.invoice.balance_due, Decimal("60.00")) # 100 - 40

        # --- Test Case 3: Multiple Payments ---
        Payment.objects.create(invoice=self.invoice, amount=Decimal("60.00"))
        self.assertEqual(self.invoice.amount_paid, Decimal("100.00")) # 40 + 60
        self.assertEqual(self.invoice.balance_due, Decimal("0.00")) # 100 - 100

        # --- Test Case 4: Overpayment ---
        Payment.objects.create(invoice=self.invoice, amount=Decimal("10.00"))
        self.assertEqual(self.invoice.amount_paid, Decimal("110.00")) # 100 + 10
        self.assertEqual(self.invoice.balance_due, Decimal("-10.00")) # 100 - 110


    def test_invoice_status_updates_on_payment_change(self):
        """
        Test that Invoice status is updated correctly via signals
        when Payments are saved or deleted.
        """
        # --- Setup: Create Invoice with items (Subtotal=100), no discount/tax => Grand Total = 100 ---
        inv = Invoice.objects.create(client=self.db_client, issue_date=date(2025, 5, 1))
        menu_item = MenuItem.objects.create(name="Item for Status Test", unit_price=Decimal("100.00"))
        InvoiceItem.objects.create(invoice=inv, menu_item=menu_item, quantity=1, unit_price=Decimal("100.00"))

        # Manually set initial status to SENT for testing signal logic trigger
        inv.status = Invoice.Status.SENT
        inv.save(update_fields=['status']) # Save only status initially
        inv.refresh_from_db() # Refresh to be sure

        self.assertEqual(inv.grand_total, Decimal("100.00"))
        self.assertEqual(inv.amount_paid, Decimal("0.00"))
        self.assertEqual(inv.status, Invoice.Status.SENT)

        # --- Stage 1: Add Partial Payment -> Status should become PART_PAID ---
        p1 = Payment.objects.create(invoice=inv, amount=Decimal("40.00"))
        inv.refresh_from_db() # Refresh invoice to see status update from signal
        self.assertEqual(inv.amount_paid, Decimal("40.00"))
        self.assertEqual(inv.status, Invoice.Status.PARTIALLY_PAID, "Status should be Partially Paid after first payment")

        # --- Stage 2: Add Payment to cover total -> Status should become PAID ---
        p2 = Payment.objects.create(invoice=inv, amount=Decimal("60.00"))
        inv.refresh_from_db()
        self.assertEqual(inv.amount_paid, Decimal("100.00"))
        self.assertEqual(inv.status, Invoice.Status.PAID, "Status should be Paid after full payment")

        # --- Stage 3: Delete second payment -> Status should revert to PART_PAID ---
        p2.delete()
        inv.refresh_from_db()
        self.assertEqual(inv.amount_paid, Decimal("40.00"))
        self.assertEqual(inv.status, Invoice.Status.PARTIALLY_PAID, "Status should revert to Partially Paid after deleting p2")

        # --- Stage 4: Delete first payment -> Status should revert to SENT ---
        p1.delete()
        inv.refresh_from_db()
        self.assertEqual(inv.amount_paid, Decimal("0.00"))
        self.assertEqual(inv.status, Invoice.Status.SENT, "Status should revert to Sent after deleting all payments")

        # --- Stage 5: Test Draft Invoice - status should NOT change ---
        draft_inv = Invoice.objects.create(client=self.db_client, issue_date=date(2025, 5, 2), status=Invoice.Status.DRAFT)
        Payment.objects.create(invoice=draft_inv, amount=Decimal("10.00"))
        draft_inv.refresh_from_db()
        self.assertEqual(draft_inv.status, Invoice.Status.DRAFT, "Draft invoice status should not change on payment")

        # --- Stage 6: Test Cancelled Invoice - status should NOT change ---
        cancelled_inv = Invoice.objects.create(client=self.db_client, issue_date=date(2025, 5, 3), status=Invoice.Status.CANCELLED)
        Payment.objects.create(invoice=cancelled_inv, amount=Decimal("20.00"))
        cancelled_inv.refresh_from_db()
        self.assertEqual(cancelled_inv.status, Invoice.Status.CANCELLED, "Cancelled invoice status should not change on payment")

    
class InvoiceItemModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.client = Client.objects.create(name="Test Client for Inv Items")
        cls.menu_item = MenuItem.objects.create(name="Test Menu Item Inv", unit_price=Decimal("20.00"))
        cls.invoice = Invoice.objects.create(client=cls.client, issue_date=timezone.now().date())
        # We might need cls.invoice.refresh_from_db() here if tests depend on invoice_number
        cls.invoice.refresh_from_db()

    def test_invoice_item_creation(self):
        """Test creating an invoice line item."""
        # This test will fail until InvoiceItem model exists
        item = InvoiceItem.objects.create(
            invoice=self.invoice,
            menu_item=self.menu_item,
            quantity=Decimal("1.5"),
            unit_price=Decimal("25.00"), # Invoice specific price
            description="Specific invoice description",
            grouping_label="Group B"
        )
        self.assertEqual(item.invoice, self.invoice)
        self.assertEqual(item.menu_item, self.menu_item)
        self.assertEqual(item.quantity, Decimal("1.5"))
        self.assertEqual(item.unit_price, Decimal("25.00"))
        self.assertEqual(item.description, "Specific invoice description")
        self.assertEqual(item.grouping_label, "Group B")


class SettingModelTests(TestCase):

    def test_get_singleton_instance(self):
        """Test that we can retrieve the singleton settings instance."""
        settings = Setting.get_solo() # Get the single instance
        self.assertIsInstance(settings, Setting)
        # Check a default value
        self.assertEqual(settings.currency_symbol, "RM")
        self.assertFalse(settings.tax_enabled)
        self.assertEqual(settings.default_validity_days, 15) # Check new default

    def test_modify_settings(self):
        """Test modifying and saving settings."""
        settings = Setting.get_solo()
        settings.company_name = "My Awesome Catering Co."
        settings.tax_enabled = True
        settings.tax_rate = Decimal("8.00")
        settings.save()

        # Get the instance again to ensure changes were saved
        updated_settings = Setting.get_solo()
        self.assertEqual(updated_settings.company_name, "My Awesome Catering Co.")
        self.assertTrue(updated_settings.tax_enabled)
        self.assertEqual(updated_settings.tax_rate, Decimal("8.00"))

    def test_singleton_enforcement(self):
        """Test that we always get the same instance."""
        settings1 = Setting.get_solo()
        settings1.phone = "111-111"
        settings1.save()

        settings2 = Setting.get_solo()
        self.assertEqual(settings2.phone, "111-111")
        # Check they are the same object in memory (same primary key)
        self.assertEqual(settings1.pk, settings2.pk)
        # Creating directly should raise an error, but get_solo handles it.
        # Trying Setting.objects.create() would likely fail if an instance exists.


class PaymentModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create objects needed for payment tests
        cls.client = Client.objects.create(name="Client for Payments")
        # Create an invoice, explicitly setting issue date as it's now required before save
        cls.invoice = Invoice.objects.create(client=cls.client, issue_date=date(2025, 5, 1))
        cls.invoice.refresh_from_db() # Ensure invoice number is generated if needed

    def test_payment_creation(self):
        """Test creating a payment record with all fields."""
        today = timezone.now().date()
        payment = Payment.objects.create(
            invoice=self.invoice,
            payment_date=today,
            amount=Decimal("100.50"),
            payment_method=PaymentMethod.BANK_TRANSFER,
            reference_number="TXN12345",
            notes="Partial payment received."
        )
        self.assertEqual(payment.invoice, self.invoice)
        self.assertEqual(payment.payment_date, today)
        self.assertEqual(payment.amount, Decimal("100.50"))
        self.assertEqual(payment.payment_method, PaymentMethod.BANK_TRANSFER)
        self.assertEqual(payment.reference_number, "TXN12345")
        self.assertEqual(payment.notes, "Partial payment received.")

    def test_payment_date_default(self):
        """Test that payment_date defaults to today."""
        today = timezone.now().date()
        # Create payment without specifying payment_date
        payment = Payment.objects.create(
            invoice=self.invoice,
            amount=Decimal("50.00")
        )
        payment.refresh_from_db()
        self.assertEqual(payment.payment_date, today)

    def test_amount_validation_positive(self):
        """Test that the amount must be positive."""
        # Test zero amount
        with self.assertRaises(ValidationError):
            payment_zero = Payment(invoice=self.invoice, amount=Decimal("0.00"))
            payment_zero.full_clean() # full_clean() runs model validation

        # Test negative amount
        with self.assertRaises(ValidationError):
            payment_neg = Payment(invoice=self.invoice, amount=Decimal("-10.00"))
            payment_neg.full_clean()

        # Test valid amount (should not raise error)
        try:
            payment_ok = Payment(invoice=self.invoice, amount=Decimal("0.01"))
            payment_ok.full_clean()
        except ValidationError:
            self.fail("Positive amount validation failed unexpectedly.")

    def test_payment_str_representation(self):
        """Test the string representation of the payment."""
        payment_date=date(2025, 5, 4) # Use a fixed date for predictable string
        payment = Payment.objects.create(
            invoice=self.invoice,
            payment_date=payment_date,
            amount=Decimal("75.25")
        )
        # Using RM as hardcoded in __str__ for now
        expected_str = f"Payment of RM 75.25 for Invoice {self.invoice.invoice_number} on 2025-05-04"
        self.assertEqual(str(payment), expected_str)