# Provision a dedicated Hetzner computer

Use this recipe when you need a new always-on machine. The account owner creates
a Hetzner Cloud account/project and chooses a server plan with the setup agent.

## Choose and authenticate

Install the official [hcloud CLI](https://github.com/hetznercloud/cli) locally
(`brew install hcloud` on macOS; see its releases for Linux). Use a project-scoped
read/write API token through the interactive context command:

```sh
hcloud context create health-notebook
hcloud context active
hcloud server-type list
hcloud location list
hcloud image list --type system
```

Enter the token in the CLI prompt, not this repo or chat. Confirm the active
project with the owner. Check the [current plans and pricing](https://www.hetzner.com/cloud/)
including IPv4, tax, and optional backups. Choose an available Ubuntu 24.04 image,
location, and server type with at least 2 GB RAM as a starting point. Do not
hard-code an old SKU or price. Record the selected plan and authorization privately.
Use `hcloud COMMAND --help` to reconcile flags with the installed CLI.

## Create resources

The following commands run on the local computer. Replace `CHOSEN_*` values with
the agreed choices. Use a new SSH key (choose a passphrase interactively); first
check that the filename and cloud resource names are unused. On a rerun, inspect
existing resources and reuse the correct ones rather than creating duplicates.

```sh
ssh-keygen -t ed25519 -f ~/.ssh/health-notebook_ed25519 -C health-notebook
hcloud ssh-key create --name health-notebook --public-key-from-file ~/.ssh/health-notebook_ed25519.pub
```

Prepare a temporary firewall JSON file outside the kit. Allow inbound SSH only;
Remote Control requires no inbound web port. Prefer the owner's stable public
IPv4 `/32` and/or IPv6 `/128` as sources when practical. If the owner's address
changes, they must update that rule through the provider before reconnecting.
For roaming access, the example permits key-authenticated SSH from any address:

```json
[
  {
    "direction": "in",
    "protocol": "tcp",
    "port": "22",
    "source_ips": ["0.0.0.0/0", "::/0"],
    "description": "SSH maintenance"
  }
]
```

Save as `/tmp/health-notebook-firewall.json`, then:

```sh
hcloud firewall create --name health-notebook --rules-file /tmp/health-notebook-firewall.json
hcloud server create --name health-notebook --type CHOSEN_TYPE --image ubuntu-24.04 --location CHOSEN_LOCATION --ssh-key health-notebook --firewall health-notebook --label purpose=health-notebook
hcloud server describe health-notebook
```

The server begins billing upon creation. A powered-off server still incurs
charges; deletion is a separate deliberate action after backing up its data.
If creation fails partway, inspect the project for resources already created.

## Establish SSH and the service account

Obtain the IP from the provider. Verify the server SSH host-key fingerprint
through its provider console (e.g. run `ssh-keygen -lf
/etc/ssh/ssh_host_ed25519_key.pub` there) before accepting it locally. Do not use
`StrictHostKeyChecking=no`. Add an alias locally using the observed IP:

```sshconfig
Host health-notebook-admin
    HostName SERVER_IP
    User root
    IdentityFile ~/.ssh/health-notebook_ed25519
    IdentitiesOnly yes

Host health-notebook
    HostName SERVER_IP
    User notebook
    IdentityFile ~/.ssh/health-notebook_ed25519
    IdentitiesOnly yes
```

On a **fresh dedicated server**, connect as the administrator and run:

```sh
apt-get update
apt-get upgrade -y
apt-get install -y git python3 curl ca-certificates
adduser --disabled-password --gecos '' notebook
install -d -m 700 -o notebook -g notebook /home/notebook/.ssh
```

From the local computer, upload the public key (not its private half):

```sh
scp ~/.ssh/health-notebook_ed25519.pub health-notebook-admin:/tmp/health-notebook.pub
```

Back in the administrator shell:

```sh
install -m 600 -o notebook -g notebook /tmp/health-notebook.pub /home/notebook/.ssh/authorized_keys
rm /tmp/health-notebook.pub
loginctl enable-linger notebook
```

On reruns, preserve any existing account and authorized keys; inspect and append
only the missing key instead of using the fresh-server commands blindly. The
notebook account should not belong to sudo. Keep administrator access separate.
Verify `ssh health-notebook` from a second local terminal before proceeding.

Check effective SSH configuration with `sshd -T`; require public-key auth and
disable password and keyboard-interactive login if enabled. Use an sshd drop-in,
validate with `sshd -t`, reload `ssh`, and re-test in a new terminal while keeping
the original admin session open. Do not change unrelated settings on shared hosts.

Return to [SETUP.md, step 2](SETUP.md#2-prepare-the-computer), using the
`health-notebook` SSH alias. When transferring the kit, use
`rsync -av --exclude=.git --exclude=__pycache__ ./ health-notebook:health-notebook-kit/`.
Complete login, service, phone, and reboot checks. No DNS name or public website
is needed. Consider provider backups or private Git backup as described in the
operations guide; never enable paid extras without the owner's authorization.
