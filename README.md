# Pitstop Maintenance Tracker

A modern, self-hosted vehicle management application for tracking fuel consumption, expenses, reminders, and maintenance across your entire fleet.

Named Pitstop, because keeping on top of vehicle maintenance should be as quick and painless as a pit stop.

## Screenshots

<p align="center">
  <img src="screenshots/dashboard.png" alt="Dashboard" width="45%">
  <img src="screenshots/vehicles.png" alt="Vehicles" width="45%">
</p>
<p align="center">
  <img src="screenshots/vehicle_details.png" alt="Vehicle Details" width="45%">
  <img src="screenshots/integrations.png" alt="Integrations" width="45%">
</p>
<p align="center">
  <img src="screenshots/import_export.png" alt="Import/Export" width="45%">
</p>

## Features

- **Multi-Vehicle Support**: Track cars, vans, motorbikes, and scooters with custom vehicle types
- **Fuel Logging**: Record fill-ups with automatic consumption calculations (L/100km, MPG)
- **Quick Entry Mode**: Rapid fuel logging with a streamlined interface
- **Expense Tracking**: Monitor maintenance, insurance, repairs, tax, and other costs by category
- **Recurring Expenses**: Track regular payments like insurance, tax, and subscriptions
- **Maintenance Schedules**: Plan and track scheduled maintenance with mileage/date intervals
- **Reminders**: Set up recurring reminders for MOT, service, insurance, and tax renewals
- **Multi-Channel Notifications**: Get reminded via Email, ntfy, Pushover, or Webhooks
- **Document Storage**: Store important documents (insurance, registration, manuals) per vehicle
- **Favorite Stations**: Save and quickly select your preferred fuel stations
- **Multi-User**: Share vehicles between family members or team members
- **Analytics Dashboard**: View spending trends and consumption statistics with interactive charts
- **Attachment Support**: Upload receipts and documents to fuel logs and expenses
- **PDF Reports**: Generate comprehensive vehicle reports for record-keeping
- **Customizable Units**: Support for metric/imperial, multiple currencies
- **Menu Customization**: Show/hide menu items and set your preferred start page
- **Internationalization**: Available in multiple languages (English, German, Spanish, French, and more)
- **Custom Branding**: Personalize with your own logo, colors, and app name
- **Dark Mode**: Toggle between light and dark themes
- **Import/Export**: Import from Fuelly CSV, export all data as JSON or CSV
- **DVLA Integration**: Look up UK vehicle MOT and tax status automatically
- **PWA Support**: Install as a mobile app with offline capabilities
- **REST API**: Full API access for integrations and automation
- **Home Assistant Integration**: Create sensors and automations for your vehicles
- **Calendar Subscription**: Subscribe to reminders in Apple Calendar, Google Calendar, Outlook
- **Docker Ready**: Easy self-hosting via Docker

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
| `OIDC_ENABLED` | Turn on single sign-on (see [Single Sign-On](#single-sign-on-oidc)) | `false` |
| `OIDC_DISCOVERY_URL` | Provider's `.well-known/openid-configuration` URL | — |
| `OIDC_CLIENT_ID` / `OIDC_CLIENT_SECRET` | Client credentials registered with your provider | — |
| `OIDC_PROVIDER_NAME` | Button text: "Sign in with *name*" | `SSO` |
| `OIDC_SCOPES` | Scopes to request | `openid email profile groups` |
| `OIDC_AUTO_REGISTER` | Create an account on first SSO login if none matches | `true` |
| `OIDC_ADMIN_GROUP` | Members of this group are admins, everyone else isn't (synced each SSO login) | — |
| `OIDC_REDIRECT_URI` | Override the callback URL if Pitstop builds the wrong one behind a proxy | auto |

`SECRET_KEY` is automatically generated and stored on first startup — you do not need to set it manually. If you want a fixed key (e.g. to keep sessions alive across container restarts), you can provide it as an environment variable.

By default, Tailwind loads from `app/static/vendor/tailwindcss.js` and falls back to the CDN URL if the local asset is missing.

## Usage

### Dashboard
The main dashboard shows an overview of all your vehicles with key statistics:
- Total fuel costs and consumption averages
- Recent fuel logs and expenses
- Upcoming reminders and overdue alerts

### Vehicles
Add and manage your vehicles with detailed information:
- Make, model, year, and registration
- Fuel type and tank capacity
- Custom specifications and notes
- Photo upload support

### Fuel Logs
Track every fill-up with:
- Date, odometer reading, and fuel amount
- Total cost and price per unit
- Full tank indicator for accurate consumption calculations
- Automatic MPG/L per 100km calculations

### Expenses
Categorize all vehicle-related costs:
- Maintenance & Repairs
- Insurance
- Tax & Registration
- Parking & Tolls
- Accessories
- Other expenses

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
- Track prices at different stations
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
- **User Management**: Create, edit, and manage user accounts

## API

Pitstop includes a REST API for automation and integrations:

```bash
# Generate an API key in Settings > API
curl -H "Authorization: Bearer pitstop_your_api_key" \
  http://localhost:5151/api/v1/vehicles
```

See the API documentation at `/api/docs` when logged in.

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

Available endpoints: `/api/ha/status`, `/api/ha/vehicles`, `/api/ha/alerts`, `/api/ha/summary`

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

- **Backend**: Python / Flask
- **Database**: SQLite (easily swappable)
- **Frontend**: Tailwind CSS, Chart.js
- **Server**: Gunicorn
- **Notifications**: SMTP, ntfy, Pushover, Webhooks
- **PDF Generation**: WeasyPrint

## Troubleshooting

### Application Won't Start
- Check that all dependencies are installed: `pip install -r requirements.txt`
- Ensure the data directory is writable
- Check logs for specific error messages

### Database Issues
- Default SQLite database is created at `data/pitstop.db`
- Ensure the directory exists and is writable
- For schema updates, the app handles migrations automatically

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

## Support

- **Issues**: [GitHub Issues](https://github.com/austincnunn/Pitstop/issues)
- **Documentation**: This README and in-app help
