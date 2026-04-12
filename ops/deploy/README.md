# Deploy Operations

## This Directory Holds Deployment Artifacts and Environment Glue
Deployment remains downstream of validation and verification.

## Local User Service Deployment Lives Under `systemd`

- `systemd/vela-api.service` runs the governed HTTP service.
- `systemd/vela-patrol.timer` schedules Warden patrol at `02:00, 06:00, 10:00, 14:00, 18:00, 22:00`.
- `systemd/vela-night-cycle.timer` schedules the night cycle at `03:00`.
- `systemd/vela.env.example` provides the local host, port, and actor defaults.

## Install Through The Bootstrap Script

- `ops/bootstrap/install-user-services.sh`
- then `systemctl --machine=knosence@.host --user daemon-reload`
- then `systemctl --machine=knosence@.host --user enable --now vela-api.service vela-patrol.timer vela-night-cycle.timer`
