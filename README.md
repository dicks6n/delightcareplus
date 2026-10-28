# Delight Care Plus

Online shop for supplements, skincare (serums, face masks, facial care) and tea, selling to customers in Kenya.
Products are grouped into three collections: **France**, **Japan** and **USA**. Supplier brand names are kept off the site on purpose.

Built with Django 5. Payments are M-Pesa (STK push), Airtel Money or pay on delivery. Delivery is priced by zone, method and weight.

---

## 1. Run it on your computer

```bash
cd delightcare_site
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # then open .env and fill it in
python manage.py migrate
python manage.py setup_shop       # departments, categories, brands, delivery prices, sample products
python manage.py createsuperuser  # your admin login
python manage.py runserver
```

- Shop: http://127.0.0.1:8000
- **Seller Center (your admin): http://127.0.0.1:8000/manage/**
- Advanced Django admin: http://127.0.0.1:8000/django-admin/

To set up without the 25 sample products, run `python manage.py setup_shop --no-samples`.

---

## 2. First things to do in Seller Center

1. **Check the supplement line-up.** Setup adds 15 real products (collagen, glutathione, berberine, K2 + D3,
   calcium-magnesium-zinc, omega-3, maca, NMN, turmeric, ashwagandha, saw palmetto, CoQ10, glucosamine and the
   liver formula). Prices for berberine, K2 + D3 and calcium-magnesium-zinc follow Kenyan marketplace prices; **all
   other prices are estimates**. Also check capsule counts, the daily dose (for refill reminders) and stock against
   your actual packs. The list lives in `catalog/catalog_data.py`.
2. **Add your other products.** Use **Bulk import** to load many at once:
   - Download the CSV template and fill it in using Excel or Google Sheets.
   - Upload the CSV together with a .zip of the photos, named as in the `image` column.
   - Running the import again updates products that have the same name and brand.
3. **Remove the samples.** On **Products**, click "Remove samples". The samples are only there so you can see the design.
4. **Collections.** Products are grouped as the France, Japan and USA collections (Seller Center → Brands).
   Supplier brand names are deliberately not used anywhere on the site; they only appear if a photo you upload shows them.
5. **Delivery prices.** Edit the fees and towns for each zone. The starting prices are estimates in the same range as Jumia and Kilimall.
   - Pickup is hidden until you add pickup stations to a zone (one station per line).
6. **Shop settings.** Set the announcement bar, WhatsApp, phone and email, social links, free-delivery amount, pay on delivery, the Airtel Money number, and the store open/closed switch.
7. **Help pages.** The text in Returns, Privacy and Terms (`templates/core/policy.html`) is a starting point. Replace it with your own terms.

### What the Seller Center does

| Area | What you can do |
|---|---|
| Overview | Today/7/30-day sales, a to-do list (Airtel payments to confirm, orders to pack/ship, unread chats), sales chart, top products, low stock |
| Orders | Tabs by status, search (number, name, phone, M-Pesa code), bulk status change, CSV export, timeline, internal notes, courier and tracking, invoice/packing slip, WhatsApp/call buttons |
| Products | Edit price, stock and live/hidden right in the table, bulk publish/hide/feature, % sale and end sale, duplicate, gallery, sizes/variants, batches and expiry, CSV export/import |
| Customers | Spend, orders, Glow Points (add/remove), CSV export |
| Marketing | Coupons (%, fixed, free delivery), home banners, blog posts, testimonials, newsletter list |
| Inbox | Live chat with customers |
| Reports | Sales by day, product, brand, category, payment method and town, all exportable |

---

### Product photos

Every product made by setup gets two photos:

- **Main photo: an infographic poster.** It shows the pack, the product name, three ingredient call-outs with
  icons, and a row of benefits, in the style used on marketplace listings. Shoppers see it on the product page.
- **Studio photo.** A clean shot of the pack, used in product grids, the home page and the slideshow.

For any product, including ones you add yourself, click **Create infographic** in its editor, or tick several
products and choose **Create infographic photos** from the bulk actions. The poster is drawn from the product's
name, size, benefits (one per line) and concerns, so fill those in first. A photo you uploaded is kept in the gallery.

Your own photos (for example, real pack shots or posters from your supplier) always work too: upload them in the
product editor or in the Bulk import zip. Before posting a supplier's poster, check it for misspellings and for
badges you can't back up. For example, "FDA certified" is not a real certification for supplements.

## 3. Special features

- **Routine Finder**: a 60-second quiz that builds a morning, evening and inside-out routine. Adding 3 or more products gives 5% off (coupon `ROUTINE5`, created automatically — edit or switch it off in Coupons).
- **Verify Product**: customers type the batch code on their box to see its origin and expiry. Add batches on each product's page.
- **Refill reminders**: supplements show how many days a pack lasts, and customers get an email shortly before it runs out. Run this daily (cron, or a PythonAnywhere scheduled task):
  ```bash
  python manage.py send_refill_reminders
  ```
- **Glow Points**: 1 point for every KES 100 spent, credited when the order is delivered.
  - 1 point = KES 1 off.
  - Points can pay up to 20% of an order.
  - Points are returned if an order is cancelled.
- **Back-in-stock alerts**: customers ask to be notified, and they're emailed automatically when stock goes from 0 to a positive number.
- Shop by concern, compare up to 4 products, frequently bought together, wishlist, quick view, recently viewed, guest checkout and order tracking.

---

## 4. Moving data from the old website

This copies customers (their old passwords keep working), categories, products with sizes and photos, orders, reviews, coupons, blog posts and newsletter emails. The old database is only read, never changed, and running it twice is safe.

```bash
python manage.py import_old_shop /path/to/old/db.sqlite3 --media /path/to/old/media
```

After importing:

- Old categories are sorted into Supplements, Skincare or Tea by name. Check them in **Categories**.
- Set the brand on imported products.
- Old orders keep their numbers. If a number is already used on the new site, the old order gets `-OLD` added.

---

## 5. M-Pesa (Daraja)

1. Create an app at https://developer.safaricom.co.ke. Put the consumer key/secret, shortcode and passkey in `.env`.
2. Set `MPESA_CALLBACK_URL` to `https://YOUR-DOMAIN/orders/mpesa/callback/`. It must be public HTTPS.
3. Set `MPESA_CALLBACK_TOKEN` to a long random string. Calls that don't carry it are rejected, so nobody can fake a "paid" message.
4. Test with `MPESA_ENVIRONMENT=sandbox`, then switch to `production` with your live credentials.

A payment is only marked paid when the full amount arrives. If the callback is late, the payment page also asks Safaricom directly for the result.

---

## 6. Going live

In `.env`:

```
DEBUG=False
SECRET_KEY=<a long random string>
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SITE_URL=https://yourdomain.com
```

Then:

```bash
python manage.py migrate
python manage.py collectstatic
```

- Serve `staticfiles/` at `/static/` and `media/` at `/media/`. On PythonAnywhere, use the "Static files" section of the Web tab.
- Add the daily `send_refill_reminders` task.
- Set up email (for Gmail, use an App Password) so customers get order emails.

---

## Project layout

```
config/      settings, urls
core/        home, help pages, contact, newsletter, shop settings
catalog/     brands, departments, categories, products, variants, batches, reviews, routine finder, product image generator
cart/        bag, coupons, delivery zones and pricing
orders/      checkout, M-Pesa / Airtel / pay on delivery, order status, emails, refill reminders
accounts/    login/signup, profile, wishlist, Glow Points
chat/        live chat + staff inbox
blog/        journal posts
dashboard/   Seller Center (/manage/)
templates/   all pages and emails
static/      css, js, logo
```
