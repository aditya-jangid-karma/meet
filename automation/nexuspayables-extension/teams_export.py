#!/usr/bin/env python3
"""
Export (almost) everything from the Microsoft Teams web app into ONE combined CSV.

How it works
  1. Finds your Chrome profile by name (default: "Vipul"), copies it to a private
     folder (Chrome blocks automation on the live profile) so you stay signed in.
  2. Opens https://teams.cloud.microsoft/ in that profile with Playwright.
  3. Passively records the JSON the Teams web app itself loads (teams, channels, chats).
  4. Using the already-authenticated browser session, pages through the full message
     history of every chat / group / meeting chat / channel (replies included).
  5. Writes raw JSON to <out>/raw/ and a single combined CSV (record_type column:
     team | channel | chat | member | message | file).

Usage
  python teams_export.py                       # profile "Vipul"
  python teams_export.py --profile "Profile 1" # or a folder name / account e-mail
  python teams_export.py --parse-only          # rebuild the CSV from <out>/raw/ only
  python teams_export.py --manual 600          # also record 10 min of manual clicking
  python teams_export.py --help

Tokens/headers are kept in memory only and never written to disk.
Only export data you are authorised to export.
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
from urllib.parse import quote

TEAMS_URL = "https://teams.cloud.microsoft/"
TEAMS_HOSTS = ("teams.cloud.microsoft", "teams.microsoft.com", "teams.live.com")
INTERESTING = ("/chatsvc/", "/csa/", "/api/mt/", "/mt/part/", "calendar")
CHATSVC_RE = re.compile(r"^(https://[^/]+/api/chatsvc/[^/]+)/v1/")
MSG_URL_RE = re.compile(r"/conversations/([^/?]+)/messages")
SKIP_HEADERS = {"host", "content-length", "cookie", "accept-encoding", "connection"}
MSG_VIEW = "msnp24Equivalent|supportsMessageProperties"
SKIP_CONV_PREFIXES = ("48:calllogs", "48:mentions", "48:threads", "48:notifications",
                      "48:savedItems", "48:annotations", "48:drafts")

# People on OUR side (exact Teams display names). Their messages are type="reply";
# everyone else is the client side -> type="response". Can also be passed via --our-side.
OUR_SIDE: list[str] = [
    # "Kunti Rathi",
]

# Columns of the final CSV (messages only)
CLEAN_COLUMNS = ["record_type", "team_name", "channel_name", "conversation_type", "conversation_name",
                 "created_at", "sender_name", "message_type", "content_text", "type"]

COLUMNS = [
    "record_type", "team_id", "team_name", "channel_id", "channel_name",
    "conversation_id", "conversation_type", "conversation_name",
    "message_id", "parent_message_id", "created_time", "edited_time", "deleted_time",
    "sender_id", "sender_name", "message_type", "subject", "importance",
    "content_text", "content_html", "mentions", "reactions", "reaction_count",
    "attachment_count", "member_id", "member_name", "member_role",
    "file_name", "file_type", "file_url", "file_id",
    "description", "is_archived", "last_message_time",
]


# --------------------------------------------------------------------------- profile
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


# --------------------------------------------------------------------------- helpers
def jprop(v):
    """Teams stores many properties as JSON strings."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def html_to_text(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>|</tr>", "\n", s)
    s = re.sub(r'(?i)<img[^>]*?alt="([^"]*)"[^>]*>', r"\1", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(s)).strip()


def mri_from(v) -> str:
    if not v:
        return ""
    m = re.search(r"((?:8|28):[^\s/?]+)$", str(v))
    return m.group(1) if m else str(v)


def to_utc(ts: str) -> str:
    """Teams timestamp -> 'YYYY-MM-DD HH:MM:SS' in UTC."""
    if not ts:
        return ""
    t = re.sub(r"(\.\d{6})\d+", r"\1", ts.strip()).replace("Z", "+00:00")
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        return ts
    if d.tzinfo:
        d = d.astimezone(timezone.utc)
    return d.strftime("%Y-%m-%d %H:%M:%S")


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


def is_junk_name(n: str) -> bool:
    return not n.strip() or "orgid:" in n


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", s)[:120]


