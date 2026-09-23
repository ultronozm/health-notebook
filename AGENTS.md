# Working with health-notebook

Read README.md and docs/SETUP.md. For setup requests, carry out the runbook with
available terminal and SSH tools, reusing suitable existing infrastructure.
Ask for missing choices together and guide the user through account logins.
Use authorization already given; confirm the plan and cost before purchasing a
server if those have not been agreed.

The initializer creates a separate ~/health-notebook with its own Git history.
This is the default layout, which users can adapt. Preserve existing files and
services when setting up on a machine already in use. Keep credentials out of
Git and tool output. Use the documented non-root account and permission settings,
or the user's chosen configuration.

Verify the phone connection as well as service startup using docs/SETUP.md.
Report what worked and any steps still needing login or a phone check. If waiting
for the user, complete independent setup work and give the precise next step.

For development, preserve existing edits and run the checks in README.md when
changing the scripts. Examples should be fictional. Keep the documentation
practical and concise, describing the workflow rather than imposing rules on
how people may use their own copy.
