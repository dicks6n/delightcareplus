# store/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
import json
import logging
import requests
import base64
from datetime import datetime
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# ✅ ALL MODELS
from .models import Product, ProductVariant, Order, OrderItem, Category, BlogPost

logger = logging.getLogger(__name__)


# =============================================
# HOME VIEW
# =============================================
def home(request):
    products = Product.objects.filter(is_active=True)
    categories = Category.objects.filter(is_active=True)

    liver_products = products.filter(category__name__icontains='Liver')[:4]
    kidney_products = products.filter(category__name__icontains='Kidney')[:4]
    lung_products = products.filter(category__name__icontains='Lung')[:4]
    heart_products = products.filter(category__name__icontains='Heart')[:4]
    digestive_products = products.filter(category__name__icontains='Digestive')[:4]
    brain_products = products.filter(category__name__icontains='Brain')[:4]
    immune_products = products.filter(category__name__icontains='Immune')[:4]
    joint_products = products.filter(category__name__icontains='Joint')[:4]
    skin_products = products.filter(category__name__icontains='Skin')[:4]
    energy_products = products.filter(category__name__icontains='Energy')[:4]

    paginator = Paginator(products, 12)
    page = request.GET.get('page')

    try:
        paginated_products = paginator.page(page)
    except PageNotAnInteger:
        paginated_products = paginator.page(1)
    except EmptyPage:
        paginated_products = paginator.page(paginator.num_pages)

    featured_products = products.filter(is_featured=True)[:3]

    return render(request, "store/home.html", {
        "products": products,
        "page_obj": paginated_products,
        "categories": categories,
        "liver_products": liver_products,
        "kidney_products": kidney_products,
        "lung_products": lung_products,
        "heart_products": heart_products,
        "digestive_products": digestive_products,
        "brain_products": brain_products,
        "immune_products": immune_products,
        "joint_products": joint_products,
        "skin_products": skin_products,
        "energy_products": energy_products,
        "featured_products": featured_products,
        "products_count": products.count(),
    })


