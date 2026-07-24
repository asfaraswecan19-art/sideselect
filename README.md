# Side Select — Streamlit app

Public pick ledger + waitlist for LoL esports predictions. Two tabs:
**Ledger** (the public track record, with an admin-only add/settle flow) and
**About & Waitlist** (methodology, the "graveyard" of rejected ideas, and an
email signup).

## Run it locally

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit .streamlit/secrets.toml and set a real ADMIN_PASSWORD

streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`). Log in with
your admin password in the sidebar to post and settle picks; everyone else
sees a read-only public view.

Data lives in `sideselect.db`, a SQLite file created next to `app.py` on
first run. Back it up before you redeploy anywhere that wipes disk.

## Admin auth vs. the earlier HTML version

The admin password here is checked **on the server**, inside `app.py` — not
in anything sent to the browser. That's a real improvement over a client-side
PIN: nobody can read the password by viewing page source. It's still just a
single shared password, though, so treat it like any other credential — don't
commit `secrets.toml`, and rotate it if you ever suspect it leaked.

## Deploying

**Streamlit Community Cloud** (free, easiest):
1. Push this folder to a GitHub repo (`secrets.toml` stays out — it's
   gitignored).
2. Go to [share.streamlit.io](https://share.streamlit.io), connect the repo,
   set the main file to `app.py`.
3. In the app's settings → Secrets, paste in `ADMIN_PASSWORD = "..."`.

**Important persistence caveat:** Community Cloud's filesystem is not
guaranteed to survive redeploys or long idle periods — your `sideselect.db`
file can reset. That's fine while you're testing, but it's a problem for a
product whose whole pitch is an unbroken public record. Before you rely on
this for real:
- Deploy somewhere with a persistent disk instead (a small VPS, Render/
  Railway with a mounted volume), **or**
- Swap SQLite for a small hosted Postgres (Supabase and Neon both have free
  tiers) — the `get_conn()` / `init_db()` functions in `app.py` are the only
  place that would need to change.

Either is a small follow-up once you know which host you want; ask if you'd
like the Postgres version built out.

## File map

- `app.py` — the whole app
- `requirements.txt` — Python deps
- `.streamlit/config.toml` — theme (dark navy + brass, matches the original design)
- `.streamlit/secrets.toml.example` — copy to `secrets.toml`, do not commit the real one
- `sideselect.db` — created automatically on first run (SQLite)
