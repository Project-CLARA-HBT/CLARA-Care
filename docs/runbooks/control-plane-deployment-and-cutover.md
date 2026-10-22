# Runbook: Control-Plane Deployment & Migration Cutover (PH41)

## 1. Prerequisites
- `DATABASE_CONTROL_URL`: PostgreSQL instance dedicated exclusively to control-plane governance.
- Network routing: Port 8200 restricted to internal VPN or administrative bastion.

## 2. Database Migration Procedure
Execute migrations against the control database:
```bash
cd services/control-plane
alembic upgrade head
```
Verify downgrade routine safety:
```bash
python3 scripts/ops/check_migration_downgrade.py services/control-plane/alembic/versions
```

## 3. Service Launch
1. Launch Control Plane Gateway:
   ```bash
   uvicorn clara_control.api.router:control_router --port 8200 --host 0.0.0.0
   ```
2. Verify Readiness Probe:
   ```bash
   curl -s http://localhost:8200/control/v1/health | jq .
   ```
   **Expected Response:**
   ```json
   {
     "status": "healthy",
     "plane": "control-plane-isolated"
   }
   ```
