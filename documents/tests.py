from django.test import TestCase
from decimal import Decimal
from django.utils import timezone
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.urls import reverse
from django.test import Client as TestClient
from django.contrib.auth import get_user_model


# Create your tests here.
from .models import (
    Client, MenuItem, Quotation, QuotationItem, Invoice, InvoiceItem,
    Setting, DiscountType, Payment, PaymentMethod, Order, OrderItem 
)

User = get_user_model()


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

    def test_create_revision(self):
        """
        Test the create_revision() method on the Quotation model.
        """
        # --- Setup: Create V1 with items ---
        quote_v1 = Quotation.objects.create(
            client=self.db_client,
            issue_date=date(2025, 5, 1), # Must have issue date if Sent
            title="Original Quote V1",
            terms_and_conditions="V1 Terms",
            notes="V1 Notes",
            discount_type=DiscountType.PERCENTAGE,
            discount_value=Decimal("10.00"),
            status=Quotation.Status.SENT # Start from a SENT state
        )
        quote_v1.refresh_from_db() # Get PK and number
        menu_item1 = MenuItem.objects.create(name="Rev Test Item 1", unit_price=100)
        menu_item2 = MenuItem.objects.create(name="Rev Test Item 2", unit_price=20)

        item1_v1 = QuotationItem.objects.create(
            quotation=quote_v1, menu_item=menu_item1, quantity=1, unit_price=100, description="Desc A", grouping_label="G1"
        )
        item2_v1 = QuotationItem.objects.create(
            quotation=quote_v1, menu_item=menu_item2, quantity=2, unit_price=25, description="Desc B", grouping_label="G2" # Price override
        )
        original_item_count = quote_v1.items.count()
        self.assertEqual(original_item_count, 2)

        # --- Action: Create the revision ---
        quote_v2 = quote_v1.create_revision()

        # --- Assertions ---
        # Check V2 exists and basic properties
        self.assertIsNotNone(quote_v2)
        self.assertIsInstance(quote_v2, Quotation)
        self.assertEqual(quote_v2.status, Quotation.Status.DRAFT)
        self.assertEqual(quote_v2.version, quote_v1.version + 1) # Should be 2
        self.assertEqual(quote_v2.previous_version, quote_v1)
        self.assertIsNotNone(quote_v2.quotation_number) # Should have a new number
        self.assertNotEqual(quote_v2.quotation_number, quote_v1.quotation_number)
        self.assertIsNone(quote_v2.issue_date) # Dates should be reset
        self.assertIsNone(quote_v2.valid_until)

        # Check copied fields
        self.assertEqual(quote_v2.client, quote_v1.client)
        self.assertEqual(quote_v2.title, quote_v1.title)
        self.assertEqual(quote_v2.terms_and_conditions, quote_v1.terms_and_conditions)
        self.assertEqual(quote_v2.notes, quote_v1.notes)
        self.assertEqual(quote_v2.discount_type, quote_v1.discount_type)
        self.assertEqual(quote_v2.discount_value, quote_v1.discount_value)

        # Check original quote status updated
        quote_v1.refresh_from_db() # Refresh V1 to get its updated status
        self.assertEqual(quote_v1.status, Quotation.Status.SUPERSEDED)

        # Check items copied correctly
        self.assertEqual(quote_v2.items.count(), original_item_count)
        v1_items = list(QuotationItem.objects.filter(quotation=quote_v1).order_by('pk'))
        v2_items = list(quote_v2.items.all().order_by('pk')) # Fetch items from V2

        for i in range(original_item_count):
            self.assertEqual(v2_items[i].menu_item, v1_items[i].menu_item)
            self.assertEqual(v2_items[i].description, v1_items[i].description)
            self.assertEqual(v2_items[i].quantity, v1_items[i].quantity)
            self.assertEqual(v2_items[i].unit_price, v1_items[i].unit_price) # Crucial check
            self.assertEqual(v2_items[i].grouping_label, v1_items[i].grouping_label)
            self.assertNotEqual(v2_items[i].pk, v1_items[i].pk) # Ensure they are new item records
            self.assertEqual(v2_items[i].quotation, quote_v2) # Ensure linked to V2

    def test_create_revision_from_invalid_status(self):
        """Test that revising a Draft or Superseded quote doesn't work."""
        draft_quote = Quotation.objects.create(client=self.db_client, status=Quotation.Status.DRAFT)
        superseded_quote = Quotation.objects.create(client=self.db_client, status=Quotation.Status.SUPERSEDED)

        self.assertIsNone(draft_quote.create_revision(), "Should not revise a Draft")
        self.assertIsNone(superseded_quote.create_revision(), "Should not revise a Superseded quote")

        # Ensure original statuses didn't change
        self.assertEqual(draft_quote.status, Quotation.Status.DRAFT)
        self.assertEqual(superseded_quote.status, Quotation.Status.SUPERSEDED)

    def test_finalize_quotation(self):
        """
        Test the finalize() method on the Quotation model.
        """
        # --- Setup: Configure default validity days in Settings ---
        settings = Setting.get_solo()
        settings.default_validity_days = 10 # Use 10 days for this test
        settings.save()

        today = timezone.now().date()

        # --- Scenario 1: Finalize a Draft with unset dates ---
        draft_quote1 = Quotation.objects.create(
            client=self.db_client,
            status=Quotation.Status.DRAFT
            # issue_date and valid_until are None
        )
        self.assertTrue(draft_quote1.finalize(), "Finalizing draft_quote1 should succeed")
        draft_quote1.refresh_from_db()

        self.assertEqual(draft_quote1.status, Quotation.Status.SENT)
        self.assertEqual(draft_quote1.issue_date, today)
        self.assertEqual(draft_quote1.valid_until, today + timedelta(days=10))

        # --- Scenario 2: Finalize a Draft with issue_date pre-set, valid_until not set ---
        preset_issue_date = date(2025, 6, 1)
        draft_quote2 = Quotation.objects.create(
            client=self.db_client,
            status=Quotation.Status.DRAFT,
            issue_date=preset_issue_date
        )
        self.assertTrue(draft_quote2.finalize(), "Finalizing draft_quote2 should succeed")
        draft_quote2.refresh_from_db()

        self.assertEqual(draft_quote2.status, Quotation.Status.SENT)
        self.assertEqual(draft_quote2.issue_date, preset_issue_date) # Should keep preset date
        self.assertEqual(draft_quote2.valid_until, preset_issue_date + timedelta(days=10))

        # --- Scenario 3: Finalize a Draft with both dates pre-set ---
        preset_issue_date_manual = date(2025, 6, 5)
        preset_valid_until_manual = date(2025, 6, 20) # 15 days
        draft_quote3 = Quotation.objects.create(
            client=self.db_client,
            status=Quotation.Status.DRAFT,
            issue_date=preset_issue_date_manual,
            valid_until=preset_valid_until_manual
        )
        self.assertTrue(draft_quote3.finalize(), "Finalizing draft_quote3 should succeed")
        draft_quote3.refresh_from_db()

        self.assertEqual(draft_quote3.status, Quotation.Status.SENT)
        self.assertEqual(draft_quote3.issue_date, preset_issue_date_manual) # Should keep preset date
        self.assertEqual(draft_quote3.valid_until, preset_valid_until_manual) # Should keep preset date

        # --- Scenario 4: Try to finalize a non-Draft quote ---
        sent_quote = Quotation.objects.create(
            client=self.db_client,
            status=Quotation.Status.SENT, # Already Sent
            issue_date=today
        )
        original_issue_date = sent_quote.issue_date
        self.assertFalse(sent_quote.finalize(), "Finalizing a Sent quote should fail (return False)")
        sent_quote.refresh_from_db()
        self.assertEqual(sent_quote.status, Quotation.Status.SENT) # Status should remain SENT
        self.assertEqual(sent_quote.issue_date, original_issue_date) # Dates should not change

    def test_revert_quotation_to_draft(self):
        """
        Test the revert_to_draft() method on the Quotation model.
        """
        # --- Setup: Create a SENT quote ---
        settings = Setting.get_solo() # Ensure settings are loaded if needed by finalize
        settings.default_validity_days = 10
        settings.save()

        issue_date_for_sent_quote = date(2025, 5, 7) # Use a fixed date for testing
        sent_quote = Quotation.objects.create(
            client=self.db_client,
            status=Quotation.Status.DRAFT, # Start as draft
            issue_date=None, # Explicitly None for finalize to set
            valid_until=None # Explicitly None for finalize to set
        )
        # Finalize it to make it SENT and populate dates
        self.assertTrue(sent_quote.finalize(), "Finalizing quote for revert test should succeed.")
        sent_quote.refresh_from_db()
        self.assertEqual(sent_quote.status, Quotation.Status.SENT)
        self.assertIsNotNone(sent_quote.issue_date)
        self.assertIsNotNone(sent_quote.valid_until)

        # --- Scenario 1: Revert a SENT quote ---
        revert_success = sent_quote.revert_to_draft()
        self.assertTrue(revert_success, "Reverting a SENT quote to draft should succeed.")
        sent_quote.refresh_from_db()

        self.assertEqual(sent_quote.status, Quotation.Status.DRAFT)
        self.assertIsNone(sent_quote.issue_date, "Issue date should be cleared when reverted to draft.")
        self.assertIsNone(sent_quote.valid_until, "Valid until date should be cleared when reverted to draft.")

        # --- Scenario 2: Attempt to revert a DRAFT quote (should fail) ---
        # The quote is already DRAFT from the previous step
        self.assertFalse(sent_quote.revert_to_draft(), "Reverting an already DRAFT quote should fail (return False).")
        self.assertEqual(sent_quote.status, Quotation.Status.DRAFT) # Should remain DRAFT

        # --- Scenario 3: Attempt to revert other non-SENT statuses (should fail) ---
        statuses_to_test = [
            Quotation.Status.ACCEPTED,
            Quotation.Status.REJECTED,
            Quotation.Status.SUPERSEDED
        ]
        for invalid_status in statuses_to_test:
            other_quote = Quotation.objects.create(
                client=self.db_client,
                status=invalid_status,
                issue_date=date(2025, 1, 1) # Give it some dates
            )
            self.assertFalse(other_quote.revert_to_draft(), f"Reverting a {invalid_status} quote should fail.")
            other_quote.refresh_from_db()
            self.assertEqual(other_quote.status, invalid_status, f"Status for {invalid_status} quote should not change.")

    
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

    def test_finalize_invoice(self):
        """
        Test the finalize() method on the Invoice model.
        """
        # --- Setup: Configure default payment terms in Settings ---
        settings = Setting.get_solo()
        settings.default_payment_terms_days = 14 # Use 14 days for this test
        settings.save()

        today = timezone.now().date()

        # --- Scenario 1: Finalize a Draft with unset dates ---
        draft_invoice1 = Invoice.objects.create(
            client=self.db_client, # Use client from setUpTestData
            status=Invoice.Status.DRAFT
            # issue_date and due_date are None
        )
        self.assertTrue(draft_invoice1.finalize(), "Finalizing draft_invoice1 should succeed")
        draft_invoice1.refresh_from_db()

        self.assertEqual(draft_invoice1.status, Invoice.Status.SENT)
        self.assertEqual(draft_invoice1.issue_date, today)
        self.assertEqual(draft_invoice1.due_date, today + timedelta(days=14))

        # --- Scenario 2: Finalize a Draft with issue_date pre-set, due_date not set ---
        preset_issue_date = date(2025, 8, 1)
        draft_invoice2 = Invoice.objects.create(
            client=self.db_client,
            status=Invoice.Status.DRAFT,
            issue_date=preset_issue_date
        )
        self.assertTrue(draft_invoice2.finalize(), "Finalizing draft_invoice2 should succeed")
        draft_invoice2.refresh_from_db()

        self.assertEqual(draft_invoice2.status, Invoice.Status.SENT)
        self.assertEqual(draft_invoice2.issue_date, preset_issue_date) # Should keep preset date
        self.assertEqual(draft_invoice2.due_date, preset_issue_date + timedelta(days=14))

        # --- Scenario 3: Finalize a Draft with both dates pre-set ---
        preset_issue_date_manual = date(2025, 8, 5)
        preset_due_date_manual = date(2025, 8, 25) # 20 days
        draft_invoice3 = Invoice.objects.create(
            client=self.db_client,
            status=Invoice.Status.DRAFT,
            issue_date=preset_issue_date_manual,
            due_date=preset_due_date_manual
        )
        self.assertTrue(draft_invoice3.finalize(), "Finalizing draft_invoice3 should succeed")
        draft_invoice3.refresh_from_db()

        self.assertEqual(draft_invoice3.status, Invoice.Status.SENT)
        self.assertEqual(draft_invoice3.issue_date, preset_issue_date_manual) # Should keep preset date
        self.assertEqual(draft_invoice3.due_date, preset_due_date_manual) # Should keep preset date

        # --- Scenario 4: Try to finalize a non-Draft invoice ---
        sent_invoice = Invoice.objects.create(
            client=self.db_client,
            status=Invoice.Status.SENT, # Already Sent
            issue_date=today
        )
        original_issue_date = sent_invoice.issue_date
        self.assertFalse(sent_invoice.finalize(), "Finalizing a Sent invoice should fail (return False)")
        sent_invoice.refresh_from_db()
        self.assertEqual(sent_invoice.status, Invoice.Status.SENT) # Status should remain SENT
        self.assertEqual(sent_invoice.issue_date, original_issue_date) # Dates should not change
    
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
        self.assertEqual(settings.default_payment_terms_days, 30) # Check new default (adjust if you chose a different default)

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
        cls.db_client = Client.objects.create(name="Client for Payments")
        # Create an invoice, explicitly setting issue date as it's now required before save
        cls.invoice = Invoice.objects.create(client=cls.db_client, issue_date=date(2025, 5, 1))
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
        # Test zero amount - uses self.invoice (which is DRAFT, validation fails - OK for assertRaises)
        # Note: The reason this raises ValidationError might now be the status check,
        # but assertRaises still passes, which is acceptable for this test's original purpose.
        with self.assertRaises(ValidationError):
            payment_zero = Payment(invoice=self.invoice, amount=Decimal("0.00"))
            payment_zero.full_clean() # Raises validation error (MinValue or Status)

        # Test negative amount - uses self.invoice (which is DRAFT, validation fails - OK for assertRaises)
        with self.assertRaises(ValidationError):
            payment_neg = Payment(invoice=self.invoice, amount=Decimal("-10.00"))
            payment_neg.full_clean() # Raises validation error (MinValue or Status)

        # Test valid amount (should not raise error)
        # --- Create a SENT invoice specifically for this check ---
        sent_invoice = Invoice.objects.create(
            client=self.db_client, # Use self.db_client from setUpTestData
            issue_date=date(2025, 5, 4),
            status=Invoice.Status.SENT # Set status to SENT
        )
        # --- End create SENT invoice ---
        try:
            # Use the sent_invoice here
            payment_ok = Payment(invoice=sent_invoice, amount=Decimal("0.01"))
            payment_ok.full_clean() # Should NOT raise ValidationError now
        except ValidationError as e:
            # If it fails, include the error message for easier debugging
            self.fail(f"Positive amount validation failed unexpectedly for SENT invoice: {e}")

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

    def test_payment_validation_for_invoice_status(self):
        """
        Test that Payments cannot be created for Draft or Cancelled invoices.
        """
        # Use a different client to avoid interference if needed
        client = Client.objects.create(name="Validation Client")

        # Scenario 1: Draft Invoice
        draft_invoice = Invoice.objects.create(
            client=client,
            issue_date=date(2025, 5, 4),
            status=Invoice.Status.DRAFT # Explicitly Draft
        )
        payment_for_draft = Payment(
            invoice=draft_invoice,
            amount=Decimal("50.00"),
            payment_date=date(2025, 5, 4)
        )
        with self.assertRaisesRegex(ValidationError, "status: DRAFT"):
            payment_for_draft.full_clean() # Should raise ValidationError

        # Scenario 2: Cancelled Invoice
        cancelled_invoice = Invoice.objects.create(
            client=client,
            issue_date=date(2025, 5, 4),
            status=Invoice.Status.CANCELLED # Explicitly Cancelled
        )
        payment_for_cancelled = Payment(
            invoice=cancelled_invoice,
            amount=Decimal("50.00"),
            payment_date=date(2025, 5, 4)
        )
        with self.assertRaisesRegex(ValidationError, "status: CANCELLED"):
            payment_for_cancelled.full_clean() # Should raise ValidationError

        # Scenario 3: Sent Invoice (Should PASS validation)
        sent_invoice = Invoice.objects.create(
            client=client,
            issue_date=date(2025, 5, 4),
            status=Invoice.Status.SENT # Explicitly Sent
        )
        payment_for_sent = Payment(
            invoice=sent_invoice,
            amount=Decimal("50.00"),
            payment_date=date(2025, 5, 4)
        )
        try:
            payment_for_sent.full_clean() # Should NOT raise ValidationError
        except ValidationError as e:
            self.fail(f"Validation failed unexpectedly for SENT invoice: {e}")


class OrderModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.db_client  = Client.objects.create(name="Client for Orders")
        # Create a quote to potentially link
        cls.quote = Quotation.objects.create(client=cls.db_client , issue_date=date(2025, 5, 1))
        cls.quote.refresh_from_db()

    def test_order_creation(self):
        """Test creating a basic order record."""
        order_event_date = date(2025, 6, 15)
        order = Order.objects.create(
            client=self.db_client ,
            related_quotation=self.quote,
            title="Wedding Catering Order",
            event_date=order_event_date,
            delivery_address="123 Event Hall Lane",
            notes="Allergic to nuts"
            # status defaults to CONFIRMED
        )
        # We will test auto-numbering later
        # order.refresh_from_db()

        self.assertEqual(order.client, self.db_client )
        self.assertEqual(order.related_quotation, self.quote)
        self.assertEqual(order.title, "Wedding Catering Order")
        self.assertEqual(order.status, Order.OrderStatus.CONFIRMED) # Check default
        self.assertEqual(order.event_date, order_event_date)
        self.assertEqual(order.delivery_address, "123 Event Hall Lane")
        self.assertEqual(order.notes, "Allergic to nuts")

    def test_order_str_representation(self):
        """Test the string representation includes the auto-generated number."""
        order = Order.objects.create(client=self.db_client)
        order.refresh_from_db() # Refresh to get the generated number

        # Construct expected number based on refreshed object
        expected_number = f"ORD-{order.created_at.year}-{order.pk}"
        expected_str = f"Order {expected_number} ({self.db_client.name})"
        self.assertEqual(str(order), expected_str)

    def test_order_number_auto_generation(self):
        """Test that order_number is generated correctly on first save."""
        order = Order.objects.create(client=self.db_client)

        # --- REMOVE THIS LINE ---
        # self.assertIsNone(order.order_number)
        # --- END REMOVE ---

        # Refresh from DB to ensure we definitely have the committed value
        order.refresh_from_db()

        # Check the format (these assertions are the important ones)
        expected_number = f"ORD-{order.created_at.year}-{order.pk}"
        self.assertIsNotNone(order.order_number)
        self.assertEqual(order.order_number, expected_number)
        
    def test_order_client_matches_quotation_client(self):
        """
        Test validation that Order.client must match Order.related_quotation.client.
        """
        # --- Setup: Create two clients and a quote for client A ---
        client_a = self.db_client # Use the client from setup
        client_b = Client.objects.create(name="Different Client Inc.")
        quote_for_a = Quotation.objects.create(client=client_a, issue_date=date(2025, 5, 4))
        quote_for_a.refresh_from_db() # Get PK if needed

        # --- Scenario 1: Mismatch - Should Fail Validation ---
        order_mismatch = Order(
            client=client_b, # Assign Client B
            related_quotation=quote_for_a, # Use Quote for Client A
            event_date=date(2025, 6, 1)
        )
        with self.assertRaises(ValidationError) as cm:
            order_mismatch.full_clean() # full_clean() triggers the clean() method

        # Optionally check the error messages targeting the specific fields
        self.assertIn('client', cm.exception.error_dict)
        self.assertIn('related_quotation', cm.exception.error_dict)
        self.assertIn("match the client", cm.exception.message_dict['client'][0])


        # --- Scenario 2: Match - Should Pass Validation ---
        order_match = Order(
            client=client_a, # Assign Client A
            related_quotation=quote_for_a, # Use Quote for Client A
            event_date=date(2025, 6, 2)
        )
        try:
            order_match.full_clean() # Should not raise ValidationError
        except ValidationError as e:
            self.fail(f"Validation failed unexpectedly when clients match: {e}")

        # --- Scenario 3: No Quote Linked - Should Pass Validation ---
        order_no_quote = Order(
            client=client_a, # Assign Client A
            related_quotation=None, # No quote linked
            event_date=date(2025, 6, 3)
        )
        try:
            order_no_quote.full_clean() # Should not raise ValidationError
        except ValidationError as e:
            self.fail(f"Validation failed unexpectedly when no quote is linked: {e}")

    def test_order_subtotal_and_discount(self):
        """Test subtotal and discount amount calculations for Order."""
        # --- Setup ---
        order = Order.objects.create(client=self.db_client, event_date=date(2025, 8, 1))
        menu_item = MenuItem.objects.create(name="Item for Order Disc Test", unit_price=Decimal("100.00"))
        # Add items: 1 * 100 = 100, 2 * 50 = 100. Subtotal = 200.00
        OrderItem.objects.create(order=order, menu_item=menu_item, quantity=1, unit_price=Decimal("100.00"))
        OrderItem.objects.create(order=order, menu_item=menu_item, quantity=2, unit_price=Decimal("50.00"))


        # --- Test subtotal ---
        self.assertEqual(order.subtotal, Decimal("200.00"))

        # --- Test No Discount ---
        order.discount_type = DiscountType.NONE
        order.discount_value = Decimal("10.00") # Value ignored
        order.save()
        self.assertEqual(order.discount_amount, Decimal("0.00"))

        # --- Test Percentage Discount (15% of 200 = 30.00) ---
        order.discount_type = DiscountType.PERCENTAGE
        order.discount_value = Decimal("15.00")
        order.save()
        self.assertEqual(order.discount_amount, Decimal("30.00"))

        # --- Test Fixed Discount (RM 50.00) ---
        order.discount_type = DiscountType.FIXED
        order.discount_value = Decimal("50.00")
        order.save()
        self.assertEqual(order.discount_amount, Decimal("50.00"))

        # --- Test Fixed Discount exceeding subtotal ---
        order.discount_type = DiscountType.FIXED
        order.discount_value = Decimal("300.00")
        order.save()
        self.assertEqual(order.discount_amount, Decimal("200.00")) # Should cap at subtotal

    def test_order_tax_and_grand_total(self):
        """Test tax amount and grand total calculations for Order."""
        # --- Setup ---
        order = Order.objects.create(client=self.db_client, event_date=date(2025, 9, 1))
        menu_item = MenuItem.objects.create(name="Item for Order Tax Test", unit_price=Decimal("200.00"))
        # Add items: Subtotal = 200.00
        OrderItem.objects.create(order=order, menu_item=menu_item, quantity=1, unit_price=Decimal("200.00"))

        # Add Discount: Fixed RM 20.00. Total before tax = 180.00
        order.discount_type = DiscountType.FIXED
        order.discount_value = Decimal("20.00")
        order.save() # Save discount settings

        settings = Setting.get_solo() # Get settings instance

        # --- Test Case 1: Tax Disabled ---
        settings.tax_enabled = False
        settings.tax_rate = Decimal("6.00") # Rate doesn't matter if disabled
        settings.save()

        self.assertEqual(order.total_before_tax, Decimal("180.00")) # Subtotal - Discount
        self.assertEqual(order.tax_amount, Decimal("0.00"))     # Tax should be 0
        self.assertEqual(order.grand_total, Decimal("180.00"))   # Grand total = total before tax

        # --- Test Case 2: Tax Enabled (6% of 180.00 = 10.80) ---
        settings.tax_enabled = True
        settings.tax_rate = Decimal("6.00")
        settings.save()

        self.assertEqual(order.total_before_tax, Decimal("180.00")) # Should be unchanged
        self.assertEqual(order.tax_amount, Decimal("10.80"))      # 6% tax on 180.00
        self.assertEqual(order.grand_total, Decimal("190.80"))    # 180.00 + 10.80

    def test_create_invoice(self):
        """Test the create_invoice() method on the Order model."""
        # --- Setup: Create a Confirmed Order with items and details ---
        order = Order.objects.create(
            client=self.db_client,
            related_quotation=self.quote, # Use quote from setUpTestData
            title="Confirmed Order Title",
            status=Order.OrderStatus.CONFIRMED, # Must be confirmable status
            event_date=date(2025, 10, 15),
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("10.00")
        )
        order.refresh_from_db() # Get PK/Number

        menu_item1 = MenuItem.objects.create(name="Inv Create Item 1", unit_price=30)
        menu_item2 = MenuItem.objects.create(name="Inv Create Item 2", unit_price=40)
        item1 = OrderItem.objects.create(order=order, menu_item=menu_item1, quantity=2, unit_price=30, description="Desc X")
        item2 = OrderItem.objects.create(order=order, menu_item=menu_item2, quantity=1, unit_price=45, description="Desc Y") # Price override
        original_item_count = order.items.count()

        # --- Action: Create the invoice ---
        invoice = order.create_invoice()

        # --- Assertions: Check Invoice ---
        self.assertIsNotNone(invoice)
        self.assertIsInstance(invoice, Invoice)
        self.assertEqual(invoice.status, Invoice.Status.DRAFT)
        self.assertEqual(invoice.client, order.client)
        self.assertEqual(invoice.related_order, order)
        self.assertEqual(invoice.related_quotation, order.related_quotation)
        self.assertEqual(invoice.title, order.title)
        self.assertEqual(invoice.discount_type, order.discount_type)
        self.assertEqual(invoice.discount_value, order.discount_value)
        # Dates should be None initially
        self.assertIsNone(invoice.issue_date)
        self.assertIsNone(invoice.due_date)
        # Check basic __str__ to ensure no errors
        invoice.refresh_from_db() # Ensure number is loaded
        expected_str = f"Invoice {invoice.invoice_number} ({order.client.name})"
        self.assertEqual(str(invoice), expected_str)

        # --- Assertions: Check Invoice Items ---
        self.assertEqual(invoice.items.count(), original_item_count)
        order_items = list(order.items.all().order_by('pk'))
        invoice_items = list(invoice.items.all().order_by('pk'))

        for i in range(original_item_count):
            self.assertEqual(invoice_items[i].menu_item, order_items[i].menu_item)
            self.assertEqual(invoice_items[i].description, order_items[i].description)
            self.assertEqual(invoice_items[i].quantity, order_items[i].quantity)
            self.assertEqual(invoice_items[i].unit_price, order_items[i].unit_price) # Check price copied
            self.assertEqual(invoice_items[i].grouping_label, order_items[i].grouping_label)
            self.assertEqual(invoice_items[i].invoice, invoice) # Ensure linked correctly

    def test_create_invoice_from_invalid_status(self):
        """Test that creating an invoice from Pending/Cancelled order fails."""
        pending_order = Order.objects.create(client=self.db_client, status=Order.OrderStatus.PENDING)
        cancelled_order = Order.objects.create(client=self.db_client, status=Order.OrderStatus.CANCELLED)

        self.assertIsNone(pending_order.create_invoice(), "Should not create invoice from Pending order")
        self.assertIsNone(cancelled_order.create_invoice(), "Should not create invoice from Cancelled order")

        # Ensure original statuses didn't change
        self.assertEqual(pending_order.status, Order.OrderStatus.PENDING)
        self.assertEqual(cancelled_order.status, Order.OrderStatus.CANCELLED)


class OrderItemModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.client = Client.objects.create(name="Client for Order Items")
        cls.menu_item = MenuItem.objects.create(name="Order Item Test", unit_price=Decimal("50.00"))
        cls.order = Order.objects.create(client=cls.client, event_date=date(2025, 7, 1))
        # cls.order.refresh_from_db() # If needed for order number later

    def test_order_item_creation(self):
        """Test creating an order line item."""
        item = OrderItem.objects.create(
            order=self.order,
            menu_item=self.menu_item,
            description="Special instructions for order item",
            quantity=Decimal("10"),
            unit_price=Decimal("48.00"), # Agreed price for the order
            grouping_label="Main Course"
        )
        self.assertEqual(item.order, self.order)
        self.assertEqual(item.menu_item, self.menu_item)
        self.assertEqual(item.description, "Special instructions for order item")
        self.assertEqual(item.quantity, Decimal("10"))
        self.assertEqual(item.unit_price, Decimal("48.00"))
        self.assertEqual(item.grouping_label, "Main Course")

    def test_order_item_str_representation(self):
        """Test the string representation."""
        # self.order is created in setUpTestData and refreshed there
        item = OrderItem.objects.create(
            order=self.order, menu_item=self.menu_item, quantity=5, unit_price=50
        )
        # Use the actual order number now
        expected_str = f"5 x Order Item Test on Order {self.order.order_number}"
        self.assertEqual(str(item), expected_str)


    def test_order_item_line_total(self):
        """Test the line_total calculation property."""
        # This test will fail until the property exists
        item = OrderItem.objects.create(
            order=self.order,
            menu_item=self.menu_item,
            quantity=Decimal("2.5"),
            unit_price=Decimal("10.00") # 2.5 * 10.00 = 25.00
        )
        self.assertEqual(item.line_total, Decimal("25.00"))


class DocumentViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        # Create a user for login testing
        cls.test_user_email = 'testuser@example.com'
        cls.test_user_password = 'password123'
        cls.test_user = User.objects.create_user(
            # No username field, use email for identification if supported by custom manager later,
            # for default manager, username might still be technically required even if not used for login.
            # Let's assume email is sufficient for create_user if using allauth setup,
            # otherwise we might need: username=cls.test_user_email
            username=cls.test_user_email,
            email=cls.test_user_email,
            password=cls.test_user_password
        )
        # Need to set email as verified if mandatory verification is on
        # Easiest for testing is often to temporarily disable verification or use allauth test helpers,
        # but let's try setting it manually if possible. Requires importing EmailAddress.
        try:
            from allauth.account.models import EmailAddress
            EmailAddress.objects.create(
                user=cls.test_user,
                email=cls.test_user_email,
                primary=True,
                verified=True
            )
        except ImportError:
             print("WARNING: allauth EmailAddress model not found, cannot mark email as verified for test user.")

        Setting.get_solo() # Creates the singleton if it doesn't exist


        # Create some data to view
        cls.client_obj = Client.objects.create(name="Client for View Test")
        cls.quote1 = Quotation.objects.create(client=cls.client_obj, quotation_number="Q-VIEW-1", status=Quotation.Status.SENT, issue_date=date.today()) # Added issue_date
        cls.quote2 = Quotation.objects.create(client=cls.client_obj, quotation_number="Q-VIEW-2", status=Quotation.Status.DRAFT, issue_date=date.today()) # Added issue_date
        
        # Make sure quote numbers are generated if needed elsewhere
        cls.quote1.refresh_from_db()
        cls.quote2.refresh_from_db()

        # --- Add items to quote1 for detail view testing ---
        menu_item = MenuItem.objects.create(name="Detail Test Item", unit_price=Decimal("50.00"))
        QuotationItem.objects.create(quotation=cls.quote1, menu_item=menu_item, quantity=2, unit_price=Decimal("50.00")) # 100.00
        # --- End Add items ---

        # Need issue_date as it's required on save now (even if optional in model)
        # unless create allows None? Let's add it.
        today = date.today()
        cls.inv1 = Invoice.objects.create(client=cls.client_obj, issue_date=today, status=Invoice.Status.SENT)
        cls.inv2 = Invoice.objects.create(client=cls.client_obj, issue_date=today, status=Invoice.Status.DRAFT)
        # Refresh to get generated numbers
        cls.inv1.refresh_from_db()
        cls.inv2.refresh_from_db()

        # --- Add items and payment to inv1 for detail view testing ---
        menu_item_inv = MenuItem.objects.create(name="Inv Detail Item", unit_price=Decimal("80.00"))
        InvoiceItem.objects.create(invoice=cls.inv1, menu_item=menu_item_inv, quantity=1, unit_price=Decimal("80.00")) # 80.00
        InvoiceItem.objects.create(invoice=cls.inv1, menu_item=menu_item_inv, quantity=1, unit_price=Decimal("20.50")) # 20.50
        # Total = 100.50 (assuming no tax/discount for simplicity in this setup)
        Payment.objects.create(invoice=cls.inv1, amount=Decimal("50.00"), payment_date=today) # Add a partial payment
        # --- End Add items/payment ---


    def setUp(self):
        # Create a fresh test client for each test method
        self.client = TestClient() # Use the imported HTTP test client

    def test_quotation_list_view_logged_out_redirect(self):
        """Test that accessing the list view when logged out redirects to login."""
        list_url = reverse('documents:quotation_list')
        response = self.client.get(list_url)
        # Expect redirect status code (302)
        self.assertEqual(response.status_code, 302)
        # Expect redirect to login URL (fetching it dynamically is best)
        login_url = reverse('account_login') # Default allauth URL name
        self.assertRedirects(response, f"{login_url}?next={list_url}")

    def test_quotation_list_view_logged_in_success(self):
        """Test the list view loads correctly for a logged-in user."""
        list_url = reverse('documents:quotation_list')
        # Log the user in using the test client's login method
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        # Make request as logged-in user
        response = self.client.get(list_url)

        # Check response
        self.assertEqual(response.status_code, 200) # OK status
        self.assertTemplateUsed(response, 'documents/quotation_list.html') # Correct template
        self.assertTemplateUsed(response, 'base.html') # Uses base template
        self.assertContains(response, "Quotations") # Page title/heading
        self.assertIn('quotations', response.context) # Context variable exists
        # Check if specific quote numbers are present in the rendered HTML
        self.assertContains(response, self.quote1.quotation_number)
        self.assertContains(response, self.quote2.quotation_number)
        self.assertContains(response, self.client_obj.name) # Check client name appears


    def test_invoice_list_view_logged_out_redirect(self):
        """Test accessing invoice list view when logged out redirects to login."""
        list_url = reverse('documents:invoice_list')
        response = self.client.get(list_url) # Use the HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={list_url}")

    def test_invoice_list_view_logged_in_success(self):
        """Test the invoice list view loads correctly for a logged-in user."""
        list_url = reverse('documents:invoice_list')
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(list_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/invoice_list.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, "Invoices") # Page title/heading
        self.assertIn('invoices', response.context) # Context variable exists
        # Check if specific invoice numbers/client are present
        self.assertContains(response, self.inv1.invoice_number)
        self.assertContains(response, self.inv2.invoice_number)
        self.assertContains(response, self.client_obj.name)

    def test_quotation_detail_view_logged_out_redirect(self):
        """Test accessing detail view when logged out redirects to login."""
        detail_url = reverse('documents:quotation_detail', args=[self.quote1.pk])
        response = self.client.get(detail_url) # Use the HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={detail_url}")

    def test_quotation_detail_view_logged_in_success(self):
        """Test the detail view loads correctly for a logged-in user."""
        detail_url = reverse('documents:quotation_detail', args=[self.quote1.pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200) # OK status
        self.assertTemplateUsed(response, 'documents/quotation_detail.html') # Correct template
        self.assertTemplateUsed(response, 'base.html') # Uses base template
        self.assertContains(response, f"Quotation {self.quote1.quotation_number}") # Heading/Title check
        self.assertIn('quotation', response.context) # Context variable exists
        self.assertEqual(response.context['quotation'], self.quote1) # Correct quote object passed
        self.assertIn('items', response.context) # Items passed
        self.assertContains(response, "Detail Test Item") # Check item name rendered
        self.assertContains(response, "100.00") # Check item line total rendered (or grand total)

    def test_quotation_detail_view_not_found(self):
        """Test accessing detail view for a non-existent quote returns 404."""
        # Use a PK that is unlikely to exist
        invalid_pk = self.quote1.pk + self.quote2.pk + 100
        detail_url = reverse('documents:quotation_detail', args=[invalid_pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404) # Not Found status

    def test_invoice_detail_view_logged_out_redirect(self):
        """Test accessing invoice detail view when logged out redirects to login."""
        detail_url = reverse('documents:invoice_detail', args=[self.inv1.pk])
        response = self.client.get(detail_url) # Use the HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={detail_url}")

    def test_invoice_detail_view_logged_in_success(self):
        """Test the invoice detail view loads correctly for a logged-in user."""
        detail_url = reverse('documents:invoice_detail', args=[self.inv1.pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200) # OK status
        self.assertTemplateUsed(response, 'documents/invoice_detail.html') # Correct template
        self.assertTemplateUsed(response, 'base.html') # Uses base template
        self.assertContains(response, f"Invoice {self.inv1.invoice_number}") # Heading/Title check
        self.assertIn('invoice', response.context) # Context variable exists
        self.assertEqual(response.context['invoice'], self.inv1) # Correct invoice object passed
        self.assertIn('items', response.context) # Items passed
        self.assertContains(response, "Inv Detail Item") # Check item name rendered
        self.assertContains(response, "100.50") # Check grand total rendered (sum of 80 + 20.50)
        self.assertContains(response, "50.00") # Check amount paid rendered
        self.assertContains(response, "50.50") # Check balance due rendered (100.50 - 50.00)

    def test_invoice_detail_view_not_found(self):
        """Test accessing detail view for a non-existent invoice returns 404."""
        invalid_pk = self.inv1.pk + self.inv2.pk + 100
        detail_url = reverse('documents:invoice_detail', args=[invalid_pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404) # Not Found status
