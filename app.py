"""
Side Select — public pick ledger + waitlist, built for Streamlit.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Data lives in sideselect.db (SQLite) next to this file. See README.md for
deployment notes, especially around persistence on hosted platforms.
"""

import os
import re
import uuid
import sqlite3
from datetime import datetime, date, time as dtime

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sideselect.db")
KNOWN_LEAGUES = [
    "LCK", "LPL", "LEC", "LCS", "CBLOL", "MSI", "EWC",
    "First Stand", "Worlds", "LCK Challengers", "LFL", "EMEA Masters", "Prime League",
]

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    ADMIN_PASSWORD = "changeme"  # dev fallback — set a real one in .streamlit/secrets.toml

st.set_page_config(page_title="Side Select", page_icon="🎯", layout="wide")

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    conn = get_conn()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS picks (
            id TEXT PRIMARY KEY,
            posted_at TEXT NOT NULL,
            league TEXT NOT NULL,
            market TEXT NOT NULL,
            match TEXT NOT NULL,
            pick TEXT NOT NULL,
            edge REAL NOT NULL DEFAULT 0,
            odds REAL,
            units REAL,
            confidence REAL,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            settled_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS waitlist (
            email TEXT PRIMARY KEY,
            ts TEXT NOT NULL
        )"""
    )
    # Migrate any pre-existing picks table that predates the odds/units columns.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(picks)").fetchall()}
    if "odds" not in cols:
        conn.execute("ALTER TABLE picks ADD COLUMN odds REAL")
    if "units" not in cols:
        conn.execute("ALTER TABLE picks ADD COLUMN units REAL")
    conn.commit()
    conn.close()


def get_picks_df() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM picks", conn)
    conn.close()
    if df.empty:
        return df
    df["posted_at"] = pd.to_datetime(df["posted_at"])
    return df.sort_values("posted_at", ascending=False).reset_index(drop=True)


def add_pick(league, market, match, pick, odds, units, confidence, note, posted_at):
    conn = get_conn()
    conn.execute(
        """INSERT INTO picks (id, posted_at, league, market, match, pick, edge, odds, units, confidence, note, status, settled_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 'pending', NULL)""",
        (str(uuid.uuid4()), posted_at.isoformat(), league, market, match, pick, odds, units, confidence, note),
    )
    conn.commit()
    conn.close()


def update_pick(pick_id, league, market, match, pick, odds, units, confidence, note, posted_at):
    conn = get_conn()
    conn.execute(
        """UPDATE picks SET league=?, market=?, match=?, pick=?, odds=?, units=?, confidence=?, note=?, posted_at=?
           WHERE id=?""",
        (league, market, match, pick, odds, units, confidence, note, posted_at.isoformat(), pick_id),
    )
    conn.commit()
    conn.close()


def set_status(pick_id, status):
    conn = get_conn()
    settled_at = datetime.now().isoformat() if status in ("win", "loss") else None
    conn.execute("UPDATE picks SET status = ?, settled_at = ? WHERE id = ?", (status, settled_at, pick_id))
    conn.commit()
    conn.close()


def delete_pick(pick_id):
    conn = get_conn()
    conn.execute("DELETE FROM picks WHERE id = ?", (pick_id,))
    conn.commit()
    conn.close()


def add_waitlist_email(email):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO waitlist (email, ts) VALUES (?, ?)", (email, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_waitlist_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0]
    conn.close()
    return n


init_db()

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

.ss-brand { font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:26px; }
.ss-brand .accent { color:#C9A227; }
.ss-tag { color:#8B93A7; font-size:13px; margin-top:-8px; }

.ss-pill { font-family:'JetBrains Mono',monospace; font-size:10.5px; letter-spacing:0.05em;
    background:#1C2438; border:1px solid #2A3448; color:#8B93A7; padding:2px 8px; border-radius:5px; }
.ss-market { font-family:'JetBrains Mono',monospace; font-size:10.5px; letter-spacing:0.05em; color:#C9A227; }
.ss-posted { font-family:'JetBrains Mono',monospace; font-size:10.5px; color:#8B93A7; float:right; }
.ss-num { font-family:'JetBrains Mono',monospace; color:#8A701F; font-size:12px; }
.ss-match { font-family:'Space Grotesk',sans-serif; font-weight:700; font-size:17px; margin:4px 0 2px; }
.ss-note { font-size:12.5px; color:#8B93A7; font-style:italic; margin-top:4px; }

.ss-badge { font-family:'JetBrains Mono',monospace; font-size:10.5px; letter-spacing:0.06em; text-transform:uppercase;
    padding:3px 9px; border-radius:999px; border:1px solid #2A3448; color:#8B93A7; }
.ss-badge.win { color:#4FD1AE; border-color:#4FD1AE; }
.ss-badge.loss { color:#E2694B; border-color:#E2694B; }
.ss-badge.void { color:#8B93A7; text-decoration:line-through; }

.ss-stat-label { font-family:'JetBrains Mono',monospace; font-size:14px; font-weight:600; color:#C9A227; }
.ss-stat-label.win { color:#4FD1AE; } .ss-stat-label.loss { color:#E2694B; }
.ss-stat-sub { font-family:'JetBrains Mono',monospace; font-size:11px; color:#8B93A7; margin-top:1px; }

.ss-grave-name { font-family:'Space Grotesk',sans-serif; text-decoration:line-through;
    text-decoration-color:#E2694B; text-decoration-thickness:1.5px; }
.ss-grave-result { font-family:'JetBrains Mono',monospace; font-size:12px; color:#E2694B; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar — brand + admin auth (real server-side check, unlike a client PIN)
# ---------------------------------------------------------------------------

if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "editing_pick_id" not in st.session_state:
    st.session_state.editing_pick_id = None

with st.sidebar:
    st.markdown('<div class="ss-brand"><span class="accent">Side</span> Select</div>', unsafe_allow_html=True)
    st.markdown('<div class="ss-tag">Public pick ledger</div>', unsafe_allow_html=True)
    st.write("")

    if st.session_state.is_admin:
        st.success("Admin mode on")
        if st.button("Log out"):
            st.session_state.is_admin = False
            st.rerun()
    else:
        with st.form("admin_login", clear_on_submit=True):
            pw = st.text_input("Admin password", type="password")
            if st.form_submit_button("Log in"):
                if pw == ADMIN_PASSWORD:
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.error("Wrong password.")

    if st.session_state.is_admin:
        st.write("")
        st.caption(f"Waitlist signups: {get_waitlist_count()}")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_ledger, tab_about = st.tabs(["Ledger", "About & Waitlist"])

# ---------------------------------------------------------------------------
# LEDGER TAB
# ---------------------------------------------------------------------------

with tab_ledger:
    df = get_picks_df()

    settled = df[df["status"].isin(["win", "loss"])] if not df.empty else df
    wins = int((settled["status"] == "win").sum()) if not settled.empty else 0
    losses = int((settled["status"] == "loss").sum()) if not settled.empty else 0
    pending = int((df["status"] == "pending").sum()) if not df.empty else 0
    accuracy = f"{wins / (wins + losses) * 100:.1f}%" if (wins + losses) > 0 else "—"
    avg_odds = f"{df['odds'].mean():.2f}" if not df.empty and df["odds"].notna().any() else "—"
    avg_units = f"{df['units'].mean():.1f}u" if not df.empty and df["units"].notna().any() else "—"
    since = df["posted_at"].min().strftime("%b %d, %Y") if not df.empty else "—"

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Record", f"{wins}–{losses}")
    c2.metric("Accuracy", accuracy)
    c3.metric("Avg. odds", avg_odds)
    c4.metric("Avg. units", avg_units)
    c5.metric("Pending", pending)
    c6.metric("Since", since)

    st.divider()

    if st.session_state.is_admin:
        with st.expander("➕ Log a new pick", expanded=df.empty):
            with st.form("add_pick_form", clear_on_submit=True):
                fc1, fc2 = st.columns(2)
                league = fc1.selectbox("League", KNOWN_LEAGUES)
                market = fc2.selectbox("Market", ["Win", "FT5"])
                match = st.text_input("Match", placeholder="e.g. T1 vs Gen.G")
                pc1, pc2, pc3 = st.columns(3)
                pick = pc1.text_input("Pick", placeholder="e.g. T1 — or Red side")
                odds = pc2.number_input("Odds", min_value=1.01, step=0.01, format="%.2f", value=1.90)
                units = pc3.number_input("Units", min_value=0.0, step=0.1, format="%.1f", value=1.0)
                cc1, cc2, cc3 = st.columns(3)
                confidence = cc1.number_input("Pick confidence (%, optional)", min_value=0.0, max_value=100.0, step=0.1, value=0.0)
                pdate = cc2.date_input("Posted date", value=date.today())
                ptime = cc3.time_input("Posted time", value=datetime.now().time().replace(second=0, microsecond=0))
                note = st.text_input("Note (optional)")

                if st.form_submit_button("Post pick", type="primary"):
                    if not match or not pick:
                        st.error("Match and pick are required.")
                    else:
                        posted_dt = datetime.combine(pdate, ptime)
                        add_pick(league, market, match, pick, odds, units, confidence or None, note, posted_dt)
                        st.success("Pick posted.")
                        st.rerun()
            st.caption("Post before the game's first pick lock — that's what makes the ledger worth anything.")

    fcol1, fcol2 = st.columns([3, 2])
    market_filter = fcol1.radio("Market", ["All", "Win", "FT5"], horizontal=True, label_visibility="collapsed")
    league_options = ["All leagues"] + sorted(set(KNOWN_LEAGUES) | (set(df["league"]) if not df.empty else set()))
    league_filter = fcol2.selectbox("League", league_options, label_visibility="collapsed")

    if df.empty:
        st.info("No picks logged yet." + (" Use the form above to post the first one." if st.session_state.is_admin else " Check back once the first pick goes up — every one is posted before the game starts."))
    else:
        # chronological numbering (oldest = 1), independent of filters/sort
        chrono = df.sort_values("posted_at")
        numbers = {pid: i + 1 for i, pid in enumerate(chrono["id"])}

        view = df.copy()
        if market_filter != "All":
            view = view[view["market"] == market_filter]
        if league_filter != "All leagues":
            view = view[view["league"] == league_filter]

        if view.empty:
            st.info("No picks match these filters.")

        for _, row in view.iterrows():
            status = row["status"]
            status_class = status if status in ("win", "loss", "void") else ""
            num = str(numbers[row["id"]]).zfill(3)
            odds_val = row["odds"] if pd.notna(row["odds"]) else None
            units_val = row["units"] if pd.notna(row["units"]) else None
            is_editing = st.session_state.is_admin and st.session_state.editing_pick_id == row["id"]

            with st.container(border=True):
                if is_editing:
                    st.markdown(f'<span class="ss-num">№{num}</span> <span class="ss-pill">editing</span>', unsafe_allow_html=True)
                    with st.form(f"edit_form_{row['id']}"):
                        efc1, efc2 = st.columns(2)
                        league_idx = KNOWN_LEAGUES.index(row["league"]) if row["league"] in KNOWN_LEAGUES else 0
                        e_league = efc1.selectbox("League", KNOWN_LEAGUES, index=league_idx, key=f"e_league_{row['id']}")
                        market_opts = ["Win", "FT5"]
                        market_idx = market_opts.index(row["market"]) if row["market"] in market_opts else 0
                        e_market = efc2.selectbox("Market", market_opts, index=market_idx, key=f"e_market_{row['id']}")
                        e_match = st.text_input("Match", value=row["match"], key=f"e_match_{row['id']}")
                        epc1, epc2, epc3 = st.columns(3)
                        e_pick = epc1.text_input("Pick", value=row["pick"], key=f"e_pick_{row['id']}")
                        e_odds = epc2.number_input("Odds", min_value=1.01, step=0.01, format="%.2f",
                                                    value=float(odds_val) if odds_val is not None else 1.90,
                                                    key=f"e_odds_{row['id']}")
                        e_units = epc3.number_input("Units", min_value=0.0, step=0.1, format="%.1f",
                                                     value=float(units_val) if units_val is not None else 1.0,
                                                     key=f"e_units_{row['id']}")
                        ecc1, ecc2, ecc3 = st.columns(3)
                        conf_val = row["confidence"] if pd.notna(row["confidence"]) else 0.0
                        e_conf = ecc1.number_input("Pick confidence (%, optional)", min_value=0.0, max_value=100.0,
                                                    step=0.1, value=float(conf_val), key=f"e_conf_{row['id']}")
                        e_pdate = ecc2.date_input("Posted date", value=row["posted_at"].date(), key=f"e_pdate_{row['id']}")
                        e_ptime = ecc3.time_input("Posted time", value=row["posted_at"].time().replace(second=0, microsecond=0),
                                                   key=f"e_ptime_{row['id']}")
                        e_note = st.text_input("Note (optional)", value=row["note"] or "", key=f"e_note_{row['id']}")

                        save_col, cancel_col = st.columns(2)
                        saved = save_col.form_submit_button("Save changes", type="primary")
                        cancelled = cancel_col.form_submit_button("Cancel")
                        if saved:
                            if not e_match or not e_pick:
                                st.error("Match and pick are required.")
                            else:
                                posted_dt = datetime.combine(e_pdate, e_ptime)
                                update_pick(row["id"], e_league, e_market, e_match, e_pick,
                                            e_odds, e_units, e_conf or None, e_note, posted_dt)
                                st.session_state.editing_pick_id = None
                                st.rerun()
                        if cancelled:
                            st.session_state.editing_pick_id = None
                            st.rerun()
                    continue

                left, right = st.columns([4, 1])
                with left:
                    st.markdown(
                        f'<span class="ss-num">№{num}</span> '
                        f'<span class="ss-pill">{row["league"]}</span> '
                        f'<span class="ss-market">{"FT5 SIGNAL" if row["market"] == "FT5" else "WIN MODEL"}</span> '
                        f'<span class="ss-posted">posted {row["posted_at"].strftime("%b %d, %Y")}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f'<div class="ss-match">{row["match"]}</div>', unsafe_allow_html=True)
                    conf_txt = f' · confidence {row["confidence"]:.0f}%' if pd.notna(row["confidence"]) and row["confidence"] else ""
                    st.markdown(f'Pick: **{row["pick"]}**{conf_txt}')
                    if row["note"]:
                        st.markdown(f'<div class="ss-note">{row["note"]}</div>', unsafe_allow_html=True)

                with right:
                    odds_txt = f'@{odds_val:.2f}' if odds_val is not None else '—'
                    units_txt = f'{units_val:.1f}u' if units_val is not None else '—'
                    st.markdown(
                        f'<div style="text-align:right;">'
                        f'<div class="ss-stat-label {status_class}">{odds_txt}</div>'
                        f'<div class="ss-stat-sub">{units_txt}</div>'
                        f'<div style="margin-top:8px;"><span class="ss-badge {status_class}">{status}</span></div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                if st.session_state.is_admin:
                    bcols = st.columns(6)
                    if status == "pending":
                        if bcols[0].button("Mark win", key=f"win_{row['id']}"):
                            set_status(row["id"], "win"); st.rerun()
                        if bcols[1].button("Mark loss", key=f"loss_{row['id']}"):
                            set_status(row["id"], "loss"); st.rerun()
                        if bcols[2].button("Void", key=f"void_{row['id']}"):
                            set_status(row["id"], "void"); st.rerun()
                    else:
                        if bcols[0].button("Reopen", key=f"reopen_{row['id']}"):
                            set_status(row["id"], "pending"); st.rerun()
                    if bcols[4].button("✏️ Edit", key=f"edit_{row['id']}"):
                        st.session_state.editing_pick_id = row["id"]
                        st.rerun()
                    if bcols[5].button("🗑 Delete", key=f"del_{row['id']}"):
                        delete_pick(row["id"]); st.rerun()

# ---------------------------------------------------------------------------
# ABOUT / WAITLIST TAB
# ---------------------------------------------------------------------------

with tab_about:
    st.markdown(
        '<div class="ss-brand" style="font-size:34px;">We publish the record '
        '<span class="accent">before</span> we publish an opinion.</div>',
        unsafe_allow_html=True,
    )
    st.write(
        "Pre-game League of Legends match predictions from a model backtested "
        "walk-forward on thousands of pro games — every pick timestamped and "
        "posted before the first ban, win or lose."
    )

    st.subheader("How this works")
    m1, m2, m3 = st.columns(3)
    method_cards = [
        ("01", "Walk-forward only", "Every statistic a pick relies on is built from games that happened before it, never after."),
        ("02", "Real stakes, real prices", "Every pick lists the odds taken and the size staked — the actual terms of the bet, not just a win/loss call."),
        ("03", "Losses stay up", "The ledger keeps every settled pick, wins and losses both, permanently."),
    ]
    for col, (num, title, body) in zip([m1, m2, m3], method_cards):
        with col:
            with st.container(border=True):
                st.markdown(f'<span class="ss-num">{num}</span>', unsafe_allow_html=True)
                st.markdown(f"**{title}**")
                st.caption(body)

    st.divider()
    st.subheader("Get picks when they go up")
    st.caption("No spam, no daily digest — just a note when a new pick is posted, before the game starts.")

    with st.form("waitlist_form", clear_on_submit=True):
        wc1, wc2 = st.columns([3, 1])
        email = wc1.text_input("Email", placeholder="you@email.com", label_visibility="collapsed")
        submitted = wc2.form_submit_button("Join the list", type="primary")
        if submitted:
            if re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email or ""):
                add_waitlist_email(email.strip().lower())
                st.success("You're on the list.")
            else:
                st.error("Enter a valid email.")

    st.divider()
    st.caption(
        "Side Select publishes model-based predictions for informational purposes only. "
        "This is not financial or gambling advice, and no figure shown is a guarantee — "
        "every result here is historical, not a promise about the next game. Must be of "
        "legal betting age in your jurisdiction; gambling is illegal or restricted in some "
        "regions. If gambling stops being fun, contact the National Problem Gambling "
        "Helpline: call or text **1-800-MY-RESET** (or 1-800-522-4700), or visit ncpgambling.org."
    )
