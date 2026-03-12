#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

normalize_env_name() {
  printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]'
}

mask_value() {
  local value="${1:-}"
  if [[ -z "${value}" ]]; then
    printf 'UNSET'
    return
  fi
  printf '[MASKED:%d]' "${#value}"
}

print_required_env() {
  local env_name="${NW_DIFF_ENV:-}"
  local normalized_env

  normalized_env="$(normalize_env_name "${env_name}")"

  printf 'Required environment variables:\n'
  printf '  DEVICE_PASSWORD=%s\n' "$(mask_value "${DEVICE_PASSWORD:-}")"
  printf '  NW_DIFF_ENV=%s\n' "$(mask_value "${env_name}")"

  if [[ -n "${env_name}" ]]; then
    case "${normalized_env}" in
      dev|development|local|test)
        ;;
      *)
        printf '  NW_DIFF_API_TOKEN=%s\n' "$(mask_value "${NW_DIFF_API_TOKEN:-}")"
        ;;
    esac
  fi
}

main() {
  local missing=()
  local env_name="${NW_DIFF_ENV:-}"
  local normalized_env

  normalized_env="$(normalize_env_name "${env_name}")"

  print_required_env

  if [[ -z "${DEVICE_PASSWORD:-}" ]]; then
    missing+=("DEVICE_PASSWORD")
  fi

  if [[ -z "${env_name}" ]]; then
    missing+=("NW_DIFF_ENV")
  else
    case "${normalized_env}" in
      dev|development|local|test)
        ;;
      *)
        if [[ -z "${NW_DIFF_API_TOKEN:-}" ]]; then
          missing+=("NW_DIFF_API_TOKEN")
        fi
        ;;
    esac
  fi

  if (( ${#missing[@]} > 0 )); then
    printf '\nMissing required environment variables: %s\n' "${missing[*]}" >&2
    printf 'Startup aborted.\n' >&2
    exit 1
  fi

  cd "${REPO_ROOT}"
  exec uvicorn nw_diff_v2.main:app --host 127.0.0.1 --port 5000 --app-dir src
}

main "$@"
