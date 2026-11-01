# GMP-129

**Task:** Build pr67_audit_nits_3f9c1a2e.plan.md
**Tier:** RUNTIME

## TODOs

- T1:  REPLACE Serve MCP schema and kernel resources through pack.read_verified and add tamper and unlisted-file regression tests
- T2:  REPLACE Add AdapterRenderer pack= verified mode: listed template via read_verified, unlisted on-disk template fails closed, absent template uses DEFAULT_TEMPLATE; pack and pack_root are mutually exclusive
- T3:  REPLACE Fail closed when template text still carries a {{ or }} marker after known tokens are removed; regression test with {{a{b}}}
- T4:  REPLACE Extend closure check 4 so selected_because must be a non-empty subset of planned requirement ids; regression test with a forged unplanned binding
- T5:  REPLACE Run the CLAUDE.md verify block and prove each new test fails on b87a5e79 sources
