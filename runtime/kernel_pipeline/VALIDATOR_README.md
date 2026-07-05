# Kernel Pipeline Validators

This directory turns the clean kernel pack from organized markdown/YAML into a self-policing pack.

## Validators

- `validate_pipeline_order.py` checks canonical phase order, kernel references, K01 -> K05 constitutional order, and terminal-only Flawless Victory activation.
- `validate_kernel_roles.py` checks each role directory exists and contains the expected kernel count.
- `validate_no_duplicate_active_kernels.py` checks active kernel identities are unique and exactly one terminal contract exists.
- `validate_phase_outputs.py` checks pipeline-required outputs match `PHASE_OUTPUT_CONTRACTS.yaml`; with `--outputs-dir`, it also checks generated phase artifacts exist.

## Run

```bash
python runtime/kernel_pipeline/run_validators.py
```

## Status Vocabulary

Validators use the pack-level status vocabulary: `passed`, `failed`, `blocked`, `unknown`, `not_applicable_with_reason`.