def conv_wanted(cid: str) -> bool:
    return bool(cid) and cid.startswith(("19:", "48:notes")) and not cid.startswith(SKIP_CONV_PREFIXES)


# --------------------------------------------------------------------------- capture
class State:
    base = None          # https://teams.cloud.microsoft/api/chatsvc/<region>
    headers = None       # in-memory only
    header_ts = 0.0
    teams_payload = None


def pump(page, ms):
    page.wait_for_timeout(ms)  # keeps Playwright event handlers running (time.sleep would not)


def api_get(ctx, page, st: State, url: str, retries: int = 6):
    """GET through the signed-in browser session. Returns parsed JSON or None."""
    for attempt in range(retries):
        try:
            r = ctx.request.get(url, headers=st.headers, timeout=60000)
        except Exception as e:
            print(f"    network error ({e}); retrying")
            pump(page, 3000)
            continue
        if r.status == 200:
            try:
                return r.json()
            except Exception:
                return None
        if r.status == 429:
            wait = int(r.headers.get("retry-after", "5")) + 1
            print(f"    throttled; waiting {wait}s")
            pump(page, wait * 1000)
        elif r.status in (401, 403):
            print(f"    auth {r.status}; refreshing session")
            before = st.header_ts
            page.reload()
            for _ in range(60):
                if st.header_ts != before:
                    break
                pump(page, 1000)
        elif r.status == 404:
            return None
        elif r.status >= 500:
            pump(page, 2000 * (attempt + 1))
        else:
            print(f"    HTTP {r.status} for {url[:120]}")
            return None
    return None


