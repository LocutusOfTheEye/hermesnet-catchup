#!/usr/bin/env python3
"""HermesNet catch-up: star the repos on a community list and follow their builders, from your own
GitHub account. Dry-run by default; pass --apply to act. Standard library only.

List sources (pick one; default is the HermesNet site):
  --source URL|PATH   HermesNet builders.json, a folder of builders/*.yaml, or any text/Markdown
                      with github.com/OWNER/REPO links ('-' = stdin)
  --hermesforce [URL] members from a hermesforce site (default https://hermesforce.gottz.de/);
                      its repo list needs sign-in, so pair it with --source for the repos
Only repos owned by a listed builder are used, so a list cannot smuggle in other repos.

Token: GITHUB_TOKEN or `gh auth token`; kept in memory, never printed.
State: ~/.hermes/state/hermesnet-catchup/ (log.jsonl, seen.json). Default --only new skips repos
already handled in an earlier --apply run.
"""
import argparse, datetime, json, os, pathlib, random, re, subprocess, sys, time, urllib.error, urllib.request

API = "https://api.github.com"
SITE = "https://hermesnet.xyz/builders.json"
BUNDLED = str(pathlib.Path(__file__).resolve().parent.parent / "list.md")
# Tried in order when no --source is given: HERMESNET_LIST (path or URL), the live site, then the copy
# of the list that ships with this skill (may be a little out of date).
DEFAULT_SOURCES = [p for p in (os.environ.get("HERMESNET_LIST"), SITE, BUNDLED) if p]
HERMESFORCE = "https://hermesforce.gottz.de/"
STATE = pathlib.Path.home() / ".hermes" / "state" / "hermesnet-catchup"
OWNER_RE = r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})"
REPO_RE = re.compile(rf"github\.com/({OWNER_RE})/([A-Za-z0-9._-]+)")
UA = {"User-Agent": "hermesnet-catchup"}


def token():
    t = os.environ.get("GITHUB_TOKEN", "").strip()
    if t:
        return t
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        sys.exit("Not signed in to GitHub yet. Install the GitHub CLI (https://cli.github.com) and run:\n"
                 "  gh auth login\nthen try again. (Advanced: set GITHUB_TOKEN instead.)")


