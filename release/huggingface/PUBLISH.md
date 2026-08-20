# Hugging Face publication checklist

The staged package is intentionally aggregate-only. Before publishing:

1. Review the current Waymo Open Dataset terms and confirm that publication of
   these aggregate research outputs is permitted.
2. Run `python planmargin-public-evidence/verify.py`.
3. Inspect `data/campaign.jsonl` and confirm that it contains no scenario ID,
   source shard, record index, trajectory, image, point cloud, Gaussian field,
   per-cell row, or proposal parameter.
4. Authenticate the current Hugging Face CLI with `hf auth login`; the legacy
   `huggingface-cli` command is not supported.
5. Create and upload the dataset repository:

   ```bash
   hf repos create YOUR_HF_USERNAME/planmargin-public-evidence \
     --type dataset \
     --exist-ok
   hf upload YOUR_HF_USERNAME/planmargin-public-evidence \
     release/huggingface/planmargin-public-evidence \
     . \
     --type dataset \
     --commit-message "Publish verified aggregate PlanMargin evidence"
   ```

6. Verify the published viewer and download in a clean directory:

   ```bash
   hf download YOUR_HF_USERNAME/planmargin-public-evidence \
     --repo-type dataset \
     --local-dir /tmp/planmargin-public-evidence
   python /tmp/planmargin-public-evidence/verify.py
   ```

Do not upload `artifacts/`, `data/raw/`, `dist/`, a PLY, a TFRecord, Parquet,
DuckDB, camera frame, model checkpoint, or the local evidence token. A gated
Hugging Face repository does not replace Waymo's recipient-registration and
terms requirements for files governed by the Waymo Dataset License Agreement.