def capture(args, out: Path) -> None:
    from playwright.sync_api import sync_playwright

    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw = open(raw_dir / "capture.jsonl", "a", encoding="utf-8")
    fetched = open(raw_dir / "fetched.jsonl", "a", encoding="utf-8")
    prog_path = out / "progress.json"
    progress = json.loads(prog_path.read_text()) if prog_path.exists() else {"done": [], "threads": []}
    date_from, date_to = date_bounds(args)
    range_key = f"{date_from or ''}|{date_to or ''}"
    # conversations finished under a narrower date range must be re-fetched if the range changed
    if progress.get("range", "|") not in ("|", range_key):
        progress["done"] = []
    progress["range"] = range_key
    if date_from or date_to:
        print(f"[range] exporting messages from {date_from or 'the beginning'} (incl.) "
              f"to {date_to or 'now'} (excl.), UTC")

    ud = chrome_user_data_dir()
    if args.fresh_login:
        folder, work = "Default", out / "playwright_profile"
        print(f"[profile] fresh Playwright profile at {work} (sign in once; it is remembered)")
    elif args.user_data_dir:
        folder, work = args.profile_dir or "Default", Path(args.user_data_dir)
    elif args.live_profile:
        # Chrome 136+ refuses automation on the *default* "User Data" path, so we reach the very same
        # folder through a junction (a second path to it). Your real, signed-in profile is used in place.
        if chrome_running():
            sys.exit("Close ALL Chrome windows first (also the tray icon / Task Manager), then re-run.")
        folder = args.profile_dir or find_profile(ud, args.profile) or "Default"
        work = Path.home() / "chrome_live_profile_link"
        if not work.exists():
            subprocess.run(["cmd", "/c", "mklink", "/J", str(work), str(ud)], check=True)
        print(f"[profile] LIVE profile '{folder}' via junction {work} -> {ud}")
    else:
        folder = args.profile_dir or find_profile(ud, args.profile)
        if not folder:
            lines = [f"  {f:<12} name={i.get('name')!r} account={i.get('user_name')!r}"
                     for f, i in list_profiles(ud).items()]
            sys.exit(f"No Chrome profile matches '{args.profile}'. Profiles on this machine:\n"
                     + "\n".join(lines) + "\nRe-run with --profile <name|folder|email>.")
        work = out / "chrome_profile_copy"
        copy_profile(ud, folder, work, args.refresh_profile)
    print(f"[profile] using folder '{folder}'")

    st = State()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(work), channel=(None if args.channel == "chromium" else args.channel),
            headless=False, no_viewport=True,
            args=[f"--profile-directory={folder}"],
            ignore_default_args=["--enable-automation"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def on_request(req):
            m = CHATSVC_RE.match(req.url)
            if not m:
                return
            try:
                h = req.all_headers()
            except Exception:
                h = req.headers
            if not any(k in h for k in ("authentication", "authorization")):
                return
            st.base = m.group(1)
            st.headers = {k: v for k, v in h.items()
                          if k.lower() not in SKIP_HEADERS and not k.startswith(":")}
            st.header_ts = time.time()

        def on_response(resp):
            url = resp.url
            if resp.status != 200 or not any(h in url for h in TEAMS_HOSTS):
                return
            if not any(k in url for k in INTERESTING):
                return
            if "json" not in resp.headers.get("content-type", ""):
                return
            try:
                data = resp.json()
            except Exception:
                return
            raw.write(json.dumps({"src": "passive", "url": url, "data": data}, ensure_ascii=False) + "\n")
            raw.flush()
            if "teams/users/me" in url and isinstance(data, dict) and ("teams" in data or "chats" in data):
                st.teams_payload = data

        ctx.on("request", on_request)
        ctx.on("response", on_response)

        print(f"[teams] opening {TEAMS_URL}  (sign in in the window if asked; waiting up to 10 min)")
        page.goto(TEAMS_URL, wait_until="domcontentloaded")
        waited = 0
        while not st.headers and waited < 600:
            pump(page, 2000)
            waited += 2
            if waited % 30 == 0:
                print(f"[teams] still waiting for Teams to load / sign-in ({waited}s)...")
        if not st.headers:
            sys.exit("Teams never made an authenticated request. Sign in, then re-run.")
        print(f"[teams] session ready (chat service: {st.base})")
        if not st.base:
            print("[teams] DIAGNOSTIC: no chat-service URL seen; check raw/capture.jsonl and send it for debugging")
        for _ in range(60):  # let the team/chat list arrive
            if st.teams_payload:
                break
            pump(page, 1000)

        if args.manual:
            print(f"[manual] recording everything the page loads for {args.manual}s - click around "
                  "(Chat, Teams, Calendar, Files) to capture more. Browser stays open.")
            pump(page, args.manual * 1000)

        # ---- conversations to fetch
        convs: dict[str, str] = {}  # id -> kind
        if st.teams_payload:
            for t in st.teams_payload.get("teams") or []:
                if t.get("id"):
                    convs[t["id"]] = "channel"
                for c in t.get("channels") or []:
                    convs[c.get("id", "")] = "channel"
            for c in st.teams_payload.get("chats") or []:
                convs[c.get("id", "")] = "chat"
        else:
            print("[teams] team/chat list not seen in page traffic; falling back to conversation list API")
        url = f"{st.base}/v1/users/ME/conversations?view=msnp24Equivalent&pageSize=500&startTime=1"
        data = api_get(ctx, page, st, url)  # best effort; the csa list above is the primary source
        if data:
            fetched.write(json.dumps({"src": "fetch", "kind": "convlist", "url": url, "data": data},
                                     ensure_ascii=False) + "\n")
            for c in data.get("conversations", []):
                convs.setdefault(c.get("id", ""), "chat")
        targets = [c for c in convs if conv_wanted(c)]
        if args.max_conversations:
            targets = targets[:args.max_conversations]
        print(f"[fetch] {len(targets)} conversations to export "
              f"({len([c for c in targets if c in progress['done']])} already done)")

        # ---- member lists for teams (team id == General channel id) and member-less chats
        if st.teams_payload and not args.no_members:
            team_ids = [t["id"] for t in st.teams_payload.get("teams") or [] if t.get("id")]
            for tid in team_ids:
                if tid in progress["threads"]:
                    continue
                data = api_get(ctx, page, st, f"{st.base}/v1/threads/{quote(tid, safe='')}?view=msnp24Equivalent")
                if data:
                    fetched.write(json.dumps({"src": "fetch", "kind": "thread", "conversation_id": tid,
                                              "data": data}, ensure_ascii=False) + "\n")
                    fetched.flush()
                progress["threads"].append(tid)
                pump(page, 150)
            prog_path.write_text(json.dumps(progress))

        # ---- messages
        for i, cid in enumerate(targets, 1):
            if cid in progress["done"]:
                continue
            url = (f"{st.base}/v1/users/ME/conversations/{quote(cid, safe='')}/messages"
                   f"?view={MSG_VIEW}&pageSize=200&startTime=1")
            total, pages = 0, 0
            while url:
                data = api_get(ctx, page, st, url)
                if not data:
                    break
                msgs = data.get("messages") or []
                fetched.write(json.dumps({"src": "fetch", "kind": "messages", "conversation_id": cid,
                                          "data": {"messages": msgs}}, ensure_ascii=False) + "\n")
                total += len(msgs)
                pages += 1
                url = (data.get("_metadata") or {}).get("backwardLink") if msgs else None
                if date_from and msgs:
                    # pages run newest -> oldest; once the whole page is older than the range, stop paging
                    times = [to_utc(m.get("originalarrivaltime") or m.get("composetime", "")) for m in msgs]
                    times = [t for t in times if t]
                    if times and times[0] >= times[-1] and max(times) < date_from:
                        url = None
                pump(page, 250)
            fetched.flush()
            progress["done"].append(cid)
            prog_path.write_text(json.dumps(progress))
            print(f"[fetch] {i}/{len(targets)}  {cid[:40]:<40} {total:>6} messages ({pages} pages)")

        ctx.close()
    raw.close()
    fetched.close()
    print("[fetch] done")


# --------------------------------------------------------------------------- parse
def iter_raw(out: Path):
    for name in ("capture.jsonl", "fetched.jsonl"):
        path = out / "raw" / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                try:
                    yield json.loads(line)
                except Exception:
                    continue


def parse(args, out: Path) -> Path:
    teams, channels, chats, members, names = {}, {}, {}, {}, {}
    conv_info: dict[str, dict] = {}
    messages: dict[tuple, dict] = {}

    def remember(mri, name):
        if mri and name:
            names.setdefault(mri, name)

    def add_member(conv_id, team_id, m):
        mri = m.get("mri") or m.get("id") or m.get("userId") or ""
        name = m.get("friendlyName") or m.get("displayName") or m.get("name") or ""
        remember(mri, name)
        members[(conv_id, mri)] = {"member_id": mri, "member_name": name,
                                   "member_role": m.get("role", ""), "team_id": team_id}

    for rec in iter_raw(out):
        data, url = rec.get("data"), rec.get("url", "")
        kind = rec.get("kind")
        if not isinstance(data, dict):
            continue

        if "teams/users/me" in url:
            for t in data.get("teams") or []:
                tid = t.get("id", "")
                teams[tid] = {"team_id": tid, "team_name": t.get("displayName", ""),
                              "description": t.get("description", ""),
                              "is_archived": t.get("isArchived", "")}
                conv_info[tid] = {"type": "channel", "team_id": tid, "team_name": t.get("displayName", ""),
                                  "channel_id": tid, "channel_name": "General"}
                for c in t.get("channels") or []:
                    cid = c.get("id", "")
                    channels[cid] = {"team_id": tid, "team_name": t.get("displayName", ""),
                                     "channel_id": cid, "channel_name": c.get("displayName", ""),
                                     "conversation_type": c.get("membershipType", "channel"),
                                     "description": c.get("description", ""),
                                     "is_archived": c.get("isArchived", ""),
                                     "created_time": c.get("createdAt", "")}
                    conv_info[cid] = {"type": c.get("membershipType", "channel"), "team_id": tid,
                                      "team_name": t.get("displayName", ""), "channel_id": cid,
                                      "channel_name": c.get("displayName", "")}
            for u in data.get("users") or []:
                remember(u.get("mri", ""), u.get("displayName", ""))
            for c in data.get("chats") or []:
                cid = c.get("id", "")
                mem = c.get("members") or []
                for m in mem:
                    add_member(cid, "", m)
                explicit = c.get("title") or ""
                title = explicit or ", ".join(
                    (m.get("friendlyName") or m.get("displayName") or "") for m in mem[:6]).strip(", ")
                ctype = c.get("chatType") or ("oneOnOne" if c.get("isOneOnOne") else "group")
                if (c.get("meetingInformation") or {}).get("subject"):
                    ctype = "meeting"
                    explicit = explicit or c["meetingInformation"]["subject"]
                    title = title or explicit
                lm = (c.get("lastMessage") or {}).get("originalarrivaltime") or c.get("lastMessageTime", "")
                chats[cid] = {"conversation_id": cid, "conversation_type": ctype, "conversation_name": title,
                              "created_time": c.get("createdAt", ""), "last_message_time": lm,
                              "is_archived": c.get("hidden", "")}
                conv_info[cid] = {"type": ctype, "name": title, "title": explicit}

        elif kind == "convlist":
            for c in data.get("conversations") or []:
                cid = c.get("id", "")
                topic = (c.get("threadProperties") or {}).get("topic", "")
                if cid and cid not in conv_info:
                    conv_info[cid] = {"type": "chat", "name": topic}

        elif kind == "thread" or "/threads/" in url:
            cid = rec.get("conversation_id") or data.get("id", "")
            for m in data.get("members") or []:
                add_member(cid, cid if cid in teams else "", m)

        if "messages" in data and isinstance(data["messages"], list):
            m_url = MSG_URL_RE.search(url)
            cid = rec.get("conversation_id") or (m_url.group(1).split(";")[0] if m_url else "")
            cid = cid.replace("%3A", ":").replace("%40", "@")
            for msg in data["messages"]:
                if not isinstance(msg, dict) or not msg.get("id"):
                    continue
                messages[(cid, str(msg["id"]))] = {"msg": msg, "cid": cid}

    rows: list[dict] = []

    def row(**kw):
        rows.append(kw)

    for t in teams.values():
        row(record_type="team", **t)
    for c in channels.values():
        row(record_type="channel", **c)
    for c in chats.values():
        row(record_type="chat", **c)
    for (cid, mri), m in members.items():
        info = conv_info.get(cid, {})
        row(record_type="member", conversation_id=cid,
            team_id=m["team_id"] or info.get("team_id", ""), team_name=info.get("team_name", ""),
            conversation_type=info.get("type", ""), conversation_name=info.get("name", ""),
            member_id=mri, member_name=names.get(mri, m["member_name"]), member_role=m["member_role"])

    for (cid, mid), item in messages.items():
        msg, info = item["msg"], conv_info.get(item["cid"], {})
        props = msg.get("properties") or {}
        sender = mri_from(msg.get("from"))
        remember(sender, msg.get("imdisplayname"))
        content = msg.get("content") or ""
        link = f'{msg.get("conversationLink", "")}{msg.get("conversationid", "")}'
        pm = re.search(r"messageid=(\d+)", link)
        parent = pm.group(1) if pm and pm.group(1) != mid else ""
        reactions = jprop(props.get("emotions")) or []
        react_txt = ";".join(f'{r.get("key")}:{len(r.get("users") or [])}' for r in reactions
                             if isinstance(r, dict))
        react_n = sum(len(r.get("users") or []) for r in reactions if isinstance(r, dict))
        mentions = jprop(props.get("mentions")) or []
        ment_txt = ";".join(str(x.get("displayName") or x.get("mri") or x.get("id")) for x in mentions
                            if isinstance(x, dict)) if isinstance(mentions, list) else ""
        files = jprop(props.get("files")) or []
        files = files if isinstance(files, list) else []
        base = dict(
            team_id=info.get("team_id", ""), team_name=info.get("team_name", ""),
            channel_id=info.get("channel_id", ""), channel_name=info.get("channel_name", ""),
            conversation_id=cid, conversation_type=info.get("type", ""),
            conversation_name=info.get("name", "") or info.get("channel_name", ""),
            message_id=mid, parent_message_id=parent)
        row(record_type="message", **base,
            created_time=msg.get("originalarrivaltime") or msg.get("composetime", ""),
            edited_time=props.get("edittime", ""), deleted_time=props.get("deletetime", ""),
            sender_id=sender, sender_name=msg.get("imdisplayname", ""),
            message_type=msg.get("messagetype", ""), subject=props.get("subject", ""),
            importance=props.get("importance", ""),
            content_text=html_to_text(content),
            content_html=content if args.include_html else "",
            mentions=ment_txt, reactions=react_txt, reaction_count=react_n,
            attachment_count=len(files))
        for f in files:
            if not isinstance(f, dict):
                continue
            fi = f.get("fileInfo") or {}
            row(record_type="file", **base,
                created_time=msg.get("originalarrivaltime", ""), sender_id=sender,
                sender_name=msg.get("imdisplayname", ""),
                file_name=f.get("fileName") or f.get("title", ""), file_type=f.get("fileType") or f.get("type", ""),
                file_url=f.get("objectUrl") or fi.get("shareUrl") or fi.get("fileUrl", ""),
                file_id=f.get("itemid") or f.get("id", ""))

    # fill sender names learnt later / from member lists
    for r in rows:
        if r["record_type"] in ("message", "file") and not r.get("sender_name"):
            r["sender_name"] = names.get(r.get("sender_id", ""), "")

    # ---- optional full dump (every record type, all columns)
    order = {"team": 0, "channel": 1, "chat": 2, "member": 3, "message": 4, "file": 5}
    if args.full_csv:
        rows.sort(key=lambda r: (order[r["record_type"]], r.get("conversation_id", ""), r.get("created_time", "")))
        full = out / "teams_export_full.csv"
        with open(full, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"[csv] wrote {full}  {({k: sum(1 for r in rows if r['record_type'] == k) for k in order})}")

    # ---- final CSV: every record type, 10 columns
    # "me" = the exporting user = the member who is in the most chats; chats are named after the others
    chat_count: dict[str, int] = {}
    for (cid, mri) in members:
        if cid in chats:
            chat_count[mri] = chat_count.get(mri, 0) + 1
    me = max(chat_count, key=chat_count.get) if chat_count else None
    others: dict[str, list[str]] = {}
    for (cid, mri), m in members.items():
        if cid in chats and mri != me:
            nm = names.get(mri) or m["member_name"]
            if nm and not is_junk_name(nm):
                others.setdefault(cid, []).append(nm)

    ours = {n.strip().lower() for n in (args.our_side.split(",") if args.our_side else OUR_SIDE) if n.strip()}
    if not ours and not args.no_type:
        print("[csv] WARNING: no 'our side' names given (--our-side or OUR_SIDE) -> 'type' column left blank")

    # Every record type goes into the same 10 columns:
    #   team    -> team_name, content_text = description
    #   channel -> team/channel names, conversation_type = channel kind, content_text = description
    #   chat    -> conversation_type/name, created_at
    #   member  -> conversation context, sender_name = member's name, content_text = role
    #   message -> as is (system events like "X added Y" / call logs are dropped)
    #   file    -> sender_name = who shared it, content_text = "file name | url"
    date_from, date_to = date_bounds(args)
    clean = []
    for r in rows:
        rt = r["record_type"]
        if rt == "message" and r["message_type"].startswith(("ThreadActivity", "Event")):
            continue
        cid = r.get("conversation_id", "")
        if cid in chats:  # chat / group / meeting: explicit title, else the other people
            title = conv_info.get(cid, {}).get("title", "")
            r["conversation_name"] = title if title and not is_junk_name(title) else ", ".join(others.get(cid, []))

        if rt in ("message", "file"):
            if is_junk_name(r.get("sender_name", "")):
                r["sender_name"] = names.get(r.get("sender_id", ""), "")
            if not r["sender_name"].strip():
                continue
            r["created_at"] = to_utc(r.get("created_time", ""))
            if (date_from and r["created_at"] < date_from) or (date_to and r["created_at"] >= date_to):
                continue
            r["type"] = ("reply" if r["sender_name"].strip().lower() in ours else "response") if ours else ""
            if rt == "file":
                r["message_type"] = "File"
                r["content_text"] = " | ".join(x for x in (r.get("file_name"), r.get("file_url")) if x)
        elif rt == "member":
            r["sender_name"] = r.get("member_name", "")
            r["content_text"] = r.get("member_role", "")
        elif rt in ("team", "channel"):
            if rt == "channel":
                r["conversation_name"] = r.get("channel_name", "")
            r["content_text"] = r.get("description", "")
            r["created_at"] = to_utc(r.get("created_time", ""))
        elif rt == "chat":
            r["created_at"] = to_utc(r.get("created_time", ""))
        r.setdefault("type", "")
        clean.append(r)
    if date_from or date_to:
        # with a date range, keep team/channel/chat/member rows only for conversations that have messages in it
        active = {r["conversation_id"] for r in clean if r["record_type"] in ("message", "file")}
        active_teams = {r["team_id"] for r in clean if r["record_type"] in ("message", "file") and r.get("team_id")}
        keep = {
            "team": lambda r: r.get("team_id") in active_teams,
            "channel": lambda r: r.get("channel_id") in active,
            "chat": lambda r: r.get("conversation_id") in active,
            "member": lambda r: r.get("conversation_id") in active or r.get("conversation_id") in active_teams,
        }
        clean = [r for r in clean if r["record_type"] not in keep or keep[r["record_type"]](r)]
    clean.sort(key=lambda r: (order[r["record_type"]], r.get("conversation_id", ""), r.get("created_at", "")))

    path = out / "teams_export.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=[c for c in CLEAN_COLUMNS if not (args.no_type and c == 'type')], extrasaction="ignore")
        w.writeheader()
        w.writerows(clean)
    counts = {k: sum(1 for r in clean if r["record_type"] == k) for k in order}
    summary = {t: sum(1 for r in clean if r["type"] == t) for t in ("reply", "response")} if ours else {}
    print(f"[csv] wrote {path}  {counts} {summary}")
    return path


# --------------------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Export Microsoft Teams (web) to one combined CSV.")
    ap.add_argument("--profile", default="Vipul", help="Chrome profile name / folder / e-mail (default: Vipul)")
    ap.add_argument("--fresh-login", action="store_true",
                    help="Don't use Chrome profiles; open a private Playwright profile and sign in once")
    ap.add_argument("--live-profile", action="store_true",
                    help="Use your real Chrome profile in place (keeps you signed in; Chrome must be closed)")
    ap.add_argument("--channel", default="chrome", choices=["chrome", "msedge", "chromium"],
                    help="Browser to drive (default chrome; 'chromium' needs: playwright install chromium)")
    ap.add_argument("--profile-dir", help="Chrome profile folder name, e.g. 'Profile 1' (skips name lookup)")
    ap.add_argument("--user-data-dir", help="Use this user-data-dir as-is instead of copying a profile")
    ap.add_argument("--out", default="teams_export_out", help="Output folder")
    ap.add_argument("--refresh-profile", action="store_true", help="Re-copy the Chrome profile")
    ap.add_argument("--manual", type=int, default=0, metavar="SEC",
                    help="Also record SEC seconds of manual browsing before exporting")
    ap.add_argument("--no-members", action="store_true", help="Skip team member lists")
    ap.add_argument("--our-side", default="",
                    help='Comma-separated names of OUR people, e.g. "Kunti Rathi, Sachin Rathi" '
                         '(their messages -> type=reply; everyone else -> response)')
    ap.add_argument("--from-date", default="", metavar="YYYY-MM-DD",
                    help="Only messages on/after this date (UTC, inclusive), e.g. 2026-09-01")
    ap.add_argument("--to-date", default="", metavar="YYYY-MM-DD",
                    help="Only messages before this date (UTC, exclusive), e.g. 2026-10-01")
    ap.add_argument("--no-type", action="store_true",
                    help="Leave the reply/response 'type' column out of the CSV entirely")
    ap.add_argument("--full-csv", action="store_true",
                    help="Also write teams_export_full.csv with every record type and column")
    ap.add_argument("--include-html", action="store_true", help="Also write raw message HTML to the CSV")
    ap.add_argument("--max-conversations", type=int, default=0, help="Limit conversations (for testing)")
    ap.add_argument("--parse-only", action="store_true", help="Only rebuild the CSV from saved raw data")
    ap.add_argument("--list-profiles", action="store_true", help="Show Chrome profiles and exit")
    args = ap.parse_args()

    if args.list_profiles:
        for f, i in list_profiles(chrome_user_data_dir()).items():
            print(f"{f:<12} name={i.get('name')!r} gaia_name={i.get('gaia_name')!r} account={i.get('user_name')!r}")
        return
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.parse_only:
        capture(args, out)
    parse(args, out)


if __name__ == "__main__":
    main()
