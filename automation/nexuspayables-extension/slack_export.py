#!/usr/bin/env python3
"""
Export everything you can see in a Slack workspace into ONE combined CSV (Playwright, signed-in browser).

How it works (standalone: no other file needed)
  1. Opens https://app.slack.com/ in a Chrome profile (fresh / live / copied) and reads the web client's
     session token from the page (kept in memory only, never written to disk).
  2. Calls Slack's own web API through that signed-in session: users, channels, private channels,
     group DMs and DMs, full history of each (thread replies included), file metadata.
  3. Saves raw JSON to <out>/raw/ and builds <out>/slack_export.csv from it.

Usage
  python slack_export.py --fresh-login --from-date 2026-09-01 --to-date 2026-10-01 --no-type
  python slack_export.py --live-profile --profile Vipul --our-side "Name One, Name Two"
  python slack_export.py --fresh-login --our-side auto        # reply = same Slack workspace, response = external
  python slack_export.py --parse-only --from-date 2026-09-01 --to-date 2026-10-01
  python slack_export.py --help

--from-date is inclusive, --to-date exclusive (UTC). Only export data you are authorised to export.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SLACK_URL = "https://app.slack.com/"
SYSTEM_SUBTYPES = {"pinned_item", "unpinned_item", "reminder_add", "reminder_delete", "tombstone"}

CLEAN_COLUMNS = [
    # the original 17 (same order as before)
    "record_type", "team_name", "channel_name", "conversation_type", "conversation_name",
    "created_at", "sender_name", "message_type", "content_text", "type",
    "message_ts", "thread_ts", "reactions", "file_count",
    "replied", "replied_by", "reply_minutes",
    # everything else Slack gives us
    "team_id", "channel_id", "sender_id", "sender_email", "sender_title", "sender_type",
    "parent_message", "reply_count", "reply_users_count", "latest_reply_at", "edited_at",
    "reaction_count", "reaction_users", "mentions", "links", "is_pinned", "bot_name", "permalink",
    "file_names", "file_id", "file_name", "file_type", "file_size", "file_url",
    "topic", "purpose", "member_count", "is_archived", "is_shared", "created_by", "timezone", "status_text"]
BASIC_COLUMNS = CLEAN_COLUMNS[:CLEAN_COLUMNS.index("reply_minutes") + 1]

# --------------------------------------------------------------------------- shared helpers (self-contained)
def chrome_user_data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ["LOCALAPPDATA"]) / "Google" / "Chrome" / "User Data"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Google/Chrome"
    return Path.home() / ".config/google-chrome"


def list_profiles(user_data: Path) -> dict:
    state = json.loads((user_data / "Local State").read_text("utf-8"))
    return state.get("profile", {}).get("info_cache", {})


def profile_labels(folder: str, info: dict) -> list[str]:
    keys = ("name", "gaia_name", "gaia_given_name", "given_name", "user_name")
    return [folder] + [info[k] for k in keys if info.get(k)]


def find_profile(user_data: Path, wanted: str) -> str | None:
    w = wanted.strip().lower()
    profiles = list_profiles(user_data)
    for folder, info in profiles.items():
        if any(l.lower() == w for l in profile_labels(folder, info)):
            return folder
    for folder, info in profiles.items():
        if any(w in l.lower() for l in profile_labels(folder, info)):
            return folder
    return None


def chrome_running() -> bool:
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"],
                             capture_output=True, text=True).stdout
        return "chrome.exe" in out.lower()
    except Exception:
        return False


def copy_profile(user_data: Path, folder: str, dest: Path, refresh: bool) -> None:
    if (dest / folder).exists() and not refresh:
        print(f"[profile] reusing copy at {dest}  (use --refresh-profile to re-copy)")
        return
    if chrome_running():
        print("[profile] WARNING: Chrome is running; close ALL Chrome windows (and the tray "
              "icon) for a reliable copy. Trying anyway...")
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(user_data / "Local State", dest / "Local State")
    skip = {"Cache", "Code Cache", "GPUCache", "GrShaderCache", "ShaderCache", "Crashpad",
            "BrowserMetrics", "Extensions", "CacheStorage", "DawnCache", "optimization_guide_model_store"}
    errors = []
    try:
        shutil.copytree(user_data / folder, dest / folder,
                        ignore=lambda d, names: [n for n in names if n in skip],
                        ignore_dangling_symlinks=True)
    except shutil.Error as e:
        errors = e.args[0]
    cookies = any((dest / folder / p).exists() for p in ("Network/Cookies", "Cookies"))
    if not cookies:
        sys.exit("[profile] Could not copy the Cookies database (Chrome is probably holding it). "
                 "Close every Chrome window and re-run with --refresh-profile.")
    if errors:
        print(f"[profile] {len(errors)} non-critical files could not be copied (ignored).")
    print(f"[profile] copied '{folder}' -> {dest}")


def date_bounds(args):
    """--from-date (inclusive) / --to-date (exclusive), UTC -> 'YYYY-MM-DD HH:MM:SS' strings or None."""
    out = []
    for label, v in (("--from-date", args.from_date), ("--to-date", args.to_date)):
        if not v:
            out.append(None)
            continue
        try:
            out.append(datetime.fromisoformat(v.strip()).strftime("%Y-%m-%d %H:%M:%S"))
        except ValueError:
            sys.exit(f"{label} must look like 2026-09-01 (or 2026-09-01 00:00:00), got '{v}'")
    if out[0] and out[1] and out[0] >= out[1]:
        sys.exit("--from-date must be earlier than --to-date")
    return out[0], out[1]


def resolve_profile(args, out: Path):
    ud = chrome_user_data_dir()
    if args.fresh_login:
        print(f"[profile] fresh Playwright profile (sign in once; it is remembered)")
        return out / "playwright_profile", "Default"
    if args.user_data_dir:
        return Path(args.user_data_dir), args.profile_dir or "Default"
    folder = args.profile_dir or find_profile(ud, args.profile)
    if args.live_profile:
        if chrome_running():
            sys.exit("Close ALL Chrome windows first (also the tray icon / Task Manager), then re-run.")
        folder = folder or "Default"
        work = Path.home() / "chrome_live_profile_link"
        if not work.exists():
            subprocess.run(["cmd", "/c", "mklink", "/J", str(work), str(ud)], check=True)
        print(f"[profile] LIVE profile '{folder}' via junction {work}")
        return work, folder
    if not folder:
        lines = [f"  {f:<12} name={i.get('name')!r} account={i.get('user_name')!r}" for f, i in list_profiles(ud).items()]
        sys.exit(f"No Chrome profile matches '{args.profile}'. Profiles:\n" + "\n".join(lines)
                 + "\nRe-run with --profile <name|folder|email>, --live-profile or --fresh-login.")
    work = out / "chrome_profile_copy"
    copy_profile(ud, folder, work, args.refresh_profile)
    return work, folder


# --------------------------------------------------------------------------- slack helpers
def epoch(s: str | None) -> str:
    """'YYYY-MM-DD HH:MM:SS' (UTC) -> unix seconds string for the API, or ''."""
    if not s:
        return ""
    return str(int(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()))


def ts_utc(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""


class State:
    base = ""        # https://<workspace>.slack.com/
    token = ""       # xoxc-... in memory only
    team_id = ""
    team_name = ""


def pump(page, ms):
    page.wait_for_timeout(ms)


def read_session(page, wanted: str):
    """Read the web client's tokens from localStorage. Returns (team_dict) or list of teams if ambiguous."""
    try:
        raw = page.evaluate("() => localStorage.getItem('localConfig_v2')")
    except Exception:
        return None
    if not raw:
        return None
    try:
        teams = json.loads(raw).get("teams") or {}
    except Exception:
        return None
    teams = {k: v for k, v in teams.items() if isinstance(v, dict) and v.get("token")}
    if not teams:
        return None
    if wanted:
        w = wanted.lower()
        hit = [dict(v, id=k) for k, v in teams.items()
               if w in (v.get("name", "") + " " + v.get("domain", "") + " " + k + " " + v.get("url", "")).lower()]
        return hit[0] if hit else []
    if len(teams) == 1:
        k, v = next(iter(teams.items()))
        return dict(v, id=k)
    return [dict(v, id=k) for k, v in teams.items()]


