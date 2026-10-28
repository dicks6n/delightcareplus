#!/usr/bin/env bash
# Move the PythonAnywhere copy of the shop from the old site to the new one, without losing data.
#
# Run it in a PythonAnywhere Bash console, inside the web app's virtualenv:
#
#   workon <your-virtualenv>          # the one named on the Web tab
#   cd ~/delightcareplus
#   git fetch origin main
#   git show origin/main:deploy/pythonanywhere_upgrade.sh > ~/upgrade.sh
#   bash ~/upgrade.sh
#
# What it does:
#   1. Copies the whole project folder (database, photos, old settings) to ~/delightcareplus-old-<date>
#   2. Switches the code to the new site (git reset --hard origin/main)
#   3. Fills in .env: keeps anything already there; adds the M-Pesa keys from the old settings file,
#      a new SECRET_KEY, DEBUG=False and your domains (keys are never printed)
#   4. Installs requirements, creates the new database tables
#   5. Runs setup_shop, then imports the old customers, products (into the matching new categories),
#      orders, reviews, coupons and blog posts
#   6. Collects static files, points the WSGI file at the new settings and reloads the site
#
# If anything goes wrong, the old site is untouched in the backup folder.
set -euo pipefail

APP="${1:-$HOME/delightcareplus}"
BACKUP="$HOME/delightcareplus-old-$(date +%Y%m%d-%H%M)"

[ -d "$APP/.git" ] || { echo "No git project at $APP — pass the folder, e.g.: bash ~/upgrade.sh ~/delightcare"; exit 1; }
if [ -z "${VIRTUAL_ENV:-}" ]; then
    echo "First activate the web app's virtualenv:  workon <name>"
    echo "Your virtualenvs: $(ls "$HOME/.virtualenvs" 2>/dev/null | tr '\n' ' ')"
    exit 1
fi

echo "1/6  Backing up $APP → $BACKUP"
cp -a "$APP" "$BACKUP"

echo "2/6  Switching the code to the new site"
cd "$APP"
git fetch origin main
git reset --hard origin/main

echo "3/6  Settings (.env)"
python3 - "$BACKUP" "$USER" <<'PYEOF'
import pathlib, re, secrets, sys

backup, user = pathlib.Path(sys.argv[1]), sys.argv[2]
env_path = pathlib.Path(".env")
existing = {}
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            existing[line.split("=", 1)[0].strip()] = True

old = ""
for candidate in (backup / "project" / "settings.py", ):
    if candidate.exists():
        old = candidate.read_text()


def old_value(name):
    m = re.search(rf"^{name}\s*=\s*['\"]([^'\"]*)['\"]", old, re.M)
    return m.group(1) if m else ""


hosts = f"{user}.pythonanywhere.com,delightcareplus.com,www.delightcareplus.com"
wanted = {
    "SECRET_KEY": secrets.token_urlsafe(50),
    "DEBUG": "False",
    "ALLOWED_HOSTS": hosts,
    "CSRF_TRUSTED_ORIGINS": ",".join("https://" + h for h in hosts.split(",")),
    "SITE_URL": "https://www.delightcareplus.com",
    "MPESA_ENVIRONMENT": old_value("MPESA_ENVIRONMENT") or "production",
    "MPESA_SHORTCODE": old_value("MPESA_SHORTCODE") or "4701129",
    "MPESA_CONSUMER_KEY": old_value("MPESA_CONSUMER_KEY"),
    "MPESA_CONSUMER_SECRET": old_value("MPESA_CONSUMER_SECRET"),
    "MPESA_PASSKEY": old_value("MPESA_PASSKEY"),
    "MPESA_CALLBACK_TOKEN": secrets.token_urlsafe(24),
}
added = []
with env_path.open("a") as f:
    if env_path.stat().st_size:
        f.write("\n")
    for key, value in wanted.items():
        if key in existing or not value:
            continue
        f.write(f"{key}={value}\n")
        added.append(key)
env_path.chmod(0o600)
print("     kept:", ", ".join(sorted(existing)) or "nothing (new file)")
print("     added:", ", ".join(added) or "nothing")
missing = [k for k in ("MPESA_CONSUMER_KEY", "MPESA_CONSUMER_SECRET", "MPESA_PASSKEY") if k not in existing and k not in added]
if missing:
    print("     ⚠️  Not found in the old settings, add them to .env yourself:", ", ".join(missing))
PYEOF

echo "4/6  Installing requirements and creating tables"
pip install -q -r requirements.txt
python manage.py migrate --noinput

echo "5/6  Setting up the shop, then importing the old shop's data"
python manage.py setup_shop   # first, so old products land in the new categories
if [ -f "$BACKUP/db.sqlite3" ]; then
    if [ -d "$BACKUP/media" ]; then
        python manage.py import_old_shop "$BACKUP/db.sqlite3" --media "$BACKUP/media"
    else
        python manage.py import_old_shop "$BACKUP/db.sqlite3"
    fi
else
    echo "     No db.sqlite3 in the backup — skipped"
fi

echo "6/6  Static files, WSGI file and reload"
python manage.py collectstatic --noinput -v0
for wsgi in /var/www/*_wsgi.py; do
    [ -f "$wsgi" ] || continue
    if grep -q "project.settings" "$wsgi"; then
        cp "$wsgi" "$BACKUP/$(basename "$wsgi").bak"
        sed -i 's/project\.settings/config.settings/g' "$wsgi"
        echo "     Updated $wsgi (old copy saved in the backup folder)"
    fi
    touch "$wsgi"   # reloads the web app
done

cat <<EOF

✅ Done. The old site is saved in $BACKUP

Check on the Web tab:
  • Static files:  /static/ → $APP/staticfiles      /media/ → $APP/media
  • Then press Reload if the site doesn't look updated.

Log in to the Seller Center at https://www.delightcareplus.com/manage/ with your old admin login.
EOF
