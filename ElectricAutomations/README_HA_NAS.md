# HA network storage (NAS / CIFS)

Samba on the HA host (`192.168.1.15`) exports:

| Share | Path | User |
|---|---|---|
| `nas` | `/mnt/nas/backup` | `nasuser` |
| `media` | `/mnt/nas/media` | `nasuser` |
| `share` | `/mnt/share` | `nasuser` |

Config: `/etc/samba/smb.conf`. SMB password is separate from the Unix password — reset with:

```bash
printf '%s\n%s\n' 'NEWPASS' 'NEWPASS' | smbpasswd -s nasuser
```

## Why HA mounts broke (Jul 2026)

Two independent failures:

1. **Stale SMB password** — `STATUS_LOGON_FAILURE` from the kernel CIFS client even when Windows still had a working session (cached creds).
2. **Supervisor adds `retrans=`** — Debian kernel 6.1 / `cifs-utils` 7.0 reject that option (`Unknown parameter 'retrans'` → mount error 22). HA OS images ship a newer CIFS stack; Supervised-on-Debian does not.

### Host workaround

`/usr/sbin/mount.cifs` is a small wrapper that strips `retrans=N` and execs the real helper as argv0 `mount.cifs` (`/usr/sbin/mount.cifs.bin`). An apt hook reinstalls it after `cifs-utils` upgrades:

- `/usr/local/sbin/install-mount-cifs-wrapper`
- `/etc/apt/apt.conf.d/99fix-mount-cifs-wrapper`
- Log: `/var/log/mount-cifs-wrapper.log`

### Current Supervisor mounts

```bash
ha mounts info
```

Expected: `Nas` (backup, `//127.0.0.1/nas`), `nasmedia` (`//localhost/media`), `Share` (`//localhost/share`) — all `active`. Use **127.0.0.1** or **localhost** (same host); Windows can keep using `\\192.168.1.15\nas`.
