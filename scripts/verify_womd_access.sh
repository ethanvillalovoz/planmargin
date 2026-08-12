#!/usr/bin/env bash

set -euo pipefail

dataset_version="1.3.1"
shard_uri="gs://waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/training/training_tfexample.tfrecord-00000-of-01000"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud is not installed or is not on PATH." >&2
  exit 1
fi

# Deliberately report only a count. Never print account names or access tokens.
active_account_count="$(
  gcloud auth list --filter='status:ACTIVE' --format='value(account)' 2>/dev/null \
    | awk 'NF { count += 1 } END { print count + 0 }'
)"
if [[ "${active_account_count}" -lt 1 ]]; then
  echo "ERROR: no active gcloud account; run 'gcloud auth login'." >&2
  exit 1
fi

# TensorFlow's gs:// reader uses Application Default Credentials (ADC), which
# may represent a different identity from the active gcloud CLI account. Feed
# the ADC token to gcloud through a process-substitution file descriptor so the
# token is never printed, stored in the repository, or exposed as an argument.
if ! size_bytes="$(
  gcloud storage objects describe "${shard_uri}" \
    --access-token-file=<(gcloud auth application-default print-access-token 2>/dev/null) \
    --format='value(size)' 2>/dev/null
)" || [[ -z "${size_bytes}" ]]; then
  echo "ERROR: ADC could not read WOMD shard metadata." >&2
  echo "Run 'gcloud auth application-default login' and confirm dataset access." >&2
  exit 1
fi

printf 'dataset_version=%s\n' "${dataset_version}"
printf 'split=training\n'
printf 'shard=00000-of-01000\n'
printf 'size_bytes=%s\n' "${size_bytes}"
printf 'active_account_configured=true\n'
printf 'application_default_credentials_dataset_access=true\n'
printf 'access_check=passed\n'
