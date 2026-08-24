#!/usr/bin/env bash
set -e

cd /opt/clara-care/docs/formal
rm -f TLC_DONE TLC_FAILED tlc_raw.log

echo "Starting TLC Model Checking on VPS at $(date)..."
START_TIME=$(date +%s)

# Using -Xmx3000m and -gzip to keep queue footprint compact on disk and prevent RAM exhaustion
if java -XX:+UseParallelGC -Xmx3000m -cp /tmp/opencode/tla2tools.jar tlc2.TLC -workers auto -gzip GLHS_GSA.tla -config GLHS_GSA.cfg > tlc_raw.log 2>&1; then
    END_TIME=$(date +%s)
    DIFF=$((END_TIME - START_TIME))
    MINS=$((DIFF / 60))
    SECS=$((DIFF % 60))
    DURATION="${MINS}min ${SECS}s"
    echo "TLC model checking completed in $DURATION."
    python3 parse_tlc_log.py tlc_raw.log GLHS_GSA.cfg TLC_EXECUTION_LOG.txt "$DURATION"
    echo "Cleaning up state directories..."
    rm -rf states*
    touch TLC_DONE
    echo "All finished successfully at $(date)."
else
    END_TIME=$(date +%s)
    DIFF=$((END_TIME - START_TIME))
    MINS=$((DIFF / 60))
    SECS=$((DIFF % 60))
    DURATION="${MINS}min ${SECS}s"
    echo "TLC model checking exited with non-zero exit code."
    python3 parse_tlc_log.py tlc_raw.log GLHS_GSA.cfg TLC_EXECUTION_LOG.txt "$DURATION" || true
    rm -rf states*
    touch TLC_FAILED
    exit 1
fi
