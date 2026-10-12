#!/usr/bin/env python3
"""
Export ALL folders of an Outlook on the web mailbox into ONE CSV (Playwright, signed-in browser session).

How it works (standalone: no other file needed)
  1. Opens https://outlook.office.com/mail/ in a Chrome profile (fresh / live / copied).
  2. Learns the session headers from the page's own requests to /owa/service.svc (kept in memory only).
  3. Lists every mail folder (FindFolder), pages through every folder (FindItem, newest first),
     then fetches the full item (recipients, body, attachment names/sizes) with GetItem.
  4. Writes raw JSON to <out>/raw/ and builds <out>/outlook_export.csv from it.

Usage
  python outlook_export.py --fresh-login --from-date 2026-09-01 --to-date 2026-10-01
  python outlook_export.py --live-profile --profile Vipul --our-domains kgsoffice.com
  python outlook_export.py --parse-only --from-date 2026-09-01 --to-date 2026-10-01
  python outlook_export.py --help

--from-date is inclusive, --to-date exclusive (UTC). Only export mail you are authorised to export.
"""
from __future__ import annotations

import argparse
import copy
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
from urllib.parse import parse_qsl, quote, unquote, urlencode, urlparse, urlunparse


OUTLOOK_URL = "https://outlook.office.com/mail/"
SERVICE_RE = re.compile(r"/owa/service\.svc", re.I)
SKIP_HEADERS = {"host", "content-length", "cookie", "accept-encoding", "connection"}
KEEP_ACTIONS = ("FindItem", "GetItem", "FindFolder", "GetFolder", "FindConversation", "GetConversationItems")
NON_MAIL_CLASSES = ("IPF.Appointment", "IPF.Contact", "IPF.Task", "IPF.StickyNote", "IPF.Journal",
                    "IPF.Configuration", "IPF.Note.Microsoft.Conversation")
HDR = {"__type": "JsonRequestHeaders:#Exchange", "RequestServerVersion": "Exchange2013",
       "TimeZoneContext": {"__type": "TimeZoneContext:#Exchange",
                           "TimeZoneDefinition": {"__type": "TimeZoneDefinitionType:#Exchange", "Id": "UTC"}}}

COLUMNS = ["folder", "date_received", "date_sent", "from_name", "from_email", "to", "cc", "bcc",
           "subject", "body_text", "body_complete", "has_attachments", "attachment_count", "attachments",
           "importance", "is_read", "categories", "conversation_id", "internet_message_id", "item_id",
           "size", "type"]


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


# --------------------------------------------------------------------------- generic helpers
def walk(o):
    """Yield every dict nested anywhere inside o."""
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def gid(d, key):
    v = d.get(key)
    return v.get("Id", "") if isinstance(v, dict) else (v or "")


def addr(m) -> tuple[str, str]:
    if isinstance(m, dict) and isinstance(m.get("Mailbox"), dict):
        m = m["Mailbox"]
    if not isinstance(m, dict):
        return "", ""
    return m.get("Name") or "", m.get("EmailAddress") or ""


def fmt_people(lst) -> str:
    out = []
    for p in lst or []:
        n, e = addr(p)
        out.append(f"{n} <{e}>" if n and e else (e or n))
    return "; ".join(x for x in out if x)


# --------------------------------------------------------------------------- session
class State:
    url = None            # captured service.svc URL (used as a template)
    headers = None        # in-memory only, never written to disk
    header_style = False  # True: JSON goes in the x-owa-urlpostdata header (empty body)
    header_ts = 0.0
    get_template = None   # a real GetItem request body captured from the page (fallback)


def pump(page, ms):
    page.wait_for_timeout(ms)  # keeps Playwright event handlers running


def build_request(st: State, action: str, body: dict):
    u = urlparse(st.url)
    q = [(k, v) for k, v in parse_qsl(u.query, keep_blank_values=True) if k.lower() != "action"]
    q.insert(0, ("action", action))
    url = urlunparse(u._replace(query=urlencode(q)))
    h = dict(st.headers)
    for k in list(h):
        if k.lower() == "action":
            del h[k]
    h["action"] = action
    if "x-owa-actionname" in {k.lower() for k in h}:
        h = {k: v for k, v in h.items() if k.lower() != "x-owa-actionname"}
        h["x-owa-actionname"] = action
    payload = json.dumps(body, separators=(",", ":"))
    if st.header_style:
        h = {k: v for k, v in h.items() if k.lower() != "x-owa-urlpostdata"}
        h["x-owa-urlpostdata"] = quote(payload, safe="")
        return url, h, None
    h.setdefault("content-type", "application/json; charset=utf-8")
    return url, h, payload


