# Pitstop Maintenance Tracker

A modern, self-hosted vehicle management application for tracking fuel consumption, expenses, reminders, and maintenance across your entire fleet.

Named Pitstop, because keeping on top of vehicle maintenance should be as quick and painless as a pit stop.

Pitstop is a hard fork of [May](https://github.com/dannymcc/may) by Danny McClelland.

## Screenshots

<p align="center">
  <img src="screenshots/dashboard.png" alt="Dashboard" width="45%">
  <img src="screenshots/dark_mode.png" alt="Dashboard in dark mode" width="45%">
</p>
<p align="center">
  <img src="screenshots/vehicles.png" alt="Vehicles" width="45%">
  <img src="screenshots/vehicle_details.png" alt="Vehicle Details" width="45%">
</p>
<p align="center">
  <img src="screenshots/fuel_logs.png" alt="Fuel Logs" width="45%">
  <img src="screenshots/shopping_list.png" alt="Shopping List project" width="45%">
</p>
<p align="center">
  <img src="screenshots/integrations.png" alt="Integrations" width="45%">
  <img src="screenshots/import_export.png" alt="Import/Export" width="45%">
</p>

## Features

- **Multi-Vehicle Support**: Track cars, trucks, SUVs, vans, motorbikes, scooters, ATVs/UTVs, tractors, and boats, with gas, diesel, hybrid, or electric powertrains
- **Fuel Logging**: Record fill-ups with fuel grade and automatic consumption calculations (MPG, L/100km)
- **Quick Entry Mode**: Rapid fuel logging with a streamlined interface
- **Customizable Dashboard**: Rearrange or hide widgets for spending, cheapest fuel, recent activity, and fuel cost by grade
- **Vehicle Timeline & Sharing**: See a vehicle's fill-ups, charging, and expenses in one timeline; share or archive vehicles
- **Expense Tracking**: Monitor maintenance, insurance, repairs, tax, and other costs by category
- **Recurring Expenses**: Track regular payments like insurance, tax, and subscriptions
- **Maintenance Schedules**: Plan and track scheduled maintenance with mileage/date intervals
- **Reminders**: Set up recurring reminders for MOT, service, insurance, and tax renewals
- **Multi-Channel Notifications**: Get reminded via Email, ntfy, Pushover, or Webhooks
- **Document Storage**: Store important documents (insurance, registration, manuals) per vehicle
- **Fuel Stations & Prices**: Save favorite stations, track price history, and see which is cheapest
- **Shopping List**: Plan parts and accessories per vehicle, grouped into projects; tick items off as you buy them, attach receipts, and the cost lands in Expenses automatically
- **Multi-User**: Share vehicles between family members or team members
- **Single Sign-On**: Log in with any OpenID Connect provider (Authelia, Authentik, Keycloak, …)
- **Analytics Dashboard**: View spending trends and consumption statistics with interactive charts
- **Attachment Support**: Upload receipts and documents to fuel logs and expenses
- **PDF Reports**: Generate comprehensive vehicle reports for record-keeping
- **Customizable Units**: Support for metric/imperial, multiple currencies
- **Menu Customization**: Show/hide menu items and set your preferred start page
- **Internationalization**: Available in multiple languages (English, German, Spanish, French, and more)
- **Custom Branding**: Personalize with your own logo, colors, and app name
- **Dark Mode**: Toggle between light and dark themes
- **Import/Export**: Import from Hammond, Clarkson, Fuelly, or any CSV with column mapping; export as CSV, JSON, or a full ZIP backup you can restore
- **DVLA Integration**: Look up UK vehicle MOT and tax status automatically
- **PWA Support**: Install as a mobile app with offline capabilities
- **REST API**: Full API access for integrations and automation
- **Home Assistant Integration**: Create sensors and automations for your vehicles
- **Calendar Subscription**: Subscribe to reminders in Apple Calendar, Google Calendar, Outlook
- **Docker Ready**: Easy self-hosting via Docker
- **Trips & Mileage**: Track business and personal trips for tax and mileage reporting
- **EV Charging**: Log charging sessions with energy, cost, and state of charge
- **Parts & Supplies**: Record the parts each vehicle takes (oil spec, filters, part numbers) and keep a supplies inventory
- **Vehicle Notes**: Keep free-form notes per vehicle
- **Tesla Integration (Tessie)**: Refresh odometer, battery, and range; import charging history
- **Actual Budget Import**: Import expenses from an Actual Budget instance
- **Automated Backups**: Scheduled backups to disk and email, including a full `pg_dump` when running on PostgreSQL
- **PostgreSQL or SQLite**: PostgreSQL recommended; SQLite works for small single-user setups

## Installation

### Quick Start with Docker

The provided `docker-compose.yml` runs Pitstop with a PostgreSQL database (recommended for real deployments — see `DATABASE_URL` under Environment Variables below for the lightweight SQLite alternative).

```bash
# Create a directory for Pitstop
mkdir pitstop && cd pitstop

# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/austincnunn/Pitstop/main/docker-compose.yml

# Start the containers
docker compose up -d
```

Or run directly with Docker (uses SQLite, no separate database container needed):

```bash
docker run -d \
  --name pitstop \
  -p 5151:5151 \
  -v pitstop_data:/app/data \
  ghcr.io/austincnunn/pitstop:latest
```

Access the application at `http://localhost:5151`

**First-time login:**
- Username: `admin`
- Password: Check your container logs for the auto-generated password

On first run, if no `ADMIN_PASSWORD` environment variable is set, Pitstop generates a secure random password and prints it to the console:

```
============================================================
SECURITY NOTICE: Default admin account created
Username: admin
Password: <randomly-generated-password>
Please change this password immediately after first login!
Set ADMIN_PASSWORD environment variable to avoid this message.
============================================================
```

To view the password, run:
```bash
docker logs pitstop
```

**Tip:** Set `ADMIN_PASSWORD` in your docker-compose.yml or environment to use a fixed password.

### Upgrading from Willman

Pitstop was previously published as "Willman". Change the image in your compose file or run command from `ghcr.io/austincnunn/willman` to `ghcr.io/austincnunn/pitstop`. On first start the container renames an existing `willman.db` to `pitstop.db` and fixes file ownership automatically. Keep your existing bind-mount path. Previously issued API keys with the `willman_` prefix keep working.

### Manual Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Session encryption key — auto-generated and persisted on first run if not set | Auto-generated |
| `DATABASE_URL` | Database connection string (Postgres recommended, e.g. `postgresql+psycopg://user:pass@host:5432/pitstop`) | `sqlite:///data/pitstop.db` |
| `UPLOAD_FOLDER` | Path for file uploads | `/app/data/uploads` |
| `ADMIN_PASSWORD` | Password for the default admin account | Auto-generated |
| `TAILWIND_ASSET_URL` | Local Tailwind Play CDN JS path | `/static/vendor/tailwindcss.js` |
| `TAILWIND_CDN_URL` | Tailwind CDN fallback URL | `https://cdn.tailwindcss.com` |
| `FLATPICKR_JS_ASSET_URL` | Local Flatpickr JS path | `/static/vendor/flatpickr.min.js` |
| `FLATPICKR_JS_CDN_URL` | Flatpickr JS CDN fallback URL | `https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.js` |
| `FLATPICKR_CSS_ASSET_URL` | Local Flatpickr CSS path | `/static/vendor/flatpickr.min.css` |
| `FLATPICKR_CSS_CDN_URL` | Flatpickr CSS CDN fallback URL | `https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.css` |
| `ADMIN_USERNAME` | Username for the default admin account (first run only) | `admin` |
| `ADMIN_EMAIL` | Email for the default admin account (first run only) | `admin@example.com` |
| `INTERNAL_API_KEY` | Secret used for internal/reverse-proxy requests | Auto-generated |
| `SESSION_COOKIE_SECURE` | Send the session cookie only over HTTPS | `false` |
| `RELEASE_CHANNEL` | Version display channel (`stable` or `dev`) | `stable` |
| `OIDC_ENABLED` | Turn on single sign-on (see [Single Sign-On](#single-sign-on-oidc)) | `false` |
| `OIDC_DISCOVERY_URL` | Provider's `.well-known/openid-configuration` URL | — |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | Client credentials registered with your provider | — |
| `OIDC_PROVIDER_NAME` | Button text: "Sign in with *name*" | `SSO` |
| `OIDC_BUTTON_TEXT` | Replaces the whole button label, e.g. `Log in` | "Sign in with *name*" |
| `OIDC_SCOPES` | Scopes to request | `openid email profile groups` |
| `OIDC_AUTO_REGISTER` | Create an account on first SSO login if none matches | `true` |
| `OIDC_ADMIN_GROUP` | Members of this group are admins, everyone else isn't (synced each SSO login) | — |
| `OIDC_REDIRECT_URI` | Override the callback URL if Pitstop builds the wrong one behind a proxy | auto |
| `OIDC_DISABLE_PASSWORD_LOGIN` | Make SSO the only way in: hides the password form, registration and password reset (ignored if SSO isn't fully configured) | `false` |
| `OIDC_AUTO_REDIRECT` | Send the login page straight to your provider (`/auth/login?local=1` shows the page instead) | `false` |

`SECRET_KEY` is automatically generated and stored on first startup — you do not need to set it manually. If you want a fixed key (e.g. to keep sessions alive across container restarts), you can provide it as an environment variable.

The Docker image ships with Tailwind CSS compiled at build time. The `TAILWIND_*` variables only matter when running from source without a compiled `app/static/css/tailwind.css`: Tailwind then compiles in the browser from `app/static/vendor/tailwindcss.js`, falling back to the CDN URL if that file is missing.

## Usage

### Dashboard
The main dashboard shows an overview of all your vehicles with key statistics:
- Total fuel cost, other expenses, distance, and cost per mile/km
- Monthly spending chart and fuel cost by grade
- Cheapest fuel among your saved stations
- Recent fuel logs and expenses

Use **Edit Layout** to reorder or hide widgets.

### Vehicles
Add and manage your vehicles with detailed information:
- Make, model, year, registration, and VIN
- Powertrain, tank or battery capacity, and default fuel grade
- Custom specifications, parts, and notes
- Photo upload support
- A timeline of fill-ups, charging sessions, and expenses
- PDF report, sharing with other users, and archiving vehicles you've sold

### Fuel Logs
Track every fill-up with:
- Date, odometer reading, and fuel amount
- Total cost, price per unit, and fuel grade (Regular, Plus, Premium, E85, E15, Diesel)
- Full tank and missed fill-up flags for accurate consumption calculations
- Automatic MPG/L per 100km calculations

### Expenses
Categorize all vehicle-related costs:
- Maintenance & Repairs
- Insurance
- Road Tax & Registration
- Parking & Tolls
- Cleaning
- Accessories & Upgrades
- Other expenses

Attach receipts (images or PDFs) to any expense.

### Trips
Track business and personal trips:
- Date, start/end odometer, distance
- Purpose (business, personal, commute, medical, charity) and notes
- Trip report for mileage and tax reporting

### EV Charging
Track charging sessions for electric vehicles:
- Charging location and energy (kWh)
- State of charge before/after
- Cost and charging duration
- Import from Tessie for linked Tesla vehicles

### Parts & Supplies
- **Parts** (per vehicle): what the vehicle takes, such as engine oil spec and quantity, filters, plugs, and brake parts, with part numbers and supplier links
- **Supplies**: a simple inventory of consumables you keep on hand

### Shopping List
Plan purchases for a vehicle, split into projects (e.g. "Intake manifold swap", "Exhaust work"):
- Items with quantity, estimated price, part number, and link
- **Bulk add** by pasting lines or spreadsheet rows, or **Import CSV**
- Tick **Bought?** to record the price paid, date, vendor, and a receipt for warranty claims
- Each project keeps a single expense in sync with what you've bought
- Select items to delete several at once

### Reminders
Never miss important dates:
- MOT/Inspection due dates
- Service intervals
- Insurance renewals
- Tax payments
- Custom reminders with flexible recurrence

### Maintenance Schedules
Plan regular maintenance tasks:
- Set intervals by mileage or time (e.g., oil change every 10,000 km or 12 months)
- Track completion history
- Automatic reminder generation
- Link to expenses when completed

### Recurring Expenses
Track regular payments:
- Insurance premiums
- Road tax
- Subscriptions and memberships
- Custom recurrence patterns (monthly, quarterly, yearly)
- Automatic calendar integration

### Documents
Store important vehicle documents:
- Insurance certificates
- Registration documents
- Service manuals
- MOT certificates
- Any file type with expiry date tracking

### Fuel Stations
Save your favorite stations:
- Quick selection during fuel logging
- Price history per station, recorded from your fill-ups
- **Cheapest Fuel** view ranking stations by latest price
- Notes and location information

### Notifications
Configure your preferred notification method:
- **Email**: SMTP server configuration (admin)
- **ntfy**: Free push notifications via ntfy.sh or self-hosted
- **Pushover**: iOS/Android push notifications
- **Webhook**: HTTP POST for Home Assistant, Discord, Slack, etc.

## Admin Settings

Administrators can configure:
- **SMTP Settings**: Email server for notifications
- **Pushover**: Application token for push notifications
- **DVLA API**: API key for UK vehicle lookups ([get one here](https://developer-portal.driver-vehicle-licensing.api.gov.uk/))
- **Branding**: Custom logo, app name, tagline, and primary color
- **User Management**: Create, edit, and manage user accounts, and turn self-registration on or off
- **Backups**: Schedule local backups (with retention) and optional email delivery
- **Tessie**: API token for Tesla vehicle data
- **Actual Budget**: API URL, key, budget sync ID, and category mappings

## API

Pitstop includes a REST API for automation and integrations:

```bash
# Generate an API key in Settings > API
curl -H "Authorization: Bearer pitstop_your_api_key" \
  http://localhost:5151/api/v1/vehicles
```

Endpoints cover vehicles, fuel logs, and expenses (`/api/v1/vehicles`, `/api/v1/vehicles/<id>/fuel`, `/api/v1/vehicles/<id>/expenses`, `/api/v1/categories`). See the full API documentation at `/api/docs` when logged in.

## Single Sign-On (OIDC)

Pitstop can add a **Sign in with …** button for any OpenID Connect provider (Authelia, Authentik, Keycloak, Pocket ID, …). Password login keeps working alongside it.

1. Register a confidential client with your provider:
   - Redirect URI: `https://your-pitstop-host/auth/oidc/callback`
   - Scopes: `openid email profile groups`
   - PKCE: S256
   - Token endpoint auth method: `client_secret_basic`
2. Set the environment variables:

```yaml
environment:
  - OIDC_ENABLED=true
  - OIDC_DISCOVERY_URL=https://auth.example.com/.well-known/openid-configuration
  - OIDC_CLIENT_ID=pitstop
  - OIDC_CLIENT_SECRET=your-client-secret
  - OIDC_PROVIDER_NAME=Authelia
  - OIDC_ADMIN_GROUP=admins          # optional
  - OIDC_REDIRECT_URI=https://pitstop.example.com/auth/oidc/callback   # behind a reverse proxy
```

Behind a reverse proxy that terminates TLS, set `OIDC_REDIRECT_URI`; otherwise Pitstop may send an `http://` callback URL that your provider rejects.

How accounts are matched on SSO login:

1. **Already linked:** the provider's user ID (`sub`) is remembered after the first login.
2. **Same email:** an existing account with the same email is linked automatically, but only if the provider marks the email as verified.
3. **New user:** otherwise an account is created (username from `preferred_username`), unless `OIDC_AUTO_REGISTER=false`.

If `OIDC_ADMIN_GROUP` is set, admin rights follow that group on every SSO login, so removing someone from the group removes their admin access.

### SSO-only login

Once SSO works for your admin account, you can make it the only way in:

```yaml
  - OIDC_DISABLE_PASSWORD_LOGIN=true   # no password form, registration or password reset
  - OIDC_AUTO_REDIRECT=true            # /auth/login goes straight to your provider
```

- **API keys keep working.** That covers the REST API, Home Assistant and the calendar feed.
- **If SSO isn't fully configured** (for example, a missing client secret), Pitstop ignores `OIDC_DISABLE_PASSWORD_LOGIN`, so you can't lock yourself out.
- **To get password login back,** set it to `false` and restart.
- **After logging out or a failed SSO attempt,** you land on `/auth/login?local=1` instead of being sent straight back to the provider.

<details>
<summary>Example Authelia client</summary>

```yaml
identity_providers:
  oidc:
    clients:
      - client_id: 'pitstop'
        client_name: 'Pitstop'
        client_secret: '$pbkdf2-sha512$...'   # authelia crypto hash generate pbkdf2
        public: false
        authorization_policy: 'two_factor'
        require_pkce: true
        pkce_challenge_method: 'S256'
        redirect_uris:
          - 'https://pitstop.example.com/auth/oidc/callback'
        scopes: ['openid', 'email', 'profile', 'groups']
        response_types: ['code']
        grant_types: ['authorization_code']
        access_token_signed_response_alg: 'none'
        userinfo_signed_response_alg: 'none'
        token_endpoint_auth_method: 'client_secret_basic'
```

</details>

## Integrations

### Home Assistant
Create vehicle sensors in Home Assistant:

```yaml
sensor:
  - platform: rest
    name: "Pitstop Vehicle Stats"
    resource: http://your-pitstop-instance/api/ha/summary
    headers:
      Authorization: Bearer pitstop_your_api_key
    value_template: "{{ value_json.alerts_count }}"
    json_attributes:
      - total_vehicles
      - total_cost
```

Available endpoints: `/api/ha/status`, `/api/ha/vehicles`, `/api/ha/vehicles/<id>`, `/api/ha/vehicles/<id>/stats`, `/api/ha/alerts`, `/api/ha/summary`, and `POST /api/ha/fuel/add` to log a fill-up from an automation.

### Tessie (Tesla)
Configure under Settings > Integrations > Tessie with your Tessie API token. Link a vehicle by its VIN to refresh odometer, battery level, and range on demand, and to import its charging history as EV charging sessions.

### Actual Budget
Import expenses from an Actual Budget instance via the `actual-http-api` sidecar (see the optional service in `docker-compose.yml`):

1. Configure the API URL, API key, and budget sync ID under Settings > Integrations > Actual Budget.
2. Map Actual Budget categories to a vehicle and expense category (Settings > Integrations > Actual Budget > Map categories).
3. Trigger an import manually or let the hourly background sync run automatically.

Imported transactions are deduplicated by their Actual Budget transaction ID.

### Calendar Subscription
Subscribe to reminders in your calendar app:

1. Go to Settings > Integrations > Calendar
2. Copy the webcal URL (for Apple Calendar, Outlook) or HTTPS URL (for Google Calendar)
3. Add as a subscribed calendar in your app

The calendar includes:
- Maintenance schedules
- Recurring expense due dates
- Document expiry dates
- Custom reminders

## Supported Languages

Pitstop is available in the following languages:

| Language | Code | Language | Code |
|----------|------|----------|------|
| English | `en` | Swedish | `sv` |
| German (Deutsch) | `de` | Danish (Dansk) | `da` |
| Spanish (Español) | `es` | Norwegian (Norsk) | `no` |
| French (Français) | `fr` | Finnish (Suomi) | `fi` |
| Italian (Italiano) | `it` | Japanese (Japanese) | `ja` |
| Dutch (Nederlands) | `nl` | Chinese (Chinese) | `zh` |
| Portuguese (Português) | `pt` | Korean (Korean) | `ko` |
| Polish (Polski) | `pl` | | |

You can change your language in **Settings > Units & Values > Language**.

### Improving Translations

Translations were generated with AI assistance and may contain inaccuracies. If you spot an incorrect translation, contributions are very welcome:

1. Translation files are located in `app/translations/<lang>/LC_MESSAGES/messages.po`
2. Edit the `msgstr` value for any incorrect entry
3. Submit a pull request with your fix

## Tech Stack

- **Backend**: Python / Flask, SQLAlchemy, Flask-Migrate (Alembic)
- **Database**: PostgreSQL (recommended) or SQLite
- **Frontend**: Tailwind CSS, Flatpickr, Chart.js
- **i18n**: Flask-Babel
- **Server**: Gunicorn
- **Notifications**: SMTP, ntfy, Pushover, Webhooks
- **PDF Generation**: WeasyPrint

## Troubleshooting

### Application Won't Start
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Ensure the data directory is writable
- Check logs for specific error messages

### Database Issues
- With no `DATABASE_URL`, a SQLite database is created at `data/pitstop.db` (`/app/data/pitstop.db` in Docker); ensure the directory is writable
- With PostgreSQL, check the `postgres` container is healthy and that `DATABASE_URL` matches its user, password, and database name
- Migrations run automatically when the container starts; check the container logs if startup fails

### Notification Issues
- **Email**: Verify SMTP settings and credentials in admin settings
- **ntfy**: Check your topic name is correct
- **Pushover**: Ensure admin has configured the app token
- **Webhook**: Verify the URL is accessible and accepts POST requests

### PDF Generation
- WeasyPrint requires system dependencies on some platforms
- On Ubuntu/Debian: `apt-get install libpango-1.0-0 libpangocairo-1.0-0`
- On macOS: `brew install pango`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup
1. Clone this repository
2. Create a virtual environment: `python3 -m venv venv`
3. Activate it: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Run in development mode: `python run.py`

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

Pitstop is based on [May](https://github.com/dannymcc/may), copyright (c) 2026 Danny McClelland, also released under the MIT License. The original copyright notice is kept in [LICENSE](LICENSE) as that license requires.

## Support

- **Issues**: [GitHub Issues](https://github.com/austincnunn/Pitstop/issues)
- **Documentation**: This README and in-app help
