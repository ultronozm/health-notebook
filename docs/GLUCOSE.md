# Optional LibreLinkUp glucose imports

This helper retrieves readings from Abbott's **LibreLinkUp cloud service** using
[pylibrelinkup](https://github.com/robberwick/pylibrelinkup); it does not connect
to a sensor over Bluetooth. You need a working LibreLinkUp account with access
to the desired person's readings. Confirm those readings appear in LibreLinkUp
before configuring the helper. It is an unofficial API client; availability can
vary by sensor, region, account, and changes to the cloud API.

## Install and configure

On Ubuntu, an administrator first installs `python3-venv` if needed. Then, as
the notebook user:

```sh
cd ~/health-notebook-kit
python3 -m venv .venv
.venv/bin/pip install -r extras/librelinkup/requirements.txt
mkdir -p ~/.config/health-notebook
chmod 700 ~/.config/health-notebook
cp extras/librelinkup/.env.example ~/.config/health-notebook/librelinkup.env
chmod 600 ~/.config/health-notebook/librelinkup.env
```

Enter the LibreLinkUp email/password and API region in that file. Reuse the file
on subsequent runs rather than overwriting it. `EU` is an example; choose your
account's region. The helper follows one region redirect during authentication.
The parser accepts plain `KEY=value` lines; this file is not a shell script.

List connections, then fetch the latest reading:

```sh
.venv/bin/python extras/librelinkup/fetch_glucose.py patients
.venv/bin/python extras/librelinkup/fetch_glucose.py latest
```

If the account has multiple connections, add `--patient PATIENT_ID` (from the
list) or `--patient-index N`; the helper will otherwise ask you to select one.
Confirm that the reading and **measurement timestamp** match the intended person
and are recent compared with the phone's sensor app.

## Archive and check readings

On Linux:

```sh
bash extras/scripts/pull-glucose.sh
python3 extras/librelinkup/latest_raw_status.py
```

The wrapper uses `flock` (from Ubuntu's util-linux) to prevent overlapping pulls.
Add `--patient PATIENT_ID` if needed. It stores graph/latest snapshots in
`~/health-notebook/data/raw/librelinkup`, and fetches logbook data at most once per
UTC day. The session cache lives in
`~/.local/state/health-notebook/librelinkup-session.json` and is reused between
commands. `graph` and `logbook` are also available as individual commands;
use `--format json` or `--output PATH` for export.

`latest_raw_status.py` selects the newest archive by filename timestamp. It
reports pull age and the measurement timestamp separately: a fresh pull can
contain stale cloud data. Use the sensor's own app for current readings and
alerts; this archive is for logging and review.

## Run every five minutes

```sh
mkdir -p ~/.config/systemd/user
cp ~/health-notebook-kit/extras/deploy/health-notebook-glucose.* ~/.config/systemd/user/
```

For multiple connections, use `systemctl --user edit health-notebook-glucose.service`
to select the patient in the service command:

```ini
[Service]
ExecStart=
ExecStart=/bin/bash %h/health-notebook-kit/extras/scripts/pull-glucose.sh --patient PATIENT_ID
```

Then start and schedule the puller:

```sh
systemctl --user daemon-reload
systemctl --user start health-notebook-glucose.service
systemctl --user enable --now health-notebook-glucose.timer
systemctl --user list-timers health-notebook-glucose.timer
```

Verify new archive files arrive, check their measurement times, and record that
automatic import is configured in PROFILE.md. The assistant instructions then
explain how to check the latest archive during conversations. The [dashboard](DASHBOARD.md)
reads this same directory automatically; its independent timer may display a
new reading on the following refresh.

Inspect failures with `journalctl --user -u health-notebook-glucose.service -n 30`.
Disable polling with `systemctl --user disable --now health-notebook-glucose.timer`.
Back up the archive separately if you want to keep its history; raw files are
excluded from Git and accumulate over time.

## Authentication and freshness troubleshooting

The original deployment encountered Abbott HTTP 476 login failures from Hetzner.
The helper preserves cached sessions and backs off fresh logins for 30 minutes,
doubling up to six hours. A backoff skip can exit successfully without fetching
new data, so inspect archive freshness as well as service status. Avoid repeated
fresh-login attempts or deleting the cache as a routine fix.

Distinguish login failure, blocked data endpoints, and stale cloud readings.
If another computer/network can authenticate, an owner can transfer its session
cache securely to the puller (mode 0600) and test whether cached access works.
If data endpoints remain blocked, run acquisition on a working network and sync
the archive to the notebook computer; the dashboard and Claude can stay there.

The pinned client is 0.10.0, matching the imported helper. A compatibility adapter
rounds fractional **alarm configuration thresholds** before library validation;
it does not alter glucose measurements. Tests cover this behavior and cached
login/backoff. New API behavior may require updating the helper or dependency.