def call(ctx, page, st: State, action: str, body: dict, retries: int = 5):
    """POST to service.svc through the signed-in session. Returns (status, json_or_None, text_snippet)."""
    snippet = ""
    for attempt in range(retries):
        url, h, data = build_request(st, action, body)
        try:
            r = ctx.request.post(url, headers=h, data=data, timeout=90000)
        except Exception as e:
            snippet = str(e)
            pump(page, 3000)
            continue
        if r.status == 200:
            try:
                return 200, r.json(), ""
            except Exception:
                return 200, None, "non-JSON response"
        snippet = (r.text() or "")[:300]
        if r.status == 429 or "throttl" in snippet.lower():
            wait = int(r.headers.get("retry-after", "10")) + 1
            print(f"    throttled; waiting {wait}s")
            pump(page, wait * 1000)
        elif r.status in (401, 403, 440):
            print(f"    auth {r.status} on {action}; refreshing session (attempt {attempt + 1})")
            before = st.header_ts
            page.reload()
            for _ in range(60):
                if st.header_ts != before:
                    break
                pump(page, 1000)
            if attempt >= 1:  # still refused after a fresh token: this item/folder is simply not allowed
                return r.status, None, snippet
        elif r.status >= 500:
            pump(page, 2000 * (attempt + 1))
        else:
            return r.status, None, snippet
    return 0, None, snippet


def response_items(data):
    """EWS-JSON: Body.ResponseMessages.Items[] -> list of response-message dicts."""
    try:
        return data["Body"]["ResponseMessages"]["Items"]
    except Exception:
        return [d for d in walk(data) if "ResponseClass" in d]


# --------------------------------------------------------------------------- request bodies
def folder_body():
    return {"__type": "FindFolderJsonRequest:#Exchange", "Header": HDR,
            "Body": {"__type": "FindFolderRequest:#Exchange",
                     "FolderShape": {"__type": "FolderResponseShape:#Exchange", "BaseShape": "Default"},
                     "ParentFolderIds": [{"__type": "DistinguishedFolderId:#Exchange", "Id": "msgfolderroot"}],
                     "Traversal": "Deep",
                     "Paging": {"__type": "IndexedPageView:#Exchange", "BasePoint": "Beginning",
                                "Offset": 0, "MaxEntriesReturned": 1000}}}


def list_body(folder_id: str, offset: int, size: int = 100):
    return {"__type": "FindItemJsonRequest:#Exchange", "Header": HDR,
            "Body": {"__type": "FindItemRequest:#Exchange",
                     "ItemShape": {"__type": "ItemResponseShape:#Exchange", "BaseShape": "IdOnly"},
                     "ParentFolderIds": [{"__type": "FolderId:#Exchange", "Id": folder_id}],
                     "Traversal": "Shallow",
                     "Paging": {"__type": "IndexedPageView:#Exchange", "BasePoint": "Beginning",
                                "Offset": offset, "MaxEntriesReturned": size},
                     "ViewFilter": "All", "IsWarmUpSearch": False, "FocusedViewFilter": -1, "Grouping": None,
                     "ShapeName": "MailListItem",
                     "SortOrder": [{"__type": "SortResults:#Exchange", "Order": "Descending",
                                    "Path": {"__type": "PropertyUri:#Exchange", "FieldURI": "DateTimeReceived"}}]}}


def item_bodies(ids: list[str], variant: int, st: State):
    ids_json = [{"__type": "ItemId:#Exchange", "Id": i} for i in ids]
    if variant == 1 and st.get_template:  # replay the page's own GetItem request with our ids
        b = copy.deepcopy(st.get_template)
        try:
            b["Body"]["ItemIds"] = ids_json
            shape = b["Body"].get("ItemShape") or {}
            if "MaximumRecipientsToReturn" in shape:
                shape["MaximumRecipientsToReturn"] = 500
            return b
        except Exception:
            return None
    if variant == 0:
        return {"__type": "GetItemJsonRequest:#Exchange", "Header": HDR,
                "Body": {"__type": "GetItemRequest:#Exchange",
                         "ItemShape": {"__type": "ItemResponseShape:#Exchange", "BaseShape": "AllProperties",
                                       "BodyType": "Text", "MaximumRecipientsToReturn": 500},
                         "ItemIds": ids_json}}
    return None


# --------------------------------------------------------------------------- profile
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


