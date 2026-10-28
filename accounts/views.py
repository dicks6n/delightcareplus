from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from core.mail import send
from core.utils import safe_next
from orders.models import Order

from . import wishlist


def _finish_login(request, user):
    login(request, user)
    wishlist.merge_session_into_user(request, user)
    # Attach guest orders placed in this browser to the account
    numbers = request.session.get("my_orders", [])
    if numbers:
        Order.objects.filter(number__in=numbers, user__isnull=True).update(user=user)


def login_view(request):
    if request.user.is_authenticated:
        return redirect(safe_next(request, reverse("core:home")))

    ctx = {"next": request.GET.get("next", "")}
    if request.method == "POST":
        ident = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        if "@" in ident:
            match = User.objects.filter(email__iexact=ident).first()
            ident = match.username if match else ident
        user = authenticate(request, username=ident, password=password)
        if user:
            _finish_login(request, user)
            if not request.POST.get("remember"):
                request.session.set_expiry(0)
            messages.success(request, f"Welcome back, {user.first_name or user.username}! 🌿")
            return redirect(safe_next(request, reverse("core:home")))
        ctx.update(error="That email/username and password don't match.", username=request.POST.get("username", ""),
                   next=request.POST.get("next", ""))
    return render(request, "accounts/login.html", ctx)


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    ctx = {"next": request.GET.get("next", ""), "errors": {}, "data": {}}
    if request.method == "POST":
        data = {k: request.POST.get(k, "").strip() for k in ("first_name", "email", "phone", "password")}
        errors = {}
        if not data["first_name"]:
            errors["first_name"] = "Tell us your name."
        try:
            validate_email(data["email"])
            if User.objects.filter(email__iexact=data["email"]).exists():
                errors["email"] = "An account with this email already exists — try logging in."
        except ValidationError:
            errors["email"] = "Enter a valid email address."
        try:
            validate_password(data["password"], User(username=data["email"], email=data["email"], first_name=data["first_name"]))
        except ValidationError as e:
            errors["password"] = " ".join(e.messages)

        if not errors:
            base = (data["email"].split("@")[0] or "member")[:30]
            username, n = base, 1
            while User.objects.filter(username__iexact=username).exists():
                n += 1
                username = f"{base}{n}"
            user = User.objects.create_user(username=username, email=data["email"], password=data["password"],
                                            first_name=data["first_name"])
            user.profile.phone = data["phone"][:20]
            user.profile.marketing_opt_in = bool(request.POST.get("newsletter"))
            user.profile.save()
            _finish_login(request, user)
            send("Welcome to Delight Care Plus 🌿", "emails/welcome.html", {"user": user}, [user.email])
            messages.success(request, f"Welcome, {user.first_name}! Your account is ready.")
            return redirect(safe_next(request, reverse("core:home")))

        data.pop("password")
        ctx.update(errors=errors, data=data, next=request.POST.get("next", ""))
    return render(request, "accounts/signup.html", ctx)


def logout_view(request):
    cart = request.session.get("cart", {})
    logout(request)
    request.session["cart"] = cart
    messages.info(request, "You've been logged out. See you soon!")
    return redirect("core:home")


def password_reset(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user:
            url = request.build_absolute_uri(reverse("accounts:password_reset_confirm", args=[
                urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)]))
            send("Reset your Delight Care Plus password", "emails/password_reset.html",
                 {"user": user, "reset_url": url}, [user.email])
        messages.success(request, "If that email has an account, a reset link is on its way 📩")
        return redirect("accounts:login")
    return render(request, "accounts/password_reset.html")


def password_reset_confirm(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    valid = bool(user) and default_token_generator.check_token(user, token)
    error = ""
    if valid and request.method == "POST":
        pw, pw2 = request.POST.get("password", ""), request.POST.get("password2", "")
        if pw != pw2:
            error = "The two passwords don't match."
        else:
            try:
                validate_password(pw, user)
                user.set_password(pw)
                user.save()
                messages.success(request, "Password changed — you can log in now.")
                return redirect("accounts:login")
            except ValidationError as e:
                error = " ".join(e.messages)
    return render(request, "accounts/password_reset_confirm.html", {"valid": valid, "error": error})


@login_required
def profile(request):
    user = request.user
    p = user.profile
    if request.method == "POST":
        user.first_name = request.POST.get("first_name", "").strip()[:150]
        user.last_name = request.POST.get("last_name", "").strip()[:150]
        p.phone = request.POST.get("phone", "").strip()[:20]
        p.city = request.POST.get("city", "").strip()[:80]
        p.address = request.POST.get("address", "").strip()[:500]
        p.skin_type = request.POST.get("skin_type", "").strip()[:40]
        p.marketing_opt_in = bool(request.POST.get("marketing_opt_in"))
        user.save()
        p.save()
        messages.success(request, "Your details have been saved.")
        return redirect("accounts:profile")
    from .models import points_balance
    return render(request, "accounts/profile.html", {
        "profile": p,
        "points": points_balance(user),
        "history": user.points.all()[:10],
        "skin_types": ["", "Normal", "Dry", "Oily", "Combination", "Sensitive"],
    })


@login_required
@require_POST
def change_password(request):
    user = request.user
    if not user.check_password(request.POST.get("old_password", "")):
        messages.error(request, "Your current password is incorrect.")
        return redirect("accounts:profile")
    try:
        validate_password(request.POST.get("new_password", ""), user)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
        return redirect("accounts:profile")
    user.set_password(request.POST["new_password"])
    user.save()
    update_session_auth_hash(request, user)
    messages.success(request, "Password updated.")
    return redirect("accounts:profile")


@login_required
def my_orders(request):
    orders = request.user.orders.prefetch_related("items__variant__product").all()
    status = request.GET.get("status", "")
    groups = {
        "active": ["PENDING", "PAID", "PROCESSING", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY"],
        "delivered": ["DELIVERED"],
        "cancelled": ["CANCELLED", "FAILED", "REFUNDED"],
    }
    if status in groups:
        orders = orders.filter(status__in=groups[status])
    return render(request, "accounts/orders.html", {"orders": orders, "status": status})
