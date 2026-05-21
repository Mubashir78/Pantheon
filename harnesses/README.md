# Harness YAMLs — ☠️ DEPRECATED

> **These files are legacy and NOT referenced by any active code.**
> They are kept on disk for historical reference only.

**Replaced by:** Per-god profiles at `~/.hermes/profiles/<god>/` with `config.yaml` + `god.json`
**Canonical architecture:** `~/pantheon/ARCHITECTURE.md`
**Active god system:** `GET /api/gods` via `~/pantheon/webui/api/routes.py`

### What was this?
An early attempt at defining god roles through YAML "harnesses." Each file defined an agent identity, routing rules, and model config. The harness concept was never wired into the actual runtime — it stayed as aspirational architecture.

### What to do with these?
- They are safe to archive or delete
- If any config values here are useful, they've already been migrated to the profile config
- Do NOT create new harness files
