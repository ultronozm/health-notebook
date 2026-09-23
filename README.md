# health-notebook

A personal health notebook you talk to from your phone. Claude Code runs on an
always-on computer and saves meals, nutrition goals, body weight, test results,
and appointment notes as plain-text files. The Claude mobile app connects through
Remote Control. No custom phone app or database is needed.

**Not medical advice.** This is a record-keeping tool, not a medical device.
Claude's nutrition figures, photo estimates, and summaries can be wrong; check
anything important, and make treatment and diet decisions with your clinician.
Your messages and any photos you send are processed by Anthropic under your
Claude account's terms.

**Tested** on Ubuntu 24.04 with Claude Code 2.1.251 (September 2026): notebook
initialization, logging and commits without approval prompts, logging a meal
photo from the iPhone app, the dashboard build, and the service's start and
resume. That test used an already-logged-in account on an existing server;
first-time login for a new account and a reboot of a new dedicated server have
not yet been run end to end.

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

Use whichever parts are helpful to you:

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
- **Track body weight.** “72 kg this morning.” Keep a dated record and ask how
  your weight has changed over the past few weeks.
- **Keep test results together.** Send a photo or document from the lab; Claude
  records the results, units, and reference ranges for comparison over time.
- **Follow your nutrition targets.** Tell it your daily goals, then ask “How much
  protein do I have left today?” or “How am I doing against my calorie range?”
- **Keep context for appointments.** Record a question, symptom, or exercise note,
  then ask for a summary to bring to your next appointment.

The food database and logs are ordinary text files, so remembered products carry
across conversations. Org files are readable without special software; Emacs is
optional. You can change the files and instructions to suit your own habits.

Start with [the setup guide](docs/SETUP.md). For a new machine, use
[the Hetzner recipe](docs/HETZNER.md). See [operations](docs/OPERATIONS.md) for
restarts, backups, and troubleshooting, and [a fictional example](examples/meal-log.org).

## Optional tools

- **A personal website:** browse meal totals, progress against daily targets,
  weight trends, test results, saved foods, batches, and appointment notes in one
  dashboard. It builds from the same notebook files and can refresh automatically.
  See [dashboard setup](docs/DASHBOARD.md), or run `make demo` to try fictional data.
- **Glucose imports:** for people using a compatible Libre sensor and LibreLinkUp,
  fetch cloud readings on demand or every five minutes, and show glucose traces
  alongside meals. See [LibreLinkUp setup](docs/GLUCOSE.md). This uses an
  unofficial client for Abbott's cloud service, not an Abbott product; it may
  stop working without notice, and you are responsible for complying with
  LibreLinkUp's terms. It is not a substitute for the sensor app's alarms. You can also log
  readings or screenshots manually.

Both live under `extras/` and can be enabled independently. The notebook
works without either.

## Storage and backup

The setup creates `~/health-notebook` for your records, separate from the setup
files. Conversations are processed by Anthropic; files live on your computer or
server. You can back them up to another computer or a private Git repository.
See [backup instructions](docs/OPERATIONS.md#backups).

## Development

Run `make test`. After installing the optional glucose dependencies, run
`make test-glucose` as well.
The reusable notebook instructions live in `notebook-template/AGENTS.md`;
`notebook-template/CLAUDE.md` points Claude to them. Instructions are copied at
initialization and can be adapted to your own workflow.
See [instruction updates](docs/OPERATIONS.md#updating-instructions).

License: MIT; see [LICENSE](LICENSE).
