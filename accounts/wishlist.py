"""Wishlist that works for guests (session) and members (database)."""
from .models import WishlistItem

SESSION_KEY = "wishlist"


def get_ids(request):
    if request.user.is_authenticated:
        return list(WishlistItem.objects.filter(user=request.user).values_list("product_id", flat=True))
    return [int(i) for i in request.session.get(SESSION_KEY, [])]


def toggle(request, product_id):
    """Returns True if added, False if removed."""
    if request.user.is_authenticated:
        item, created = WishlistItem.objects.get_or_create(user=request.user, product_id=product_id)
        if not created:
            item.delete()
        return created
    ids = get_ids(request)
    if product_id in ids:
        ids.remove(product_id)
        added = False
    else:
        ids.insert(0, product_id)
        added = True
    request.session[SESSION_KEY] = ids
    return added


def add(request, product_id):
    if product_id not in get_ids(request):
        toggle(request, product_id)


def remove(request, product_id):
    if product_id in get_ids(request):
        toggle(request, product_id)


def merge_session_into_user(request, user):
    """Called right after login: keep what the guest saved."""
    ids = request.session.pop(SESSION_KEY, [])
    for pid in ids:
        WishlistItem.objects.get_or_create(user=user, product_id=pid)