def call(tok, method, path, retries=3):
    for attempt in range(retries):
        req = urllib.request.Request(API + path, method=method, data=b"" if method == "PUT" else None,
                                     headers={**UA, "Authorization": "Bearer " + tok,
                                              "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
                return r.status, dict(r.headers), (json.loads(body) if body else None)
        except urllib.error.HTTPError as e:
            h = dict(e.headers)
            limited = e.code in (403, 429) and (h.get("Retry-After") or h.get("X-RateLimit-Remaining") == "0")
            if limited and attempt < retries - 1:
                wait = min(int(h.get("Retry-After") or 60), 300)
                print(f"  rate limited, waiting {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            return e.code, h, None
        except urllib.error.URLError as e:
            return 0, {}, str(e)
    return 0, {}, None


def fetch(src):
    if src == "-":
        return sys.stdin.read()
    if src.startswith("http"):
        return urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=30).read().decode("utf-8", "replace")
    p = pathlib.Path(src).expanduser()
    if p.is_dir():
        return "\n".join(f.read_text() for f in sorted(p.glob("*.yaml")))
    return p.read_text(encoding="utf-8", errors="replace")


def parse(text):
    """Return (builders, repos) from builders.json, builder YAML, or any text with GitHub links."""
    builders, repos = [], []
    try:
        data = json.loads(text)
        for b in data.get("builders", []) if isinstance(data, dict) else data:
            builders.append(b["github"])
            repos += [tuple(p["repo"].split("/", 1)) for p in b.get("projects", [])]
        return builders, repos
    except (ValueError, KeyError, TypeError, AttributeError):
        pass
    builders += re.findall(rf"^github:\s*['\"]?({OWNER_RE})", text, re.M)
    repos += [tuple(x.split("/", 1)) for x in re.findall(rf"^\s*repo:\s*['\"]?({OWNER_RE}/[A-Za-z0-9._-]+)", text, re.M)]
    repos += REPO_RE.findall(text)
    builders += [o for o, _ in repos]
    return builders, repos


def hermesforce_members(url):
    html = fetch(url)
    found = re.findall(rf'class="login"\s+href="https://github\.com/({OWNER_RE})"', html)
    if not found:
        sys.exit("Could not find any members on " + url)
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", help="builders.json URL/path, builders/ folder, or text with GitHub links")
    ap.add_argument("--hermesforce", nargs="?", const=HERMESFORCE, help="read members from a hermesforce site")
    ap.add_argument("--apply", action="store_true", help="actually star/follow (default: dry-run)")
    ap.add_argument("--only", choices=["new", "all"], default="new")
    ap.add_argument("--no-follow", action="store_true")
    ap.add_argument("--no-star", action="store_true")
    ap.add_argument("--review", action="store_true", help="go through each project one at a time and choose (needs a terminal)")
    ap.add_argument("--pick", help="star only these repos: comma-separated OWNER/REPO list (from the preview)")
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between actions (minimum 2; a little random time is added)")
    a = ap.parse_args()
    a.delay = max(a.delay, 2.0)
    if a.review and not sys.stdin.isatty():
        sys.exit("--review needs a terminal you can type in. From an agent, show the preview and use --pick instead.")

    tok = token()
    st, hdr, me = call(tok, "GET", "/user")
    if st != 200:
        sys.exit(f"GitHub did not accept your sign-in (HTTP {st}). Run `gh auth login` again, then retry.")
    mine = me["login"]
    print(f"Acting as: {mine}   mode: {'APPLY' if a.apply else 'DRY-RUN'}")
    scopes = hdr.get("X-OAuth-Scopes")
    if scopes is not None:
        s = {x.strip() for x in scopes.split(",")}
        if not a.no_star and not ({"repo", "public_repo"} & s):
            print("  ! token lacks repo/public_repo scope: starring will fail")
        if not a.no_follow and not ({"user", "user:follow"} & s):
            print("  ! token lacks user:follow scope: following will fail. Fix: gh auth refresh -h github.com -s user:follow")
            if a.apply:
                a.no_follow = True
                print("    (skipping follows this run)")

    builders, repos = [], []
    if a.hermesforce:
        builders = hermesforce_members(a.hermesforce)
    if a.source or not a.hermesforce:
        src, err = None, []
        for cand in [a.source] if a.source else DEFAULT_SOURCES:
            try:
                b, repos = parse(fetch(cand))
                if not repos:
                    raise ValueError("no GitHub repos found in it")
                src = cand; break
            except Exception as e:
                err.append(f"{cand}: {e}")
        if not src:
            sys.exit("No list source reachable:\n  " + "\n  ".join(err) + "\nPass --source with a file or URL.")
        builders = builders or b
        print(f"List source: {src}" + ("  (copy bundled with the skill; may be slightly out of date)" if src == BUNDLED else ""))
    elif not a.no_star:
        sys.exit("The hermesforce repo list needs sign-in. Add --source with the repo list (or --no-star).")

    seen_b, members = set(), []
    for b in builders:
        if b.lower() not in seen_b:
            seen_b.add(b.lower()); members.append(b)
    keep, seen_r = [], set()
    for o, r in repos:
        r = re.sub(r"\.git$", "", r).rstrip(".")
        key = (o.lower(), r.lower())
        if o.lower() in seen_b and r and key not in seen_r:
            seen_r.add(key); keep.append((o, r))
    others = [m for m in members if m.lower() != mine.lower()]
    stars = [(o, r) for o, r in keep if o.lower() != mine.lower()]

    STATE.mkdir(parents=True, exist_ok=True)
    seen_file, log_file = STATE / "seen.json", STATE / "log.jsonl"
    seen = set(json.loads(seen_file.read_text())) if seen_file.exists() else set()
    if a.only == "new":
        stars = [x for x in stars if f"{x[0]}/{x[1]}".lower() not in seen]
    print(f"Builders: {len(members)} ({len(members) - len(others)} is you). Repos: {len(keep)} listed, {len(stars)} to check")

    todo_star, todo_follow, already, bad, orgs, forks = [], [], 0, [], [], []
    if not a.no_star:
        for o, r in stars:
            st, _, _ = call(tok, "GET", f"/user/starred/{o}/{r}")
            if st == 204: already += 1
            elif st == 404:
                _, _, info = call(tok, "GET", f"/repos/{o}/{r}")
                info = info if isinstance(info, dict) else {}
                if info.get("fork"):
                    # A fork is not the project. Starring the copy supports nobody, and the work
                    # that matters lands upstream, so keep it off the star list and report it.
                    up = info.get("parent") or info.get("source") or {}
                    forks.append((o, r, up.get("full_name") or "another repository",
                                  (info.get("description") or "").strip()))
                else:
                    todo_star.append((o, r, (info.get("description") or "").strip()))
            else: bad.append((f"{o}/{r}", st))
            time.sleep(0.1)
    if not a.no_follow:
        for u in others:
            st, _, info = call(tok, "GET", f"/users/{u}")
            if st != 200: bad.append((u, st)); continue
            if info.get("type") != "User": orgs.append(u); continue
            st, _, _ = call(tok, "GET", f"/user/following/{u}")
            if st == 404: todo_follow.append(u)
            elif st != 204: bad.append((u, st))
    print(f"\nStars:   {len(todo_star)} to add, {already} already starred")
    print(f"Follows: {len(todo_follow)} to add")
    if forks:
        print(f"Forks:   {len(forks)} skipped (listed below)")
    if orgs: print("Organizations (cannot be followed):", ", ".join(orgs))
    for t, s in bad: print(f"  check failed: {t} (HTTP {s})")
    for o, r, desc in todo_star:
        print(f"  star   {o}/{r}\n         {desc or '(no description)'}\n         https://github.com/{o}/{r}")
    for u in todo_follow: print(f"  follow {u}")
    if forks:
        print(f"\nSkipped {len(forks)} fork{'s' if len(forks) != 1 else ''} of another project:"
              " star the upstream instead")
        for o, r, upstream, desc in forks:
            print(f"  skip   {o}/{r}  (fork of {upstream})\n         https://github.com/{o}/{r}")
    if a.pick:
        want = {x.strip().lower() for x in a.pick.split(",") if x.strip()}
        asked_for_forks = [f"{o}/{r}" for o, r, _u, _d in forks if f"{o}/{r}".lower() in want]
        todo_star = [t for t in todo_star if f"{t[0]}/{t[1]}".lower() in want]
        print(f"\nPicked {len(todo_star)} of the projects above.")
        if asked_for_forks:
            print("Not starred, fork of another project: " + ", ".join(asked_for_forks))
    if a.apply and a.review:
        chosen = []
        print("\nFor each project: y = star, n = not this one, o = open it in your browser first, q = stop here")
        for i, (o, r, desc) in enumerate(todo_star, 1):
            print(f"\n[{i}/{len(todo_star)}] {o}/{r}\n  {desc or '(no description)'}\n  https://github.com/{o}/{r}")
            while True:
                ans = input("  star it? [y/n/o/q] ").strip().lower()
                if ans == "o":
                    import webbrowser; webbrowser.open(f"https://github.com/{o}/{r}"); continue
                if ans in ("y", "n", "q"): break
            if ans == "q": break
            if ans == "y": chosen.append((o, r, desc))
        todo_star = chosen
    if not a.apply:
        print("\nDry-run only. Re-run with --apply after the user approves this list.")
        return

    fails = set()
    with log_file.open("a") as log:
        for kind, items in (("follow", todo_follow), ("star", [f"{o}/{r}" for o, r, _ in todo_star])):
            for it in items:
                st, _, _ = call(tok, "PUT", f"/user/following/{it}" if kind == "follow" else f"/user/starred/{it}")
                ok = st == 204
                if not ok: fails.add(it)
                log.write(json.dumps({"time_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                      "kind": kind, "target": it, "status": st}) + "\n")
                log.flush()
                print(f"  {kind} {it}: {'ok' if ok else 'FAILED ' + str(st)}", flush=True)
                time.sleep(a.delay + random.uniform(0, a.delay))
    # Only what was actually acted on counts as handled, so skipped projects come back next time.
    handled = {f"{o}/{r}".lower() for o, r, _ in todo_star} - {f.lower() for f in fails}
    seen_file.write_text(json.dumps(sorted(seen | handled)))
    print(f"\nDone: {len(todo_star) + len(todo_follow) - len(fails)} ok, {len(fails)} failed. Log: {log_file}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
