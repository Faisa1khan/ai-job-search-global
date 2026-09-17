#!/usr/bin/env python3
"""Read-only Gmail helper for the job-search sync.

Refreshes the OAuth access token automatically and queries the Gmail API.
Reads the repo's .env (gitignored) for GMAIL_CLIENT_SECRET / GMAIL_TOKEN overrides.
Defaults: token at gmail_sync/token.json, client at gmail_sync/client_secret.json,
falling back to ~/Personal/client_secret_*.json.

Usage:
  python3 tools/gmail_sync.py profile
  python3 tools/gmail_sync.py labels
  python3 tools/gmail_sync.py search '<gmail query>'
  python3 tools/gmail_sync.py thread <thread_id>
"""
import glob, json, os, sys, urllib.parse, urllib.request, urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env():
    p = os.path.join(REPO, ".env")
    if not os.path.exists(p):
        return
    with open(p) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()

TOKEN_PATH = os.environ.get("GMAIL_TOKEN", os.path.join(REPO, "gmail_sync", "token.json"))


def _load(p):
    with open(p) as f:
        return json.load(f)


def _client_secret():
    path = os.environ.get("GMAIL_CLIENT_SECRET")
    if not path:
        path = os.path.join(REPO, "gmail_sync", "client_secret.json")
    if not os.path.exists(path):
        matches = glob.glob(os.path.expanduser("~/Personal/client_secret_*.json"))
        if matches:
            path = matches[0]
    if not os.path.exists(path):
        raise SystemExit(
            "no Google client_secret found — set GMAIL_CLIENT_SECRET or place it "
            "at gmail_sync/client_secret.json"
        )
    return _load(path)["installed"]


def _refresh(tok):
    cs = _client_secret()
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
        "client_id": cs["client_id"],
        "client_secret": cs["client_secret"],
    }).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    resp = json.load(urllib.request.urlopen(req))
    tok.update(resp)
    with open(TOKEN_PATH, "w") as f:
        json.dump(tok, f, indent=2)
        f.write("\n")
    return tok


def _call(path, tok, method="GET", body=None):
    def req_once():
        r = urllib.request.Request(
            f"https://gmail.googleapis.com/gmail/v1/users/me/{path}",
            headers={"Authorization": f"Bearer {tok['access_token']}"},
            method=method,
        )
        if body is not None:
            r.data = json.dumps(body).encode()
            r.add_header("Content-Type", "application/json")
        return r

    try:
        return json.load(urllib.request.urlopen(req_once()))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            tok = _refresh(tok)
            return json.load(urllib.request.urlopen(req_once()))
        raise


def profile():
    return _call("profile", _load(TOKEN_PATH))


def list_labels():
    return _call("labels", _load(TOKEN_PATH))


def search_threads(query):
    tok = _load(TOKEN_PATH)
    qs = urllib.parse.urlencode({"q": query, "maxResults": 50})
    return _call(f"threads?{qs}", tok)


def get_thread(thread_id):
    return _call(f"threads/{thread_id}", _load(TOKEN_PATH))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "profile"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    out = {
        "profile": profile,
        "labels": list_labels,
        "search": lambda: search_threads(arg or "newer_than:7d"),
        "thread": lambda: get_thread(arg),
    }.get(cmd, lambda: None)()
    if out is None:
        print("usage: gmail_sync.py profile|labels|search '<query>'|thread <id>")
        sys.exit(1)
    print(json.dumps(out, indent=2))
