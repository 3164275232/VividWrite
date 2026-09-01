# VividWrite Research Data Collection

## Participant Accounts

The deployed study uses 31 independent accounts, `tester01` through
`tester31`. They share the existing study password, but every stored session,
event, essay version, and artifact is associated with the authenticated account.

Participants must accept the research data notice on the login page. They
should use only their assigned account and must not enter personal or
confidential information.

## What Is Recorded

- Login, logout, session start/end, active time, idle time, page visibility,
  device/browser metadata, viewport size, and a one-way client fingerprint.
- Button clicks, selections, stage changes, task/chart type choices, practice
  sample choices, scrolling, feedback expansion, zoom, and error states.
- Every essay edit as an insertion/deletion delta, plus periodic and milestone
  full-text snapshots with word and character counts.
- Model/API request metadata, duration, status, input, response, DePlot text,
  generated suggestions, seven-criterion feedback, and failures.
- Original task images, generated comparison images, annotated originals, and
  other generated visual artifacts.

Passwords, cookies, authorization headers, API keys, and administrator secrets
are never written to research events. Raw client IP addresses are not stored;
the system saves a salted one-way fingerprint for session diagnostics.

## Storage and Isolation

Structured data is stored in SQLite at
`backend_user_data:/app/user_data/research/research.sqlite3`. Artifact files are
stored below the same Docker volume in participant/session folders. The Docker
volume persists across `docker compose up -d --build`. Never run
`docker compose down -v`, because that removes the study data volume.

## Configure 31 Accounts on the Server

Run this after authentication is already configured. It preserves the existing
shared password hash and model keys.

```bash
python3 deploy/configure_research.py \
  --env backend/.env \
  --user-count 31 \
  --admin-key-file "$HOME/.vividwrite-research-admin-key"
docker compose up -d --build
```

The administrator key file is mode `0600`. Do not give it to participants or
commit it to Git.

## View Participant Activity Securely

Until HTTPS is configured, do not send the administrator key to the public HTTP
address. Run the viewer through SSH so the API request stays on the server:

```bash
ssh -i LightsailDefaultKey-ap-southeast-1.pem ubuntu@SERVER_PUBLIC_IP \
  "cd VividWrite && python3 deploy/download_research_data.py \
  --base-url http://127.0.0.1 \
  --admin-key-file \$HOME/.vividwrite-research-admin-key --list"
```

## Download Data

Create one participant export on the server:

```bash
ssh -i LightsailDefaultKey-ap-southeast-1.pem ubuntu@SERVER_PUBLIC_IP \
  "cd VividWrite && python3 deploy/download_research_data.py \
  --base-url http://127.0.0.1 \
  --admin-key-file \$HOME/.vividwrite-research-admin-key \
  --participant tester07 --output \$HOME/vividwrite-tester07-research-data.zip"
```

Create an all-participant export:

```bash
ssh -i LightsailDefaultKey-ap-southeast-1.pem ubuntu@SERVER_PUBLIC_IP \
  "cd VividWrite && python3 deploy/download_research_data.py \
  --base-url http://127.0.0.1 \
  --admin-key-file \$HOME/.vividwrite-research-admin-key \
  --all --output \$HOME/vividwrite-study-export.zip"
```

Download either ZIP with `scp`:

```bash
scp -i LightsailDefaultKey-ap-southeast-1.pem \
  ubuntu@SERVER_PUBLIC_IP:~/vividwrite-study-export.zip .
```

Each ZIP contains `summary.html` for quick review; participant, session, event,
essay-version, and artifact CSV files for analysis; JSON/JSONL raw records; and
the archived image files. A participant can also download only their own data
while signed in from `/api/research/me/export`.

The participant site and administrator endpoints should be placed behind HTTPS
before external data collection begins.

## Study Operations

- Export and back up the study data regularly during data collection.
- Record the consent version used in the study protocol. Increment
  `APP_RESEARCH_CONSENT_VERSION` when the notice or collection scope changes.
- Restrict server and administrator-key access to the research team.
- Define retention and deletion periods in the approved ethics protocol.
- Before analysis, verify that each participant used only the assigned account.