def api(ctx, page, st: State, method: str, wanted: str = "", **params):
    """Call a Slack Web API method through the signed-in session. Returns the JSON dict (ok true/false)."""
    data = {"token": st.token}
    data.update({k: str(v) for k, v in params.items() if v not in (None, "")})
    refreshed = False
    for attempt in range(10):
        try:
            r = ctx.request.post(st.base + "api/" + method, form=data,
                                 headers={"Origin": "https://app.slack.com"}, timeout=90000)
        except Exception as e:
            print(f"    network error ({e}); retrying")
            pump(page, 3000)
            continue
        if r.status == 429:
            wait = int(r.headers.get("retry-after", "10")) + 1
            print(f"    rate limited; waiting {wait}s")
            pump(page, wait * 1000)
            continue
        try:
            j = r.json()
        except Exception:
            pump(page, 2000 * (attempt + 1))
            continue
        if j.get("ok"):
            return j
        err = j.get("error", "")
        if err == "ratelimited":
            pump(page, 15000)
        elif err in ("invalid_auth", "not_authed", "token_expired", "token_revoked") and not refreshed:
            print(f"    {err}; refreshing session token")
            refreshed = True
            page.reload()
            pump(page, 8000)
            t = read_session(page, wanted or st.team_id)
            if isinstance(t, dict):
                st.token = t["token"]
                data["token"] = st.token
        else:
            return j
    return {"ok": False, "error": "gave_up"}


