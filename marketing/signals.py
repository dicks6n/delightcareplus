from catalog.models import Variant


def restore_bag(sender, request, user, **kwargs):
    """On login, bring back what the member left in their bag on another device (guest items are kept too)."""
    from cart.cart import SESSION_KEY

    from .models import SavedBag
    saved = SavedBag.objects.filter(user=user).first()
    if not saved or not saved.items:
        return
    bag = dict(request.session.get(SESSION_KEY, {}))
    live = set(Variant.objects.filter(id__in=[int(k) for k in saved.items if str(k).isdigit()],
                                      product__is_active=True).values_list("id", flat=True))
    for key, qty in saved.items.items():
        if str(key).isdigit() and int(key) in live and str(key) not in bag:
            bag[str(key)] = int(qty)
    request.session[SESSION_KEY] = bag
    request.session.modified = True