# --------------------------------------------------------------------------- capture
def capture(args, out: Path) -> None:
    from playwright.sync_api import sync_playwright

    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw = open(raw_dir / "capture.jsonl", "a", encoding="utf-8")
    fetched_path = raw_dir / "fetched.jsonl"
    prog_path = out / "progress.json"
    progress = json.loads(prog_path.read_text()) if prog_path.exists() else {"done": []}
    date_from, date_to = date_bounds(args)
    key = f"{date_from or ''}|{date_to or ''}"
    if progress.get("range", "|") not in ("|", key):
        progress["done"] = []
    progress["range"] = key
    if date_from or date_to:
        print(f"[range] {date_from or 'beginning'} (incl.) -> {date_to or 'now'} (excl.), UTC")

    have_bodies: set[str] = set()   # items already fetched in an earlier (interrupted) run
    if fetched_path.exists():
        with open(fetched_path, encoding="utf-8-sig") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("kind") == "items":
                    for d in walk(rec["data"]):
                        if "ItemId" in d and "Body" in d:
                            have_bodies.add(gid(d, "ItemId"))
    fetched = open(fetched_path, "a", encoding="utf-8")

    work, folder = resolve_profile(args, out)
    st = State()

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(work), channel=(None if args.channel == "chromium" else args.channel),
            headless=False, no_viewport=True, args=[f"--profile-directory={folder}"],
            ignore_default_args=["--enable-automation"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        def action_of(url):
            return dict(parse_qsl(urlparse(url).query)).get("action", "")

        def on_request(req):
            if req.method != "POST" or not SERVICE_RE.search(req.url):
                return
            try:
                h = req.all_headers()
            except Exception:
                h = req.headers
            low = {k.lower(): v for k, v in h.items()}
            if "x-owa-canary" not in low and "authorization" not in low:
                return
            st.url = req.url
            st.headers = {k: v for k, v in h.items() if k.lower() not in SKIP_HEADERS and not k.startswith(":")}
            st.header_style = "x-owa-urlpostdata" in low
            st.header_ts = time.time()
            if action_of(req.url) == "GetItem":
                try:
                    body = json.loads(unquote(low["x-owa-urlpostdata"])) if st.header_style else json.loads(req.post_data)
                    st.get_template = body
                except Exception:
                    pass

        def on_response(resp):
            url = resp.url
            if resp.status != 200 or not SERVICE_RE.search(url) or action_of(url) not in KEEP_ACTIONS:
                return
            try:
                data = resp.json()
            except Exception:
                return
            raw.write(json.dumps({"src": "passive", "action": action_of(url), "data": data}, ensure_ascii=False) + "\n")
            raw.flush()

        ctx.on("request", on_request)
        ctx.on("response", on_response)

        print(f"[outlook] opening {args.url}  (sign in in the window if asked; waiting up to 10 min)")
        page.goto(args.url, wait_until="domcontentloaded")
        waited = 0
        while not st.headers and waited < 600:
            pump(page, 2000)
            waited += 2
            if waited % 30 == 0:
                print(f"[outlook] still waiting for Outlook to load / sign-in ({waited}s)...")
        if not st.headers:
            sys.exit("Outlook never made an authenticated request. Sign in, then re-run.")
        print("[outlook] session ready")
        pump(page, 3000)
        try:  # opening one mail makes the page send a real GetItem we can use as a template
            page.locator('div[role="option"]').first.click(timeout=4000)
            pump(page, 4000)
        except Exception:
            pass
        if args.manual:
            print(f"[manual] recording page traffic for {args.manual}s - click folders / emails to help")
            pump(page, args.manual * 1000)

        # ---- 1. all folders
        status, data, snip = call(ctx, page, st, "FindFolder", folder_body())
        if not data:
            sys.exit(f"[folders] FindFolder failed (HTTP {status}): {snip}\n"
                     "Send me this message plus raw/capture.jsonl and I will adjust the request.")
        fetched.write(json.dumps({"src": "fetch", "kind": "folders", "data": data}, ensure_ascii=False) + "\n")
        folders = {}
        for d in walk(data):
            if "FolderId" in d and "DisplayName" in d:
                cls = d.get("FolderClass") or ""
                if cls.startswith(NON_MAIL_CLASSES):
                    continue
                folders[gid(d, "FolderId")] = {"name": d["DisplayName"], "parent": gid(d, "ParentFolderId"),
                                               "total": d.get("TotalCount", "?")}
        if args.folders:
            wanted = {x.strip().lower() for x in args.folders.split(",")}
            folders = {k: v for k, v in folders.items() if v["name"].lower() in wanted}
        print(f"[folders] {len(folders)} mail folders: "
              + ", ".join(f"{v['name']}({v['total']})" for v in list(folders.values())[:15]))
        fetched.flush()

        # ---- 2. each folder: list (newest first) then fetch bodies
        variant = None  # which GetItem request style works, found on first use
        for n, (fid, info) in enumerate(folders.items(), 1):
            if fid in progress["done"]:
                continue
            ids, offset, listed = [], 0, 0
            while True:
                status, data, snip = call(ctx, page, st, "FindItem", list_body(fid, offset))
                if not data:
                    print(f"    [{info['name']}] FindItem failed (HTTP {status}): {snip}")
                    break
                fetched.write(json.dumps({"src": "fetch", "kind": "list", "folder_id": fid, "data": data},
                                         ensure_ascii=False) + "\n")
                rows = [d for d in walk(data) if "ItemId" in d and ("Subject" in d or "From" in d or "DateTimeReceived" in d)]
                last_page = any(d.get("IncludesLastItemInRange") for d in walk(data) if "IncludesLastItemInRange" in d)
                times = []
                for d in rows:
                    t = to_utc(d.get("DateTimeReceived") or d.get("DateTimeSent") or "")
                    times.append(t)
                    if t and ((date_from and t < date_from) or (date_to and t >= date_to)):
                        continue
                    ids.append(gid(d, "ItemId"))
                listed += len(rows)
                offset += len(rows)
                pump(page, 200)
                if not rows or last_page:
                    break
                times = [t for t in times if t]
                if date_from and times and min(times) < date_from and times[0] >= times[-1]:
                    break  # newest -> oldest: everything further is older than the range
                if args.max_items and listed >= args.max_items:
                    break
            ids = [i for i in dict.fromkeys(ids) if i and i not in have_bodies]
            if args.max_items:
                ids = ids[:args.max_items]
            got = 0
            if not args.no_bodies:
                for b in range(0, len(ids), 10):
                    batch = ids[b:b + 10]
                    order = [variant] if variant is not None else [0, 1]
                    for v in order:
                        body = item_bodies(batch, v, st)
                        if body is None:
                            continue
                        status, data, snip = call(ctx, page, st, "GetItem", body)
                        ok = data and any(("Body" in d and "ItemId" in d) for d in walk(data))
                        if ok:
                            variant = v
                            fetched.write(json.dumps({"src": "fetch", "kind": "items", "data": data},
                                                     ensure_ascii=False) + "\n")
                            got += len(batch)
                            have_bodies.update(batch)
                            break
                        print(f"    GetItem variant {v} failed (HTTP {status}): {snip[:160]}")
                    else:
                        continue
                    pump(page, 200)
            fetched.flush()
            progress["done"].append(fid)
            prog_path.write_text(json.dumps(progress))
            print(f"[fetch] {n}/{len(folders)}  {info['name'][:30]:<30} listed {listed:>6}, in range {len(ids):>6}, full bodies {got:>6}")
        ctx.close()
    raw.close()
    fetched.close()
    print("[fetch] done")


# --------------------------------------------------------------------------- parse
def parse(args, out: Path) -> Path:
    date_from, date_to = date_bounds(args)
    folders: dict[str, dict] = {}
    items: dict[str, dict] = {}

    for name in ("capture.jsonl", "fetched.jsonl"):
        path = out / "raw" / name
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                data = rec.get("data")
                for d in walk(data):
                    if "FolderId" in d and "DisplayName" in d and "ItemId" not in d:
                        folders[gid(d, "FolderId")] = {"name": d["DisplayName"], "parent": gid(d, "ParentFolderId")}
                for d in walk(data):
                    if "ItemId" not in d or not isinstance(d.get("ItemId"), dict):
                        continue
                    if not ("Subject" in d or "From" in d or "DateTimeReceived" in d or "Body" in d):
                        continue
                    iid = gid(d, "ItemId")
                    cur = items.setdefault(iid, {})
                    if rec.get("folder_id"):
                        cur.setdefault("_folder", rec["folder_id"])
                    for k, v in d.items():       # later / fuller records fill in missing fields
                        if v not in (None, "", [], {}):
                            cur[k] = v

    def path_of(fid: str) -> str:
        parts, seen = [], set()
        while fid in folders and fid not in seen:
            seen.add(fid)
            parts.append(folders[fid]["name"])
            fid = folders[fid]["parent"]
        parts = [p for p in parts if p.lower() not in ("top of information store", "msgfolderroot")]
        return "/".join(reversed(parts))

    ours = {x.strip().lower().lstrip("@") for x in (args.our_domains or "").split(",") if x.strip()}
    rows = []
    for iid, d in items.items():
        received = to_utc(d.get("DateTimeReceived") or d.get("DateTimeSent") or "")
        if (date_from and received < date_from) or (date_to and received >= date_to):
            continue
        fname, femail = addr(d.get("From") or d.get("Sender"))
        body = d.get("Body") or d.get("NormalizedBody") or d.get("UniqueBody") or {}
        text = body.get("Value", "") if isinstance(body, dict) else str(body)
        if isinstance(body, dict) and str(body.get("BodyType", "")).upper() == "HTML":
            text = html_to_text(text)
        complete = "yes" if text else "no"
        if not text:
            text = d.get("Preview", "")
            complete = "preview only" if text else "no"
        atts = [a for a in (d.get("Attachments") or []) if isinstance(a, dict)]
        att_txt = "; ".join(f"{a.get('Name', '')} ({a.get('Size', '')} bytes)" for a in atts)
        parent = gid(d, "ParentFolderId") or d.get("_folder", "")
        row = {
            "folder": path_of(parent) or path_of(d.get("_folder", "")),
            "date_received": received, "date_sent": to_utc(d.get("DateTimeSent", "")),
            "from_name": fname, "from_email": femail,
            "to": fmt_people(d.get("ToRecipients")) or d.get("DisplayTo", ""),
            "cc": fmt_people(d.get("CcRecipients")) or d.get("DisplayCc", ""),
            "bcc": fmt_people(d.get("BccRecipients")),
            "subject": d.get("Subject", ""), "body_text": text, "body_complete": complete,
            "has_attachments": d.get("HasAttachments", ""),
            "attachment_count": len(atts) if atts else (1 if d.get("HasAttachments") else 0),
            "attachments": att_txt, "importance": d.get("Importance", ""), "is_read": d.get("IsRead", ""),
            "categories": "; ".join(d.get("Categories") or []), "conversation_id": gid(d, "ConversationId"),
            "internet_message_id": d.get("InternetMessageId", ""), "item_id": iid, "size": d.get("Size", ""),
            "type": "",
        }
        if ours:
            row["type"] = "reply" if femail.split("@")[-1].lower() in ours else "response"
        rows.append(row)
    rows.sort(key=lambda r: (r["folder"], r["date_received"]))

    cols = [c for c in COLUMNS if not (c == "type" and not ours)]
    path = out / "outlook_export.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    full = sum(1 for r in rows if r["body_complete"] == "yes")
    print(f"[csv] wrote {path}  {len(rows)} emails ({full} with full body, "
          f"{len(rows) - full} list/preview only)")
    return path


# --------------------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Export Outlook on the web (all folders) to one CSV.")
    ap.add_argument("--profile", default="Vipul", help="Chrome profile name / folder / e-mail (default: Vipul)")
    ap.add_argument("--fresh-login", action="store_true", help="Private Playwright profile; sign in once")
    ap.add_argument("--live-profile", action="store_true", help="Use the real Chrome profile in place (Chrome closed)")
    ap.add_argument("--profile-dir", help="Chrome profile folder name, e.g. 'Profile 1'")
    ap.add_argument("--user-data-dir", help="Use this user-data-dir as-is")
    ap.add_argument("--channel", default="chrome", choices=["chrome", "msedge", "chromium"])
    ap.add_argument("--refresh-profile", action="store_true", help="Re-copy the Chrome profile")
    ap.add_argument("--url", default=OUTLOOK_URL, help=f"Outlook web URL (default {OUTLOOK_URL})")
    ap.add_argument("--out", default="outlook_export_out", help="Output folder")
    ap.add_argument("--from-date", default="", metavar="YYYY-MM-DD", help="On/after this date (UTC, inclusive)")
    ap.add_argument("--to-date", default="", metavar="YYYY-MM-DD", help="Before this date (UTC, exclusive)")
    ap.add_argument("--our-domains", default="", help='Add a type column: sender domain in this list -> "reply", '
                                                       'else "response". e.g. "kgsoffice.com"')
    ap.add_argument("--folders", default="", help='Only these folders, e.g. "Inbox,Sent Items"')
    ap.add_argument("--no-bodies", action="store_true", help="Skip full-item fetch (list fields + preview only; fast)")
    ap.add_argument("--max-items", type=int, default=0, help="Limit items per folder (for testing)")
    ap.add_argument("--manual", type=int, default=0, metavar="SEC", help="Also record SEC seconds of manual browsing")
    ap.add_argument("--parse-only", action="store_true", help="Only rebuild the CSV from saved raw data")
    args = ap.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.parse_only:
        capture(args, out)
    parse(args, out)


if __name__ == "__main__":
    main()
