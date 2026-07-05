# L9 Intent Compiler

Converges human intent into a canonical runtime intent contract.

Pipeline position:

```text
Human Intent -> Intent Contract -> Kernel Activation Plan -> Universal Execution Contract -> Execution Graph -> Adapter Render
```

This layer is intentionally small. It does not execute work and does not render prompts. It normalizes mission, task type, constraints, desired outputs, known context, and unknowns so downstream stages are model-agnostic.

