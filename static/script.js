document.addEventListener('DOMContentLoaded', function() {
    // Check if the current page is index.html based on URL path
    const isIndexPage = window.location.pathname === '/';
    const isShopPage = window.location.pathname === '/shop';
    const isCartPage = window.location.pathname === '/cart';
    const isPredictPage = window.location.pathname === '/predict';

    // --- Product Data ---
    // Products data. These categories must match 'Product_Category' in your LabelEncoder.
    const products = [
        { id: 1, name: "Smartphone", price: 1499.00, category: "Electronics", image: "electronics.jpg" },
        { id: 2, name: "Stylish Jean", price: 799.00, category: "Clothing", image: "fashion.jpg" },
        { id: 3, name: "Organic Rice Pack", price: 299.00, category: "Groceries", image: "grocery.jpg" },
        { id: 4, name: "Smart Blender", price: 999.00, category: "Electronics", image: "home.jpg" },
        { id: 5, name: "Noise-Cancelling Headphones", price: 2199.00, category: "Electronics", image: "headphones.jpg" },
        { id: 6, name: "Comfortable Sweater", price: 1299.00, category: "Clothing", image: "sweater.jpg" },
        { id: 7, name: "Fresh Produce Basket", price: 450.00, category: "Groceries", image: "fruit.jpg" },
        { id: 8, name: "Ergonomic Office Chair", price: 3500.00, category: "Home Decor", image: "chair.jpg" }
    ];

    // --- Shop Page Logic ---
    const productGrid = document.getElementById("productGrid");

    if (isShopPage && productGrid) {
        products.forEach(p => {
            const card = document.createElement("div");
            card.className = "col-sm-6 col-md-4 col-lg-3 mb-4"; // Adjusted for more columns on larger screens
            card.innerHTML = `
                <div class="card h-100 shadow product-card border-0">
                    <img src="/static/assets/products/${p.image}" class="card-img-top product-image animated fadeIn" alt="${p.name}">
                    <div class="card-body d-flex flex-column">
                        <h5 class="card-title fw-bold text-primary">${p.name}</h5>
                        <p class="card-text text-muted">Category: ${p.category}</p>
                        <p class="card-text fs-5 fw-bold text-success">₹${p.price.toFixed(2)}</p>
                        <div class="mt-auto">
                            <button class="btn btn-warning w-100 add-to-cart-btn" data-product='${JSON.stringify(p)}'>Add to Cart</button>
                        </div>
                    </div>
                </div>
            `;
            productGrid.appendChild(card);
        });

        productGrid.addEventListener('click', function(event) {
            if (event.target.classList.contains('add-to-cart-btn')) {
                const productData = JSON.parse(event.target.dataset.product);
                addToCart(productData);
            }
        });
    }

    // --- Add To Cart Function ---
    function addToCart(product) {
        let cart = JSON.parse(localStorage.getItem("cart") || "[]");
        // Ensure product has original_price for logging later, fallback to its price
        const originalPrice = product.original_price !== undefined ? product.original_price : product.price; 
        
        let existingItemIndex = cart.findIndex(item => item.id === product.id);
        if (existingItemIndex > -1 && product.id.toString().indexOf('predict_offer_') === -1) { // Don't combine predicted offers
            cart[existingItemIndex].quantity = (cart[existingItemIndex].quantity || 1) + 1; // Increment quantity
        } else {
            product.quantity = 1; // Initialize quantity
            product.original_price = originalPrice; // Store original price for later logging
            cart.push(product);
        }
        localStorage.setItem("cart", JSON.stringify(cart));
        updateCartCount(); // Update cart count in navbar
        alert(`"${product.name}" added to cart!`);
    }

    // --- Price Prediction Logic ---
    if (isPredictPage) {
        const predictionForm = document.getElementById('predictionForm');
        const predictButton = document.getElementById('predictButton');
        const resultBox = document.getElementById('resultBox');
        const predictedPriceElem = document.getElementById('predictedPrice');
        const conversionProbElem = document.getElementById('conversionProb');
        const customerSegmentElem = document.getElementById('customerSegment');
        const proceedButtonContainer = document.getElementById('proceedButtonContainer');
        const predictSound = document.getElementById('predictSound'); // Assumes element exists

        // Form fields for personal/demographic data (conditionally shown for guests)
        // Note: IDs now match Colab notebook's feature names (e.g., 'Age', 'Gender')
        const ageInput = document.getElementById('Age');
        const genderSelect = document.getElementById('Gender');
        const citySelect = document.getElementById('City');
        const occupationSelect = document.getElementById('Occupation');
        const loyaltyTierSelect = document.getElementById('Loyalty_Tier');
        const userProductCountInput = document.getElementById('User_Product_Count'); // For guest users

        // Product and Environment fields (always visible)
        // IDs now match Colab notebook's feature names
        const productCategorySelect = document.getElementById('Product_Category');
        const originalPurchaseAmountInput = document.getElementById('Purchase_Amount'); // Changed ID
        const weatherSelect = document.getElementById('Weather');
        const timeOfDaySelect = document.getElementById('Time_of_Day');

        // Hide result box and proceed button initially
        resultBox.classList.add('d-none');
        proceedButtonContainer.classList.add('d-none');

        predictionForm.addEventListener('submit', async function(event) {
            event.preventDefault();

            const formData = {};

            // Conditionally collect data based on authentication status (passed from Flask Jinja)
            if (window.isAuthenticated) {
                // Logged in: Backend will fetch profile data. Only send product and environment data from form.
                // The keys sent here MUST match the notebook's feature names AND be present in the backend's request_data.
                formData.Product_Category = productCategorySelect.value;
                formData.Purchase_Amount = parseFloat(originalPurchaseAmountInput.value); 
                formData.Weather = weatherSelect.value;
                formData.Time_of_Day = timeOfDaySelect.value;
                
                // Client-side validation: Make sure these required fields are filled.
                if (!formData.Product_Category || isNaN(formData.Purchase_Amount) || formData.Purchase_Amount <= 0 || !formData.Weather || !formData.Time_of_Day) {
                    alert("Please fill in Product Category, Original Price, Weather, and Time of Day.");
                    return;
                }
            } else {
                // Not logged in (guest): gather all fields from form.
                // The keys sent here MUST match the notebook's feature names.
                formData.Age = parseInt(ageInput.value);
                formData.Gender = genderSelect.value;
                formData.City = citySelect.value;
                formData.Occupation = occupationSelect.value;
                formData.Loyalty_Tier = loyaltyTierSelect.value;
                formData.User_Product_Count = parseInt(userProductCountInput.value); // User enters this for guest
                formData.Product_Category = productCategorySelect.value;
                formData.Purchase_Amount = parseFloat(originalPurchaseAmountInput.value);
                formData.Weather = weatherSelect.value;
                formData.Time_of_Day = timeOfDaySelect.value;

                // Client-side validation for guest user fields
                const guestFields = [
                    { name: 'Age', value: formData.Age, min: 1, max: 120 },
                    { name: 'Gender', value: formData.Gender },
                    { name: 'City', value: formData.City },
                    { name: 'Occupation', value: formData.Occupation },
                    { name: 'Loyalty_Tier', value: formData.Loyalty_Tier },
                    { name: 'User_Product_Count', value: formData.User_Product_Count, min: 0 },
                    { name: 'Product_Category', value: formData.Product_Category },
                    { name: 'Purchase_Amount', value: formData.Purchase_Amount, min: 0.01 },
                    { name: 'Weather', value: formData.Weather },
                    { name: 'Time_of_Day', value: formData.Time_of_Day }
                ];

                for (const field of guestFields) {
                    if (field.value === null || field.value === '' || (typeof field.value === 'number' && isNaN(field.value))) {
                        alert(`Please fill in all fields. Missing: ${field.name}`);
                        return;
                    }
                    if (typeof field.min !== 'undefined' && field.value < field.min) {
                        alert(`${field.name} must be at least ${field.min}.`);
                        return;
                    }
                    if (typeof field.max !== 'undefined' && field.value > field.max) {
                        alert(`${field.name} cannot be more than ${field.max}.`);
                        return;
                    }
                }
            }
            
            predictButton.disabled = true;
            predictButton.textContent = 'Predicting...';
            predictButton.classList.add('highlight-button'); // Add a class for prediction state
            predictButton.classList.remove('btn-primary');
            predictButton.classList.add('btn-secondary');


            try {
                const response = await fetch(window.PREDICT_API_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });

                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(errorData.error || `HTTP error! Status: ${response.status}`);
                }

                const data = await response.json();

                if (data.error) {
                    alert('Prediction Error: ' + data.error);
                    resultBox.classList.add('d-none');
                    proceedButtonContainer.classList.add('d-none');
                } else {
                    predictedPriceElem.textContent = `₹${data.optimized_price.toFixed(2)}`;
                    conversionProbElem.textContent = `${(data.predicted_conversion_probability * 100).toFixed(2)}%`;
                    customerSegmentElem.textContent = data.customer_segment;

                    // Store details for cart, including product category and price.
                    localStorage.setItem("predictedPrice", data.optimized_price);
                    localStorage.setItem("predictedProductName", productCategorySelect.value); // Store name for cart button text
                    localStorage.setItem("predictedProductCategory", productCategorySelect.value); // Store category for purchase record

                    resultBox.classList.remove('d-none');
                    proceedButtonContainer.classList.remove('d-none');

                    if (predictSound) predictSound.play();
                }
            } catch (error) {
                console.error('Fetch error:', error);
                alert('An error occurred during prediction: ' + error.message);
                resultBox.classList.add('d-none');
                proceedButtonContainer.classList.add('d-none');
            } finally {
                predictButton.disabled = false;
                predictButton.textContent = 'Predict Price';
                predictButton.classList.remove('highlight-button');
                predictButton.classList.remove('btn-secondary');
                predictButton.classList.add('btn-primary');
            }
        });

        // Function added to onclick from predict.html
        window.addToCartWithPredictedPrice = function() {
            const predictedPrice = parseFloat(localStorage.getItem("predictedPrice"));
            const predictedProductName = localStorage.getItem("predictedProductName");
            const predictedProductCategory = localStorage.getItem("predictedProductCategory"); // Get category

            if (predictedProductName && !isNaN(predictedPrice) && predictedPrice > 0) {
                // Create a "virtual product" specifically representing this prediction to add to cart
                const virtualProduct = {
                    id: 'predict_offer_' + Date.now(), // Unique ID, won't combine with other products
                    name: `Predicted Offer for ${predictedProductName}`, // Descriptive name for the cart
                    price: predictedPrice, // Use the predicted price for display
                    original_price: parseFloat(originalPurchaseAmountInput.value), // Store original amount for backend logging
                    category: predictedProductCategory, // Use the category
                    quantity: 1, // Always 1 for now, as it's an offer on a single product
                };
                addToCart(virtualProduct);
                alert(`"${virtualProduct.name}" added to cart!`);
            } else {
                alert("No valid predicted price to add to cart. Please predict first!");
            }
        };

        // This is called from the HTML button onclick
        window.goToCart = function() {
            if (window.CART_URL) {
                window.location.href = window.CART_URL;
            } else {
                console.error("CART_URL not defined. Cannot navigate to cart. Falling back to /cart.");
                window.location.href = '/cart'; // Fallback for debugging
            }
        };
    }

    // --- Cart Page Logic ---
    if (isCartPage) {
        const cartItemsList = document.getElementById("cartItems");
        const noItemsMessage = document.getElementById("noItemsMessage");
        const totalOriginalDisplay = document.getElementById("totalOriginalPrice");
        const totalCalculatedDisplay = document.getElementById("totalCalculatedPrice"); // New element
        const predictedSection = document.getElementById("predictedSection");
        const predictedValueSpan = document.getElementById("predictedValue");
        const applySmartPriceBtn = document.getElementById("applySmartPriceBtn");
        const payNowBtn = document.getElementById("payNowBtn");
        const dingSound = document.getElementById("ding");
        const paymentModal = new bootstrap.Modal(document.getElementById('paymentModal')); // Bootstrap modal instance
        const confirmPaymentBtn = document.getElementById('confirmPaymentBtn'); // Btn inside modal

        // Function to render/re-render the cart display
        function renderCart() {
            cartItemsList.innerHTML = ''; // Clear current display
            const cart = JSON.parse(localStorage.getItem("cart") || "[]");

            let totalOriginalSum = 0; // Sum of original_price * quantity for all items
            let totalCurrentSum = 0; // Sum of price * quantity (might include predicted offer prices)

            if (cart.length === 0) {
                noItemsMessage.classList.remove('d-none');
                payNowBtn.disabled = true;
            } else {
                noItemsMessage.classList.add('d-none');
                payNowBtn.disabled = false;
                cart.forEach((item, index) => {
                    const li = document.createElement("li");
                    li.className = "list-group-item d-flex justify-content-between align-items-center animate__animated animate__fadeInLeft"; // Add animation
                    li.innerHTML = `
                        <span>${item.name} <small class="text-muted">(${item.category})</small> x ${item.quantity || 1}</span>
                        <div class="d-flex align-items-center">
                            <span class="badge bg-primary fs-6 me-2">₹${(item.price * (item.quantity||1)).toFixed(2)}</span>
                            <button class="btn btn-sm btn-outline-danger remove-item-btn" data-index="${index}">Remove</button>
                        </div>
                    `;
                    cartItemsList.appendChild(li);
                    // Calculate total original price of all items
                    totalOriginalSum += (item.original_price || item.price) * (item.quantity || 1); 
                    // Calculate total current price displayed in cart (can be original or predicted)
                    totalCurrentSum += item.price * (item.quantity||1); 
                });
            }

            totalOriginalDisplay.textContent = totalOriginalSum.toFixed(2);
            totalCalculatedDisplay.textContent = totalCurrentSum.toFixed(2); 

            // Dynamic visibility for "Apply Smart Price" section
            const latestPredictedPrice = parseFloat(localStorage.getItem("predictedPrice") || "0");
            const latestPredictedProductName = localStorage.getItem("predictedProductName");

            if (latestPredictedPrice > 0 && latestPredictedProductName) {
                // Only show "Apply Smart Price" if the predicted price can actually apply a discount
                // For simplicity, we apply the SINGLE predicted price to the TOTAL calculated price.
                // This means the user predicts for one item, then applies that price to the whole cart.
                // This is a simplification of a "smart final price" based on one prediction.
                if (latestPredictedPrice < totalCurrentSum) {
                    predictedSection.classList.remove('d-none');
                    predictedValueSpan.textContent = `₹${latestPredictedPrice.toFixed(2)}`;
                    applySmartPriceBtn.classList.remove('d-none');
                } else {
                    predictedSection.classList.add('d-none'); // Hide if no discount offered
                }
            } else {
                predictedSection.classList.add('d-none'); // Hide if no prediction in local storage
            }
        }

        renderCart(); // Initial rendering of the cart

        cartItemsList.addEventListener('click', function(event) {
            if (event.target.classList.contains('remove-item-btn')) {
                const indexToRemove = parseInt(event.target.dataset.index);
                removeItemFromCart(indexToRemove);
            }
        });

        function removeItemFromCart(index) {
            let cart = JSON.parse(localStorage.getItem("cart") || "[]");
            if (index > -1 && index < cart.length) {
                const removedItem = cart.splice(index, 1);
                console.log("Removed:", removedItem[0].name);
                localStorage.setItem("cart", JSON.stringify(cart));
                renderCart(); // Re-render the cart display
                updateCartCount(); // Update cart count in navbar
            }
        }

        if (applySmartPriceBtn) {
            applySmartPriceBtn.addEventListener('click', function() {
                const latestPredictedPrice = parseFloat(localStorage.getItem("predictedPrice") || "0");
                const currentTotalCalculated = parseFloat(totalCalculatedDisplay.textContent);

                if (latestPredictedPrice > 0 && latestPredictedPrice < currentTotalCalculated) {
                    totalCalculatedDisplay.textContent = latestPredictedPrice.toFixed(2);
                    if (dingSound) dingSound.play();
                    alert("🎉 Smart price applied successfully!");
                    applySmartPriceBtn.classList.add('d-none'); // Hide button after applying
                    predictedSection.classList.add('d-none'); // Hide the whole offer section
                } else {
                    alert("The predicted price does not offer a significant discount for this cart or isn't applicable.");
                }
            });
        }

        if (payNowBtn) {
            payNowBtn.addEventListener('click', function() {
                const cart = JSON.parse(localStorage.getItem("cart") || "[]");
                if (cart.length === 0) {
                     alert("Your cart is empty. Please add items before paying.");
                     return;
                }
                document.getElementById('modalFinalPrice').textContent = parseFloat(totalCalculatedDisplay.textContent).toFixed(2);
                paymentModal.show();
            });
        }

        if (confirmPaymentBtn) {
            confirmPaymentBtn.addEventListener('click', async function() {
                const paymentMethod = document.getElementById('paymentMethodModal').value;
                const finalPricePaid = parseFloat(totalCalculatedDisplay.textContent);
                const cart = JSON.parse(localStorage.getItem("cart") || "[]");

                if (!window.isAuthenticated) {
                    alert("Please log in to complete your purchase and log it to your history.");
                    paymentModal.hide();
                    window.location.href = window.LOGIN_URL; 
                    return;
                }
                
                confirmPaymentBtn.disabled = true;
                confirmPaymentBtn.textContent = 'Processing...';

                try {
                    const response = await fetch('/complete_purchase', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ cart_items: cart }) // Send entire cart for logging in purchases table
                    });

                    if (!response.ok) {
                        const error = await response.json();
                        throw new Error(error.error || `Failed to record purchase: ${response.status}`);
                    }
                    const result = await response.json();
                    console.log(result.message);

                    alert(`✅ Payment of ₹${finalPricePaid.toFixed(2)} successful via ${paymentMethod}! Your purchase history has been updated.`);
                    
                } catch (error) {
                    console.error("Purchase completion error:", error);
                    alert(`An error occurred during payment processing or recording: ${error.message}. Please try again.`);
                } finally {
                    confirmPaymentBtn.disabled = false;
                    confirmPaymentBtn.textContent = 'Confirm Payment';
                    paymentModal.hide(); // Hide modal

                    // Clear cart and redirect
                    localStorage.removeItem("cart");
                    localStorage.removeItem("predictedPrice");
                    localStorage.removeItem("predictedProductName");
                    localStorage.removeItem("predictedProductCategory"); 
                    
                    if (window.INDEX_URL) { 
                        window.location.href = window.INDEX_URL;
                    } else {
                        window.location.href = '/';
                    }
                }
            });
        }
    }

    // --- Global Functions ---
    // Update cart count once on DOM ready
    updateCartCount();

    // Global function for cart count update in navbar
    function updateCartCount() {
        const cartCountElement = document.getElementById('cartCount');
        if (cartCountElement) {
            const cart = JSON.parse(localStorage.getItem('cart') || '[]');
            cartCountElement.textContent = cart.length;
            cartCountElement.classList.toggle('d-none', cart.length === 0);
        }
    }
    // Functions attached to window for HTML onclick compatibility
    window.goToCart = function() { 
        if (window.CART_URL) {
            window.location.href = window.CART_URL;
        } else {
            console.error("CART_URL not present in window. Falling back.");
            window.location.href = '/cart';
        }
    };
});