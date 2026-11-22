#!/bin/sh
# Entrypoint for the backend and ai-worker images.
# When Vault is enabled, the Vault agent renders secrets into /vault/secrets/*.env
# as `export NAME="value"` lines (DEV-11); load them before starting the process.
set -e
for secrets_file in /vault/secrets/*.env; do
  if [ -f "$secrets_file" ]; then
    # shellcheck disable=SC1090
    . "$secrets_file"
  fi
done
exec "$@"
