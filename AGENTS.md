# Working with this setup kit

Read README.md, then docs/SETUP.md. This is public source code, not a personal
health notebook. Never record the user's health information here.

For a setup request, carry out the runbook with available terminal/SSH tools.
Inspect first; reuse suitable existing infrastructure. Ask only for missing
choices, credentials the user must enter themselves, and authorizations not
already provided. Do not ask again for an approved deployment. Before creating
billable infrastructure, establish the project, location, plan, current price,
and spending authorization. Do not create infrastructure merely to test this kit.

Never print tokens, private keys, Claude authentication files, or health logs.
Use interactive/provider login flows. Keep deployment notes outside this checkout.
Do not alter unrelated services, overwrite an existing notebook, disable SSH host
key checking, or copy credentials from another user's setup. A dedicated non-root
account runs Claude; its default configuration must not bypass permissions.

The public kit and private notebook must be separate directories. Run the
initializer on the target computer. It creates a new Git repo with no remote;
only add a verified private backup destination on user request. Never attach
health records to this kit's public origin.

Complete the verification checklist in docs/SETUP.md. Report exactly which steps
were verified and which need a human phone/login check. An active systemd service
alone does not prove Remote Control works. If blocked on login, prepare the rest
and give the precise next command rather than declaring setup complete.

For development, preserve existing edits, use fictional fixtures, and run the
checks in README.md. Do not deploy changes to an existing health notebook unless
that is part of the user's request.
