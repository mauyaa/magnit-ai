#!/usr/bin/env bash
#
# Restore a MagnetAI backup into a scratch database and assert it is usable.
#
# An unverified backup is a guess, not a backup. Run this on a schedule (monthly at
# minimum) so a restore is a rehearsed procedure rather than something first
# attempted during an incident.
#
# Usage:
#   ops/scripts/verify-backup.sh magai-2026-07-25.dump
#   ops/scripts/verify-backup.sh magai-2026-07-25.dump postgresql://user:pw@host:5432
#
# Exits non-zero if the restore fails or the restored data fails its checks, so
# this is safe to wire into cron with alerting on failure.

set -euo pipefail

DUMP_FILE="${1:-}"
PG_BASE_URL="${2:-${PGBASE_URL:-postgresql://postgres@localhost:5432}}"
SCRATCH_DB="magai_restore_check_$(date +%s)"

if [[ -z "$DUMP_FILE" ]]; then
  echo "usage: $0 <dump-file> [postgres-base-url]" >&2
  exit 64
fi

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "FAIL: dump file not found: $DUMP_FILE" >&2
  exit 1
fi

for binary in pg_restore psql createdb dropdb; do
  command -v "$binary" >/dev/null 2>&1 || {
    echo "FAIL: required tool '$binary' is not installed" >&2
    exit 1
  }
done

# Always drop the scratch database, including on failure, so repeated runs do not
# accumulate databases on the host.
cleanup() {
  dropdb --if-exists --maintenance-db="${PG_BASE_URL}/postgres" "$SCRATCH_DB" 2>/dev/null || true
}
trap cleanup EXIT

echo "==> Verifying $DUMP_FILE"
echo "    size: $(du -h "$DUMP_FILE" | cut -f1)"
echo "    age:  $(( ( $(date +%s) - $(date -r "$DUMP_FILE" +%s) ) / 3600 )) hours"

echo "==> Creating scratch database $SCRATCH_DB"
createdb --maintenance-db="${PG_BASE_URL}/postgres" "$SCRATCH_DB"

SCRATCH_URL="${PG_BASE_URL}/${SCRATCH_DB}"

echo "==> Restoring"
# --exit-on-error so a partial restore is a failure, not a warning we might miss.
if ! pg_restore --no-owner --no-privileges --exit-on-error \
      --dbname="$SCRATCH_URL" "$DUMP_FILE" 2>/tmp/pg_restore_err.log; then
  echo "FAIL: pg_restore reported errors:" >&2
  tail -30 /tmp/pg_restore_err.log >&2
  exit 1
fi

echo "==> Checking schema"
# Every table the application requires must be present. A dump taken mid-migration
# can restore cleanly yet be missing a table.
REQUIRED_TABLES=(
  users widgets leads payments
  widget_heal_events widget_deployments auth_tokens alembic_version
)
for table in "${REQUIRED_TABLES[@]}"; do
  if ! psql -qtAX -d "$SCRATCH_URL" \
        -c "SELECT to_regclass('public.${table}') IS NOT NULL" | grep -q '^t$'; then
    echo "FAIL: table '${table}' is missing from the restored database" >&2
    exit 1
  fi
done
echo "    all ${#REQUIRED_TABLES[@]} required tables present"

echo "==> Checking migration state"
MIGRATION=$(psql -qtAX -d "$SCRATCH_URL" -c "SELECT version_num FROM alembic_version" | tr -d '[:space:]')
if [[ -z "$MIGRATION" ]]; then
  echo "FAIL: alembic_version is empty — the schema is not at a known revision" >&2
  exit 1
fi
echo "    schema at revision $MIGRATION"

echo "==> Checking data"
USER_COUNT=$(psql -qtAX -d "$SCRATCH_URL" -c "SELECT count(*) FROM users" | tr -d '[:space:]')
WIDGET_COUNT=$(psql -qtAX -d "$SCRATCH_URL" -c "SELECT count(*) FROM widgets" | tr -d '[:space:]')
LEAD_COUNT=$(psql -qtAX -d "$SCRATCH_URL" -c "SELECT count(*) FROM leads" | tr -d '[:space:]')
echo "    users: $USER_COUNT   widgets: $WIDGET_COUNT   leads: $LEAD_COUNT"

if [[ "$USER_COUNT" -eq 0 ]]; then
  # A dump of an empty database restores perfectly and is worthless. Catch it here
  # rather than discovering it during a real recovery.
  echo "FAIL: no users in the restored database — this backup has no recoverable data" >&2
  exit 1
fi

echo "==> Checking referential integrity"
# Cascades and FKs should make these impossible; a non-zero count means the dump
# was taken in a way that lost consistency.
ORPHAN_WIDGETS=$(psql -qtAX -d "$SCRATCH_URL" -c \
  "SELECT count(*) FROM widgets w LEFT JOIN users u ON u.id = w.user_id WHERE u.id IS NULL" \
  | tr -d '[:space:]')
ORPHAN_LEADS=$(psql -qtAX -d "$SCRATCH_URL" -c \
  "SELECT count(*) FROM leads l LEFT JOIN widgets w ON w.id = l.widget_id WHERE w.id IS NULL" \
  | tr -d '[:space:]')

if [[ "$ORPHAN_WIDGETS" -ne 0 || "$ORPHAN_LEADS" -ne 0 ]]; then
  echo "FAIL: orphaned rows found (widgets=$ORPHAN_WIDGETS leads=$ORPHAN_LEADS)" >&2
  exit 1
fi
echo "    no orphaned rows"

echo
echo "PASS: $DUMP_FILE restores cleanly and the data is consistent."
