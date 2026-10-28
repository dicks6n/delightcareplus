/* Ad tracking: Meta Pixel (Facebook/Instagram), TikTok Pixel and Google Analytics 4.
 *
 * The IDs come from Seller Center → Marketing. Nothing loads until the visitor accepts the cookie
 * notice (Kenya Data Protection Act). Shop events are sent to every platform that is set up:
 *   page view · ViewContent (product page) · AddToCart · InitiateCheckout · Purchase · Search ·
 *   CompleteRegistration (sign-up) · Lead (newsletter)
 * Pages describe their event with a data-track="…" attribute holding JSON (see templates).
 */
(function () {
    const cfgEl = document.getElementById("trackingConfig");
    if (!cfgEl) return;
    const cfg = JSON.parse(cfgEl.textContent);
    const CURRENCY = "KES";
    const queue = [];
    let ready = false;

    // ------------------------------------------------------------------ loaders (official snippets)
    function loadMeta(id) {
        !function (f, b, e, v, n, t, s) {
            if (f.fbq) return; n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); };
            if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = "2.0"; n.queue = [];
            t = b.createElement(e); t.async = !0; t.src = v; s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
        }(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
        fbq("init", id);
        fbq("track", "PageView");
    }
    function loadTikTok(id) {
        !function (w, d, t) {
            w.TiktokAnalyticsObject = t; var ttq = w[t] = w[t] || [];
            ttq.methods = ["page", "track", "identify", "instances", "debug", "on", "off", "once", "ready", "alias", "group", "enableCookie", "disableCookie"];
            ttq.setAndDefer = function (t, e) { t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))); }; };
            for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]);
            ttq.instance = function (t) { for (var e = ttq._i[t] || [], n = 0; n < ttq.methods.length; n++) ttq.setAndDefer(e, ttq.methods[n]); return e; };
            ttq.load = function (e, n) {
                var r = "https://analytics.tiktok.com/i18n/pixel/events.js"; ttq._i = ttq._i || {}; ttq._i[e] = []; ttq._i[e]._u = r;
                ttq._t = ttq._t || {}; ttq._t[e] = +new Date; ttq._o = ttq._o || {}; ttq._o[e] = n || {};
                var o = document.createElement("script"); o.type = "text/javascript"; o.async = !0; o.src = r + "?sdkid=" + e + "&lib=" + t;
                var a = document.getElementsByTagName("script")[0]; a.parentNode.insertBefore(o, a);
            };
            ttq.load(id); ttq.page();
        }(window, document, "ttq");
    }
    function loadGA(id) {
        const s = document.createElement("script");
        s.async = true;
        s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(id);
        document.head.appendChild(s);
        window.dataLayer = window.dataLayer || [];
        window.gtag = function () { dataLayer.push(arguments); };
        gtag("js", new Date());
        gtag("config", id);
    }

    function start() {
        if (ready) return;
        ready = true;
        if (cfg.meta) loadMeta(cfg.meta);
        if (cfg.tiktok) loadTikTok(cfg.tiktok);
        if (cfg.ga4) loadGA(cfg.ga4);
        queue.splice(0).forEach(args => send(...args));
    }

    // ------------------------------------------------------------------ one event → every platform
    const NAMES = {
        //               Meta                     TikTok                  Google Analytics 4
        ViewContent: ["ViewContent", "ViewContent", "view_item"],
        AddToCart: ["AddToCart", "AddToCart", "add_to_cart"],
        InitiateCheckout: ["InitiateCheckout", "InitiateCheckout", "begin_checkout"],
        Purchase: ["Purchase", "CompletePayment", "purchase"],
        Search: ["Search", "Search", "search"],
        CompleteRegistration: ["CompleteRegistration", "CompleteRegistration", "sign_up"],
        Lead: ["Lead", "SubmitForm", "generate_lead"],
    };

    function send(event, data) {
        const [metaName, ttName, gaName] = NAMES[event] || [event, event, event];
        const items = data.items || [];
        const value = Number(data.value || items.reduce((t, i) => t + i.price * (i.quantity || 1), 0)) || undefined;
        const ids = items.map(i => String(i.id));
        try {
            if (window.fbq) {
                const p = { currency: CURRENCY, value, content_ids: ids, content_type: "product",
                            num_items: items.reduce((t, i) => t + (i.quantity || 1), 0) || undefined };
                if (data.query) p.search_string = data.query;
                fbq("track", metaName, p, data.event_id ? { eventID: data.event_id } : undefined);
            }
            if (window.ttq) {
                ttq.track(ttName, {
                    currency: CURRENCY, value, content_type: "product", query: data.query,
                    contents: items.map(i => ({ content_id: String(i.id), content_name: i.name, quantity: i.quantity || 1, price: i.price })),
                }, data.event_id ? { event_id: data.event_id } : undefined);
            }
            if (window.gtag) {
                gtag("event", gaName, {
                    currency: CURRENCY, value, transaction_id: data.order, search_term: data.query,
                    items: items.map(i => ({ item_id: String(i.id), item_name: i.name, price: i.price, quantity: i.quantity || 1 })),
                });
            }
        } catch (e) { /* an ad blocker or a platform outage must never break the shop */ }
    }

    function track(event, data) {
        data = data || {};
        if (ready) send(event, data); else queue.push([event, data]);
    }
    window.DCP = window.DCP || {};
    window.DCP.track = track;

    // ------------------------------------------------------------------ page events
    document.querySelectorAll("[data-track]").forEach(el => {
        let d;
        try { d = JSON.parse(el.dataset.track); } catch (e) { return; }
        if (d.event === "Purchase") {
            // Count a purchase once, even if the thank-you page is reloaded
            const key = "dcp_tracked_" + d.order;
            try { if (localStorage.getItem(key)) return; localStorage.setItem(key, "1"); } catch (e) { /* private mode */ }
            d.event_id = d.order;
        }
        track(d.event, d);
    });
    document.addEventListener("dcp:cart", e => {
        if (e.detail && e.detail.item) track("AddToCart", { items: [e.detail.item] });
    });
    document.addEventListener("submit", e => {
        const f = e.target;
        if (f.matches(".js-newsletter")) track("Lead", {});
        if (f.matches("[data-track-search]")) { const q = f.querySelector("[name=q]"); if (q && q.value) track("Search", { query: q.value }); }
    }, true);

    // ------------------------------------------------------------------ consent
    const bar = document.getElementById("consentBar");
    function choose(answer) {
        document.cookie = "dcp_consent=" + answer + ";path=/;max-age=" + 60 * 60 * 24 * 180 + ";SameSite=Lax";
        if (bar) bar.remove();
        if (answer === "yes") start();
    }
    if (cfg.consent === "yes") start();
    else if (bar && cfg.consent !== "no") {
        bar.hidden = false;
        bar.querySelector("[data-consent=yes]").addEventListener("click", () => choose("yes"));
        bar.querySelector("[data-consent=no]").addEventListener("click", () => choose("no"));
    }
})();
