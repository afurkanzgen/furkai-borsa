# FurkAI BIST V15.9.7 — Render Persistent Disk

## What changed
- Render Blueprint attaches a persistent disk named `furkai-data` at `/var/data` with 1 GB.
- `FURKAI_DATA_DIR=/var/data` is set in `render.yaml`.
- SQLite DB, config, secret, and application log are stored under that directory.
- On first runtime boot only, the packaged demo DB/config are copied into the persistent directory if they do not exist.
- The seed DB contains the 11 demo portfolio positions but no test users or sessions. The configured bootstrap admin claims that demo portfolio.
- Subsequent restarts/redeploys keep the persistent DB and do not overwrite it.

## Render requirements
Persistent disks are available for paid web services. The disk mount only preserves files written under `/var/data`; the rest of the service filesystem remains ephemeral.

## Dashboard check after deploy
1. Open the FurkAI web service in Render.
2. Open **Disks** and confirm the disk `furkai-data` is attached at `/var/data`.
3. Deploy V15.9.7.
4. Create a test account and add a test position.
5. Trigger a new deploy/restart.
6. Log in again and confirm the account and position still exist.
