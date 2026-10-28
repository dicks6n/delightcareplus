from datetime import timedelta

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.utils import int_or

from .models import Conversation, Message

MAX_LEN = 1000
MAX_PER_MINUTE = 12


def _conversation(request, create=False):
    if not request.session.session_key:
        request.session.save()
    key = request.session.session_key
    convo = None
    if request.user.is_authenticated:
        convo = Conversation.objects.filter(user=request.user).first()
        if not convo:
            convo = Conversation.objects.filter(session_key=key, user__isnull=True).first()
            if convo:
                convo.user = request.user
                convo.save(update_fields=["user"])
    else:
        convo = Conversation.objects.filter(session_key=key, user__isnull=True).first()
    if not convo and create:
        convo = Conversation.objects.create(user=request.user if request.user.is_authenticated else None, session_key=key)
    return convo


# ------------------------------------------------------------- customer side
def messages_api(request):
    convo = _conversation(request)
    needs_name = not request.user.is_authenticated and not (convo and convo.guest_name)
    if not convo:
        return JsonResponse({"messages": [], "unread": 0, "needs_name": needs_name})
    after = int_or(request.GET.get("after"), 0, lo=0, hi=10**12)
    msgs = list(convo.messages.select_related("sender").filter(id__gt=after)[:100])
    if request.GET.get("open") == "1":
        convo.messages.filter(is_staff=True, is_read=False).update(is_read=True)
    return JsonResponse({
        "messages": [m.as_dict() for m in msgs],
        "unread": convo.messages.filter(is_staff=True, is_read=False).count(),
        "needs_name": needs_name,
    })


@require_POST
def send(request):
    body = request.POST.get("body", "").strip()[:MAX_LEN]
    if not body:
        return JsonResponse({"ok": False, "error": "Type a message first."}, status=400)
    convo = _conversation(request, create=True)
    recent = convo.messages.filter(is_staff=False, created_at__gte=timezone.now() - timedelta(minutes=1)).count()
    if recent >= MAX_PER_MINUTE:
        return JsonResponse({"ok": False, "error": "You're sending messages very fast — please wait a moment."}, status=429)
    if not request.user.is_authenticated:
        if request.POST.get("name"):
            convo.guest_name = request.POST["name"].strip()[:100]
        if request.POST.get("contact"):
            convo.guest_contact = request.POST["contact"].strip()[:120]
    if not convo.page_url:
        convo.page_url = request.POST.get("page", "")[:300]
    msg = Message.objects.create(conversation=convo, body=body, is_staff=False,
                                 sender=request.user if request.user.is_authenticated else None)
    convo.status = "open"
    convo.last_message_at = msg.created_at
    convo.save()
    return JsonResponse({"ok": True, "message": msg.as_dict()})


# ---------------------------------------------------------------- staff side
@staff_member_required
def inbox_list(request):
    status = request.GET.get("status", "open")
    q = request.GET.get("q", "").strip()
    convos = Conversation.objects.select_related("user").annotate(
        unread=Count("messages", filter=Q(messages__is_staff=False, messages__is_read=False)),
        total=Count("messages"),
    ).filter(total__gt=0)
    if status in ("open", "closed"):
        convos = convos.filter(status=status)
    if q:
        convos = convos.filter(Q(guest_name__icontains=q) | Q(guest_contact__icontains=q) | Q(user__username__icontains=q)
                               | Q(user__email__icontains=q) | Q(user__first_name__icontains=q)
                               | Q(messages__body__icontains=q)).distinct()
    rows = []
    for c in convos[:100]:
        last = c.messages.order_by("-id").first()
        rows.append({
            "id": c.id, "name": c.display_name, "contact": c.contact, "guest": c.user_id is None,
            "status": c.status, "unread": c.unread,
            "last": (("You: " if last.is_staff else "") + last.body)[:90] if last else "",
            "time": timezone.localtime(c.last_message_at).strftime("%b %d, %H:%M"),
        })
    return JsonResponse({"conversations": rows,
                         "total_unread": Message.objects.filter(is_staff=False, is_read=False).count()})


@staff_member_required
def inbox_thread(request, pk):
    from orders.models import Order

    c = get_object_or_404(Conversation.objects.select_related("user"), pk=pk)
    after = int_or(request.GET.get("after"), 0, lo=0, hi=10**12)
    msgs = list(c.messages.select_related("sender").filter(id__gt=after)[:300])
    c.messages.filter(is_staff=False, is_read=False).update(is_read=True)
    orders = []
    if c.user_id:
        orders = [{"number": o.number, "status": o.get_status_display(), "total": float(o.total),
                   "url": f"/manage/orders/{o.number}/"} for o in Order.objects.filter(user_id=c.user_id)[:5]]
    return JsonResponse({
        "conversation": {"id": c.id, "name": c.display_name, "contact": c.contact, "guest": c.user_id is None,
                         "status": c.status, "page": c.page_url, "orders": orders,
                         "started": timezone.localtime(c.created_at).strftime("%b %d, %Y %H:%M")},
        "messages": [m.as_dict() for m in msgs],
    })


@staff_member_required
@require_POST
def inbox_reply(request, pk):
    c = get_object_or_404(Conversation, pk=pk)
    body = request.POST.get("body", "").strip()[:MAX_LEN]
    if not body:
        return JsonResponse({"ok": False, "error": "Message is empty."}, status=400)
    msg = Message.objects.create(conversation=c, sender=request.user, is_staff=True, body=body)
    c.last_message_at, c.status = msg.created_at, "open"
    c.save(update_fields=["last_message_at", "status"])
    return JsonResponse({"ok": True, "message": msg.as_dict()})


@staff_member_required
@require_POST
def inbox_status(request, pk):
    c = get_object_or_404(Conversation, pk=pk)
    status = request.POST.get("status")
    if status not in ("open", "closed"):
        return JsonResponse({"ok": False}, status=400)
    c.status = status
    c.save(update_fields=["status"])
    return JsonResponse({"ok": True, "status": status})
