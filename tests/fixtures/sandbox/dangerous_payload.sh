#!/bin/sh
# Probe script used by sandbox tests to verify the Docker backend's
# defaults from sandbox-spec §1:
#   - Network egress should be denied (--network=none)
#   - Root filesystem should be read-only (--read-only)
#   - All capabilities should be dropped (--cap-drop=ALL)
#
# When the sandbox is configured correctly each block exits non-zero and
# the script writes a tag the test asserts on. Stdout is the only side
# channel — never write to the network and never depend on /tmp surviving.

set -u

# 1. Network egress should fail (no DNS, no route, no socket).
if wget -q -T 2 -O - https://example.com/ >/dev/null 2>&1; then
  echo "NETWORK_EGRESS_LEAKED"
else
  echo "NETWORK_EGRESS_BLOCKED"
fi

# 2. Writing to / should fail under read-only root fs.
if echo "x" > /sentinel.tmp 2>/dev/null; then
  echo "ROOTFS_WRITABLE"
  rm -f /sentinel.tmp 2>/dev/null
else
  echo "ROOTFS_READ_ONLY"
fi

# 3. Capability-gated operations (mount) should be denied.
if mount -t tmpfs none /mnt >/dev/null 2>&1; then
  echo "CAPS_LEAKED"
else
  echo "CAPS_DROPPED"
fi

exit 0
