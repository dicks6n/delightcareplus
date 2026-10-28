/* Delight Care Plus — storefront interactions (no build step, no jQuery) */
(function () {
    "use strict";

    const $ = (sel, root = document) => root.querySelector(sel);
    const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

    const CSRF = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

    function esc(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    function kes(n) {
        return "KES " + Math.round(Number(n || 0)).toLocaleString("en-KE");
    }

    function post(url, data) {
        const body = data instanceof FormData ? data : new URLSearchParams(data || {});
        return fetch(url, {
            method: "POST",
            headers: { "X-CSRFToken": CSRF, "X-Requested-With": "XMLHttpRequest" },
            body,
            credentials: "same-origin",
        }).then(r => r.json().catch(() => ({ ok: false, message: "Something went wrong" })));
    }

    // ------------------------------------------------------------------ toasts
    function toast(message, type = "ok", link = null) {
        let stack = $(".toast-stack");
        if (!stack) {
            stack = document.createElement("div");
            stack.className = "toast-stack";
            stack.setAttribute("aria-live", "polite");
            document.body.appendChild(stack);
        }
        const t = document.createElement("div");
        t.className = "toast-x" + (type === "err" ? " err" : "");
        t.innerHTML = `<i class="fa-solid ${type === "err" ? "fa-circle-exclamation" : "fa-circle-check"}"></i>
            <span>${esc(message)}</span>${link ? `<a href="${esc(link.url)}">${esc(link.label)}</a>` : ""}`;
        stack.appendChild(t);
        setTimeout(() => { t.classList.add("out"); setTimeout(() => t.remove(), 300); }, link ? 4200 : 3000);
    }

    function setBadge(id, n) {
        $$(`[data-badge="${id}"]`).forEach(b => {
            b.textContent = n > 99 ? "99+" : n;
            b.classList.toggle("show", n > 0);
            const btn = b.closest(".icon-btn");
            if (btn) { btn.classList.remove("bump"); void btn.offsetWidth; btn.classList.add("bump"); }
        });
    }

    window.DCP = { $, $$, esc, kes, post, toast, setBadge, csrf: CSRF };

    // ------------------------------------------------------------------ header
    const header = $(".site-header");
    const topBtn = $(".fab.top");
    const onScroll = () => {
        const y = window.scrollY;
        if (header) header.classList.toggle("scrolled", y > 10);
        if (topBtn) topBtn.classList.toggle("show", y > 600);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    if (topBtn) topBtn.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));

    // Mobile drawer
    const drawer = $("#drawer");
    $$("[data-drawer-open]").forEach(b => b.addEventListener("click", () => { drawer.classList.add("open"); document.body.style.overflow = "hidden"; }));
    $$("[data-drawer-close]").forEach(b => b.addEventListener("click", () => { drawer.classList.remove("open"); document.body.style.overflow = ""; }));

    // Flash messages fade
    $$(".flash").forEach(f => {
        const btn = f.querySelector("button");
        if (btn) btn.addEventListener("click", () => f.remove());
        setTimeout(() => { f.style.transition = "opacity .5s"; f.style.opacity = "0"; setTimeout(() => f.remove(), 500); }, 6000);
    });

    // ------------------------------------------------------------------ search suggest
    $$(".header-search").forEach(box => {
        const input = box.querySelector("input[name=q]");
        const list = box.querySelector(".suggest");
        if (!input || !list) return;
        let timer, ctrl, active = -1;

        input.addEventListener("input", () => {
            clearTimeout(timer);
            const q = input.value.trim();
            if (q.length < 2) { list.classList.remove("show"); return; }
            timer = setTimeout(() => {
                if (ctrl) ctrl.abort();
                ctrl = new AbortController();
                fetch(`/shop/api/search/?q=${encodeURIComponent(q)}`, { signal: ctrl.signal })
                    .then(r => r.json())
                    .then(d => {
                        active = -1;
                        list.innerHTML = d.results.length
                            ? d.results.map(r => `<a href="${esc(r.url)}">
                                    ${r.image ? `<img src="${esc(r.image)}" alt="">` : '<span class="ph"></span>'}
                                    <span class="nm">${esc(r.name)}<span class="br">${esc(r.brand)}</span></span>
                                    <span class="pr">${kes(r.price)}</span></a>`).join("") +
                              `<a class="all" href="${esc(d.all_url)}">See all results for “${esc(q)}” →</a>`
                            : `<div class="empty">No products match “${esc(q)}”. Try “serum”, “collagen” or “tea”.</div>`;
                        list.classList.add("show");
                    }).catch(() => {});
            }, 200);
        });
        input.addEventListener("keydown", e => {
            const links = $$("a", list);
            if (!links.length) return;
            if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                e.preventDefault();
                active = (active + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
                links.forEach((l, i) => l.classList.toggle("active", i === active));
            } else if (e.key === "Enter" && active >= 0) {
                e.preventDefault();
                window.location.href = links[active].href;
            } else if (e.key === "Escape") {
                list.classList.remove("show");
            }
        });
        document.addEventListener("click", e => { if (!box.contains(e.target)) list.classList.remove("show"); });
    });
    document.addEventListener("keydown", e => {
        if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
            const input = $(".header-search:not(.mobile) input") || $(".header-search input");
            if (input && input.offsetParent) { e.preventDefault(); input.focus(); }
        }
    });

    // ------------------------------------------------------------------ add to cart (any .js-add form)
    document.addEventListener("submit", e => {
        const form = e.target.closest(".js-add");
        if (!form) return;
        e.preventDefault();
        const btn = e.submitter || form.querySelector("button[type=submit]");
        const fd = new FormData(form);
        if (btn && btn.name) fd.append(btn.name, btn.value || "1");
        const html = btn ? btn.innerHTML : "";
        if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>'; }
        post(form.action, fd).then(d => {
            if (d.redirect) { window.location.href = d.redirect; return; }
            if (!d.ok) { toast(d.message || "Couldn't add that item", "err"); return; }
            setBadge("cart", d.cart_count);
            toast(d.message, "ok", { url: "/cart/", label: "View bag →" });
            document.dispatchEvent(new CustomEvent("dcp:cart", { detail: d }));
        }).catch(() => toast("Connection problem — please try again", "err"))
          .finally(() => { if (btn) { btn.disabled = false; btn.innerHTML = html; } });
    });

    // ------------------------------------------------------------------ wishlist + compare
    document.addEventListener("click", e => {
        const wish = e.target.closest(".js-wish");
        if (wish) {
            e.preventDefault();
            const id = wish.dataset.id;
            post(`/shop/wishlist/${id}/toggle/`).then(d => {
                if (!d.ok) return toast("Couldn't update your wishlist", "err");
                $$(`.js-wish[data-id="${id}"]`).forEach(b => {
                    b.classList.toggle("on", d.added);
                    const i = b.querySelector("i");
                    if (i) { i.classList.toggle("fa-solid", d.added); i.classList.toggle("fa-regular", !d.added); }
                    b.setAttribute("aria-pressed", d.added);
                    b.classList.remove("pop"); void b.offsetWidth; b.classList.add("pop");
                });
                setBadge("wishlist", d.count);
                toast(d.message, "ok", d.added ? { url: "/shop/wishlist/", label: "View →" } : null);
                document.dispatchEvent(new CustomEvent("dcp:wishlist", { detail: { id, ...d } }));
            });
            return;
        }
        const cmp = e.target.closest(".js-compare");
        if (cmp) {
            e.preventDefault();
            post(`/shop/compare/${cmp.dataset.id}/toggle/`).then(d => {
                $$(`.js-compare[data-id="${cmp.dataset.id}"]`).forEach(b => b.classList.toggle("on", d.added));
                updateCompareBar(d.count);
                toast(d.added ? "Added to compare" : "Removed from compare", "ok", d.count > 1 ? { url: "/shop/compare/", label: `Compare (${d.count}) →` } : null);
            });
        }
    });

    function updateCompareBar(n) {
        const bar = $("#compareBar");
        if (!bar) return;
        bar.classList.toggle("show", n > 0);
        const c = bar.querySelector("[data-count]");
        if (c) c.textContent = n;
    }
    if ($("#compareBar")) updateCompareBar(parseInt($("#compareBar").dataset.initial || "0", 10));

    // ------------------------------------------------------------------ quick view
    const qv = $("#quickView");
    function stars(avg) {
        let s = "";
        for (let i = 1; i <= 5; i++) s += `<i class="fa-${avg >= i - 0.25 ? "solid" : "regular"} fa-star"></i>`;
        return s;
    }
    function openQuickView(id) {
        if (!qv) return;
        const card = qv.querySelector(".modal-card");
        card.innerHTML = '<button class="x" data-close aria-label="Close"><i class="fa-solid fa-xmark"></i></button><div class="qv"><div class="qv-loading"><i class="fa-solid fa-spinner fa-spin"></i></div></div>';
        qv.classList.add("open");
        document.body.style.overflow = "hidden";
        fetch(`/shop/api/quick/${id}/`).then(r => r.json()).then(p => {
            const multi = p.variants.length > 1;
            card.innerHTML = `<button class="x" data-close aria-label="Close"><i class="fa-solid fa-xmark"></i></button>
            <div class="qv">
              <div class="qv-img">${p.image ? `<img src="${esc(p.image)}" alt="${esc(p.name)}">` : ""}</div>
              <div class="qv-body">
                <div class="p-brand">${esc(p.flag)} ${esc(p.brand)}</div>
                <h3 class="mt-2 mb-2">${esc(p.name)}</h3>
                <div class="pdp-rating"><span class="stars">${stars(p.rating.avg)}</span>
                    <span>${p.rating.count ? `${p.rating.avg} · ${p.rating.count} review${p.rating.count === 1 ? "" : "s"}` : "No reviews yet"}</span></div>
                <div class="pdp-price"><strong id="qvPrice">${kes(p.variants[0].price)}</strong>
                    ${p.compare_price ? `<del>${kes(p.compare_price)}</del><span class="save-pill">-${p.discount}%</span>` : ""}</div>
                ${p.low_stock ? `<div class="p-low mb-2"><i class="fa-solid fa-fire"></i> Only ${p.stock} left</div>` : ""}
                <p class="pdp-short">${esc(p.description)}</p>
                <form class="js-add" action="/cart/add/" method="post">
                  <input type="hidden" name="csrfmiddlewaretoken" value="${esc(CSRF)}">
                  ${multi ? `<div class="opt-label">Size</div><div class="variants">${p.variants.map((v, i) =>
                      `<label class="${v.stock <= 0 ? "disabled" : ""}"><input type="radio" name="variant" value="${v.id}" data-price="${v.price}" ${i === 0 ? "checked" : ""} ${v.stock <= 0 ? "disabled" : ""}>${esc(v.label)}<small>${kes(v.price)}</small></label>`).join("")}</div>`
                      : `<input type="hidden" name="variant" value="${p.variants[0].id}">`}
                  <div class="buy-row">
                    <div class="qty"><button type="button" data-step="-1" aria-label="Less">−</button><input name="quantity" value="1" inputmode="numeric" aria-label="Quantity"><button type="button" data-step="1" aria-label="More">+</button></div>
                    <button class="btn-glow" type="submit"${p.stock <= 0 ? " disabled" : ""}><i class="fa-solid fa-bag-shopping"></i> ${p.stock <= 0 ? "Sold out" : "Add to bag"}</button>
                    <button class="p-act js-wish ${p.in_wishlist ? "on" : ""}" type="button" data-id="${p.id}" aria-label="Wishlist"><i class="fa-${p.in_wishlist ? "solid" : "regular"} fa-heart"></i></button>
                  </div>
                </form>
                <a class="see-all mt-3" href="${esc(p.url)}">Full details <i class="fa-solid fa-arrow-right"></i></a>
              </div>
            </div>`;
            card.querySelectorAll('input[name=variant][data-price]').forEach(r => r.addEventListener("change", () => {
                $("#qvPrice").textContent = kes(r.dataset.price);
            }));
        }).catch(() => { card.querySelector(".qv").innerHTML = '<div class="qv-loading" style="font-size:1rem">Could not load this product.</div>'; });
    }
    function closeModals() {
        $$(".modal-x.open").forEach(m => m.classList.remove("open"));
        document.body.style.overflow = "";
    }
    document.addEventListener("click", e => {
        const btn = e.target.closest(".js-qv");
        if (btn) { e.preventDefault(); openQuickView(btn.dataset.id); return; }
        if (e.target.closest("[data-close]") || e.target.classList.contains("modal-x")) closeModals();
    });
    document.addEventListener("keydown", e => { if (e.key === "Escape") closeModals(); });
    document.addEventListener("dcp:cart", () => { if (qv && qv.classList.contains("open")) closeModals(); });

    // ------------------------------------------------------------------ quantity steppers
    document.addEventListener("click", e => {
        const b = e.target.closest(".qty [data-step]");
        if (!b) return;
        const input = b.parentElement.querySelector("input");
        const max = parseInt(input.max || "99", 10);
        input.value = Math.max(1, Math.min(max, (parseInt(input.value, 10) || 1) + parseInt(b.dataset.step, 10)));
        input.dispatchEvent(new Event("change", { bubbles: true }));
    });

    // ------------------------------------------------------------------ newsletter
    $$(".js-newsletter").forEach(form => form.addEventListener("submit", e => {
        e.preventDefault();
        const msg = form.parentElement.querySelector(".msg-line");
        post(form.action, new FormData(form)).then(d => {
            if (msg) { msg.className = "msg-line " + (d.ok ? "ok" : "err"); msg.textContent = d.message; }
            if (d.ok) form.reset();
        });
    }));

    // ------------------------------------------------------------------ live chat
    (function chat() {
        const fab = $("#chatFab"), panel = $("#chatPanel");
        if (!fab || !panel) return;
        const body = $("#chatBody"), form = $("#chatForm"), input = $("#chatInput"), guest = $("#chatGuest"),
              hello = $("#chatHello"), badge = fab.querySelector(".badge-dot");
        let lastId = 0, open = false, timer = null, lastDate = null;
        let known = false;
        try { known = localStorage.getItem("dcpChat") === "1"; } catch (err) {}

        function render(m, cls = "") {
            if (m.date !== lastDate) {
                lastDate = m.date;
                const d = document.createElement("div");
                d.className = "day-chip";
                d.textContent = m.date;
                body.appendChild(d);
            }
            const el = document.createElement("div");
            el.className = `bubble ${m.is_staff ? "them" : "me"} ${cls}`;
            el.innerHTML = `${esc(m.body)}<span class="t">${m.is_staff && m.sender ? esc(m.sender) + " · " : ""}${esc(m.time)}</span>`;
            body.appendChild(el);
            return el;
        }
        const down = () => { body.scrollTop = body.scrollHeight; };
        function schedule() {
            clearTimeout(timer);
            if (open) timer = setTimeout(poll, 4000);
            else if (known) timer = setTimeout(poll, 30000);
        }
        function poll() {
            fetch(`/chat/messages/?after=${lastId}${open ? "&open=1" : ""}`).then(r => r.json()).then(d => {
                guest.classList.toggle("show", !!d.needs_name);
                if (d.messages.length) {
                    if (hello) hello.style.display = "none";
                    d.messages.forEach(m => render(m));
                    lastId = d.messages[d.messages.length - 1].id;
                    if (open) down();
                    known = true;
                    try { localStorage.setItem("dcpChat", "1"); } catch (err) {}
                }
                const n = open ? 0 : d.unread;
                badge.textContent = n;
                badge.classList.toggle("show", n > 0);
            }).catch(() => {}).finally(schedule);
        }
        function toggle(force) {
            open = force === undefined ? !open : force;
            panel.classList.toggle("open", open);
            fab.setAttribute("aria-expanded", open);
            fab.querySelector("i").className = open ? "fa-solid fa-xmark" : "fa-solid fa-comment-dots";
            if (open) { badge.classList.remove("show"); poll(); setTimeout(() => { down(); input.focus(); }, 150); }
            else schedule();
        }
        fab.addEventListener("click", () => toggle());
        $$("[data-chat-close]").forEach(b => b.addEventListener("click", () => toggle(false)));
        $$("[data-chat-open]").forEach(b => b.addEventListener("click", e => {
            e.preventDefault();
            toggle(true);
            if (b.dataset.chatOpen) { input.value = b.dataset.chatOpen; }
        }));
        $$("[data-quick]", panel).forEach(b => b.addEventListener("click", () => { input.value = b.dataset.quick; input.focus(); }));
        input.addEventListener("input", () => { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 110) + "px"; });
        input.addEventListener("keydown", e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
        form.addEventListener("submit", e => {
            e.preventDefault();
            const text = input.value.trim();
            if (!text) return;
            const nameEl = $("#chatName");
            if (guest.classList.contains("show") && !nameEl.value.trim()) { nameEl.focus(); toast("Please tell us your name first", "err"); return; }
            const fd = new FormData();
            fd.append("body", text);
            fd.append("page", location.pathname);
            if (guest.classList.contains("show")) { fd.append("name", nameEl.value.trim()); fd.append("contact", $("#chatContact").value.trim()); }
            if (hello) hello.style.display = "none";
            const temp = render({ body: text, is_staff: false, time: "Sending…", date: lastDate || "Today" }, "pending");
            down();
            input.value = "";
            input.style.height = "auto";
            post("/chat/send/", fd).then(d => {
                if (!d.ok) throw new Error(d.error);
                temp.remove();
                if (d.message.id > lastId) { render(d.message); lastId = d.message.id; }
                guest.classList.remove("show");
                known = true;
                try { localStorage.setItem("dcpChat", "1"); } catch (err) {}
                down();
            }).catch(err => {
                temp.classList.add("failed");
                temp.querySelector(".t").textContent = "Not sent";
                toast((err && err.message) || "Message not sent", "err");
            });
        });
        if (known) poll();
    })();
})();
