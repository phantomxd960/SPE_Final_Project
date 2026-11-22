#!/usr/bin/env bash
# Run an Ansible playbook from WSL/Linux with the local .env loaded.
#   scripts/ansible.sh site.yml                      full environment setup
#   scripts/ansible.sh deploy.yml -e image_tag=42    deploy one build
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
playbook="${1:?usage: scripts/ansible.sh <playbook.yml> [ansible options]}"
shift

if [ -f "$root/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . <(tr -d '\r' < "$root/.env")
  set +a
fi
export PATH="$HOME/.local/bin:$PATH"
export DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE:-vijayvignesh960}"
export K8S_FLAVOUR="${K8S_FLAVOUR:-docker-desktop}"
# Ansible ignores ansible.cfg in world-writable folders (e.g. /mnt/d in WSL), so pass it explicitly.
export ANSIBLE_CONFIG="$root/ansible/ansible.cfg"
export ANSIBLE_ROLES_PATH="$root/ansible/roles"
export ANSIBLE_INVENTORY="$root/ansible/inventories/dev/hosts.yml"

cd "$root/ansible"
exec ansible-playbook "playbooks/$playbook" "$@"
