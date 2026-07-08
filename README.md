# fanctl — simple web UI for nct6775/nct6797 fan control

A minimal Flask app that reads and writes the Linux `nct6775` hwmon sysfs
files, so you get a browser dashboard with live RPM readings and per-channel
Auto/Manual + duty-cycle sliders — built for the MSI B450 (NCT6797D) setup
you were testing over SSH, but it'll work for any board using this driver
family.

## Before you start

The `nct6775` kernel module has to be loaded on the **TrueNAS host**
before this container can read/write anything under `/sys/class/hwmon`.
The container does not load the module itself — it only reads/writes the
sysfs files that already exist once the host has the module loaded.

Confirm the module is loaded and note which `hwmonN` path is yours:

```bash
sudo /sbin/modprobe nct6775
for d in /sys/class/hwmon/hwmon*; do echo "$d: $(cat $d/name)"; done
```

Update `HWMON_PATH` in `docker-compose.yml` if your number isn't `hwmon2`
(it can shift between reboots).

## Run it

```bash
docker compose up -d --build
```

Then open `http://<your-truenas-ip>:5000`.

## Permissions

Writing to sysfs from inside a container usually needs elevated
privileges. The compose file starts with `cap_add: SYS_RAWIO`, which is
enough on most systems. If you still get "Permission denied" errors when
moving a slider, uncomment `privileged: true` in `docker-compose.yml`
instead (broader access, but guaranteed to work).

## Persisting across TrueNAS reboots/upgrades

TrueNAS resets anything installed by hand on the base OS. Two things need
to survive a reboot:

1. **The kernel module** — add this to
   **System Settings → Advanced → Init/Shutdown Scripts** as a **Post
   Init** script (When: *Post Init*, Type: *Command*):

   ```bash
   /sbin/modprobe nct6775
   ```

2. **The container** — if you deploy this via `docker compose` directly on
   the host (outside the TrueNAS Apps system), make sure `restart:
   unless-stopped` is set (already in the compose file) and that Docker
   itself is set to start on boot. If you instead import this as a
   TrueNAS **custom App**, the Apps system handles restart-on-boot for
   you — just make sure the Init/Shutdown Script above still runs *before*
   the app starts, since the container depends on the module already
   being loaded.

## Notes on safety

- Switching a channel to **Manual** disables the BIOS/EC's own thermal
  curve for that header until you switch it back to **Auto** (or reboot).
- If a fan's RPM reads 0 shortly after you lower its duty cycle, it's
  likely stalled — raise the value. 3-pin (non-PWM) fans typically need a
  noticeably higher floor than 4-pin PWM fans before they stall.
- This app applies your changes directly and immediately — it does not
  currently implement its own temperature-based auto-curve. If you want
  that added (e.g. auto-adjust `pwm2` based on `CPUTIN`), that's a
  straightforward addition — just say the word.
