// Wait for the entire HTML document to be fully loaded before running the script
document.addEventListener('DOMContentLoaded', function() {

    // Use event delegation on the main content area where inlines appear
    // This ensures the script works for rows added dynamically ("Add another")
    document.getElementById('content-main').addEventListener('change', function(event) {

        // Check if the changed element is a select input for a menu item in our inlines
        // Django admin inline field names typically end with '-menu_item'
        // Adjust selector if your inline prefix or field name is different
        if (event.target.tagName === 'SELECT' && event.target.name.endsWith('-menu_item')) {
            const selectElement = event.target;
            const menuItemId = selectElement.value;

            // Find the closest parent row element for this inline item
            // For TabularInline, this is often a <tr>; for StackedInline, a <div> with a specific class.
            // Adjust '.dynamic-items' if needed - inspect your admin HTML using browser dev tools!
            // Common classes might be '.dynamic-YOUR_INLINE_PREFIX', '.inline-related', or just 'tr' for tabular.
            // Let's assume 'tr' for TabularInline as a starting point. If using StackedInline, inspect!
            const row = selectElement.closest('tr'); // Or '.inline-related', '.dynamic-items', etc.

            if (!row) {
                console.error("Could not find parent row for", selectElement);
                return; // Exit if we can't find the row
            }

            // Find the price and description fields within the same row
            // Their names usually follow the pattern 'prefix-INDEX-fieldname'
            const priceInput = row.querySelector('input[name$="-unit_price"]'); // Find input ending with -unit_price
            const descriptionInput = row.querySelector('textarea[name$="-description"]'); // Find textarea ending with -description

            // Check if we found the fields (might not exist if admin layout changed)
            if (!priceInput || !descriptionInput) {
                 console.error("Could not find price or description input in row for", selectElement);
                 return;
            }

            // If a valid menu item is selected (not the empty "-----" option)
            if (menuItemId) {
                // Construct the API URL using the selected item's ID (pk)
                // Ensure the '/docs/' prefix matches what's in core/urls.py include()
                const url = `/docs/api/menuitem/${menuItemId}/`;

                // Use the Fetch API to call our Django view
                fetch(url)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json(); // Parse the JSON response
                    })
                    .then(data => {
                        // Check if data was returned successfully
                        if (data && data.unit_price !== undefined && data.description !== undefined) {
                            // Update the price and description fields in the current row
                            priceInput.value = data.unit_price;
                            descriptionInput.value = data.description;
                        } else if (data && data.error) {
                            console.error("API Error:", data.error);
                        }
                    })
                    .catch(error => {
                        console.error('Error fetching menu item details:', error);
                        // Optionally clear fields on error, or leave them
                        // priceInput.value = '';
                        // descriptionInput.value = '';
                    });
            } else {
                // If the empty "----" option is selected, clear the fields
                priceInput.value = '';
                descriptionInput.value = '';
            }
        }
    });
});