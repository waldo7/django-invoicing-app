from django.test import TestCase, Client as TestClient
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import date, timedelta
from django.utils import timezone
from django.urls import reverse
from decimal import Decimal
from django import forms


# Create your tests here.
from .forms import (
    QuotationForm, QuotationItemFormSet, 
    InvoiceForm, InvoiceItemFormSet,
    OrderForm, OrderItemFormSet,
    ClientForm
)

from .models import (
    Client, MenuItem, Quotation, QuotationItem, Invoice, InvoiceItem,
    Setting, DiscountType, Payment, PaymentMethod, Order, OrderItem,
    DeliveryOrder, DeliveryOrderItem, DeliveryOrderStatus,
    CreditNote, CreditNoteItem, CreditNoteStatus 
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

    def test_create_order_from_quotation(self):
        """
        Test the create_order() method on the Quotation model.
        """
        # --- Setup: Create an ACCEPTED Quotation with items and details ---
        accepted_quote = Quotation.objects.create(
            client=self.db_client,
            # quotation_number will be auto-generated
            issue_date=date(2025, 5, 10), # Today's date: May 12, 2025
            title="Accepted Quote for Order",
            terms_and_conditions="Order Terms based on Quote",
            notes="Order Notes from Quote",
            discount_type=DiscountType.FIXED,
            discount_value=Decimal("15.00"),
            status=Quotation.Status.ACCEPTED # CRITICAL: Must be ACCEPTED
        )
        accepted_quote.refresh_from_db() # Get PK and number

        menu_item_for_order_test = MenuItem.objects.create(name="Order Create Test Item A", unit_price=Decimal("75.00"))
        # You can create another distinct menu item if needed for item2_quote, or reuse.
        # Let's create another for clarity, or reuse if distinctness isn't key to this part of the test.
        menu_item_B_for_order_test = MenuItem.objects.create(name="Order Create Test Item B", unit_price=Decimal("25.00"))
        
        item1_quote = QuotationItem.objects.create(
            quotation=accepted_quote, menu_item=menu_item_for_order_test, quantity=3, unit_price=Decimal("75.00"), description="Item X desc"
        )
        item2_quote = QuotationItem.objects.create(
            quotation=accepted_quote, menu_item=menu_item_B_for_order_test, quantity=1, unit_price=Decimal("25.00"), description="Item Y desc" # Using menu_item1 from setUpTestData
        )
        original_item_count = accepted_quote.items.count()
        self.assertEqual(original_item_count, 2)

        # --- Action: Create the order ---
        order = accepted_quote.create_order()

        # --- Assertions: Check Order ---
        self.assertIsNotNone(order, "Order creation should succeed for an accepted quote.")
        self.assertIsInstance(order, Order)
        self.assertEqual(order.status, Order.OrderStatus.CONFIRMED)
        self.assertEqual(order.client, accepted_quote.client)
        self.assertEqual(order.related_quotation, accepted_quote)
        self.assertEqual(order.title, accepted_quote.title)
        self.assertEqual(order.discount_type, accepted_quote.discount_type)
        self.assertEqual(order.discount_value, accepted_quote.discount_value)
        # self.assertEqual(order.terms_and_conditions, accepted_quote.terms_and_conditions)
        self.assertEqual(order.notes, accepted_quote.notes)
        self.assertIsNotNone(order.order_number) # Should be auto-generated

        # --- Assertions: Check Order Items ---
        self.assertEqual(order.items.count(), original_item_count)
        # Fetch items to compare details
        # Order them to ensure consistent comparison if order doesn't matter
        quote_items_qs = accepted_quote.items.all().order_by('menu_item__name')
        order_items_qs = order.items.all().order_by('menu_item__name')

        for q_item, o_item in zip(quote_items_qs, order_items_qs):
            self.assertEqual(o_item.menu_item, q_item.menu_item)
            self.assertEqual(o_item.description, q_item.description)
            self.assertEqual(o_item.quantity, q_item.quantity)
            self.assertEqual(o_item.unit_price, q_item.unit_price) # Crucial price copy
            self.assertEqual(o_item.grouping_label, q_item.grouping_label)
            # self.assertNotEqual(o_item.pk, q_item.pk) # Must be new item records
            self.assertEqual(o_item.order, order) # Must be linked to new order

        # --- Test Duplicate Prevention ---
        order_again = accepted_quote.create_order()
        self.assertIsNone(order_again, "Should not create a duplicate order from the same quote.")

        # --- Test Invalid Status for Order Creation ---
        draft_quote = Quotation.objects.create(client=self.db_client, status=Quotation.Status.DRAFT, issue_date=date.today())
        self.assertIsNone(draft_quote.create_order(), "Should not create order from Draft quote.")

        sent_quote = Quotation.objects.create(client=self.db_client, status=Quotation.Status.SENT, issue_date=date.today())
        self.assertIsNone(sent_quote.create_order(), "Should not create order from Sent quote.")
    
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

    def test_revert_invoice_to_draft(self):
        """
        Test the revert_to_draft() method on the Invoice model.
        """
        # --- Setup: Create a SENT invoice ---
        settings = Setting.get_solo()
        settings.default_payment_terms_days = 14 # Use 14 days for this test
        settings.save()

        today = timezone.now().date() # Correct for today: May 7, 2025
        sent_invoice = Invoice.objects.create(
            client=self.db_client,
            status=Invoice.Status.DRAFT, # Start as draft
            # issue_date and due_date will be set by finalize()
        )
        # Finalize it to make it SENT and populate dates
        self.assertTrue(sent_invoice.finalize(), "Finalizing invoice for revert test should succeed.")
        sent_invoice.refresh_from_db()
        self.assertEqual(sent_invoice.status, Invoice.Status.SENT)
        self.assertIsNotNone(sent_invoice.issue_date)
        self.assertIsNotNone(sent_invoice.due_date)
        original_issue_date_for_sent = sent_invoice.issue_date # Store for later comparison
        original_due_date_for_sent = sent_invoice.due_date

        # --- Scenario 1: Revert a SENT invoice ---
        revert_success = sent_invoice.revert_to_draft()
        self.assertTrue(revert_success, "Reverting a SENT invoice to draft should succeed.")
        sent_invoice.refresh_from_db()

        self.assertEqual(sent_invoice.status, Invoice.Status.DRAFT)
        self.assertIsNone(sent_invoice.issue_date, "Issue date should be cleared when reverted to draft.")
        self.assertIsNone(sent_invoice.due_date, "Due date should be cleared when reverted to draft.")

        # --- Scenario 2: Attempt to revert a DRAFT invoice (should fail) ---
        # The invoice is already DRAFT from the previous step
        self.assertFalse(sent_invoice.revert_to_draft(), "Reverting an already DRAFT invoice should fail (return False).")
        self.assertEqual(sent_invoice.status, Invoice.Status.DRAFT) # Should remain DRAFT

        # --- Scenario 3: Attempt to revert other non-SENT statuses (should fail) ---
        statuses_to_test = [
            Invoice.Status.PAID,
            Invoice.Status.PARTIALLY_PAID,
            Invoice.Status.CANCELLED
        ]
        for invalid_status in statuses_to_test:
            # Create a new invoice for each status test, setting dates as they would be set if it reached that state
            other_invoice = Invoice.objects.create(
                client=self.db_client,
                status=invalid_status,
                issue_date=today, # Give it some dates
                due_date=today + timedelta(days=settings.default_payment_terms_days)
            )
            self.assertFalse(other_invoice.revert_to_draft(), f"Reverting a {invalid_status} invoice should fail.")
            other_invoice.refresh_from_db()
            self.assertEqual(other_invoice.status, invalid_status, f"Status for {invalid_status} invoice should not change.")
            # Also check that dates weren't cleared
            self.assertIsNotNone(other_invoice.issue_date)
            self.assertIsNotNone(other_invoice.due_date)
    

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
        # 1. Create a user for login testing
        cls.test_user_email = 'testuser@example.com'
        cls.test_user_password = 'password123'
        cls.test_user = User.objects.create_user(
            username=cls.test_user_email,
            email=cls.test_user_email,
            password=cls.test_user_password
        )
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

        # 2. Ensure Settings exist
        Setting.get_solo()
        today = date.today() # Using May 12, 2025 based on current context

        # 3. Create a general client
        cls.client_obj = Client.objects.create(name="Client for View Test")

        # 4. Create Quotations
        # Quote 1 (for detail view, and to create a linked order from)
        cls.quote1 = Quotation.objects.create(
            client=cls.client_obj,
            status=Quotation.Status.DRAFT,
            issue_date=None, # Will be set by finalize
            title="Quote 1 for Detail & Order Test"
        )
        cls.quote1.finalize() # Sets status to SENT, sets issue_date
        cls.quote1.status = Quotation.Status.ACCEPTED # Manually change to ACCEPTED for create_order test
        cls.quote1.save(update_fields=['status'])
        cls.quote1.refresh_from_db() # Ensure all changes are reflected, including number

        menu_item_q1 = MenuItem.objects.create(name="Detail Test Item Q1", unit_price=Decimal("50.00"))
        QuotationItem.objects.create(quotation=cls.quote1, menu_item=menu_item_q1, quantity=2, unit_price=Decimal("50.00"))

        # Create the linked order for quote1
        cls.linked_order_for_quote1 = cls.quote1.create_order()
        if cls.linked_order_for_quote1:
            cls.linked_order_for_quote1.refresh_from_db()
        else:
            print("WARNING: cls.linked_order_for_quote1 was not created in setUpTestData for quote1.")


        # Quote 2 (DRAFT, specifically for update/edit tests, with exactly 2 items)
        cls.quote2 = Quotation.objects.create(
            client=cls.client_obj,
            # quotation_number="Q-VIEW-2", # Let signal handle it for consistency
            status=Quotation.Status.DRAFT,
            issue_date=None,
            title="Quote 2 for Editing"
        )
        cls.quote2.refresh_from_db()
        menu_item_q2_a = MenuItem.objects.create(name="Quote2 Edit Item A", unit_price=Decimal("25.00"), unit="ITEM")
        menu_item_q2_b = MenuItem.objects.create(name="Quote2 Edit Item B", unit_price=Decimal("70.00"), unit="ITEM")
        QuotationItem.objects.create(quotation=cls.quote2, menu_item=menu_item_q2_a, quantity=5, unit_price=Decimal("25.00"))
        QuotationItem.objects.create(quotation=cls.quote2, menu_item=menu_item_q2_b, quantity=1, unit_price=Decimal("70.00"))


        # 5. Create Invoices
        # Invoice 1 (SENT, for detail view, with items and payment)
        cls.inv1 = Invoice.objects.create(client=cls.client_obj, issue_date=None, status=Invoice.Status.DRAFT, title="Invoice 1 Detail")
        cls.inv1.finalize() # Sets to SENT, sets issue_date/due_date
        cls.inv1.refresh_from_db()

        menu_item_inv1 = MenuItem.objects.create(name="Inv Detail Item For Inv1", unit_price=Decimal("80.00"))
        InvoiceItem.objects.create(invoice=cls.inv1, menu_item=menu_item_inv1, quantity=1, unit_price=Decimal("80.00"))
        InvoiceItem.objects.create(invoice=cls.inv1, menu_item=menu_item_inv1, quantity=1, unit_price=Decimal("20.50"))
        Payment.objects.create(invoice=cls.inv1, amount=Decimal("50.00"), payment_date=today)

        # Invoice 2 (DRAFT, for update view, with items)
        cls.inv2 = Invoice.objects.create(client=cls.client_obj, issue_date=None, status=Invoice.Status.DRAFT, title="Invoice 2 Editing")
        cls.inv2.refresh_from_db()
        menu_item_inv2 = MenuItem.objects.create(name="Inv Edit Item for Inv2", unit_price=Decimal("10.00"))
        InvoiceItem.objects.create(invoice=cls.inv2, menu_item=menu_item_inv2, quantity=10, unit_price=Decimal("10.00"))
        InvoiceItem.objects.create(invoice=cls.inv2, menu_item=menu_item_inv2, quantity=5, unit_price=Decimal("11.00"))


        # 6. Create Orders
        # Order 1 (CONFIRMED, for detail/edit tests, with items)
        # Ensure menu_item_ord1 is defined before being used for order_completed too
        menu_item_ord1 = MenuItem.objects.create(name="Ord Detail/Edit Item", unit_price=Decimal("75.00"))
        cls.order1 = Order.objects.create(client=cls.client_obj, event_date=today, status=Order.OrderStatus.CONFIRMED, title="Order 1 for Editing")
        cls.order1.refresh_from_db()
        OrderItem.objects.create(order=cls.order1, menu_item=menu_item_ord1, quantity=2, unit_price=Decimal("75.00"))
        OrderItem.objects.create(order=cls.order1, menu_item=menu_item_ord1, quantity=1, unit_price=Decimal("70.00"))

        # Order 2 (IN_PROGRESS, for list view)
        cls.order2 = Order.objects.create(client=cls.client_obj, event_date=today - timedelta(days=5), status=Order.OrderStatus.IN_PROGRESS, title="Order 2 Past")
        cls.order2.refresh_from_db()

        # Order Completed (for non-editable status tests)
        cls.order_completed = Order.objects.create(
            client=cls.client_obj,
            event_date=today - timedelta(days=10),
            status=Order.OrderStatus.COMPLETED,
            title="Completed Order Test"
        )
        cls.order_completed.refresh_from_db()
        OrderItem.objects.create(order=cls.order_completed, menu_item=menu_item_ord1, quantity=1, unit_price=Decimal("60.00"))


        # 7. General MenuItems (for use in CREATE form tests, should be distinct from items used above if names need to be unique)
        cls.menu_item1 = MenuItem.objects.create(name="General Form Test Item A", unit_price=Decimal("25.00"), unit="ITEM")
        cls.menu_item2 = MenuItem.objects.create(name="General Form Test Item B", unit_price=Decimal("70.00"), unit="ITEM")


        # 8. Delivery Order (for DO PDF tests and other DO tests)
        cls.order1_item1_for_do = OrderItem.objects.filter(order=cls.order1).first()
        if not cls.order1_item1_for_do: # Fallback
            menu_item_do_fallback = MenuItem.objects.create(name="DO Fallback Item", unit_price=1)
            cls.order1_item1_for_do = OrderItem.objects.create(order=cls.order1, menu_item=menu_item_do_fallback, quantity=1, unit_price=1)

        cls.delivery_order1 = DeliveryOrder.objects.create(
            order=cls.order1,
            delivery_date=date(2025, 5, 11), # Using specific date from example
            status=DeliveryOrderStatus.PLANNED
        )
        cls.delivery_order1.refresh_from_db() # Get auto-generated do_number
        DeliveryOrderItem.objects.create(
            delivery_order=cls.delivery_order1,
            order_item=cls.order1_item1_for_do,
            quantity_delivered=cls.order1_item1_for_do.quantity
        )
    


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

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/quotation_detail.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, f"Quotation {self.quote1.quotation_number}")
        self.assertIn('quotation', response.context)
        self.assertEqual(response.context['quotation'], self.quote1)
        self.assertIn('items', response.context)
        self.assertContains(response, "Detail Test Item Q1") # Check item name from quote1

        # --- Add these assertions for linked orders ---
        self.assertIn('linked_orders', response.context)
        # Check if the specific linked order's number is present (if created successfully)
        if self.linked_order_for_quote1 and self.linked_order_for_quote1.order_number:
            self.assertContains(response, self.linked_order_for_quote1.order_number)
        elif self.linked_order_for_quote1: # If number wasn't generated but object exists
             self.assertContains(response, f"Order PK {self.linked_order_for_quote1.pk}")
        else:
            # If linked_order_for_quote1 is None, maybe check for "No orders" message
            # For this test, we expect an order to be linked.
            self.assertIsNotNone(self.linked_order_for_quote1, "Linked order should have been created in setUpTestData")

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

    def test_order_list_view_logged_out_redirect(self):
        """Test accessing order list view when logged out redirects to login."""
        list_url = reverse('documents:order_list')
        response = self.client.get(list_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={list_url}")

    def test_order_list_view_logged_in_success(self):
        """Test the order list view loads correctly for a logged-in user."""
        list_url = reverse('documents:order_list')
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(list_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/order_list.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, "Orders") # Page title/heading
        self.assertIn('orders', response.context) # Context variable
        # Check if specific order numbers/client are present
        self.assertContains(response, self.order1.order_number)
        self.assertContains(response, self.order2.order_number)
        self.assertContains(response, self.client_obj.name)

    def test_order_detail_view_logged_out_redirect(self):
        """Test accessing order detail view when logged out redirects to login."""
        detail_url = reverse('documents:order_detail', args=[self.order1.pk])
        response = self.client.get(detail_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={detail_url}")

    def test_order_detail_view_logged_in_success(self):
        """Test the order detail view loads correctly for a logged-in user."""
        detail_url = reverse('documents:order_detail', args=[self.order1.pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/order_detail.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, f"Order {self.order1.order_number}") # Heading/Title check
        self.assertIn('order', response.context) # Context variable
        self.assertEqual(response.context['order'], self.order1) # Correct order object
        self.assertContains(response, "Ord Detail/Edit Item") # Check item name rendered (add "/Edit")
        # Check one of the prices from the items
        self.assertContains(response, "75.00")
        # Check grand total (assuming no tax/discount set directly on this order for this test)
        # self.order1.grand_total should be 220.00 here
        self.assertContains(response, self.order1.grand_total)


    def test_order_detail_view_not_found(self):
        """Test accessing detail view for a non-existent order returns 404."""
        invalid_pk = self.order1.pk + self.order2.pk + 100 # A PK unlikely to exist
        detail_url = reverse('documents:order_detail', args=[invalid_pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404) # Not Found status

    def test_client_list_view_logged_out_redirect(self):
        """Test accessing client list view when logged out redirects to login."""
        list_url = reverse('documents:client_list')
        response = self.client.get(list_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={list_url}")

    def test_client_list_view_logged_in_success(self):
        """Test the client list view loads correctly for a logged-in user."""
        list_url = reverse('documents:client_list')
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(list_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/client_list.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, "Clients") # Page title/heading
        self.assertIn('clients', response.context) # Context variable
        # Check if the client created in setUpTestData is present
        self.assertContains(response, self.client_obj.name)
        # Check that the list of clients in context contains our client object
        self.assertIn(self.client_obj, response.context['clients'])

    def test_client_detail_view_logged_out_redirect(self):
        """Test accessing client detail view when logged out redirects to login."""
        # Use client_obj created in setUpTestData
        detail_url = reverse('documents:client_detail', args=[self.client_obj.pk])
        response = self.client.get(detail_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={detail_url}")

    def test_client_detail_view_logged_in_success(self):
        """Test the client detail view loads correctly for a logged-in user."""
        detail_url = reverse('documents:client_detail', args=[self.client_obj.pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/client_detail.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, f"Client: {self.client_obj.name}") # Heading/Title check
        self.assertIn('client', response.context) # Context variable
        self.assertEqual(response.context['client'], self.client_obj) # Correct client object
        self.assertIn('quotations', response.context) # Related documents
        self.assertIn('orders', response.context)
        self.assertIn('invoices', response.context)

        # Check if some data from the client and related documents are present
        self.assertContains(response, self.client_obj.email)
        # quote1 was linked to client_obj in setUpTestData
        if hasattr(self, 'quote1') and self.quote1.quotation_number:
             self.assertContains(response, self.quote1.quotation_number)
        # inv1 was linked to client_obj in setUpTestData
        if hasattr(self, 'inv1') and self.inv1.invoice_number:
            self.assertContains(response, self.inv1.invoice_number)
        # order1 was linked to client_obj in setUpTestData
        if hasattr(self, 'order1') and self.order1.order_number:
            self.assertContains(response, self.order1.order_number)


    def test_client_detail_view_not_found(self):
        """Test accessing detail view for a non-existent client returns 404."""
        # Calculate a PK that is very unlikely to exist
        invalid_pk = self.client_obj.pk + 1000
        detail_url = reverse('documents:client_detail', args=[invalid_pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404) # Not Found status


    def test_quotation_create_view_get_logged_out_redirect(self):
        """Test GET to create view when logged out redirects to login."""
        create_url = reverse('documents:quotation_create')
        response = self.client.get(create_url)
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={create_url}")

    def test_quotation_create_view_get_logged_in(self):
        """Test GET to create view when logged in shows the form."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        response = self.client.get(reverse('documents:quotation_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/quotation_form.html')
        self.assertIsInstance(response.context['form'], QuotationForm)
        self.assertIsInstance(response.context['item_formset'], forms.BaseInlineFormSet) # Check for formset type
        self.assertContains(response, "Create New Quotation")

    def test_quotation_create_view_post_valid_data(self):
        """Test POST to create view with valid data creates quotation and items."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:quotation_create')

        # Prepare POST data
        # Main form data
        quotation_data = {
            'client': self.client_obj.pk,
            'title': 'New Test Quotation via Form',
            'issue_date': '', # Optional for draft
            'valid_until': '', # Optional for draft
            'discount_type': DiscountType.NONE.value,
            'discount_value': '0.00',
            'terms_and_conditions': 'Test terms.',
            'notes': 'Test notes.',
        }
        # Formset data (prefix 'items' as used in view and template)
        # Management form data is crucial for formsets
        item_formset_data = {
            'items-TOTAL_FORMS': '2', # We are submitting two item forms
            'items-INITIAL_FORMS': '0', # No initial forms (it's a create view)
            'items-MIN_NUM_FORMS': '0', # Or whatever your min_num is
            'items-MAX_NUM_FORMS': '1000', # A high number

            # Data for item 0
            'items-0-menu_item': self.menu_item1.pk,
            'items-0-description': 'Description for item A',
            'items-0-quantity': '2.00',
            'items-0-unit_price': '25.00',
            'items-0-grouping_label': 'Group X',
            # 'items-0-DELETE': '', # Not deleting

            # Data for item 1
            'items-1-menu_item': self.menu_item2.pk,
            'items-1-description': 'Description for item B',
            'items-1-quantity': '1.00',
            'items-1-unit_price': '70.00',
            'items-1-grouping_label': 'Group Y',
            # 'items-1-DELETE': '', # Not deleting
        }
        post_data = {**quotation_data, **item_formset_data}

        response = self.client.post(create_url, post_data)

        error_message_detail = ""
        if response.status_code != 302: # If we didn't get the expected redirect
            if response.context:
                form_errors = response.context.get('form').errors if hasattr(response.context.get('form'), 'errors') else 'N/A'
                item_formset_errors = response.context.get('item_formset').errors if hasattr(response.context.get('item_formset'), 'errors') else 'N/A'
                error_message_detail = f" Form errors: {form_errors}, Item formset errors: {item_formset_errors}"
            else:
                error_message_detail = " No context available in response."

        # Should redirect to detail view of the new quotation
        self.assertEqual(
            response.status_code,
            302,
            f"Expected redirect (302), got {response.status_code}.{error_message_detail}"
        )
        
        # Verify quotation created
        new_quote = Quotation.objects.latest('pk') # Get the instance with the highest PK (most recent)
        self.assertIsNotNone(new_quote)
        self.assertEqual(new_quote.title, 'New Test Quotation via Form')
        self.assertEqual(new_quote.client, self.client_obj)
        self.assertEqual(new_quote.status, Quotation.Status.DRAFT)
        self.assertEqual(new_quote.version, 1)
        self.assertEqual(new_quote.items.count(), 2) # Check two items were created

        # Check details of one item
        item_a = new_quote.items.get(menu_item=self.menu_item1)
        self.assertEqual(item_a.quantity, Decimal('2.00'))
        self.assertEqual(item_a.unit_price, Decimal('25.00'))

    def test_quotation_create_view_post_invalid_main_form(self):
        """Test POST with invalid main form data re-renders form with errors."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:quotation_create')
        # Invalid: Missing client
        quotation_data = {
            'title': 'Invalid Quotation',
        }
        item_formset_data = { # Need valid management form at least
            'items-TOTAL_FORMS': '0',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
        }
        post_data = {**quotation_data, **item_formset_data}

        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 200) # Should re-render form
        self.assertTemplateUsed(response, 'documents/quotation_form.html')
        self.assertIn('form', response.context)
        self.assertTrue(response.context['form'].errors) # Check for errors
        self.assertContains(response, "Please correct the errors below.")

    def test_quotation_create_view_post_invalid_item_formset(self):
        """Test POST with invalid item formset data re-renders form with errors."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:quotation_create')
        quotation_data = {
            'client': self.client_obj.pk,
            'title': 'Quote with Invalid Item',
        }
        item_formset_data = {
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-menu_item': self.menu_item1.pk,
            'items-0-quantity': '', # Invalid: missing quantity
            'items-0-unit_price': '10.00',
        }
        post_data = {**quotation_data, **item_formset_data}

        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/quotation_form.html')
        self.assertIn('item_formset', response.context)
        self.assertTrue(response.context['item_formset'].errors or response.context['item_formset'].non_form_errors())
        self.assertContains(response, "Please correct the errors below.")

    def test_invoice_create_view_get_logged_out_redirect(self):
        """Test GET to invoice create view when logged out redirects."""
        create_url = reverse('documents:invoice_create')
        response = self.client.get(create_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={create_url}")

    def test_invoice_create_view_get_logged_in(self):
        """Test GET to invoice create view when logged in shows the form."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        response = self.client.get(reverse('documents:invoice_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/invoice_form.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertIsInstance(response.context['form'], InvoiceForm)
        self.assertIsInstance(response.context['item_formset'], forms.BaseInlineFormSet)
        self.assertContains(response, "Create New Invoice")

    def test_invoice_create_view_post_valid_data(self):
        """Test POST to create view with valid data creates invoice and items."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:invoice_create')

        # Prepare POST data (using cls.client_obj, cls.menu_item1 from setUpTestData)
        invoice_data = {
            'client': self.client_obj.pk,
            'title': 'New Test Invoice via Form',
            'issue_date': '', # Optional for draft
            'due_date': '', # Optional for draft
            'discount_type': DiscountType.NONE.value,
            'discount_value': '0.00',
            'payment_details': 'Pay Here Ltd.',
        }
        item_formset_data = {
            'items-TOTAL_FORMS': '1', # Submitting one item form
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-menu_item': self.menu_item1.pk,
            'items-0-description': 'Invoice Item Desc A',
            'items-0-quantity': '3.00',
            'items-0-unit_price': '25.00', # Use the price from menu_item1
            'items-0-grouping_label': '',
        }
        post_data = {**invoice_data, **item_formset_data}

        response = self.client.post(create_url, post_data)

        # Check for redirect after successful creation
        self.assertEqual(response.status_code, 302, f"Form errors: {response.context.get('form').errors if response.context else 'No Context'}, Item formset errors: {response.context.get('item_formset').errors if response.context else 'No Context'}")

        # Verify invoice created
        new_invoice = Invoice.objects.filter(title='New Test Invoice via Form').order_by('-created_at').first()
        self.assertIsNotNone(new_invoice)
        self.assertEqual(new_invoice.client, self.client_obj)
        self.assertEqual(new_invoice.status, Invoice.Status.DRAFT)
        self.assertEqual(new_invoice.items.count(), 1)

        # Check item details
        item_a = new_invoice.items.first()
        self.assertEqual(item_a.menu_item, self.menu_item1)
        self.assertEqual(item_a.quantity, Decimal('3.00'))
        self.assertEqual(item_a.unit_price, Decimal('25.00'))

    def test_invoice_create_view_post_invalid_main_form(self):
        """Test POST with invalid main form data re-renders form with errors."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:invoice_create')
        # Invalid: Missing client
        invoice_data = {'title': 'Invalid Invoice'}
        item_formset_data = { # Need valid management form
            'items-TOTAL_FORMS': '0', 'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',
        }
        post_data = {**invoice_data, **item_formset_data}

        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 200) # Re-renders form
        self.assertTemplateUsed(response, 'documents/invoice_form.html')
        self.assertTrue(response.context['form'].errors) # Check for errors

    def test_invoice_create_view_post_invalid_item_formset(self):
        """Test POST with invalid item formset data re-renders form with errors."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:invoice_create')
        invoice_data = {
            'client': self.client_obj.pk,
            'title': 'Invoice with Invalid Item',
        }
        item_formset_data = {
            'items-TOTAL_FORMS': '1', 'items-INITIAL_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-menu_item': self.menu_item1.pk,
            'items-0-quantity': '', # Invalid: missing quantity
            'items-0-unit_price': '', # Invalid: missing price
        }
        post_data = {**invoice_data, **item_formset_data}

        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/invoice_form.html')
        self.assertTrue(response.context['item_formset'].errors or response.context['item_formset'].non_form_errors())

    def test_quotation_update_view_get_logged_out_redirect(self):
        """Test GET to update view when logged out redirects."""
        update_url = reverse('documents:quotation_update', args=[self.quote2.pk]) # Use Draft quote
        response = self.client.get(update_url)
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={update_url}")

    def test_quotation_update_view_get_not_draft(self):
        """Test GET to update view for non-draft quote redirects to detail."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:quotation_update', args=[self.quote1.pk]) # Use SENT quote
        response = self.client.get(update_url)
        # Should redirect back to the detail page
        self.assertEqual(response.status_code, 302)
        detail_url = reverse('documents:quotation_detail', args=[self.quote1.pk])
        self.assertRedirects(response, detail_url)

    def test_quotation_update_view_get_draft(self):
        """Test GET to update view for draft quote loads form correctly."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:quotation_update', args=[self.quote2.pk]) # Use DRAFT quote
        response = self.client.get(update_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/quotation_form.html')
        self.assertIsInstance(response.context['form'], QuotationForm)
        self.assertIsInstance(response.context['item_formset'], forms.BaseInlineFormSet)
        self.assertEqual(response.context['form'].instance, self.quote2) # Check form bound to instance
        self.assertEqual(response.context['item_formset'].instance, self.quote2) # Check formset bound
        self.assertContains(response, f"Edit Quotation {self.quote2.quotation_number}") # Check title/heading
        self.assertContains(response, self.client_obj.name) # Check client selected
        self.assertContains(response, "Quote2 Edit Item A") # Or "Quote2 Edit Item B"

    def test_quotation_update_view_post_valid_data(self):
        """Test POST to update view with valid data updates quotation and items."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:quotation_update', args=[self.quote2.pk]) # Edit Draft quote

        # Fetch existing items to get their PKs for the formset data
        existing_items = list(self.quote2.items.all().order_by('pk'))
        self.assertEqual(len(existing_items), 2) # Should have 2 from setup

        # Prepare POST data - simulate updating details and items
        quotation_data = {
            'client': self.quote2.client.pk,
            'title': 'UPDATED Quote Title',
            'issue_date': '',
            'valid_until': '',
            'discount_type': DiscountType.PERCENTAGE.value, # Change discount
            'discount_value': '5.00', # Set 5% discount
            'terms_and_conditions': 'Updated terms.',
            'notes': 'Updated notes.',
        }
        # Formset data: update item 0, delete item 1, add item 2
        item_formset_data = {
            'items-TOTAL_FORMS': '3', # One original updated, one original deleted, one new
            'items-INITIAL_FORMS': '2', # Started with 2 items
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',

            # Data for item 0 (Update existing_items[0])
            'items-0-id': existing_items[0].pk, # IMPORTANT: Include ID for existing forms
            'items-0-menu_item': existing_items[0].menu_item.pk,
            'items-0-description': existing_items[0].description,
            'items-0-quantity': '3.00', # Change quantity
            'items-0-unit_price': existing_items[0].unit_price,
            'items-0-grouping_label': existing_items[0].grouping_label,
            'items-0-DELETE': '', # Do not delete

            # Data for item 1 (Delete existing_items[1])
            'items-1-id': existing_items[1].pk, # IMPORTANT: Include ID
            'items-1-menu_item': existing_items[1].menu_item.pk,
            'items-1-description': existing_items[1].description,
            'items-1-quantity': existing_items[1].quantity,
            'items-1-unit_price': existing_items[1].unit_price,
            'items-1-grouping_label': existing_items[1].grouping_label,
            'items-1-DELETE': 'on', # Mark for deletion

            # Data for item 2 (New item)
            'items-2-id': '', # IMPORTANT: Empty ID for new forms
            'items-2-menu_item': self.menu_item1.pk, # Use a menu item
            'items-2-description': 'A brand new item',
            'items-2-quantity': '1.00',
            'items-2-unit_price': '99.00',
            'items-2-grouping_label': 'Group New',
            'items-2-DELETE': '', # Do not delete
        }
        post_data = {**quotation_data, **item_formset_data}

        response = self.client.post(update_url, post_data)

        # Should redirect to detail view after successful update
        self.assertEqual(response.status_code, 302, f"Form errors: {response.context.get('form').errors if response.context else 'No Context'}, Item formset errors: {response.context.get('item_formset').errors if response.context else 'No Context'}")
        detail_url = reverse('documents:quotation_detail', args=[self.quote2.pk])
        self.assertRedirects(response, detail_url)

        # Verify changes saved
        self.quote2.refresh_from_db()
        self.assertEqual(self.quote2.title, 'UPDATED Quote Title')
        self.assertEqual(self.quote2.discount_type, DiscountType.PERCENTAGE)
        self.assertEqual(self.quote2.discount_value, Decimal('5.00'))
        self.assertEqual(self.quote2.items.count(), 2) # 2 original + 1 new - 1 deleted = 2

        # Check updated item quantity
        updated_item_0 = self.quote2.items.get(pk=existing_items[0].pk)
        self.assertEqual(updated_item_0.quantity, Decimal('3.00'))

        # Check new item exists
        self.assertTrue(self.quote2.items.filter(description='A brand new item').exists())

        # Check deleted item is gone
        self.assertFalse(self.quote2.items.filter(pk=existing_items[1].pk).exists())

    def test_quotation_update_view_post_invalid_data(self):
        """Test POST to update view with invalid data re-renders form."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:quotation_update', args=[self.quote2.pk])
        # Invalid: Set quantity to non-number
        post_data = {
            'client': self.quote2.client.pk, 'title': 'Valid Title',
            'items-TOTAL_FORMS': '2', 'items-INITIAL_FORMS': '2',
            'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',
            'items-0-id': self.quote2.items.all()[0].pk,
            'items-0-menu_item': self.quote2.items.all()[0].menu_item.pk,
            'items-0-quantity': 'abc', # Invalid quantity
            'items-0-unit_price': '10.00',
            'items-1-id': self.quote2.items.all()[1].pk,
            'items-1-menu_item': self.quote2.items.all()[1].menu_item.pk,
            'items-1-quantity': '1',
            'items-1-unit_price': '10.00',
        }
        response = self.client.post(update_url, post_data)
        self.assertEqual(response.status_code, 200) # Re-render
        self.assertTemplateUsed(response, 'documents/quotation_form.html')
        self.assertTrue(response.context['item_formset'].errors) # Check formset errors

    def test_quotation_update_view_post_not_draft(self):
        """Test POST to update view for non-draft quote redirects."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:quotation_update', args=[self.quote1.pk]) # quote1 is SENT
        original_title = self.quote1.title
        post_data = { # Minimal valid-looking data
            'client': self.quote1.client.pk, 'title': 'Attempt Update Sent',
            'items-TOTAL_FORMS': '0', 'items-INITIAL_FORMS': '0', 'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',
        }
        response = self.client.post(update_url, post_data)
        self.assertEqual(response.status_code, 302) # Should redirect away
        detail_url = reverse('documents:quotation_detail', args=[self.quote1.pk])
        self.assertRedirects(response, detail_url)
        # Verify original data didn't change
        self.quote1.refresh_from_db()
        self.assertEqual(self.quote1.title, original_title) # Title should not be updated


    def test_invoice_update_view_get_logged_out_redirect(self):
        """Test GET to invoice update view when logged out redirects."""
        update_url = reverse('documents:invoice_update', args=[self.inv2.pk]) # Use Draft invoice
        response = self.client.get(update_url)
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={update_url}")

    def test_invoice_update_view_get_not_draft(self):
        """Test GET to update view for non-draft invoice redirects to detail."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:invoice_update', args=[self.inv1.pk]) # Use SENT invoice
        response = self.client.get(update_url)
        # Should redirect back to the detail page
        self.assertEqual(response.status_code, 302)
        detail_url = reverse('documents:invoice_detail', args=[self.inv1.pk])
        self.assertRedirects(response, detail_url)

    def test_invoice_update_view_get_draft(self):
        """Test GET to update view for draft invoice loads form correctly."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:invoice_update', args=[self.inv2.pk]) # Use DRAFT invoice
        response = self.client.get(update_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/invoice_form.html') # Reuses create template
        self.assertIsInstance(response.context['form'], InvoiceForm)
        self.assertIsInstance(response.context['item_formset'], forms.BaseInlineFormSet)
        self.assertEqual(response.context['form'].instance, self.inv2) # Check form bound to instance
        self.assertEqual(response.context['item_formset'].instance, self.inv2) # Check formset bound
        self.assertContains(response, f"Edit Invoice {self.inv2.invoice_number}") # Check title/heading
        self.assertContains(response, "Inv Edit Item") # Check item appears

    def test_invoice_update_view_post_valid_data(self):
        """Test POST to update view with valid data updates invoice and items."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:invoice_update', args=[self.inv2.pk]) # Edit Draft invoice

        existing_items = list(self.inv2.items.all().order_by('pk'))
        self.assertEqual(len(existing_items), 2) # Should have 2 from setup

        # Prepare POST data - simulate updating details and items
        invoice_data = {
            'client': self.inv2.client.pk,
            'title': 'UPDATED Invoice Title',
            'issue_date': '', # Still Draft
            'due_date': '',   # Still Draft
            'discount_type': DiscountType.FIXED.value, # Change discount
            'discount_value': '5.00',
            'payment_details': 'Updated payment details',
        }
        item_formset_data = {
            'items-TOTAL_FORMS': '3', # 2 initial + 1 extra = 3
            'items-INITIAL_FORMS': '2', # Started with 2 items
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',

            # Data for item 0 (Update existing_items[0])
            'items-0-id': existing_items[0].pk,
            'items-0-menu_item': existing_items[0].menu_item.pk,
            'items-0-quantity': '12.00', # Change quantity
            'items-0-unit_price': existing_items[0].unit_price,
            'items-0-DELETE': '',

            # Data for item 1 (Delete existing_items[1])
            'items-1-id': existing_items[1].pk,
            'items-1-menu_item': existing_items[1].menu_item.pk,
            'items-1-quantity': existing_items[1].quantity,
            'items-1-unit_price': existing_items[1].unit_price,
            'items-1-DELETE': 'on', # Mark for deletion

            # Data for item 2 (New item)
            'items-2-id': '',
            'items-2-menu_item': self.menu_item1.pk, # Use another menu item
            'items-2-description': 'A brand new invoice item',
            'items-2-quantity': '1.00',
            'items-2-unit_price': '55.00',
            'items-2-DELETE': '',
        }
        post_data = {**invoice_data, **item_formset_data}

        response = self.client.post(update_url, post_data)

        # Should redirect to detail view after successful update
        self.assertEqual(response.status_code, 302, f"Update Form errors: {response.context.get('form').errors if response.context else 'No Context'}, Item formset errors: {response.context.get('item_formset').errors if response.context else 'No Context'}")
        detail_url = reverse('documents:invoice_detail', args=[self.inv2.pk])
        self.assertRedirects(response, detail_url)

        # Verify changes saved
        self.inv2.refresh_from_db()
        self.assertEqual(self.inv2.title, 'UPDATED Invoice Title')
        self.assertEqual(self.inv2.discount_type, DiscountType.FIXED)
        self.assertEqual(self.inv2.items.count(), 2) # 2 original + 1 new - 1 deleted = 2

        # Check updated item quantity
        updated_item_0 = self.inv2.items.get(pk=existing_items[0].pk)
        self.assertEqual(updated_item_0.quantity, Decimal('12.00'))

        # Check new item exists
        self.assertTrue(self.inv2.items.filter(description='A brand new invoice item').exists())

        # Check deleted item is gone
        self.assertFalse(self.inv2.items.filter(pk=existing_items[1].pk).exists())

    def test_invoice_update_view_post_invalid_data(self):
        """Test POST to update view with invalid data re-renders form."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:invoice_update', args=[self.inv2.pk]) # Edit Draft invoice
        existing_items = list(self.inv2.items.all().order_by('pk'))

        # Invalid: Set quantity to non-number on existing item
        post_data = {
            'client': self.inv2.client.pk, 'title': 'Valid Update Title',
            'items-TOTAL_FORMS': '2', 'items-INITIAL_FORMS': '2', # Submitting the 2 existing
            'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',
            'items-0-id': existing_items[0].pk,
            'items-0-menu_item': existing_items[0].menu_item.pk,
            'items-0-quantity': 'invalid', # Invalid quantity
            'items-0-unit_price': '10.00',
            'items-1-id': existing_items[1].pk,
            'items-1-menu_item': existing_items[1].menu_item.pk,
            'items-1-quantity': '1',
            'items-1-unit_price': '10.00',
        }
        response = self.client.post(update_url, post_data)
        self.assertEqual(response.status_code, 200) # Re-render
        self.assertTemplateUsed(response, 'documents/invoice_form.html')
        self.assertTrue(response.context['item_formset'].errors) # Check formset errors

    def test_invoice_update_view_post_not_draft(self):
        """Test POST to update view for non-draft invoice redirects."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:invoice_update', args=[self.inv1.pk]) # inv1 is SENT
        original_title = self.inv1.title
        post_data = { # Minimal valid-looking data
            'client': self.inv1.client.pk, 'title': 'Attempt Update Sent Invoice',
            'items-TOTAL_FORMS': '0', 'items-INITIAL_FORMS': '0', 'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',
        }
        response = self.client.post(update_url, post_data)
        self.assertEqual(response.status_code, 302) # Should redirect away
        detail_url = reverse('documents:invoice_detail', args=[self.inv1.pk])
        self.assertRedirects(response, detail_url)
        # Verify original data didn't change
        self.inv1.refresh_from_db()
        self.assertEqual(self.inv1.title, original_title) # Title should not be updated

    def test_order_create_view_get_logged_out_redirect(self):
        """Test GET to order create view when logged out redirects."""
        create_url = reverse('documents:order_create')
        response = self.client.get(create_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={create_url}")

    def test_order_create_view_get_logged_in(self):
        """Test GET to order create view when logged in shows the form."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        response = self.client.get(reverse('documents:order_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/order_form.html') # Check correct template
        self.assertTemplateUsed(response, 'base.html')
        self.assertIsInstance(response.context['form'], OrderForm) # Check correct form
        self.assertIsInstance(response.context['item_formset'], forms.BaseInlineFormSet) # Check formset type
        self.assertContains(response, "Create New Order/Event")

    def test_order_create_view_post_valid_data(self):
        """Test POST to create view with valid data creates order and items."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:order_create')
        event_date_str = date(2025, 11, 15).strftime('%Y-%m-%d') # Format date for POST

        # Prepare POST data (using cls.client_obj, cls.menu_item1 from setUpTestData)
        order_data = {
            'client': self.client_obj.pk,
            'title': 'New Test Order via Form',
            'event_date': event_date_str,
            'discount_type': DiscountType.NONE.value,
            'discount_value': '0.00',
        }
        item_formset_data = {
            'items-TOTAL_FORMS': '1', # Submitting one item form
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-menu_item': self.menu_item1.pk,
            'items-0-description': 'Order Item Desc A',
            'items-0-quantity': '4.00',
            'items-0-unit_price': '25.00', # Use the price from menu_item1
            'items-0-grouping_label': '',
        }
        post_data = {**order_data, **item_formset_data}

        response = self.client.post(create_url, post_data)

        # Check for redirect after successful creation
        new_order = Order.objects.filter(title='New Test Order via Form').order_by('-created_at').first()
        self.assertIsNotNone(new_order, "Order should have been created.")
        # Check redirect (status code 302) - include form errors in message if fails
        error_message_detail = ""
        if response.status_code != 302 and response.context:
            form_errors = response.context.get('form').errors if hasattr(response.context.get('form'), 'errors') else 'N/A'
            item_formset_errors = response.context.get('item_formset').errors if hasattr(response.context.get('item_formset'), 'errors') else 'N/A'
            error_message_detail = f" Form errors: {form_errors}, Item formset errors: {item_formset_errors}"
        self.assertEqual(response.status_code, 302, f"Expected redirect (302), got {response.status_code}.{error_message_detail}")

        # Verify created order details
        self.assertEqual(new_order.client, self.client_obj)
        self.assertEqual(new_order.status, Order.OrderStatus.CONFIRMED) # Check default status
        self.assertEqual(new_order.items.count(), 1)

        # Check item details
        item_a = new_order.items.first()
        self.assertEqual(item_a.menu_item, self.menu_item1)
        self.assertEqual(item_a.quantity, Decimal('4.00'))
        self.assertEqual(item_a.unit_price, Decimal('25.00'))

        # Check redirect target
        detail_url = reverse('documents:order_detail', args=[new_order.pk])
        self.assertRedirects(response, detail_url)

    def test_order_create_view_post_invalid_main_form(self):
        """Test POST with invalid main form data re-renders form with errors."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:order_create')
        # Invalid: Missing client
        order_data = {'title': 'Invalid Order'}
        item_formset_data = { # Need valid management form
            'items-TOTAL_FORMS': '0', 'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',
        }
        post_data = {**order_data, **item_formset_data}

        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 200) # Re-renders form
        self.assertTemplateUsed(response, 'documents/order_form.html')
        self.assertTrue(response.context['form'].errors) # Check for errors

    def test_order_create_view_post_invalid_item_formset(self):
        """Test POST with invalid item formset data re-renders form with errors."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:order_create')
        order_data = {
            'client': self.client_obj.pk,
            'title': 'Order with Invalid Item',
        }
        item_formset_data = {
            'items-TOTAL_FORMS': '1', 'items-INITIAL_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            'items-0-menu_item': self.menu_item1.pk,
            'items-0-quantity': '', # Invalid: missing quantity
            'items-0-unit_price': '', # Invalid: missing price
        }
        post_data = {**order_data, **item_formset_data}

        response = self.client.post(create_url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/order_form.html')
        self.assertTrue(response.context['item_formset'].errors or response.context['item_formset'].non_form_errors())

    def test_order_update_view_get_logged_out_redirect(self):
        """Test GET to order update view when logged out redirects."""
        # Use order1 created in setUpTestData (status=CONFIRMED, editable)
        update_url = reverse('documents:order_update', args=[self.order1.pk])
        response = self.client.get(update_url)
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={update_url}")

    def test_order_update_view_get_not_editable_status(self):
        """Test GET to update view for non-editable order redirects to detail."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        # Use order_completed created in setUpTestData (status=COMPLETED)
        update_url = reverse('documents:order_update', args=[self.order_completed.pk])
        response = self.client.get(update_url)
        # Should redirect back to the detail page
        self.assertEqual(response.status_code, 302)
        detail_url = reverse('documents:order_detail', args=[self.order_completed.pk])
        self.assertRedirects(response, detail_url)
        # We can't easily check the message content with the basic test client

    def test_order_update_view_get_editable_status(self):
        """Test GET to update view for editable order loads form correctly."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
         # Use order1 created in setUpTestData (status=CONFIRMED)
        update_url = reverse('documents:order_update', args=[self.order1.pk])
        response = self.client.get(update_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/order_form.html') # Reuses create template
        self.assertIsInstance(response.context['form'], OrderForm)
        self.assertIsInstance(response.context['item_formset'], forms.BaseInlineFormSet)
        self.assertEqual(response.context['form'].instance, self.order1) # Check form bound
        self.assertEqual(response.context['item_formset'].instance, self.order1) # Check formset bound
        self.assertContains(response, f"Edit Order {self.order1.order_number}")
        self.assertContains(response, "Ord Detail/Edit Item") # Check item appears

    def test_order_update_view_post_valid_data(self):
        """Test POST to update view with valid data updates order and items."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:order_update', args=[self.order1.pk]) # Edit order1

        existing_items = list(self.order1.items.all().order_by('pk'))
        self.assertEqual(len(existing_items), 2) # Should have 2 from setup

        # Prepare POST data - simulate updating details and items
        order_data = {
            'client': self.order1.client.pk,
            'title': 'UPDATED Order 1 Title',
            'event_date': self.order1.event_date.strftime('%Y-%m-%d'),
            'discount_type': DiscountType.PERCENTAGE.value, # Change discount
            'discount_value': '2.5', # 2.5%
            'delivery_address': 'New Delivery Spot',
        }
        item_formset_data = {
            'items-TOTAL_FORMS': '3', # 2 initial + 1 extra
            'items-INITIAL_FORMS': '2',
            'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',

            # Item 0 (Update existing_items[0])
            'items-0-id': existing_items[0].pk,
            'items-0-menu_item': existing_items[0].menu_item.pk,
            'items-0-quantity': '1.00', # Change quantity
            'items-0-unit_price': existing_items[0].unit_price,
            'items-0-DELETE': '',

            # Item 1 (Delete existing_items[1])
            'items-1-id': existing_items[1].pk,
            'items-1-menu_item': existing_items[1].menu_item.pk,
            'items-1-quantity': existing_items[1].quantity,
            'items-1-unit_price': existing_items[1].unit_price,
            'items-1-DELETE': 'on', # Mark for deletion

            # Item 2 (New item)
            'items-2-id': '',
            'items-2-menu_item': self.menu_item2.pk, # Use General Test Item B
            'items-2-description': 'New order item added during edit',
            'items-2-quantity': '10.00',
            'items-2-unit_price': '70.00',
            'items-2-DELETE': '',
        }
        post_data = {**order_data, **item_formset_data}

        response = self.client.post(update_url, post_data)

        # Check redirect after successful update
        detail_url = reverse('documents:order_detail', args=[self.order1.pk])
        self.assertRedirects(response, detail_url, status_code=302, target_status_code=200)

        # Verify changes saved
        self.order1.refresh_from_db()
        self.assertEqual(self.order1.title, 'UPDATED Order 1 Title')
        self.assertEqual(self.order1.discount_type, DiscountType.PERCENTAGE)
        self.assertEqual(self.order1.items.count(), 2) # 2 original + 1 new - 1 deleted = 2

        updated_item_0 = self.order1.items.get(pk=existing_items[0].pk)
        self.assertEqual(updated_item_0.quantity, Decimal('1.00'))
        self.assertTrue(self.order1.items.filter(description='New order item added during edit').exists())
        self.assertFalse(self.order1.items.filter(pk=existing_items[1].pk).exists())

    def test_order_update_view_post_invalid_data(self):
        """Test POST to order update view with invalid data re-renders form."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:order_update', args=[self.order1.pk]) # Use editable order
        existing_items = list(self.order1.items.all().order_by('pk'))
        # Invalid: Blank quantity on existing item
        post_data = {
            'client': self.order1.client.pk, 'title': 'Invalid Order Update',
            'items-TOTAL_FORMS': '2', 'items-INITIAL_FORMS': '2',
            'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000',
            'items-0-id': existing_items[0].pk,
            'items-0-menu_item': existing_items[0].menu_item.pk,
            'items-0-quantity': '', # Invalid
            'items-0-unit_price': '10.00',
            'items-1-id': existing_items[1].pk,
            'items-1-menu_item': existing_items[1].menu_item.pk,
            'items-1-quantity': '1',
            'items-1-unit_price': '10.00',
        }
        response = self.client.post(update_url, post_data)
        self.assertEqual(response.status_code, 200) # Re-render
        self.assertTemplateUsed(response, 'documents/order_form.html')
        self.assertTrue(response.context['item_formset'].errors)

    def test_order_update_view_post_not_editable_status(self):
        """Test POST to update view for non-editable order redirects."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:order_update', args=[self.order_completed.pk]) # COMPLETED order
        original_title = self.order_completed.title
        post_data = { 'client': self.order_completed.client.pk, 'title': 'Attempt Update Completed Order' }
        response = self.client.post(update_url, post_data)
        self.assertEqual(response.status_code, 302) # Redirect away
        detail_url = reverse('documents:order_detail', args=[self.order_completed.pk])
        self.assertRedirects(response, detail_url)
        # Verify original data didn't change
        self.order_completed.refresh_from_db()
        self.assertEqual(self.order_completed.title, original_title)

    def test_client_create_view_get_logged_out_redirect(self):
        """Test GET to client create view when logged out redirects."""
        create_url = reverse('documents:client_create')
        response = self.client.get(create_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={create_url}")

    def test_client_create_view_get_logged_in(self):
        """Test GET to client create view when logged in shows the form."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        response = self.client.get(reverse('documents:client_create'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/client_form.html') # Check correct template
        self.assertTemplateUsed(response, 'base.html')
        self.assertIsInstance(response.context['form'], ClientForm) # Check correct form
        self.assertContains(response, "Add New Client")

    def test_client_create_view_post_valid_data(self):
        """Test POST to create view with valid data creates client."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:client_create')
        initial_client_count = Client.objects.count()

        client_data = {
            'name': 'New Client Via Form',
            'address': '123 Form Street',
            'email': 'formclient@example.com',
            'phone': '555-0001',
            'tax_id': 'TAXFORM123'
        }
        response = self.client.post(create_url, client_data)

        # Check for redirect after successful creation
        self.assertEqual(Client.objects.count(), initial_client_count + 1)
        new_client = Client.objects.get(name='New Client Via Form')
        self.assertIsNotNone(new_client)
        self.assertEqual(new_client.email, 'formclient@example.com')

        # Check redirect (status code 302)
        detail_url = reverse('documents:client_detail', args=[new_client.pk])
        self.assertRedirects(response, detail_url, status_code=302, target_status_code=200)

        # Check for success message (requires fetching the redirected page)
        # response_redirected = self.client.get(detail_url)
        # self.assertContains(response_redirected, "Client 'New Client Via Form' created successfully.")

    def test_client_create_view_post_invalid_data(self):
        """Test POST with invalid main form data re-renders form with errors."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        create_url = reverse('documents:client_create')
        # Invalid: Missing name (which is required)
        client_data = {
            'address': 'No Name Address',
            'email': 'noname@example.com'
        }
        response = self.client.post(create_url, client_data)

        self.assertEqual(response.status_code, 200) # Re-renders form
        self.assertTemplateUsed(response, 'documents/client_form.html')
        self.assertTrue(response.context['form'].errors) # Check for errors
        self.assertContains(response, "Please correct the errors below.")

    def test_client_update_view_get_logged_out_redirect(self):
        """Test GET to client update view when logged out redirects."""
        # Use client_obj created in setUpTestData
        update_url = reverse('documents:client_update', args=[self.client_obj.pk])
        response = self.client.get(update_url)
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={update_url}")

    def test_client_update_view_get_logged_in(self):
        """Test GET to client update view for logged-in user loads form correctly."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:client_update', args=[self.client_obj.pk])
        response = self.client.get(update_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/client_form.html') # Reuses create template
        self.assertIsInstance(response.context['form'], ClientForm)
        self.assertEqual(response.context['form'].instance, self.client_obj) # Check form bound
        self.assertContains(response, f"Edit Client: {self.client_obj.name}")
        # Check if an existing value from the client_obj is in the form
        self.assertContains(response, self.client_obj.name) # Original name should be in form value

    def test_client_update_view_post_valid_data(self):
        """Test POST to update view with valid data updates client."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:client_update', args=[self.client_obj.pk])
        original_name = self.client_obj.name
        new_name = "Updated Client Name Via Form"
        new_email = "updated_client@example.com"

        client_data = {
            'name': new_name,
            'address': self.client_obj.address, # Keep existing address or update
            'email': new_email,
            'phone': '555-9999', # New phone
            'tax_id': self.client_obj.tax_id # Keep existing tax_id or update
        }
        response = self.client.post(update_url, client_data)

        # Check redirect after successful update
        detail_url = reverse('documents:client_detail', args=[self.client_obj.pk])
        self.assertRedirects(response, detail_url, status_code=302, target_status_code=200)

        # Verify changes saved
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.name, new_name)
        self.assertEqual(self.client_obj.email, new_email)
        self.assertEqual(self.client_obj.phone, '555-9999')

        # Test success message (requires fetching the redirected page)
        # response_redirected = self.client.get(detail_url)
        # self.assertContains(response_redirected, f"Client '{new_name}' updated successfully.")


    def test_client_update_view_post_invalid_data(self):
        """Test POST to update view with invalid data re-renders form."""
        self.client.login(email=self.test_user_email, password=self.test_user_password)
        update_url = reverse('documents:client_update', args=[self.client_obj.pk])
        # Invalid: Blank name
        client_data = {
            'name': '', # Invalid
            'email': 'stillvalid@example.com'
        }
        response = self.client.post(update_url, client_data)

        self.assertEqual(response.status_code, 200) # Re-renders form
        self.assertTemplateUsed(response, 'documents/client_form.html')
        self.assertTrue(response.context['form'].errors) # Check for errors
        self.assertContains(response, "Please correct the errors below.")

    def test_generate_delivery_order_pdf_logged_out_redirect(self):
        """Test accessing DO PDF view when logged out redirects to login."""
        pdf_url = reverse('documents:delivery_order_pdf', args=[self.delivery_order1.pk])
        response = self.client.get(pdf_url)
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={pdf_url}")

    def test_generate_delivery_order_pdf_logged_in_success(self):
        """Test the DO PDF view generates a PDF for a logged-in user."""
        pdf_url = reverse('documents:delivery_order_pdf', args=[self.delivery_order1.pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(pdf_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        # Check for a reasonable filename in Content-Disposition
        # Filename will include the do_number (e.g., DO-2025-X.pdf)
        expected_filename_part = f"DO-{self.delivery_order1.do_number}"
        self.assertIn(f'filename="{expected_filename_part}', response['Content-Disposition'])
        self.assertIn("inline;", response['Content-Disposition']) # Should display inline

        # Check if the content looks like a PDF (starts with %PDF-)
        self.assertTrue(response.content.startswith(b'%PDF-'))
        # Optionally check for some key text from the DO if needed (more complex)
        # self.assertContains(response, self.delivery_order1.order.client.name, html=False) # html=False for PDF

    def test_generate_delivery_order_pdf_not_found(self):
        """Test accessing DO PDF view for a non-existent DO returns 404."""
        invalid_pk = self.delivery_order1.pk + 999 # A PK unlikely to exist
        pdf_url = reverse('documents:delivery_order_pdf', args=[invalid_pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(pdf_url)
        self.assertEqual(response.status_code, 404)

    def test_generate_order_pdf_logged_out_redirect(self):
        """Test accessing Order PDF view when logged out redirects to login."""
        # Use order1 created in setUpTestData
        pdf_url = reverse('documents:order_pdf', args=[self.order1.pk])
        response = self.client.get(pdf_url)
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={pdf_url}")

    def test_generate_order_pdf_logged_in_success(self):
        """Test the Order PDF view generates a PDF for a logged-in user."""
        pdf_url = reverse('documents:order_pdf', args=[self.order1.pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(pdf_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        # Check for a reasonable filename in Content-Disposition
        # Filename will include the order_number (e.g., Order-ORD-2025-X.pdf)
        expected_filename_part = f"Order-{self.order1.order_number}"
        self.assertIn(f'filename="{expected_filename_part}', response['Content-Disposition'])
        self.assertIn("inline;", response['Content-Disposition'])

        # Check if the content looks like a PDF (starts with %PDF-)
        self.assertTrue(response.content.startswith(b'%PDF-'))
        # You could add more specific content checks if necessary,
        # e.g., self.assertContains(response, self.order1.client.name, html=False) # for PDF content

    def test_generate_order_pdf_not_found(self):
        """Test accessing Order PDF view for a non-existent Order returns 404."""
        invalid_pk = self.order1.pk + self.order2.pk + 999 # A PK unlikely to exist
        pdf_url = reverse('documents:order_pdf', args=[invalid_pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(pdf_url)
        self.assertEqual(response.status_code, 404)
    
    def test_delivery_order_list_view_logged_out_redirect(self):
        """Test accessing delivery order list view when logged out redirects to login."""
        list_url = reverse('documents:delivery_order_list')
        response = self.client.get(list_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={list_url}")

    def test_delivery_order_list_view_logged_in_success(self):
        """Test the delivery order list view loads correctly for a logged-in user."""
        list_url = reverse('documents:delivery_order_list')
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(list_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'documents/delivery_order_list.html')
        self.assertTemplateUsed(response, 'base.html')
        self.assertContains(response, "Delivery Orders") # Page title/heading
        self.assertIn('page_obj', response.context) # Context variable for Paginator
        # Check if the delivery_order1's number is present
        self.assertContains(response, self.delivery_order1.do_number)
        # Check if the parent order's number is present
        self.assertContains(response, self.delivery_order1.order.order_number)
        # Check if the client name (via parent order) is present
        self.assertContains(response, self.delivery_order1.order.client.name)
        
    def test_delivery_order_detail_view_logged_out_redirect(self):
        """Test accessing DO detail view when logged out redirects to login."""
        # Use delivery_order1 created in setUpTestData
        detail_url = reverse('documents:delivery_order_detail', args=[self.delivery_order1.pk])
        response = self.client.get(detail_url) # HTTP TestClient
        self.assertEqual(response.status_code, 302)
        login_url = reverse('account_login')
        self.assertRedirects(response, f"{login_url}?next={detail_url}")

    def test_delivery_order_detail_view_logged_in_success(self):
        """Test the DO detail view loads correctly for a logged-in user."""
        detail_url = reverse('documents:delivery_order_detail', args=[self.delivery_order1.pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, 200) # OK status
        self.assertTemplateUsed(response, 'documents/delivery_order_detail.html') # Correct template
        self.assertTemplateUsed(response, 'base.html') # Uses base template
        # Check title in context (passed from view)
        self.assertContains(response, f"Delivery Order {self.delivery_order1.do_number}")
        self.assertIn('delivery_order', response.context) # Context variable exists
        self.assertEqual(response.context['delivery_order'], self.delivery_order1) # Correct DO object
        self.assertIn('items', response.context) # Items passed

        # Check for key data from DO and its related objects
        self.assertContains(response, self.delivery_order1.order.client.name) # Client name
        self.assertContains(response, self.delivery_order1.order.order_number) # Parent Order number
        # The first item of delivery_order1 is order1_item1_for_do, which uses menu_item_ord1
        # menu_item_ord1 was named "Ord Detail/Edit Item"
        self.assertContains(response, "Ord Detail/Edit Item") # Check name of delivered item
        # Check quantity delivered for that item (which was set to order_item1_for_do.quantity)
        delivered_item = self.delivery_order1.items.first()
        if delivered_item:
            self.assertContains(response, f"{delivered_item.quantity_delivered:.2f}")


    def test_delivery_order_detail_view_not_found(self):
        """Test accessing detail view for a non-existent DO returns 404."""
        invalid_pk = self.delivery_order1.pk + 999 # A PK unlikely to exist
        detail_url = reverse('documents:delivery_order_detail', args=[invalid_pk])
        login_successful = self.client.login(email=self.test_user_email, password=self.test_user_password)
        self.assertTrue(login_successful, "Test user login failed")

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 404) # Not Found status
    
    
class DeliveryOrderModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.client = Client.objects.create(name="Client for DOs")
        cls.order = Order.objects.create(
            client=cls.client,
            event_date=date(2025, 12, 25),
            status=Order.OrderStatus.CONFIRMED
        )
        # Manually set order_number for predictability in DO __str__ tests if needed now,
        # or rely on signal if already implemented and tested
        cls.order.order_number = "ORD-SETUP-1"
        cls.order.save(update_fields=['order_number'])


    def test_delivery_order_creation(self):
        """Test creating a basic Delivery Order record."""
        delivery_date = date(2025, 12, 24)
        do = DeliveryOrder.objects.create(
            order=self.order,
            delivery_date=delivery_date,
            recipient_name="John Doe Receiver",
            delivery_address_override="123 Festive Lane, North Pole",
            notes="Deliver by sleigh."
            # status defaults to PLANNED
        )

        self.assertEqual(do.order, self.order)
        self.assertEqual(do.delivery_date, delivery_date)
        self.assertEqual(do.status, DeliveryOrderStatus.PLANNED) # Check default
        self.assertEqual(do.recipient_name, "John Doe Receiver")
        self.assertEqual(do.delivery_address_override, "123 Festive Lane, North Pole")
        self.assertEqual(do.notes, "Deliver by sleigh.")
        # We'll test do_number generation separately if we add a signal

    def test_delivery_order_str_representation(self):
        """Test the string representation of DeliveryOrder."""
        do = DeliveryOrder.objects.create(order=self.order, delivery_date=date(2025, 12, 20))
        do.refresh_from_db() # Refresh to get the generated do_number
        # Relies on Order having an order_number (set in setUpTestData)
        # and DO not having do_number yet (will be 'Draft DO')
        expected_number = f"DO-{do.created_at.year}-{do.pk}"
        self.assertEqual(do.do_number, expected_number) # Verify number itself
        expected_str = f"Delivery Order {do.do_number} for Order {self.order.order_number or self.order.pk}"
        self.assertEqual(str(do), expected_str)
    

    def test_do_number_auto_generation(self):
        """Test that do_number is generated correctly on first save."""
        do = DeliveryOrder.objects.create(order=self.order, delivery_date=date(2025, 12, 1))
        # Refresh from DB to get the value set by the signal
        do.refresh_from_db()

        # Check the format
        expected_number = f"DO-{do.created_at.year}-{do.pk}"
        self.assertIsNotNone(do.do_number)
        self.assertEqual(do.do_number, expected_number)
    
    
class DeliveryOrderItemModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        client = Client.objects.create(name="Client for DO Validation")
        menu_item_A = MenuItem.objects.create(name="DO Valid Item A", unit_price=Decimal("10.00"))
        menu_item_B = MenuItem.objects.create(name="DO Valid Item B", unit_price=Decimal("20.00"))

        # Order 1 with items
        cls.order1 = Order.objects.create(
            client=client, event_date=date(2025, 11, 1), status=Order.OrderStatus.CONFIRMED
        )
        cls.order1.order_number = "ORD-DOV-1"; cls.order1.save() # Set for clarity
        cls.order_item1_on_order1 = OrderItem.objects.create(
            order=cls.order1, menu_item=menu_item_A, quantity=Decimal("10.00"), unit_price=Decimal("10.00")
        )
        cls.order_item2_on_order1 = OrderItem.objects.create(
            order=cls.order1, menu_item=menu_item_B, quantity=Decimal("5.00"), unit_price=Decimal("20.00")
        )

        # Order 2 with an item (to test incorrect assignment)
        cls.order2 = Order.objects.create(
            client=client, event_date=date(2025, 11, 5), status=Order.OrderStatus.CONFIRMED
        )
        cls.order2.order_number = "ORD-DOV-2"; cls.order2.save()
        cls.order_item_on_order2 = OrderItem.objects.create(
            order=cls.order2, menu_item=menu_item_A, quantity=Decimal("3.00"), unit_price=Decimal("10.00")
        )

        # Delivery Order linked to Order 1
        cls.delivery_order_for_order1 = DeliveryOrder.objects.create(
            order=cls.order1,
            delivery_date=date(2025, 11, 1)
        )
        cls.delivery_order_for_order1.refresh_from_db() # Get DO number if auto-generated


    def test_delivery_order_item_creation(self):
        """Test creating a Delivery Order Item record."""
        do_item = DeliveryOrderItem.objects.create(
            delivery_order=self.delivery_order_for_order1,
            order_item=self.order_item1_on_order1, # This is the correct OrderItem from setUpTestData
            quantity_delivered=Decimal("5.00"),
            notes="Half delivered."
        )
        self.assertEqual(do_item.delivery_order, self.delivery_order_for_order1)
        # --- Correct this line ---
        self.assertEqual(do_item.order_item, self.order_item1_on_order1)
        # --- End Correction ---
        self.assertEqual(do_item.quantity_delivered, Decimal("5.00"))
        self.assertEqual(do_item.notes, "Half delivered.")
        

    def test_quantity_delivered_validation(self):
        """Test that quantity_delivered must be positive."""
        with self.assertRaises(ValidationError):
            item_zero = DeliveryOrderItem(
                delivery_order=self.delivery_order_for_order1,
                order_item=self.order_item1_on_order1,   
                quantity_delivered=Decimal("0.00")
            )
            item_zero.full_clean()

        with self.assertRaises(ValidationError):
            item_neg = DeliveryOrderItem(
                delivery_order=self.delivery_order_for_order1,
                order_item=self.order_item1_on_order1,    
                quantity_delivered=Decimal("-1.00")
            )
            item_neg.full_clean()

        # Test valid amount
        try:
            item_ok = DeliveryOrderItem(
                delivery_order=self.delivery_order_for_order1,
                order_item=self.order_item1_on_order1,  
                quantity_delivered=Decimal("0.01")
            )
            item_ok.full_clean() # Should not raise
        except ValidationError as e:
            self.fail(f"Positive quantity_delivered validation failed unexpectedly: {e}")

    def test_delivery_order_item_str_representation(self):
            """Test the string representation."""
            do_item = DeliveryOrderItem.objects.create(
                delivery_order=self.delivery_order_for_order1, # <-- Use correct name
                order_item=self.order_item1_on_order1,       # <-- Use correct name
                quantity_delivered=Decimal("3")
            )
            # self.delivery_order_for_order1 was refreshed in setUpTestData so do_number is available
            expected_str = f"3 x {self.order_item1_on_order1.menu_item.name} on {self.delivery_order_for_order1.do_number}"
            self.assertEqual(str(do_item), expected_str)

    def test_do_item_validation_order_item_matches_parent_order(self):
        """
        Test that selected OrderItem must belong to the DeliveryOrder's parent Order.
        """
        # Valid case: OrderItem belongs to the DeliveryOrder's parent Order
        valid_do_item = DeliveryOrderItem(
            delivery_order=self.delivery_order_for_order1,
            order_item=self.order_item1_on_order1, # Belongs to order1
            quantity_delivered=Decimal("1.00")
        )
        try:
            valid_do_item.full_clean() # Should not raise ValidationError
        except ValidationError as e:
            self.fail(f"Validation failed unexpectedly for correct OrderItem: {e.message_dict}")

        # Invalid case: OrderItem belongs to a different Order
        invalid_do_item = DeliveryOrderItem(
            delivery_order=self.delivery_order_for_order1, # Belongs to order1
            order_item=self.order_item_on_order2,      # Belongs to order2
            quantity_delivered=Decimal("1.00")
        )
        with self.assertRaisesRegex(ValidationError, "This item does not belong to the parent Order"):
            invalid_do_item.full_clean()

    def test_do_item_validation_quantity_delivered_not_exceeds_ordered(self):
        """
        Test that quantity_delivered does not exceed OrderItem.quantity.
        order_item1_on_order1 has quantity 10.
        """
        # Valid case: Quantity less than ordered
        do_item_less = DeliveryOrderItem(
            delivery_order=self.delivery_order_for_order1,
            order_item=self.order_item1_on_order1,
            quantity_delivered=Decimal("5.00")
        )
        try:
            do_item_less.full_clean() # Should not raise
        except ValidationError as e:
            self.fail(f"Validation for quantity_delivered < ordered failed: {e.message_dict}")

        # Valid case: Quantity equal to ordered
        do_item_equal = DeliveryOrderItem(
            delivery_order=self.delivery_order_for_order1,
            order_item=self.order_item1_on_order1,
            quantity_delivered=Decimal("10.00")
        )
        try:
            do_item_equal.full_clean() # Should not raise
        except ValidationError as e:
            self.fail(f"Validation for quantity_delivered == ordered failed: {e.message_dict}")

        # Invalid case: Quantity more than ordered
        do_item_over = DeliveryOrderItem(
            delivery_order=self.delivery_order_for_order1,
            order_item=self.order_item1_on_order1,
            quantity_delivered=Decimal("11.00") # Ordered 10
        )
        with self.assertRaisesRegex(ValidationError, "Cannot deliver more than ordered"):
            do_item_over.full_clean()


class CreditNoteModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.db_client = Client.objects.create(name="Client for Credit Notes")
        cls.invoice = Invoice.objects.create(
            client=cls.db_client,
            issue_date=date(2025, 4, 1), # Use May 14, 2025 as current
            status=Invoice.Status.PAID # Assume invoice was paid
        )
        cls.invoice.invoice_number = "INV-CN-TEST-1" # Manually set for __str__
        cls.invoice.save()

    def test_credit_note_creation(self):
        """Test creating a basic Credit Note record."""
        cn_issue_date = date(2025, 5, 14)
        cn = CreditNote.objects.create(
            client=self.db_client,
            related_invoice=self.invoice,
            issue_date=cn_issue_date,
            reason="Product return for item X."
            # status defaults to DRAFT
        )
        # We'll test cn_number generation separately later
        self.assertEqual(cn.client, self.db_client)
        self.assertEqual(cn.related_invoice, self.invoice)
        self.assertEqual(cn.issue_date, cn_issue_date)
        self.assertEqual(cn.reason, "Product return for item X.")
        self.assertEqual(cn.status, CreditNoteStatus.DRAFT) # Check default

    def test_credit_note_str_representation(self):
        """Test the string representation of CreditNote."""
        cn = CreditNote.objects.create(client=self.db_client, related_invoice=self.invoice)
        cn.refresh_from_db()
        
        # Construct expected number
        expected_number = f"CN-{cn.created_at.year}-{cn.pk}"
        self.assertEqual(cn.cn_number, expected_number) # Verify number itself
        expected_str = f"Credit Note {cn.cn_number} for {self.db_client.name} (Invoice: {self.invoice.invoice_number})"
        self.assertEqual(str(cn), expected_str)
        # After cn_number generation, this test would change

    def test_cn_number_auto_generation(self):
        """Test that cn_number is generated correctly on first save."""
        cn = CreditNote.objects.create(client=self.db_client, related_invoice=self.invoice)
        # Refresh from DB to get the value set by the signal
        cn.refresh_from_db()

        # Check the format
        expected_number = f"CN-{cn.created_at.year}-{cn.pk}"
        self.assertIsNotNone(cn.cn_number)
        self.assertEqual(cn.cn_number, expected_number)


class CreditNoteItemModelTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        client = Client.objects.create(name="Client for CN Items")
        menu_item = MenuItem.objects.create(name="CN Test Item", unit_price=Decimal("30.00"))

        cls.invoice = Invoice.objects.create(
            client=client,
            issue_date=date(2025, 3, 15),
            status=Invoice.Status.PAID
        )
        cls.invoice.invoice_number = "INV-CN-ITEM-1"; cls.invoice.save(update_fields=['invoice_number'])

        cls.invoice_item = InvoiceItem.objects.create(
            invoice=cls.invoice,
            menu_item=menu_item,
            quantity=Decimal("3.00"),
            unit_price=Decimal("30.00")
        )

        cls.credit_note = CreditNote.objects.create(
            client=client,
            related_invoice=cls.invoice,
            issue_date=date(2025, 5, 14)
        )
        cls.credit_note.refresh_from_db()


    def test_credit_note_item_creation(self):
        """Test creating a Credit Note Item record."""
        cn_item = CreditNoteItem.objects.create(
            credit_note=self.credit_note,
            related_invoice_item=self.invoice_item, # Optional link
            description="Credit for 1 unit of CN Test Item",
            quantity=Decimal("1.00"),
            unit_price=Decimal("30.00")
        )
        self.assertEqual(cn_item.credit_note, self.credit_note)
        self.assertEqual(cn_item.related_invoice_item, self.invoice_item)
        self.assertEqual(cn_item.description, "Credit for 1 unit of CN Test Item")
        self.assertEqual(cn_item.quantity, Decimal("1.00"))
        self.assertEqual(cn_item.unit_price, Decimal("30.00"))

    def test_credit_note_item_str_representation(self):
        """Test the string representation."""
        cn_item = CreditNoteItem.objects.create(
            credit_note=self.credit_note,
            description="Item to credit",
            quantity=Decimal("2.00"),
            unit_price=Decimal("15.00")
        )
        # Uses self.credit_note.cn_number which was manually set in setUpTestData
        expected_str = f"2.00 x Item to credit on {self.credit_note.cn_number}"
        self.assertEqual(str(cn_item), expected_str)


    



