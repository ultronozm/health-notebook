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
> account logins when needed.

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

## Everyday uses

- **Photograph a food label once.** “Remember this yoghurt.” Claude saves the
  product and its nutrition values in `foods.org`, your personal food database.
  Next time, just say “200 g of my usual yoghurt” and it uses the saved values.
- **Weigh ingredients at home.** “Lunch: 120 g tofu, 150 g cooked rice, 10 g olive
  oil.” Claude calculates the meal and adds it to the day's totals.
- **Send a photo when eating out.** “Here's my cafeteria lunch.” Claude estimates
  the portions and nutrition, marks them as estimates, and can adjust the entry
  if you mention a sauce, a second helping, or something you left on the plate.
- **Remember a batch you cooked.** Give the ingredient weights and finished batch
  weight once; later, “250 g of yesterday's lentil stew” is enough to log a portion.
- **Review the day.** “How much protein and carbohydrate have I logged today?”
  Get totals from the record, with estimates and incomplete meals identified.
- **Keep context for appointments.** Send a glucose screenshot or a quick note
  about a walk after lunch, then ask for a summary of recorded observations and
  questions to bring to your next appointment.

The food database and logs are ordinary text files, so remembered products carry
across conversations. Org files are readable without special software; Emacs is
optional. You can change the files and instructions to suit your own habits.

Start with [the setup guide](docs/SETUP.md). For a new machine, use
[the Hetzner recipe](docs/HETZNER.md). See [operations](docs/OPERATIONS.md) for
restarts, backups, and troubleshooting, and [a fictional example](examples/meal-log.org).

This setup uses the glucose readings and screenshots you send it. It does not
include an automatic CGM connection or a dashboard.

## Storage and backup

The setup creates `~/health-notebook` for your records, separate from the setup
files. Conversations are processed by Anthropic; files live on your computer or
server. You can back them up to another computer or a private Git repository.
See [backup instructions](docs/OPERATIONS.md#backups).

## Development

Run `python3 -m unittest discover -s tests -v` and `for script in scripts/*.sh; do bash -n "$script"; done`.
The reusable notebook instructions live in `notebook-template/AGENTS.md`;
`notebook-template/CLAUDE.md` points Claude to them. Instructions are copied at
initialization and can be adapted to your own workflow.
See [instruction updates](docs/OPERATIONS.md#updating-instructions).

License: MIT; see [LICENSE](LICENSE).
