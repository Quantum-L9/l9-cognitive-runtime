---
id: "l9-cognitive-runtime.context.runtime_kernel_pipeline_validator_readme__md"
title: "VALIDATOR README"
artifact_type: "context"
mcp_primitive: "resource"
callable: true
retrievable: true
injectable: true
namespace: "l9-cognitive-runtime"
sharing_scope: "agnostic"
source_path: "runtime/kernel_pipeline/VALIDATOR_README.md"
content_hash: "fd6762920b33494867352f2543be7b0896289156eb182d2c721b8f683be72295"
token_cost_estimate: 231
authority: "Quantum-L9"
created_or_detected_at: "Unknown"
family: "meta_kernel_forge"
description: "Unknown"
activation_signals: ["kernel", "contract"]
input_contract: "Unknown"
output_contract: "Unknown"
validation_gates: "Unknown"
stop_conditions: "Unknown"
---
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
