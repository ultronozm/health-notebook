# health-notebook

A personal health notebook you talk to from your phone. Claude Code runs on an
always-on computer and saves meals, glucose observations, weight, and questions
for appointments as plain-text files. The Claude mobile app connects through
Remote Control. No custom phone app or database is needed.

**Draft:** the setup helpers have local automated checks; a clean-server and
phone walkthrough is still required before calling this a tested deployment.

## Ask your coding agent to set it up

Clone or download this repository, open it in your local coding agent, and say:

> Read AGENTS.md and docs/SETUP.md and set up my health notebook. Use an existing
> always-on computer if I have one; otherwise help me choose and provision a
> Hetzner server. Handle the installation and verification, and guide me through
> account logins when needed. Keep my health records private and outside this
> public setup repository.

Any agent with terminal/SSH access can follow the runbook. The service it installs
uses **Claude Code**, so you still need a Claude account eligible for Remote
Control. Check [current requirements](https://code.claude.com/docs/en/remote-control).
The initial recipe targets Ubuntu 24.04 with systemd. A laptop can demonstrate
Remote Control, but must stay awake to remain available.

The agent can prepare the machine, initialize the notebook, and install its
service. You handle account creation/payment, SSH or cloud authorization, Claude
login, and the final phone check. A new cloud server has a recurring cost; the
agent should establish the chosen plan and your authorization before creating it.

## What you get

- A private `~/health-notebook` directory with blank Org files and assistant rules.
- A named `health-notebook` session in Claude Remote Control.
- A Linux user service that starts after reboot and resumes the session.
- Optional private Git backup, with no public Git remote in the initial notebook.

Try: “Record lunch at 12:30: 150 g cooked rice and 120 g tofu. Mark the nutrition
as estimated.” Or: “Put this question on my appointment list.” Org files are
readable text; Emacs is optional. Review quantities and calculations as you go.

Start with [the setup guide](docs/SETUP.md). For a new machine, use
[the Hetzner recipe](docs/HETZNER.md). See [operations](docs/OPERATIONS.md) for
restarts, backups, and troubleshooting, and [a fictional example](examples/meal-log.org).

Automatic CGM imports and a dashboard are future additions. This version records
glucose observations you supply; it does not monitor a sensor or provide alerts.
It organizes records for you and your clinicians, and does not prescribe treatment.

## Where the information goes

The template is public; your initialized notebook is separate and private by
default. Conversation content is processed by Anthropic. The computer provider
stores the files, and a private Git host stores them if you enable backup. Do not
put health records, chat transcripts, credentials, or real screenshots in this
repository or its issues. Local Git history is useful undo, but is not an off-machine
backup. See the operations guide before relying on the notebook for your only copy.

## Development

Run `python3 -m unittest discover -s tests -v` and `for script in scripts/*.sh; do bash -n "$script"; done`.
The reusable notebook instructions live in `notebook-template/AGENTS.md`;
`notebook-template/CLAUDE.md` points Claude to them. Instructions are copied at
initialization so an upstream update cannot silently change a live notebook.
See [instruction updates](docs/OPERATIONS.md#updating-instructions).

License: MIT; see [LICENSE](LICENSE).
