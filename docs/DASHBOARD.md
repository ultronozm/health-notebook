# Optional personal dashboard

The dashboard turns the notebook's Org tables into a self-contained HTML page:
daily nutrition totals, target progress, weight trends, test results, foods,
batches, and appointment notes. Glucose charts appear when a LibreLinkUp archive
is present. Python 3.10+ builds it without extra Python packages.

## Try it

From the setup kit:

```sh
make demo
```

Open `examples/notebook/exports/site/index.html`. All example records and targets
are fictional. The demo fixes “today” to its example date so the progress cards
are visible. It does not initialize a real notebook or fetch glucose data.

## Build your notebook

On the notebook computer, as the notebook user:

```sh
cd ~/health-notebook-kit
HEALTH_NOTEBOOK_TZ=Europe/London bash scripts/build-dashboard.sh
```

Use the owner's IANA timezone from PROFILE.md instead of the example. The default
is UTC. This writes `~/health-notebook/exports/site/index.html` and the derived
`data/processed/site-data.json`. Both are ignored by the notebook's Git setup.
Open the HTML file locally or copy it to your phone. `HEALTH_NOTEBOOK_DIR` can
select a different notebook; `HEALTH_NOTEBOOK_GLUCOSE_RAW_DIR` can select an
external LibreLinkUp archive. The default archive is `data/raw/librelinkup` inside
the notebook.

The builder reports validation warnings, such as unlinked foods or mismatched
totals. Review them in the page's Validation section. `--strict` exits nonzero
when warnings exist. The website is a view of the files; update records through
Claude or a text editor, then rebuild.

## Phone access through Tailscale

Install [Tailscale](https://tailscale.com/download) on the server and phone and
sign into the same network. As the server administrator, serve only the generated
site directory (replace the home path if using another account):

```sh
tailscale serve --bg /home/notebook/health-notebook/exports/site
tailscale serve status
```

Follow any HTTPS setup link printed by Tailscale. Open the resulting HTTPS URL on
the phone with Tailscale connected. [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
shares within your tailnet; Funnel exposes content publicly. No public website
or domain registration is needed here. Check existing Serve configuration before
changing it on a shared server.

## Refresh automatically

As the notebook user, with the kit at `~/health-notebook-kit`:

```sh
mkdir -p ~/.config/systemd/user
cp ~/health-notebook-kit/deploy/health-notebook-site.* ~/.config/systemd/user/
systemctl --user edit health-notebook-site.service
```

Add the owner's timezone:

```ini
[Service]
Environment=HEALTH_NOTEBOOK_TZ=Europe/London
```

Then:

```sh
systemctl --user daemon-reload
systemctl --user start health-notebook-site.service
systemctl --user enable --now health-notebook-site.timer
systemctl --user list-timers health-notebook-site.timer
```

The timer rebuilds every five minutes. Tailscale continues serving the updated
file. Verify that a new notebook entry appears after a rebuild and that the
phone displays the page. Check failures with
`journalctl --user -u health-notebook-site.service -n 30`. Disable with
`systemctl --user disable --now health-notebook-site.timer`.

## Table conventions

Use the headers in `notebook-template` and the fictional `examples/notebook`.
Existing notebooks can adopt these formats without being reinitialized.

- Meals: one table per dated day, with `Time`, `Item`, `Wt.`, `Carb`, `Cal`, `Fat`,
  `Prot.`, `Sat.`, `Notes`. Totals begin `Subtotal`, `Day so far`, or `Day total`.
  In-progress totals sum food rows, excluding those aggregate rows.
- Foods: a `Products` table with nutrition per 100 g. Match meal names to `Food`,
  or `Food, Product` when there are variants. Mark photo estimates in Notes.
- Targets: `Metric`, `Lower`, `Target`, `Upper`, `Direction`, `Units`, `Notes`.
  Supported metrics are Cal, Carb, Fat, Protein, Sat.; directions are range,
  minimum, maximum, track. Empty targets mean no progress cards.
- Weight: `Date`, `Weight`, `Units`, `Notes`. Different units get separate charts.
- Labs: `Date`, `Test`, `Result`, `Units`, `Reference range`, `Flag`, `Note`.
  All results appear in the table. Exact numeric results are plotted per test/unit;
  inequalities and text remain in the table. Charts show observations, not diagnoses.
- Batches: see [the format example](../examples/notebook/batches.org). The imported
  batch parser groups by date, so it currently supports one batch per date.

Free-form daily notes and manually recorded glucose readings remain available
in the notebook; this dashboard does not parse those files. Its glucose charts
use the optional raw LibreLinkUp archive, in mmol/L. The shaded 3.9–10 mmol/L band
is a fixed visual reference inherited from the original dashboard, not a personal
target. Nutrition targets always come from the owner's file.
