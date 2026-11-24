# HermesNet catch-up

A Hermes Agent skill for keeping up with the HermesNet community list (hermesnet.xyz). When new builders
or projects join the list, tell your Hermes:

> catch up on HermesNet

It shows you what is new, you pick what you like, and only then does it star the projects and follow
the builders from your own GitHub account. Nothing happens without your yes.

## Install

Ask your Hermes to install it for you:

> install the skill from github.com/LocutusOfTheEye/hermesnet-catchup

Or do it yourself:

```bash
git clone https://github.com/LocutusOfTheEye/hermesnet-catchup ~/.hermes/skills/hermesnet-catchup
```

On Windows (PowerShell):

```powershell
git clone https://github.com/LocutusOfTheEye/hermesnet-catchup "$env:USERPROFILE\.hermes\skills\hermesnet-catchup"
```

The first time you use it, Hermes checks that Python and the GitHub CLI are installed and walks you
through signing in to GitHub in your browser.

## Good to know

- Preview first, every time. It only acts after you approve.
- Skips your own repos and anything you already starred or follow.
- Paced (4 seconds between actions) and logged.
- Reads the live list from hermesnet.xyz, with a copy of the list included as a backup.
- Stars are voluntary: star what you actually like.

## License

MIT
