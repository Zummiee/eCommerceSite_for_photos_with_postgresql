Main Website Features:
1. Users can register, log in & log out.
2. Flash messages will appear in red if users try registerring more than once with the same email or the same name, use an invalid email address during registeration, or input an incorrect password or non-registered email address during log-in.
3. Users can view all available products by clicking the "SEE PRODUCTS" button or by selecting the "Products" option in the left sidebar of the homepage.
4. Users can return to the home page by clicking the title in header or by selecting the "Home" option in the left sidebar of the homepage.
5. Users can access detailed information about a specific product, but only logged-in users are allowed to add comments, delete previously added comments, and add the product to their cart.
6. Users can see all comments added to a given product, but can only delete comments they added themselves (delete comment button is only visible to users who created that comment).
7. Non logged-in users will be redirected to the log-in page when trying to add comments to a given product.
8. Users can purchase multiple quantities of the same product, with the quantity reflected in the corresponding product section on the shopping cart page.
9. On the shopping cart page, users can remove products from their cart or proceed to checkout to purchase all items in the cart.
10. After completing the checkout process, users will be redirected to a successful checkout page, which includes an option to return to the homepage.
11. Once the checkout is successfully completed, the stock quantity of the relevant products will be updated, and the quantity of products in the user's shopping cart will be adjusted accordingly.
12. Users have the option to cancel a created check-out session, upon doing so, they will be rediected to a page where they can see a rediect option to the products page (if a check-out session is cancelled, all products will still remain in the users cart)
13. Non logged-in users can use the "buy now" button to purchase products directly, but to add products to cart, they will need to log in first (non logged-in users will be redirected to the log-in page after clicking on "add to cart" button).
14. Only admin users can add, edit or remove products.

Notes: 
- Deployed site can be found at https://ecommercesite-for-photos.onrender.com (not yet mobile friendly, please view via desktop)
- Developed the backend independently using Python.
- Adapted a pre-existing frontend template to meet project requirements, some front-end adjustments still needed.
- Not Started:
1) create About, Client, Contact html
2) update htmls to be mobile view friendly
3) update base & header html so that page title will remain in the middle of the header for both logged-in and non logged-in users view
4) update script to prevent users from adding more than what's in stock to cart for a given product
5) create htmls and routes for photo catogories under best products
6) update script to allow users to adjust purchase amount on the shopping cart page
7) also create a purchase record for single product purchase via "buy now" button
8) update script to allow admin to delete comments as s/he sees fit

