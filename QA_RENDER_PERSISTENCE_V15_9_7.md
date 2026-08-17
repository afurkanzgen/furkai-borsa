# FurkAI BIST V15.9.7 — Render Persistent Disk

- Render persistent disk: `/var/data`, 1 GB.
- `FURKAI_DATA_DIR=/var/data`.
- SQLite DB, config, secret, and log are stored under DATA_DIR.
- On first boot only, packaged DB/config are copied into persistent storage.
- Seed DB contains the 11 demo portfolio positions but no test users/sessions; the configured bootstrap admin claims the demo portfolio.
- Subsequent deploys/restarts reuse the persistent DB and do not overwrite it.
