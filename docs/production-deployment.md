# Production deployment runbook

This application ships as one portable container. Run the same image for the web service and all scheduled jobs. Production is deliberately fail-closed: it will not start with SQLite, local photo storage, HTTP links, missing SMTP, or missing host/origin settings.

## 1. Provision managed services

Create these before the first deployment:

1. A Supabase project with PostgreSQL 15 or newer. Use the session-pooler connection details and require TLS.
2. A private Supabase Storage bucket named `lemon-photos` and an S3 access-key pair. Do not make the bucket public.
3. An SMTP account with a verified sender address.
4. A DNS name with HTTPS terminated by the container host or load balancer.
5. Automated Postgres backups with a documented retention period. Enable object-storage versioning or an equivalent photo recovery policy when available.

Do not copy the local demo SQLite database or demo users into production. Initialize clean production data and import the current receiving file through the application.

## 2. Build and configure

Build the image from the repository root:

```sh
docker build -t citrus-inventory:release .
```

Configure every value in `.env.example` through the host's secret/environment manager. At minimum, production requires:

- `DJANGO_ENV=production`, `DJANGO_DEBUG=0`, and a unique random `DJANGO_SECRET_KEY`.
- `DJANGO_ALLOWED_HOSTS=lemons.example.com`.
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://lemons.example.com`.
- `SITE_URL=https://lemons.example.com`.
- All `SUPABASE_DB_*`, `SUPABASE_S3_*`, and SMTP values.
- `DJANGO_BEHIND_HTTPS_PROXY=1` when the platform terminates TLS before forwarding to the container.

Start HSTS at the default one hour. Increase it only after HTTPS and subdomains have been verified. Do not enable HSTS preload casually; it is difficult to reverse.

## 3. Define processes

Use these commands against the same built image and environment:

| Process | Command | Schedule / behavior |
|---|---|---|
| Release | `sh scripts/release.sh` | Once before routing traffic to a new release |
| Web | `sh scripts/web.sh` | Always running; route traffic only when `/readyz/` returns 200 |
| Photo scoring | `python manage.py score_photos --limit 50` | Every minute; allow only one active run per scheduled instance |
| Predictions | `python manage.py build_predictions` | Daily at 02:15 America/Los_Angeles |
| Monday report | `python manage.py send_monday_report` | Monday at 05:30 America/Los_Angeles |

`/healthz/` is a process liveness check. `/readyz/` verifies the database and is the traffic-readiness check. Neither endpoint exposes credentials or exception details.

The initial web settings are conservative because photo scoring is CPU-heavy: two workers, four threads, and a 120-second request timeout. Run scheduled photo scoring in a separate job/container so OpenCV never competes inside a web request.

## 4. Initialize production

After the first release command succeeds, run these one-off commands:

```sh
python manage.py seed_plants
python manage.py createsuperuser
python manage.py send_monday_report --dry-run
```

Then:

1. Confirm the three plant codes and replace placeholder plant names/cities in Admin.
2. Set each plant's weekly capacity and report recipients.
3. Create named foreman and GM accounts. Pin every foreman to one plant through `UserProfile`.
4. Import the current receiving CSV.
5. Never run `seed_demo --force` in production.

## 5. Staging acceptance

Complete all of these on the same infrastructure pattern before production:

- `python manage.py check --deploy` reports no errors.
- Release migrations succeed twice, proving the release command is repeatable.
- `/healthz/` and `/readyz/` return 200; `/login/` loads over HTTPS.
- A real foreman phone can log in, take a photo, save a sample, and see scoring finish.
- A deliberately poor photo produces a same-visit retake instruction.
- Receiving, room-move, partial-packout, and final-packout imports reconcile correctly.
- The report dry run is correct, then one real test report reaches the intended internal recipients.
- A foreman cannot access another plant and a GM cannot change admin-only settings.
- A database backup is restored into a disposable environment and a private photo can be retrieved.

## 6. Release and rollback

Deploy immutable image tags. Run `scripts/release.sh`, start the new web revision, wait for `/readyz/`, then move traffic. Retain the previous image for rollback.

Before each schema change, review whether the migration is backward-compatible with the previous image. If it is not, use an expand/migrate/contract rollout rather than relying on a database rollback. Database restoration is the last resort and must be tested before the pilot.

## 7. Go-live gate

The system may support decisions during the pilot, but should not make autonomous pack calls. Keep the existing process in parallel until the calibration protocol has at least 20 directly labeled packouts, inventory is reconciled daily, and management explicitly accepts the measured error and downgrade outcomes.
