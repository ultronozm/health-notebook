# Setup runbook for a person or coding agent

## 1. Establish the destination

Inspect available tools and existing SSH configuration without printing secrets.
Ask for missing essentials together: existing always-on machine or new Hetzner
server, timezone, glucose/weight units, and desired private backup. Reuse known
answers. If provisioning, follow [HETZNER.md](HETZNER.md) first.

This recipe uses Ubuntu 24.04, a dedicated non-root login called `notebook`, Git,
Python 3, and user systemd. We suggest at least 2 GB RAM for one Claude session;
actual usage varies. Claude needs outbound HTTPS. No public web listener is
needed for Remote Control. Keep the computer awake and connected.

Check the current [Claude installation guide](https://code.claude.com/docs/en/setup)
and [Remote Control requirements](https://code.claude.com/docs/en/remote-control)
before installing; account eligibility and flags can change. The resume flag used
here requires Claude Code 2.1.200 or newer. API-key authentication is not a
substitute for the Claude account login needed by Remote Control.

## 2. Prepare the computer

An administrator installs the small set of prerequisites:

```sh
sudo apt-get update
sudo apt-get install -y git python3 curl ca-certificates
sudo loginctl enable-linger notebook
```

For an existing machine, create a separate `notebook` account and install the
owner's SSH **public** key as described in HETZNER.md. Do not give the Claude
account passwordless sudo. Log in directly over SSH as that user; `sudo su` may
not establish the user systemd session correctly.

Copy this kit to `~/health-notebook-kit` on the target using Git or rsync. Before
publication, a local checkout can be transferred as follows (replace `HOST` with
the verified SSH alias/IP; do not paste placeholders literally):

```sh
rsync -av --exclude=.git --exclude=__pycache__ ./ notebook@HOST:health-notebook-kit/
ssh notebook@HOST
```

Subsequent commands run **on the target, as notebook**, unless labeled otherwise.
Install Claude Code using the current official installer. Download and inspect
it first if required by your environment:

```sh
curl -fsSL https://claude.ai/install.sh -o /tmp/health-notebook-claude-install.sh
bash /tmp/health-notebook-claude-install.sh
~/.local/bin/claude --version
python3 ~/health-notebook-kit/scripts/init-notebook.py
cd ~/health-notebook
```

The initializer refuses an existing destination and creates a separate Git repo
with no remote. It does not copy example entries. Fill in PROFILE.md with the
owner's preferences. Configure a **local** Git identity chosen by the owner:

```sh
git config user.name 'YOUR CHOSEN NAME'
git config user.email 'YOUR CHOSEN EMAIL'
git add .
git commit -m 'Initialize private health notebook'
```

The service uses `~/health-notebook`. A custom initialization path is supported
for experiments, but requires adapting both the launcher and service before use.

## 3. Complete interactive authentication and connect the phone

Use an interactive SSH terminal; the owner should perform login themselves:

```sh
cd ~/health-notebook
~/.local/bin/claude
```

Follow login (or `/login`) and accept workspace trust for this directory. Exit
Claude, then start the first Remote Control server:

```sh
~/.local/bin/claude remote-control --name health-notebook --spawn=same-dir --capacity 1 --permission-mode acceptEdits
```

Accept any first-run Remote Control confirmation. Open the displayed session URL
or QR code on the phone, signed into the same Claude account. The user can also
find the session in the app's Code section. Select this Remote Control session;
starting a hosted cloud coding task does not connect to this notebook.

Send: “Read AGENTS.md and PROFILE.md and tell me which preferences still need
setting.” Confirm a reply. This proves the actual mobile connection works.
Stop the foreground server with Ctrl-C before starting the service.

`acceptEdits` allows routine file edits; shell operations may still ask permission
on the phone. This is the default. Fully unattended operation is an explicit
option described in OPERATIONS.md, not a requirement for setup.

## 4. Keep it running

```sh
bash ~/health-notebook-kit/scripts/install-service.sh
systemctl --user enable --now health-notebook.service
systemctl --user is-active health-notebook.service
journalctl --user -u health-notebook.service -n 40 --no-pager
```

Inspect the journal locally for a session link or errors; don't paste the entire
journal into public issues. The launcher first tries to resume; if that fails,
it starts a named server with capacity one. Authentication failures can cause
repeated restarts, so check for a working session rather than just an active unit.
The unit retries once a minute and user lingering permits startup after reboot.

## 5. Verify and hand over

- Reconnect from the phone after starting the service. If the original session
  cannot be resumed, use the new link reported in the private journal.
- Ask Claude to put “SETUP TEST — fictional entry” in daily-log.org; confirm the
  file changed and the entry is clearly fictional. Ask it to remove the entry.
- Check the local commit and `git status`; account for any intended changes.
- Disconnect SSH and confirm the phone still works.
- Restart the service and verify phone reconnection and file persistence.
- On a newly provisioned dedicated server, reboot and repeat the check. For a
  shared existing machine, schedule the reboot with its owner; mark that check
  pending if it cannot be performed now.
- Confirm `loginctl show-user notebook -p Linger` reports `yes` and
  `systemctl --user is-enabled health-notebook.service` reports `enabled`.
- Confirm `git remote -v` is empty, or the owner has verified the backup remote
  is private. Choose an off-machine backup before retaining important records.

Give the owner the SSH alias, private notebook location, service name, how to
reconnect, and [operations guide](OPERATIONS.md). Record versions tested and any
unverified steps in private deployment notes outside this public kit. Do not say
“complete” if mobile access or required login is still unverified.
