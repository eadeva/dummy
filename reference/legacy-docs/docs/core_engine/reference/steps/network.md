# Network — SSH & TFTP

SSH clients live in `self.resources["ssh_connections"]` (lazy `paramiko` import, `AutoAddPolicy`, 15 s connect timeout). TFTP server runs in a daemon thread (lazy `tftpy` import).

```{note}
**Shape: PARAMS-DICT.** All fields below are nested under a `params:` mapping, not flat siblings
of `type`.
```

## `ssh_connection_setup`

- **Source:** [`ssh_steps.py`](../../../../xc_ce_utils/core_engine/steps/ssh_steps.py)

```yaml
ssh_connect:
  type: ssh_connection_setup
  params:
    SSH_IP_ADDRESS: 192.168.1.42
    USER_ID: root
    USER_PWD: ""
    PORT: 22
    retries: 6
```

## `ssh_run_cmd`

```yaml
ssh_uptime:
  type: ssh_run_cmd
  params:
    SSH_IP_ADDRESS: 192.168.1.42
    cmd: "uptime"
    check_output:
      expected_strs: ["load average"]
      order_relevant: false
```

## `ssh_disconnect`

```yaml
ssh_close:
  type: ssh_disconnect
  params:
    SSH_IP_ADDRESS: 192.168.1.42
```

## `tftp_upload` / `tftp_download`

- **Source:** [`tftp_steps.py`](../../../../xc_ce_utils/core_engine/steps/tftp_steps.py)

```yaml
tftp_push:
  type: tftp_upload
  params:
    server_ip: 192.168.1.10
    server_port: 69
    remote_path: firmware.hex
    local_path: _bin/firmware.hex

tftp_pull:
  type: tftp_download
  params:
    server_ip: 192.168.1.10
    server_port: 69
    remote_path: logs/boot.log
    local_path: _log/boot.log
```

## `tftp_server_setup`

```yaml
tftp_start:
  type: tftp_server_setup
  params:
    server_ip: 0.0.0.0
    server_port: 69
    server_directory: _bin
```

## `tftp_server_close`

```yaml
tftp_stop:
  type: tftp_server_close
  params:
    server_ip: 0.0.0.0
```

## Category index

| Step type | Description |
|---|---|
| `ssh_connection_setup` | Establish an SSH connection |
| `ssh_run_cmd` | Execute a remote command |
| `ssh_disconnect` | Close the SSH connection |
| `tftp_upload` | Upload a file via TFTP |
| `tftp_download` | Download a file via TFTP |
| `tftp_server_setup` | Start a local TFTP server |
| `tftp_server_close` | Stop the TFTP server |
