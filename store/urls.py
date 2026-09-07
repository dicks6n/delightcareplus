# store/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Home & Product
    path("", views.home, name="home"),
    path("product/<int:product_id>/", views.product_detail, name="product_detail"),
    


# store/urls.py - Add this URL
    path('update-cart/<str:key>/<int:quantity>/', views.update_cart_quantity, name='update_cart_quantity'),
    # ... existing URLs ...
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),  # ADD THIS LINE
    # ... other URLs ...
    # Cart
    path("add-to-cart/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path("cart/", views.cart, name="cart"),
    path('cart/count/', views.cart_count, name='cart_count'),

    path("remove-from-cart/<str:key>/", views.remove_from_cart, name="remove_from_cart"),
    
    # Checkout & Orders
    path("checkout/", views.checkout, name="checkout"),
    path("order-success/", views.order_success, name="order_success"),
    path("order-success/<int:order_id>/", views.order_success, name="order_success_with_id"),
    path("my-orders/", views.my_orders, name="my_orders"),
    path("cancel-order/<int:order_id>/", views.cancel_order, name="cancel_order"),
    
    # Payment
    path("payment/", views.payment, name="payment"),
    path("payment/card/", views.process_card_payment, name="process_card_payment"),
    path('payment/mpesa-push/', views.initiate_stk_push, name='initiate_stk_push'),
    path('payment/status/<int:order_id>/', views.payment_status, name='payment_status'),
    path('payment/check-status/<int:order_id>/', views.check_payment_status_ajax, name='check_payment_status_ajax'),
    
    # M-Pesa Callback
    path('mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    
    # Category
    path('category/<slug:slug>/', views.category_products, name='category_products'),
    
    # Blog
    path('blog/create/', views.admin_create_post, name='admin_create_post'),
    path('blog/upload-image/', views.upload_blog_image, name='upload_blog_image'),
    path('blog/edit/<int:post_id>/', views.admin_edit_post, name='admin_edit_post'),
    path('blog/delete/<int:post_id>/', views.admin_delete_post, name='admin_delete_post'),
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    
    # Admin Products
    path('admin/products/', views.admin_product_list, name='admin_product_list'),
    path('admin/products/add/', views.admin_product_add, name='admin_product_add'),
    path('admin/products/edit/<int:product_id>/', views.admin_product_form, name='admin_product_form'),
    path('admin/products/delete/<int:product_id>/', views.admin_product_delete, name='admin_product_delete'),
    
    # Authentication
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
]