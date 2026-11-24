---
name: hermesnet-catchup
description: "Keep starring and following the HermesNet community list from your own GitHub account: preview, then apply."
version: 1.4.0
author: HermesNet
license: MIT
metadata:
  hermes:
    tags: [github, community, stars, follows, hermesnet]
    category: community
    related_skills: [community-directory, github]
---

# HermesNet catch-up

Star the projects on the HermesNet community list and follow their builders, from the user's own
GitHub account. Built to be run every now and again: each run only looks at what was added since the
last one.

Use when the user says things like "star the new ones", "catch up on HermesNet", "who's new on HermesNet", "keep up with HermesNet",
"follow the new builders", or "did anyone new join the list?"

## First time: set it up for the user

Many users do not code. Do these checks yourself, explain each step in one plain sentence, and only ask
the user to do the parts that need them (installing an app, approving in the browser).

1. **Python.** Try `python3 --version`; on Windows try `python --version` or `py --version`. Use
   whichever works for every command below. If none work, help the user install Python 3 from
   https://www.python.org/downloads/ (Windows: tick "Add python.exe to PATH").
2. **GitHub CLI.** Check `gh --version`. If missing, install it:
   Windows `winget install --id GitHub.cli`, macOS `brew install gh`, Linux see https://cli.github.com.
   Tell the user to reopen the terminal afterwards if `gh` is still not found.
3. **Sign in.** Check `gh auth status`. If not signed in, run `gh auth login`, choose GitHub.com, HTTPS,
   and "Login with a web browser". The user copies the code shown and approves it in the browser.
4. **Permission to follow.** Run `gh auth refresh -h github.com -s user:follow` and have the user approve
   it in the browser the same way. Without it the skill still stars, but skips follows.

The script lives in this skill's `scripts/` folder. On Windows the skill folder is usually
`%USERPROFILE%\.hermes\skills\hermesnet-catchup`; on macOS and Linux `~/.hermes/skills/hermesnet-catchup`.

## The routine (every time)

1. **Preview.** Run the script with no flags. It changes nothing and lists what it would star and
   follow.
   ```bash
   python3 ~/.hermes/skills/hermesnet-catchup/scripts/catchup.py
   ```
2. **Show the user** the counts and names exactly as printed. If the list says 0 and 0, say the user is
   up to date and stop.
3. **Ask** "Star and follow these?" The user may drop any repo or builder. Stars mean "I like this".
4. **Apply** only after a yes, with the same flags plus `--apply`.
   ```bash
   python3 ~/.hermes/skills/hermesnet-catchup/scripts/catchup.py --apply
   ```
5. **Report** in plain words what the script printed: how many ok, how many failed and why, where the log is.
   Never guess numbers.

If the user dropped some items, use `--source` with a trimmed list, or run `--no-star` and
`--no-follow` passes separately.

## Rules

- **The user's own account only.** Never run it for, or with the token of, anyone else.
- **Preview first, every time.** `--apply` only after the user says yes to the printed list.
- **No schedule** unless the user explicitly asks for one. Even then, preview and ask before applying.
- **Voluntary stars.** Never present it as "star mine and I'll star yours" or run it to meet a quota.
  Keep it a personal tool; do not push the whole crew to run it on the same list at once.

## Options

| Flag | What it does |
|---|---|
| *(none)* | Preview new entries since the last applied run |
| `--apply` | Actually star and follow |
| `--only all` | Look at the whole list, not just new entries |
| `--no-star` / `--no-follow` | Only follow / only star |
| `--source X` | Use a different list: a `builders.json` URL or file, a folder of `builders/*.yaml`, or any text with `github.com/OWNER/REPO` links (`-` = stdin) |
| `--hermesforce [URL]` | Read members from a hermesforce site (repo list needs `--source` too) |
| `--delay N` | Seconds between actions (default 4, minimum 2) |

Where the list comes from when `--source` is not given, first that works:
1. `HERMESNET_LIST` environment variable, if set (a path or URL)
2. `https://hermesnet.xyz/builders.json` (the live site)
3. `list.md` in this skill's folder, a copy of the list that ships with the skill (may be slightly
   out of date; the script says so when it uses it)

## Built-in safety

- Only repos owned by a listed builder are used, so a list cannot slip in someone else's repo.
- Skips the user's own repos, organizations, and anything already starred or followed.
- Checks the token's permissions first. If `user:follow` is missing it skips follows and says how to
  fix it: `gh auth refresh -h github.com -s user:follow` (the user approves in the browser).
- Waits out GitHub rate limits; never prints the token.
- Logs every action to `~/.hermes/state/hermesnet-catchup/log.jsonl`; remembers handled repos in
  `seen.json` so the next run only shows new ones.