# =============================================
# CATEGORY PRODUCTS VIEW
# =============================================
def category_products(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    products = Product.objects.filter(category=category, is_active=True)
    categories = Category.objects.filter(is_active=True)

    return render(request, "store/category_products.html", {
        "category": category,
        "products": products,
        "categories": categories,
    })


# =============================================
# PRODUCT VIEWS
# =============================================
def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    return render(request, "store/product_detail.html", {"product": product})


# =============================================
# CART VIEWS
# =============================================

# store/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


# =============================================
# CART VIEWS
# =============================================

def add_to_cart(request, product_id):
    """Standard (non-AJAX) add to cart — fallback"""
    variant_id = request.POST.get("variant_id")
    quantity = int(request.POST.get("quantity", 1))

    if not variant_id:
        variant_id = product_id

    variant = get_object_or_404(ProductVariant, id=variant_id)

    cart = request.session.get("cart", {})
    key = str(variant_id)

    if key in cart:
        cart[key]["quantity"] += quantity
    else:
        cart[key] = {
            "variant_id": variant_id,
            "quantity": quantity,
        }

    request.session["cart"] = cart
    request.session.modified = True
    messages.success(request, f"{variant.product.name} added to cart!")

    return redirect(f"{request.META.get('HTTP_REFERER', '/')}?added=true")


def add_to_cart_ajax(request, product_id):
    """AJAX endpoint: adds product to cart, returns JSON"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    try:
        variant_id = request.POST.get("variant_id") or product_id
        quantity = int(request.POST.get("quantity", 1))

        variant = get_object_or_404(ProductVariant, id=variant_id)

        cart = request.session.get("cart", {})
        key = str(variant_id)

        if key in cart:
            cart[key]["quantity"] += quantity
        else:
            cart[key] = {
                "variant_id": variant_id,
                "quantity": quantity,
            }

        request.session["cart"] = cart
        request.session.modified = True

        cart_count = sum(item.get("quantity", 1) for item in cart.values())

        return JsonResponse({
            "success": True,
            "message": f"{variant.product.name} added to cart!",
            "product_name": variant.product.name,
            "cart_count": cart_count,
        })

    except ProductVariant.DoesNotExist:
        return JsonResponse({"success": False, "error": "Product variant not found"}, status=404)
    except Exception as e:
        logger.error(f"AJAX add to cart error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def buy_now_ajax(request, product_id):
    """AJAX endpoint: adds to cart, returns URL to redirect to"""
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Invalid method"}, status=405)

    try:
        variant_id = request.POST.get("variant_id") or product_id
        quantity = int(request.POST.get("quantity", 1))

        variant = get_object_or_404(ProductVariant, id=variant_id)

        cart = request.session.get("cart", {})
        key = str(variant_id)

        if key in cart:
            cart[key]["quantity"] += quantity
        else:
            cart[key] = {
                "variant_id": variant_id,
                "quantity": quantity,
            }

        request.session["cart"] = cart
        request.session.modified = True

        if not request.user.is_authenticated:
            redirect_url = "/login/"
        else:
            redirect_url = "/checkout/"

        return JsonResponse({
            "success": True,
            "message": f"{variant.product.name} added. Redirecting...",
            "redirect_url": redirect_url,
        })

    except ProductVariant.DoesNotExist:
        return JsonResponse({"success": False, "error": "Product variant not found"}, status=404)
    except Exception as e:
        logger.error(f"AJAX buy now error: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def cart_count(request):
    """Return the number of items in the cart as JSON"""
    cart = request.session.get("cart", {})
    count = sum(item.get("quantity", 1) for item in cart.values())
    return JsonResponse({"count": count})


def clear_cart(request):
    """DEBUG endpoint: clear the cart"""
    request.session["cart"] = {}
    request.session.modified = True
    messages.success(request, "Cart cleared!")
    return JsonResponse({"success": True, "message": "Cart cleared", "count": 0})


def cart(request):
    """View the shopping cart"""
    cart_data = request.session.get("cart", {})
    cart_items = []
    total_price = Decimal("0")

    for key, item in cart_data.items():
        variant_id = item.get("variant_id")
        if not variant_id:
            continue

        try:
            variant = ProductVariant.objects.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            continue

        quantity = item.get("quantity", 1)
        item_total = variant.price * quantity
        total_price += item_total

        cart_items.append({
            "key": key,
            "product": variant.product,
            "size": variant.size,    # ⭐ FIX: use .size not .get_size_display()
            "price": variant.price,
            "quantity": quantity,
            "item_total": item_total,
        })

    gst = total_price * Decimal("0.18")
    grand_total = total_price + gst

    return render(request, "store/cart.html", {
        "cart_items": cart_items,
        "total_price": total_price,
        "gst": gst,
        "grand_total": grand_total,
    })

def cart_count(request):
    """Return the number of items in the cart as JSON"""
    cart = request.session.get("cart", {})
    count = sum(item.get("quantity", 1) for item in cart.values())
    return JsonResponse({"count": count})


def remove_from_cart(request, key):
    cart = request.session.get("cart", {})
    if key in cart:
        del cart[key]
        request.session["cart"] = cart
        request.session.modified = True
        messages.success(request, "Item removed from cart.")
    else:
        messages.error(request, "Item not found in cart.")
    return redirect("cart")


# =============================================
# UPDATE CART QUANTITY
# =============================================
def update_cart_quantity(request, key, quantity):
    if request.method == 'GET':
        cart = request.session.get("cart", {})

        if key in cart:
            cart[key]["quantity"] = quantity
            request.session["cart"] = cart
            request.session.modified = True

            variant = get_object_or_404(ProductVariant, id=cart[key]["variant_id"])
            item_total = variant.price * quantity

            total_price = 0
            for item in cart.values():
                try:
                    v = ProductVariant.objects.get(id=item["variant_id"])
                    total_price += v.price * item["quantity"]
                except:
                    continue

            gst = total_price * Decimal("0.18")
            grand_total = total_price + gst

            return JsonResponse({
                'success': True,
                'item_total': float(item_total),
                'total_price': float(total_price),
                'gst': float(gst),
                'grand_total': float(grand_total),
            })
        else:
            return JsonResponse({'success': False, 'error': 'Item not found'})

    return JsonResponse({'success': False, 'error': 'Invalid request'})


# =============================================
# BUY NOW VIEW (non-AJAX fallback)
# =============================================
def buy_now(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        variant_id = request.POST.get('variant_id')
        quantity = int(request.POST.get('quantity', 1))

        if not variant_id:
            variant_id = product_id

        cart = request.session.get('cart', {})
        item_key = str(variant_id)

        if item_key in cart:
            cart[item_key]['quantity'] += quantity
        else:
            cart[item_key] = {
                'variant_id': variant_id,
                'quantity': quantity,
            }

        request.session['cart'] = cart
        request.session.modified = True
        messages.success(request, f'{product.name} added to cart! Proceeding to checkout...')

        if not request.user.is_authenticated:
            return redirect('login')

        return redirect('checkout')

    return redirect('home')


# =============================================
# ✅ CHECKOUT VIEW - REQUIRES LOGIN
# =============================================
@login_required(login_url='login')
def checkout(request):
    cart = request.session.get("cart", {})
    if not cart:
        messages.error(request, "Your cart is empty")
        return redirect("cart")

    total_price = 0
    cart_items = []

    for item in cart.values():
        try:
            variant = ProductVariant.objects.get(id=item["variant_id"])
            quantity = item["quantity"]
            item_total = variant.price * quantity
            total_price += item_total

            cart_items.append({
                "product": variant.product,
                "quantity": quantity,
                "item_total": item_total,
            })
        except:
            continue

    gst = total_price * Decimal("0.18")
    grand_total = total_price + gst

    if request.method == "POST":
        request.session["customer_details"] = {
            "name": request.POST.get("name"),
            "phone": request.POST.get("phone"),
            "address": request.POST.get("address"),
        }
        return redirect("payment")

    return render(request, "store/checkout.html", {
        "cart_items": cart_items,
        "total_price": total_price,
        "gst": gst,
        "grand_total": grand_total,
    })


# =============================================
# ✅ PAYMENT VIEW - REQUIRES LOGIN
# =============================================
@login_required(login_url='login')
def payment(request):
    cart = request.session.get("cart", {})
    customer = request.session.get("customer_details")

    if not cart or not customer:
        messages.error(request, "Cart is empty")
        return redirect("cart")

    total_price = 0
    cart_items = []

    for item in cart.values():
        try:
            variant = ProductVariant.objects.get(id=item["variant_id"])
            quantity = item["quantity"]
            item_total = variant.price * quantity
            total_price += item_total

            cart_items.append({
                "variant": variant,
                "quantity": quantity,
                "price": variant.price,
            })
        except ProductVariant.DoesNotExist:
            messages.error(request, "Some items in your cart are no longer available.")
            return redirect("cart")

    gst = total_price * Decimal("0.18")
    grand_total = total_price + gst

    if request.method == "POST":
        payment_method = request.POST.get("payment_method")

        if payment_method == "mpesa":
            phone = request.POST.get("phone")

            if not phone:
                messages.error(request, "Phone number is required")
                return render(request, "store/payment.html", {
                    "grand_total": grand_total,
                    "cart_items": cart_items,
                    "gst": gst,
                    "total_price": total_price,
                })

            phone = format_phone_number(phone)

            order = Order.objects.create(
                user=request.user,
                name=customer["name"],
                phone=phone,
                address=customer["address"],
                total_price=total_price,
                gst=gst,
                grand_total=grand_total,
                status="PAYMENT_PENDING"
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    variant=item["variant"],
                    quantity=item["quantity"],
                    price=item["price"],
                )

            try:
                result = initiate_mpesa_payment(phone, float(grand_total), order.id)

                if result['success']:
                    order.checkout_request_id = result.get('checkout_request_id')
                    order.merchant_request_id = result.get('merchant_request_id')
                    order.save()

                    messages.info(request, "Please check your phone and enter your M-Pesa PIN.")
                    return redirect('payment_status', order_id=order.id)
                else:
                    error_msg = result.get('error', 'Unknown error')
                    logger.error(f"M-Pesa payment failed for order {order.id}: {error_msg}")
                    order.delete()

                    messages.error(request, f"Payment failed: {error_msg}")
                    return render(request, "store/payment.html", {
                        "grand_total": grand_total,
                        "cart_items": cart_items,
                        "gst": gst,
                        "total_price": total_price,
                    })
            except Exception as e:
                logger.error(f"M-Pesa exception for order {order.id}: {str(e)}")
                order.delete()
                messages.error(request, f"Payment error: {str(e)}")
                return render(request, "store/payment.html", {
                    "grand_total": grand_total,
                    "cart_items": cart_items,
                    "gst": gst,
                    "total_price": total_price,
                })

        elif payment_method == "card":
            request.session['payment_method'] = 'card'
            return redirect("process_card_payment")

        elif payment_method == "bank_transfer":
            phone = request.POST.get("phone")
            utr_last6 = request.POST.get("utr_last6")
            screenshot = request.FILES.get("payment_screenshot")

            if not phone or not utr_last6:
                messages.error(request, "Phone number and UTR are required")
                return render(request, "store/payment.html", {
                    "grand_total": grand_total,
                    "cart_items": cart_items,
                    "gst": gst,
                    "total_price": total_price,
                })

            order = Order.objects.create(
                user=request.user,
                name=customer["name"],
                phone=phone,
                address=customer["address"],
                total_price=total_price,
                gst=gst,
                grand_total=grand_total,
                utr_last6=utr_last6,
                payment_screenshot=screenshot,
                status="PAYMENT_PENDING"
            )

            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    variant=item["variant"],
                    quantity=item["quantity"],
                    price=item["price"],
                )

            request.session["cart"] = {}
            request.session.pop("customer_details", None)

            messages.success(request, f"Order #{order.id} placed successfully!")
            return redirect("order_success", order_id=order.id)

    return render(request, "store/payment.html", {
        "grand_total": grand_total,
        "cart_items": cart_items,
        "gst": gst,
        "total_price": total_price,
    })


# =============================================
# ✅ CARD PAYMENT PROCESSING - REQUIRES LOGIN
# =============================================
@login_required(login_url='login')
def process_card_payment(request):
    if request.method != "POST":
        return redirect("payment")

    try:
        cart = request.session.get("cart", {})
        customer = request.session.get("customer_details")

        if not cart or not customer:
            messages.error(request, "Cart is empty")
            return redirect("cart")

        total_price = Decimal('0')
        cart_items = []

        for item in cart.values():
            try:
                variant = ProductVariant.objects.get(id=item["variant_id"])
                quantity = item["quantity"]
                item_total = variant.price * quantity
                total_price += item_total

                cart_items.append({
                    "variant": variant,
                    "quantity": quantity,
                    "price": variant.price,
                })
            except:
                continue

        gst = total_price * Decimal("0.18")
        grand_total = total_price + gst

        cardholder_name = request.POST.get("cardholder_name")
        card_number = request.POST.get("card_number")
        expiry = request.POST.get("expiry")
        cvv = request.POST.get("cvv")

        if not all([cardholder_name, card_number, expiry, cvv]):
            messages.error(request, "All card fields are required")
            return redirect("payment")

        card_number_clean = ''.join(filter(str.isdigit, card_number))
        if len(card_number_clean) < 16:
            messages.error(request, "Invalid card number")
            return redirect("payment")

        order = Order.objects.create(
            user=request.user,
            name=customer.get("name", ""),
            phone=customer.get("phone", ""),
            address=customer.get("address", ""),
            total_price=total_price,
            gst=gst,
            grand_total=grand_total,
            status="PAID",
            utr_last6=card_number_clean[-6:],
        )

        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                variant=item["variant"],
                quantity=item["quantity"],
                price=item["price"],
            )

        request.session["cart"] = {}
        request.session.pop("customer_details", None)

        messages.success(request, f"Payment successful! Order #{order.id} confirmed.")
        return redirect("order_success", order_id=order.id)

    except Exception as e:
        logger.error(f"Card payment error: {str(e)}")
        messages.error(request, f"Payment processing error: {str(e)}")
        return redirect("payment")


# =============================================
# ORDER VIEWS
# =============================================
@login_required(login_url='login')
def my_orders(request):
    all_orders = Order.objects.filter(user=request.user).order_by("-created_at")

    pending_count = all_orders.filter(status='PAYMENT_PENDING').count()
    processing_count = all_orders.filter(status='PROCESSING').count()
    packed_count = all_orders.filter(status='PACKED').count()
    shipped_count = all_orders.filter(status='SHIPPED').count()
    out_for_delivery_count = all_orders.filter(status='OUT_FOR_DELIVERY').count()
    delivered_count = all_orders.filter(status='DELIVERED').count()
    cancelled_count = all_orders.filter(status='CANCELLED').count()
    failed_count = all_orders.filter(status='FAILED').count()
    refunded_count = all_orders.filter(status='REFUNDED').count()
    paid_count = all_orders.filter(status='PAID').count()
    placed_count = all_orders.filter(status='PLACED').count()
    total_orders = all_orders.count()

    for order in all_orders:
        if order.mpesa_receipt_number:
            order.payment_method = 'M-Pesa'
        elif order.utr_last6:
            order.payment_method = 'Bank Transfer'
        else:
            order.payment_method = 'Card'

    return render(request, "store/my_orders.html", {
        "orders": all_orders,
        "pending_count": pending_count,
        "processing_count": processing_count,
        "packed_count": packed_count,
        "shipped_count": shipped_count,
        "out_for_delivery_count": out_for_delivery_count,
        "delivered_count": delivered_count,
        "cancelled_count": cancelled_count,
        "failed_count": failed_count,
        "refunded_count": refunded_count,
        "paid_count": paid_count,
        "placed_count": placed_count,
        "total_orders": total_orders,
    })


@login_required(login_url='login')
def cancel_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    if order.status in ["CANCELLED", "DELIVERED", "REFUNDED"]:
        messages.error(request, "This order cannot be cancelled.")
        return redirect('my_orders')

    if request.method == "POST":
        reason = request.POST.get("reason")
        other_reason = request.POST.get("other_reason", "")

        if reason == "other" and other_reason:
            final_reason = other_reason
        elif reason:
            reason_map = {
                "too_costly": "It's too costly",
                "found_other": "I found another product that fulfills my need",
                "not_using": "I don't use it enough",
                "payment_failed": "Payment failed and I want to try again later",
            }
            final_reason = reason_map.get(reason, reason)
        else:
            final_reason = "No reason provided"

        order.status = "CANCELLED"
        order.cancellation_reason = final_reason
        order.cancelled_at = timezone.now()
        order.save()

        messages.success(request, f"Order #{order.id} has been cancelled successfully.")
        return redirect('my_orders')

    return render(request, "store/cancel_order.html", {"order": order})


@login_required(login_url='login')
def order_success(request, order_id=None):
    order = None
    if order_id and request.user.is_authenticated:
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            pass

    if not order and request.user.is_authenticated:
        order = Order.objects.filter(user=request.user).order_by('-created_at').first()

    return render(request, "store/order_success.html", {"order": order})


@login_required(login_url='login')
def payment_status(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, "store/payment_status.html", {"order": order})


@login_required(login_url='login')
def check_payment_status_ajax(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id, user=request.user)

        if order.status == "PAID":
            return JsonResponse({
                'status': 'completed',
                'message': 'Payment successful!',
                'receipt': order.mpesa_receipt_number,
            })
        elif order.status == "FAILED":
            return JsonResponse({
                'status': 'failed',
                'message': order.mpesa_result_desc or 'Payment failed'
            })
        elif order.checkout_request_id:
            result = query_mpesa_status(order.checkout_request_id)

            if result.get('success'):
                if result.get('status') == 'completed':
                    order.status = "PAID"
                    order.mpesa_receipt_number = result.get('mpesa_receipt_number')
                    order.save()

                    request.session["cart"] = {}
                    request.session.pop("customer_details", None)

                    return JsonResponse({
                        'status': 'completed',
                        'message': 'Payment successful!',
                        'receipt': order.mpesa_receipt_number
                    })
                elif result.get('status') == 'failed':
                    order.status = "FAILED"
                    order.mpesa_result_desc = result.get('result_desc')
                    order.save()
                    return JsonResponse({
                        'status': 'failed',
                        'message': result.get('result_desc', 'Payment failed')
                    })
                else:
                    return JsonResponse({
                        'status': 'pending',
                        'message': 'Payment is still pending. Please check your phone.'
                    })
            else:
                return JsonResponse({
                    'status': 'pending',
                    'message': 'Payment is still processing. Please check your phone.'
                })

        return JsonResponse({
            'status': 'unknown',
            'message': 'Unable to determine payment status'
        })

    except Exception as e:
        logger.error(f"Status check error: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


# =============================================
# BLOG VIEWS
# =============================================
def blog_list(request):
    posts = BlogPost.objects.filter(status='published').order_by('-created_at')
    featured = posts.filter(is_featured=True).first()
    categories = BlogPost.CATEGORY_CHOICES

    return render(request, "store/blog_list.html", {
        "posts": posts,
        "featured": featured,
        "categories": categories,
    })


def blog_detail(request, slug):
    post = get_object_or_404(BlogPost, slug=slug, status='published')
    post.views += 1
    post.save()

    related_posts = BlogPost.objects.filter(
        category=post.category,
        status='published'
    ).exclude(id=post.id)[:3]

    return render(request, "store/blog_detail.html", {
        "post": post,
        "related_posts": related_posts,
    })


# =============================================
# BLOG ADMIN VIEWS
# =============================================
@login_required(login_url='login')
def admin_create_post(request):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to create posts.")
        return redirect('home')

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        content = request.POST.get("content", "").strip()
        excerpt = request.POST.get("excerpt", "").strip()
        category = request.POST.get("category", "wellness")
        status = request.POST.get("status", "published")
        is_featured = request.POST.get("is_featured") == "on"
        featured_image = request.FILES.get("featured_image")

        if not title:
            messages.error(request, "Title is required.")
            categories = BlogPost.CATEGORY_CHOICES
            return render(request, "store/admin/create_post.html", {"categories": categories})

        if not content:
            messages.error(request, "Content is required.")
            categories = BlogPost.CATEGORY_CHOICES
            return render(request, "store/admin/create_post.html", {"categories": categories})

        try:
            post = BlogPost.objects.create(
                title=title,
                content=content,
                excerpt=excerpt,
                category=category,
                status=status,
                is_featured=is_featured,
                author=request.user,
                published_at=timezone.now() if status == 'published' else None
            )

            if featured_image:
                post.featured_image = featured_image
                post.save()

            messages.success(request, f"✅ Post '{title}' published successfully!")
            return redirect('blog_list')

        except Exception as e:
            messages.error(request, f"Error creating post: {str(e)}")
            categories = BlogPost.CATEGORY_CHOICES
            return render(request, "store/admin/create_post.html", {"categories": categories})

    categories = BlogPost.CATEGORY_CHOICES
    return render(request, "store/admin/create_post.html", {"categories": categories})


@login_required(login_url='login')
def admin_edit_post(request, post_id):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to edit posts.")
        return redirect('home')

    post = get_object_or_404(BlogPost, id=post_id)

    if request.method == "POST":
        post.title = request.POST.get("title")
        post.content = request.POST.get("content")
        post.excerpt = request.POST.get("excerpt")
        post.category = request.POST.get("category")
        post.status = request.POST.get("status")
        post.is_featured = request.POST.get("is_featured") == "on"

        if request.FILES.get("featured_image"):
            post.featured_image = request.FILES.get("featured_image")

        if post.status == 'published' and not post.published_at:
            post.published_at = timezone.now()

        post.save()

        messages.success(request, f"Post '{post.title}' updated successfully!")
        return redirect('blog_detail', slug=post.slug)

    categories = BlogPost.CATEGORY_CHOICES
    return render(request, "store/admin/edit_post.html", {"post": post, "categories": categories})


@login_required(login_url='login')
def admin_delete_post(request, post_id):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission to delete posts.")
        return redirect('home')

    post = get_object_or_404(BlogPost, id=post_id)

    if request.method == "POST":
        post_title = post.title
        post.delete()
        messages.success(request, f"Post '{post_title}' deleted successfully.")
        return redirect('blog_list')

    return render(request, "store/admin/delete_post.html", {"post": post})


def upload_blog_image(request):
    if request.method == 'POST' and request.FILES.get('image'):
        image = request.FILES['image']
        filename = default_storage.save(f'blog_uploads/{image.name}', ContentFile(image.read()))
        return JsonResponse({
            'success': True,
            'image_url': default_storage.url(filename)
        })
    return JsonResponse({'success': False}, status=400)


# =============================================
# ADMIN PRODUCT VIEWS
# =============================================
@login_required(login_url='login')
def admin_product_list(request):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission.")
        return redirect('home')

    products = Product.objects.all().order_by('-created_at')
    return render(request, "store/admin/product_list.html", {"products": products})


@login_required(login_url='login')
def admin_product_add(request):
    return admin_product_form(request, 0)


@login_required(login_url='login')
def admin_product_form(request, product_id):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission.")
        return redirect('home')

    product = None
    if product_id > 0:
        product = get_object_or_404(Product, id=product_id)

    categories = Category.objects.filter(is_active=True)

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        category_id = request.POST.get("category")
        price = request.POST.get("price")
        compare_price = request.POST.get("compare_price")
        stock = request.POST.get("stock")
        is_active = request.POST.get("is_active") == "on"
        is_featured = request.POST.get("is_featured") == "on"
        is_best_seller = request.POST.get("is_best_seller") == "on"
        image = request.FILES.get("image")

        if not name or not price:
            messages.error(request, "Name and price are required.")
            return render(request, "store/admin/product_form.html", {
                "product": product,
                "categories": categories
            })

        if product:
            product.name = name
            product.description = description
            product.category_id = category_id if category_id else None
            product.price = price
            product.compare_price = compare_price if compare_price else None
            product.stock = stock if stock else 0
            product.is_active = is_active
            product.is_featured = is_featured
            product.is_best_seller = is_best_seller
            if image:
                product.image = image
            product.save()
            messages.success(request, f"Product '{name}' updated successfully!")
        else:
            product = Product.objects.create(
                name=name,
                description=description,
                category_id=category_id if category_id else None,
                price=price,
                compare_price=compare_price if compare_price else None,
                stock=stock if stock else 0,
                is_active=is_active,
                is_featured=is_featured,
                is_best_seller=is_best_seller,
                image=image
            )
            messages.success(request, f"Product '{name}' created successfully!")

        return redirect('admin_product_list')

    return render(request, "store/admin_create_product.html", {
        "product": product,
        "categories": categories
    })


@login_required(login_url='login')
def admin_product_delete(request, product_id):
    if not request.user.is_staff:
        messages.error(request, "You don't have permission.")
        return redirect('home')

    product = get_object_or_404(Product, id=product_id)
    product_name = product.name
    product.delete()
    messages.success(request, f"Product '{product_name}' deleted successfully!")
    return redirect('admin_product_list')


# =============================================
# AUTHENTICATION VIEWS
# =============================================
def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, f"Welcome back, {username}!")
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password")
            return render(request, "store/login.html", {"error": "Invalid credentials"})

    return render(request, "store/login.html")


def signup_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email", "")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password != confirm_password:
            messages.error(request, "Passwords do not match")
            return render(request, "store/signup.html", {"error": "Passwords do not match"})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return render(request, "store/signup.html", {"error": "Username already exists"})

        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters")
            return render(request, "store/signup.html", {"error": "Password must be at least 8 characters"})

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        login(request, user)
        messages.success(request, f"Welcome {username}! Your account has been created.")
        return redirect("home")

    return render(request, "store/signup.html")


def logout_view(request):
    cart = request.session.get("cart", {})
    logout(request)
    request.session["cart"] = cart
    messages.info(request, "You have been logged out.")
    return redirect("home")


# =============================================
# MPESA HELPERS
# =============================================
def format_phone_number(phone):
    phone = ''.join(filter(str.isdigit, phone))

    if phone.startswith('254'):
        phone = phone[3:]
    elif phone.startswith('0'):
        phone = phone[1:]
    elif phone.startswith('+'):
        phone = phone[1:]
        if phone.startswith('254'):
            phone = phone[3:]

    if len(phone) == 9 and phone.startswith(('7', '1')):
        return f"254{phone}"
    elif len(phone) == 10 and phone.startswith(('7', '1')):
        return f"254{phone}"
    else:
        if len(phone) > 9:
            phone = phone[-9:]
        return f"254{phone}"


def initiate_mpesa_payment(phone, amount, order_id):
    try:
        phone = format_phone_number(phone)

        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        passkey = settings.MPESA_PASSKEY
        shortcode = settings.MPESA_SHORTCODE
        base_url = settings.MPESA_BASE_URL

        auth_string = f"{consumer_key}:{consumer_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()

        auth_url = f"{base_url}/oauth/v1/generate?grant_type=client_credentials"

        headers = {
            "Authorization": f"Basic {auth_encoded}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

        response = requests.get(auth_url, headers=headers, timeout=30)

        if response.status_code != 200:
            return {
                'success': False,
                'error': f'Authentication failed: {response.text[:200]}'
            }

        access_token = response.json().get('access_token')

        if not access_token:
            return {'success': False, 'error': 'No access token received'}

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_string = f"{shortcode}{passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()

        account_ref = f"ORDER{order_id}"
        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": int(amount),
            "PartyA": phone,
            "PartyB": shortcode,
            "PhoneNumber": phone,
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": account_ref[:12],
            "TransactionDesc": f"Order {order_id}"
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        stk_url = f"{base_url}/mpesa/stkpush/v1/processrequest"

        response = requests.post(stk_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            result = response.json()

            if result.get('ResponseCode') == '0':
                return {
                    'success': True,
                    'checkout_request_id': result.get('CheckoutRequestID'),
                    'merchant_request_id': result.get('MerchantRequestID'),
                    'response_description': result.get('ResponseDescription'),
                }
            else:
                return {
                    'success': False,
                    'error': result.get('ResponseDescription', 'Unknown error')
                }
        else:
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text[:200]}'
            }

    except Exception as e:
        logger.error(f"STK Push error: {str(e)}")
        return {'success': False, 'error': str(e)}


def query_mpesa_status(checkout_request_id):
    try:
        consumer_key = settings.MPESA_CONSUMER_KEY
        consumer_secret = settings.MPESA_CONSUMER_SECRET
        passkey = settings.MPESA_PASSKEY
        shortcode = settings.MPESA_SHORTCODE
        base_url = settings.MPESA_BASE_URL

        auth_string = f"{consumer_key}:{consumer_secret}"
        auth_encoded = base64.b64encode(auth_string.encode()).decode()

        auth_url = f"{base_url}/oauth/v1/generate?grant_type=client_credentials"
        headers = {
            "Authorization": f"Basic {auth_encoded}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }

        response = requests.get(auth_url, headers=headers, timeout=30)

        if response.status_code != 200:
            return {'success': False, 'error': 'Failed to authenticate'}

        access_token = response.json().get('access_token')

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_string = f"{shortcode}{passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()

        payload = {
            "BusinessShortCode": shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "CheckoutRequestID": checkout_request_id
        }

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        query_url = f"{base_url}/mpesa/stkpushquery/v1/query"

        response = requests.post(query_url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            result = response.json()
            result_code = result.get('ResultCode')

            if result_code == '0':
                return {
                    'success': True,
                    'status': 'completed',
                    'mpesa_receipt_number': result.get('MpesaReceiptNumber'),
                    'amount': result.get('Amount'),
                    'result_desc': result.get('ResultDesc')
                }
            elif result_code == '1037':
                return {
                    'success': True,
                    'status': 'pending',
                    'result_desc': result.get('ResultDesc', 'Pending')
                }
            else:
                return {
                    'success': True,
                    'status': 'failed',
                    'result_desc': result.get('ResultDesc', 'Payment failed')
                }
        else:
            return {'success': False, 'error': 'Failed to query status'}

    except Exception as e:
        logger.error(f"Query status error: {str(e)}")
        return {'success': False, 'error': str(e)}


# =============================================
# MPESA CALLBACK
# =============================================
@csrf_exempt
def mpesa_callback(request):
    if request.method != "POST":
        return JsonResponse({"ResultCode": 1, "ResultDesc": "Invalid method"})

    try:
        data = json.loads(request.body)
        logger.info(f"M-Pesa Callback received")

        stk_callback = data.get('Body', {}).get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        checkout_request_id = stk_callback.get('CheckoutRequestID')

        try:
            order = Order.objects.get(checkout_request_id=checkout_request_id)
        except Order.DoesNotExist:
            logger.error(f"Order not found for CheckoutRequestID: {checkout_request_id}")
            return JsonResponse({"ResultCode": 1, "ResultDesc": "Order not found"})

        if result_code == "0":
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])

            mpesa_receipt = None
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')

            order.mpesa_receipt_number = mpesa_receipt
            order.mpesa_result_code = result_code
            order.mpesa_result_desc = result_desc
            order.status = "PAID"
            order.save()

            logger.info(f"✅ Order #{order.id} updated to PAID")

        else:
            order.status = "FAILED"
            order.mpesa_result_code = result_code
            order.mpesa_result_desc = result_desc
            order.save()

            logger.error(f"❌ Order #{order.id} updated to FAILED")

        return JsonResponse({"ResultCode": 0, "ResultDesc": "Success"})

    except Exception as e:
        logger.error(f"M-Pesa callback error: {str(e)}")
        return JsonResponse({"ResultCode": 1, "ResultDesc": str(e)})


def initiate_stk_push(request):
    if request.method == "POST":
        phone = request.POST.get("phone")
        amount = request.POST.get("amount")
        return JsonResponse({
            "message": "STK Push Initiated",
            "phone": phone,
            "amount": amount
        })
    return redirect("payment")