def paginate(ctx, page, st, method, key, wanted="", **params):
    cursor = ""
    while True:
        j = api(ctx, page, st, method, wanted, cursor=cursor, **params)
        if not j.get("ok"):
            yield None, j
            return
        yield j.get(key) or [], j
        cursor = (j.get("response_metadata") or {}).get("next_cursor", "")
        if not cursor:
            return
        pump(page, 400)


# --------------------------------------------------------------------------- capture
def capture(args, out: Path) -> None:
    from playwright.sync_api import sync_playwright

    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetched = open(raw_dir / "fetched.jsonl", "a", encoding="utf-8")
    prog_path = out / "progress.json"
    progress = json.loads(prog_path.read_text()) if prog_path.exists() else {"done": []}
    date_from, date_to = date_bounds(args)
    check = bool(args.our_side.strip() or args.our_domains.strip()) and not args.no_replied   # need messages AFTER --to-date too
    key = f"{date_from or ''}|{'now' if check else (date_to or '')}"
    if progress.get("range", "|") not in ("|", key):
        progress["done"] = []
    progress["range"] = key
    if date_from or date_to:
        print(f"[range] {date_from or 'beginning'} (incl.) -> {date_to or 'now'} (excl.), UTC")
    oldest, latest = epoch(date_from), ('' if check else epoch(date_to))

    def save(kind, **kw):
        fetched.write(json.dumps({"kind": kind, **kw}, ensure_ascii=False) + "\n")

    work, folder = resolve_profile(args, out)
    st = State()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(work), channel=(None if args.channel == "chromium" else args.channel),
            headless=False, no_viewport=True, args=[f"--profile-directory={folder}"],
            ignore_default_args=["--enable-automation"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        print(f"[slack] opening {args.url}  (sign in in the window if asked; waiting up to 10 min)")
        page.goto(args.url, wait_until="domcontentloaded")
        team, warned = None, False
        for i in range(300):
            pump(page, 2000)
            # after sign-in Slack opens the workspace in a NEW tab; the session lives on app.slack.com
            app_page = next((pg for pg in ctx.pages if (pg.url or "").startswith("https://app.slack.com")), None)
            if app_page is not None:
                page = app_page
                team = read_session(page, args.workspace)
                if team:
                    break
                if team == [] and not warned:   # signed in, but --workspace matched nothing
                    warned = True
                    found = read_session(page, "")
                    found = [found] if isinstance(found, dict) else (found or [])
                    print("[slack] --workspace '%s' matched nothing. Signed-in workspaces: %s"
                          % (args.workspace, ", ".join(f"{t.get('name')!r} ({t.get('id')})" for t in found) or "none found"))
            if i and i % 15 == 0:
                print(f"[slack] still waiting for Slack to load / sign-in ({i * 2}s)... tabs: "
                      + ", ".join((pg.url or "")[:45] for pg in ctx.pages))
        if not team:
            sys.exit("No Slack session found (or --workspace matched nothing). Sign in, then re-run.")
        if isinstance(team, list):
            names = "\n".join(f"  {t.get('name')!r}  id={t['id']}  {t.get('url')}" for t in team)
            sys.exit("Several workspaces are signed in. Re-run with --workspace <name|id>:\n" + names)
        st.base = team.get("url") or f"https://{team.get('domain')}.slack.com/"
        if not st.base.endswith("/"):
            st.base += "/"
        st.token, st.team_id, st.team_name = team["token"], team["id"], team.get("name", "")
        print(f"[slack] workspace: {st.team_name} ({st.team_id})  {st.base}")

        who = api(ctx, page, st, "auth.test")
        if not who.get("ok"):
            sys.exit(f"auth.test failed: {who.get('error')}. Make sure you are signed in to this workspace.")
        me = who.get("user_id", "")
        save("auth", data={"user_id": me, "team_id": who.get("team_id", st.team_id), "team": st.team_name,
                           "user": who.get("user")})
        info = api(ctx, page, st, "team.info")
        if info.get("ok"):
            save("team", data=info.get("team"))
            st.team_name = (info.get("team") or {}).get("name", st.team_name)

        # ---- users
        known: set[str] = set()
        if not args.no_users:
            n = 0
            for items, j in paginate(ctx, page, st, "users.list", "members", limit=1000):
                if items is None:
                    print(f"[users] users.list failed: {j.get('error')} (continuing; names will come from messages)")
                    break
                save("users", data=items)
                known.update(u.get("id") for u in items)
                n += len(items)
            print(f"[users] {n} workspace members")

        # ---- conversations
        convs: dict[str, dict] = {}
        types = "public_channel,private_channel,mpim,im"
        for items, j in paginate(ctx, page, st, "users.conversations", "channels", types=types,
                                 exclude_archived="false", limit=1000):
            if items is None:
                sys.exit(f"[conversations] users.conversations failed: {j.get('error')}")
            for c in items:
                convs[c["id"]] = c
        if args.all_public:
            for items, j in paginate(ctx, page, st, "conversations.list", "channels", types="public_channel",
                                     exclude_archived="false", limit=1000):
                if items is None:
                    break
                for c in items:
                    convs.setdefault(c["id"], c)
        save("conversations", data=list(convs.values()))
        targets = list(convs.values())
        if args.channels:
            want = {x.strip().lower().lstrip("#") for x in args.channels.split(",")}
            targets = [c for c in targets if (c.get("name") or "").lower() in want]
        if args.max_conversations:
            targets = targets[:args.max_conversations]
        kinds = {"im": 0, "mpim": 0, "private": 0, "public": 0}
        for c in targets:
            kinds["im" if c.get("is_im") else "mpim" if c.get("is_mpim") else
                  "private" if c.get("is_private") else "public"] += 1
        print(f"[conversations] {len(targets)} to export: {kinds['public']} public, {kinds['private']} private, "
              f"{kinds['mpim']} group DMs, {kinds['im']} DMs  ({len([c for c in targets if c['id'] in progress['done']])} already done)")

        # ---- messages
        for n, c in enumerate(targets, 1):
            cid = c["id"]
            label = c.get("name") or c.get("user") or cid
            if cid in progress["done"]:
                continue
            total, replies_n, parents, seen_users = 0, 0, [], set()
            for items, j in paginate(ctx, page, st, "conversations.history", "messages", channel=cid,
                                     limit=200, oldest=oldest, latest=latest):
                if items is None:
                    print(f"    [{label}] history failed: {j.get('error')} (skipped)")
                    break
                save("history", channel=cid, data=items)
                total += len(items)
                for m in items:
                    if m.get("user"):
                        seen_users.add(m["user"])
                    if (m.get("reply_count") or 0) > 0 and m.get("thread_ts") == m.get("ts"):
                        parents.append(m["ts"])
            for ts in parents:
                for items, j in paginate(ctx, page, st, "conversations.replies", "messages", channel=cid, ts=ts,
                                         limit=200, oldest=oldest, latest=latest):
                    if items is None:
                        break
                    items = [m for m in items if m.get("ts") != ts]
                    save("replies", channel=cid, data=items)
                    replies_n += len(items)
                    seen_users.update(m["user"] for m in items if m.get("user"))
            for uid in seen_users - known:       # people not in users.list (Slack Connect, guests...)
                u = api(ctx, page, st, "users.info", user=uid)
                if u.get("ok"):
                    save("users", data=[u["user"]])
                known.add(uid)
            if args.channel_members and not c.get("is_im"):
                ids = []
                for items, j in paginate(ctx, page, st, "conversations.members", "members", channel=cid, limit=1000):
                    if items is None:
                        break
                    ids.extend(items)
                save("members", channel=cid, data=ids)
                for uid in set(ids) - known:
                    u = api(ctx, page, st, "users.info", user=uid)
                    if u.get("ok"):
                        save("users", data=[u["user"]])
                    known.add(uid)
            fetched.flush()
            progress["done"].append(cid)
            prog_path.write_text(json.dumps(progress))
            print(f"[fetch] {n}/{len(targets)}  {str(label)[:34]:<34} {total:>6} messages + {replies_n:>5} thread replies")
            pump(page, 300)
        ctx.close()
    fetched.close()
    print("[fetch] done")


# --------------------------------------------------------------------------- parse
def parse(args, out: Path) -> Path:
    date_from, date_to = date_bounds(args)
    users, convs, msgs, members = {}, {}, {}, {}
    team_name, my_id, my_team, team_domain = "", "", "", ""

    path = out / "raw" / "fetched.jsonl"
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                k, d = r.get("kind"), r.get("data")
                if k == "users":
                    for u in d or []:
                        users[u["id"]] = u
                elif k == "conversations":
                    for c in d or []:
                        convs[c["id"]] = c
                elif k in ("history", "replies"):
                    for m in d or []:
                        msgs[(r["channel"], m.get("ts"))] = m
                elif k == "members":
                    members[r["channel"]] = d or []
                elif k == "team":
                    team_name = (d or {}).get("name", team_name)
                    team_domain = (d or {}).get("domain", team_domain)
                elif k == "auth":
                    my_id, my_team = d.get("user_id", ""), d.get("team_id", "")
                    team_name = team_name or d.get("team", "")

    def uname(uid: str) -> str:
        u = users.get(uid) or {}
        p = u.get("profile") or {}
        return (u.get("real_name") or p.get("real_name") or p.get("display_name") or u.get("name") or uid or "")

    def clean_text(t: str) -> str:
        t = t or ""
        t = re.sub(r"<@([UW][A-Z0-9]+)(?:\|[^>]*)?>", lambda m: "@" + uname(m.group(1)), t)
        t = re.sub(r"<#[CG][A-Z0-9]+\|([^>]*)>", r"#\1", t)
        t = re.sub(r"<!subteam\^[A-Z0-9]+\|([^>]*)>", r"\1", t)
        t = re.sub(r"<!(here|channel|everyone)(?:\|[^>]*)?>", r"@\1", t)
        t = re.sub(r"<(https?://[^|>]+)\|([^>]+)>", r"\2 (\1)", t)
        t = re.sub(r"<(https?://[^>]+)>", r"\1", t)
        return html.unescape(t).strip()

    def conv_info(cid: str) -> tuple[str, str]:
        c = convs.get(cid, {})
        if c.get("is_im"):
            return "direct message", uname(c.get("user", ""))
        if c.get("is_mpim"):
            names = [uname(u) for u in members.get(cid, []) if u != my_id]
            if not names:
                names = [x for x in re.sub(r"^mpdm-|-\d+$", "", c.get("name", "")).split("--")]
            return "group direct message", ", ".join(names)
        return ("private channel" if c.get("is_private") else "public channel"), c.get("name", cid)

    ours = None
    if args.our_side.strip().lower() == "auto":
        ours = "auto"
    elif args.our_side.strip():
        ours = {n.strip().lower() for n in args.our_side.split(",") if n.strip()}
    our_domains = {x.strip().lower().lstrip("@") for x in args.our_domains.replace(" ", ",").split(",") if x.strip()}
    have_sides = ours is not None or bool(our_domains)
    if not have_sides and not args.no_type:
        print("[csv] WARNING: no --our-domains / --our-side given -> 'type' column left blank")

    def side_of(uid: str, sender: str) -> str:
        if not have_sides or not uid:        # no side info, or a bot / app post
            return ""
        if our_domains:                      # decide by the person's e-mail domain
            email = ((users.get(uid) or {}).get("profile") or {}).get("email") or ""
            if email:
                return "reply" if email.split("@")[-1].lower() in our_domains else "response"
            if ours is None:                 # no e-mail (Slackbot, some apps): cannot tell
                return ""
        if ours == "auto":
            return "reply" if (users.get(uid, {}).get("team_id") or my_team) == my_team else "response"
        return "reply" if sender.strip().lower() in ours else "response"

    # every real message (also the ones after --to-date, they can be the answer to a client message)
    info = []
    for (cid, ts), m in msgs.items():
        sub = m.get("subtype", "") or ""
        if not args.keep_system and (sub.startswith(("channel_", "group_")) or sub in SYSTEM_SUBTYPES):
            continue
        uid = m.get("user", "")
        sender = uname(uid) if uid else (m.get("username") or (m.get("bot_profile") or {}).get("name")
                                          or (m.get("user_profile") or {}).get("real_name") or m.get("bot_id", ""))
        info.append((cid, ts, m, uid, sender, side_of(uid, sender)))

    # replied yes/no for every CLIENT message: is there a LATER message from OUR side in the same scope?
    # scope = whole conversation for DMs / group DMs; for channels the thread, else the top-level messages.
    check_replied = have_sides and not args.no_replied
    answers: dict[tuple, tuple | None] = {}
    if check_replied:
        import bisect

        def scope(cid, m):
            c = convs.get(cid, {})
            return (cid,) if (c.get("is_im") or c.get("is_mpim")) else (cid, m.get("thread_ts", "") or "")

        ours_by_scope: dict[tuple, list] = {}
        for cid, ts, m, uid, sender, side in info:
            if side == "reply":
                ours_by_scope.setdefault(scope(cid, m), []).append((float(ts), sender))
        for lst in ours_by_scope.values():
            lst.sort()
        for cid, ts, m, uid, sender, side in info:
            if side == "response":
                lst = ours_by_scope.get(scope(cid, m), [])
                i = bisect.bisect_right(lst, (float(ts), "\uffff"))
                answers[(cid, ts)] = (lst[i][1], round((lst[i][0] - float(ts)) / 60, 1)) if i < len(lst) else None

    def person(uid: str) -> dict:
        if not uid:
            return {}
        u = users.get(uid) or {}
        p = u.get("profile") or {}
        kind = ("deactivated" if u.get("deleted") else "bot" if u.get("is_bot") else
                "guest" if (u.get("is_restricted") or u.get("is_ultra_restricted")) else
                "external" if (u.get("team_id") and my_team and u.get("team_id") != my_team) else "member")
        return {"sender_id": uid, "sender_email": p.get("email") or "", "sender_title": p.get("title") or "",
                "sender_type": kind, "timezone": u.get("tz") or "", "status_text": p.get("status_text") or ""}

    def mentions_of(t: str) -> str:
        names = ["@" + uname(x) for x in re.findall(r"<@([UW][A-Z0-9]+)", t or "")]
        names += ["@" + x for x in re.findall(r"<!(here|channel|everyone)", t or "")]
        return "; ".join(dict.fromkeys(names))

    def links_of(t: str) -> str:
        return "; ".join(dict.fromkeys(re.findall(r"<(https?://[^|>]+)", t or "")))

    def permalink(cid: str, ts: str = "", thread: str = "") -> str:
        if not team_domain:
            return ""
        if not ts:
            return f"https://{team_domain}.slack.com/archives/{cid}"
        link = f"https://{team_domain}.slack.com/archives/{cid}/p{str(ts).replace('.', '')}"
        return link + (f"?thread_ts={thread}&cid={cid}" if thread and thread != ts else "")

    rows = []
    active: set[str] = set()
    for cid, ts, m, uid, sender, typ in info:
        sub = m.get("subtype", "") or ""
        created = ts_utc(ts)
        if (date_from and created < date_from) or (date_to and created >= date_to):
            continue
        ctype, cname = conv_info(cid)
        text = clean_text(m.get("text", ""))
        if not text:  # bot posts often only have attachments / blocks
            text = " | ".join(clean_text(a.get("text") or a.get("fallback") or a.get("title") or "")
                              for a in m.get("attachments") or [] if isinstance(a, dict)).strip(" |")
        thread = m.get("thread_ts", "")
        mtype = sub or ("thread_reply" if thread and thread != ts else "message")
        reactions = [r for r in m.get("reactions") or [] if isinstance(r, dict)]
        reacts = "; ".join(f"{r.get('name')}:{r.get('count')}" for r in reactions)
        react_users = "; ".join(f"{r.get('name')}: " + ", ".join(uname(u) for u in r.get("users") or [])
                                for r in reactions)
        files = [f for f in m.get("files") or [] if isinstance(f, dict)]
        parent_txt = ""
        if thread and thread != ts:
            parent_txt = clean_text((msgs.get((cid, thread)) or {}).get("text", ""))[:150]
        who = person(uid) or {"sender_type": "bot" if (m.get("bot_id") or m.get("bot_profile")) else ""}
        base = dict(who, team_id=my_team, team_name=team_name, channel_id=cid, channel_name=cname,
                    conversation_type=ctype, conversation_name=cname, created_at=created, sender_name=sender,
                    type=typ, message_ts=ts, thread_ts=thread, permalink=permalink(cid, ts, thread))
        rep = {}
        if check_replied and typ == "response":
            a = answers.get((cid, ts))
            rep = {"replied": "yes", "replied_by": a[0], "reply_minutes": a[1]} if a else {"replied": "no"}
        rows.append(dict(
            base, record_type="message", message_type=mtype, content_text=text, reactions=reacts,
            reaction_users=react_users, reaction_count=sum(r.get("count", 0) for r in reactions),
            file_count=len(files), file_names="; ".join(f.get("name") or f.get("title") or "" for f in files),
            parent_message=parent_txt, reply_count=m.get("reply_count", ""),
            reply_users_count=m.get("reply_users_count", ""),
            latest_reply_at=ts_utc(m.get("latest_reply")) if m.get("latest_reply") else "",
            edited_at=ts_utc((m.get("edited") or {}).get("ts")) if m.get("edited") else "",
            mentions=mentions_of(m.get("text", "")), links=links_of(m.get("text", "")),
            is_pinned="yes" if m.get("pinned_to") else "",
            bot_name=(m.get("bot_profile") or {}).get("name") or (m.get("username") if not uid else ""), **rep))
        for f in files:
            rows.append(dict(
                base, record_type="file", message_type=f.get("filetype") or f.get("mimetype", ""),
                content_text=" | ".join(x for x in (f.get("name") or f.get("title"),
                                                    f.get("size") and f"{f.get('size')} bytes",
                                                    f.get("permalink")) if x),
                file_id=f.get("id", ""), file_name=f.get("name") or f.get("title", ""),
                file_type=f.get("filetype") or f.get("mimetype", ""), file_size=f.get("size", ""),
                file_url=f.get("permalink") or f.get("url_private", "")))
        active.add(cid)

    # structure rows: workspace, conversations, people
    ranged = bool(date_from or date_to)
    rows.append(dict(record_type="team", team_id=my_team, team_name=team_name,
                     permalink=f"https://{team_domain}.slack.com/" if team_domain else ""))
    for cid, c in convs.items():
        if ranged and cid not in active:
            continue
        ctype, cname = conv_info(cid)
        topic_v = (c.get("topic") or {}).get("value", "")
        purpose_v = (c.get("purpose") or {}).get("value", "")
        shared = any(c.get(k) for k in ("is_ext_shared", "is_shared", "is_org_shared"))
        rows.append(dict(record_type="channel", team_id=my_team, team_name=team_name, channel_id=cid,
                         channel_name=cname, conversation_type=ctype, conversation_name=cname,
                         created_at=ts_utc(c.get("created")), content_text=topic_v or purpose_v,
                         topic=topic_v, purpose=purpose_v, member_count=c.get("num_members", ""),
                         is_archived="yes" if c.get("is_archived") else "no",
                         is_shared="yes" if shared else "no",
                         created_by=uname(c.get("creator", "")) if c.get("creator") else "",
                         permalink=permalink(cid)))
        for uid in members.get(cid, []):
            rows.append(dict(person(uid), record_type="member", team_id=my_team, team_name=team_name,
                             channel_id=cid, channel_name=cname, conversation_type=ctype,
                             conversation_name=cname, sender_name=uname(uid)))
    if not ranged:
        for uid, u in users.items():
            rows.append(dict(person(uid), record_type="member", team_id=my_team, team_name=team_name,
                             sender_name=uname(uid), message_type=person(uid)["sender_type"],
                             created_at=ts_utc(u.get("updated")) if u.get("updated") else "",
                             content_text=" | ".join(x for x in ((u.get("profile") or {}).get("title"),
                                                                 (u.get("profile") or {}).get("email")) if x)))

    order = {"team": 0, "channel": 1, "member": 2, "message": 3, "file": 4}
    rows.sort(key=lambda r: (order[r["record_type"]], r.get("conversation_name", ""), r.get("message_ts", ""),
                             r.get("created_at", "")))
    cols = [c for c in (BASIC_COLUMNS if args.basic_columns else CLEAN_COLUMNS) if not (c == "type" and args.no_type)
            and not (c in ("replied", "replied_by", "reply_minutes") and not check_replied)]
    out_path = out / "slack_export.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    counts = {k: sum(1 for r in rows if r["record_type"] == k) for k in order}
    typ = {t: sum(1 for r in rows if r.get("type") == t) for t in ("reply", "response")} if have_sides else {}
    print(f"[csv] wrote {out_path}  {counts} {typ}")
    return out_path


# --------------------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Export a Slack workspace to one combined CSV.")
    ap.add_argument("--profile", default="Vipul", help="Chrome profile name / folder / e-mail (default: Vipul)")
    ap.add_argument("--fresh-login", action="store_true", help="Private Playwright profile; sign in once")
    ap.add_argument("--live-profile", action="store_true", help="Use the real Chrome profile in place (Chrome closed)")
    ap.add_argument("--profile-dir", help="Chrome profile folder name, e.g. 'Profile 1'")
    ap.add_argument("--user-data-dir", help="Use this user-data-dir as-is")
    ap.add_argument("--channel", default="chrome", choices=["chrome", "msedge", "chromium"])
    ap.add_argument("--refresh-profile", action="store_true", help="Re-copy the Chrome profile")
    ap.add_argument("--url", default=SLACK_URL, help=f"Slack web URL (default {SLACK_URL})")
    ap.add_argument("--workspace", nargs="*", default=[], help="Workspace name / domain / id, if you are signed in to several")
    ap.add_argument("--out", default="slack_export_out", help="Output folder")
    ap.add_argument("--from-date", default="", metavar="YYYY-MM-DD", help="On/after this date (UTC, inclusive)")
    ap.add_argument("--to-date", default="", metavar="YYYY-MM-DD", help="Before this date (UTC, exclusive)")
    ap.add_argument("--our-side", nargs="*", default=[], help='Names of OUR people, comma separated (reply); others = response. '
                                                    'Or "auto": same Slack workspace = reply, external = response')
    ap.add_argument("--our-domains", nargs="*", default=[],
                    help='E-mail domains of OUR people, e.g. karmacpa.com (their messages = reply, everyone else = response)')
    ap.add_argument("--no-type", action="store_true", help="Leave the reply/response 'type' column out")
    ap.add_argument("--basic-columns", action="store_true",
                    help="Only the original 17 columns, not the extra detail columns")
    ap.add_argument("--no-replied", action="store_true", help="Skip the replied yes/no columns")
    ap.add_argument("--channels", nargs="*", default=[], help='Only these channel names, e.g. "general,accounting"')
    ap.add_argument("--all-public", action="store_true", help="Also read public channels you have not joined")
    ap.add_argument("--channel-members", action="store_true", help="Also export each channel's member list (slower)")
    ap.add_argument("--no-users", action="store_true", help="Skip the workspace member directory")
    ap.add_argument("--keep-system", action="store_true", help='Keep "X joined #channel", topic changes, etc.')
    ap.add_argument("--max-conversations", type=int, default=0, help="Limit conversations (for testing)")
    ap.add_argument("--parse-only", action="store_true", help="Only rebuild the CSV from saved raw data")
    args = ap.parse_args()
    # accept multi-word values even if the shell dropped the quotes: --workspace Two River
    for k in ("workspace", "our_side", "channels", "our_domains"):
        setattr(args, k, " ".join(getattr(args, k)).strip())

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.parse_only:
        capture(args, out)
    parse(args, out)


if __name__ == "__main__":
    main()
