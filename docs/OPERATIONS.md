# Operating the notebook

Run service commands over SSH as the notebook user:

```sh
systemctl --user status health-notebook.service
systemctl --user restart health-notebook.service
journalctl --user -u health-notebook.service -n 40 --no-pager
```

Read logs privately: they may include session links and conversation-related
information. If login expires, stop the service, run Claude interactively in
`~/health-notebook`, complete `/login`, and restart the service. Do not copy
Claude credential files between people or put them in Git.

If the service is active but the phone cannot connect, inspect the journal,
verify the account and outbound network, and try a foreground Remote Control
session with the service stopped. Use the emitted session link. A hosted cloud
task in the app is a different environment. If the user systemd bus is missing,
log in directly by SSH as notebook and have the administrator verify lingering.

To stop automatic operation without deleting records:

```sh
systemctl --user disable --now health-notebook.service
```

This does not stop cloud billing. Before deleting a server, copy and verify a
backup and explicitly authorize deletion through the provider.

## Permissions

The default `acceptEdits` mode permits file edits and can still require approvals
for shell commands. `default` asks more often. If the owner explicitly wants
commands to proceed without approval, use a dedicated account with no sudo and
no unrelated private files, and explain that Claude can execute commands with
that account's access. Then create an override with `systemctl --user edit
health-notebook.service`:

```ini
[Service]
Environment=HEALTH_NOTEBOOK_PERMISSION_MODE=bypassPermissions
```

Run `systemctl --user daemon-reload` and restart the service. Set the value back
to `acceptEdits` to restore the default. Do not make bypass mode an implicit fix
for authentication or connection errors.

## Backups

Local Git commits do not survive disk loss. The simplest private file backup is
a periodic pull from another trusted computer:

```sh
mkdir -p ~/private-backups/health-notebook
chmod 700 ~/private-backups/health-notebook
rsync -a health-notebook:health-notebook/ ~/private-backups/health-notebook/
```

This includes Git history but not the Claude account's credentials outside the
notebook. Stop edits briefly for a consistent copy. Do not add `--delete` unless
you deliberately want mirror semantics. Secure the destination disk and test
restoring to a separate directory. Notebook files are the durable record; Claude
conversation history is not included in this backup.

For optional GitHub backup, create a **new private repository**, not a public
fork. Add a dedicated write deploy key scoped to it. Verify its visibility with
the owner before the first push, set the notebook's remote to that private repo,
and set `Private backup enabled: yes` in PROFILE.md. Never use the setup kit's
origin. Git stores earlier records even after deletion; keep the whole history
private. Keep large images and exports in a separate private backup.

## Updating instructions

The public kit and private notebook have independent histories. Pull updates in
`~/health-notebook-kit`, review them, then selectively copy instruction changes
into the private notebook. Preserve PROFILE.md and all records. Do not rerun the
initializer on an existing notebook. Service installation refuses differing
existing files so you can review them first.

The canonical reusable rules are `notebook-template/AGENTS.md`; CLAUDE.md points
to them. Copies are intentional: a public upstream commit should not silently
change how an unattended agent handles private data. Live symlinks are possible
for an owner-maintained checkout, but are not configured here. For a pre-existing
notebook, compare its current instructions and retain its integration-specific
rules (such as CGM freshness checks) before adopting any shared text.

Update Claude Code using its supported update mechanism, then restart and verify
phone access. Record the version used in private deployment notes. This kit does
not pin or automatically test future Claude releases.
