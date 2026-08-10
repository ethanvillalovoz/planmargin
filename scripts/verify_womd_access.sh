#!/usr/bin/env bash

set -euo pipefail

dataset_version="1.3.1"
shard_uri="gs://waymo_open_dataset_motion_v_1_3_1/uncompressed/tf_example/validation/validation_tfexample.tfrecord-00000-of-00150"

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

# TensorFlow's gs:// reader uses Application Default Credentials (ADC).
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo "ERROR: ADC is unavailable; run 'gcloud auth application-default login'." >&2
  exit 1
fi

size_bytes="$(
  gcloud storage objects describe "${shard_uri}" \
    --format='value(size)' 2>/dev/null
)"
if [[ -z "${size_bytes}" ]]; then
  echo "ERROR: WOMD shard metadata could not be read." >&2
  exit 1
fi

printf 'dataset_version=%s\n' "${dataset_version}"
printf 'split=validation\n'
printf 'shard=00000-of-00150\n'
printf 'size_bytes=%s\n' "${size_bytes}"
printf 'active_account_configured=true\n'
printf 'application_default_credentials_configured=true\n'
printf 'access_check=passed\n'
