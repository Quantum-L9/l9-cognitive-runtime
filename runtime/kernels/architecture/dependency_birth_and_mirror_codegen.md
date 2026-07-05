# L9 Coding Kernel: Dependency Birth and Mirror Codegen

```yaml
kernel_id: l9.coding.dependency_birth_mirror_codegen
kernel_name: L9 Dependency Birth Mirror Codegen Kernel
version: 1.0.0
status: canonical_candidate
artifact_type: prompt_compiled
purpose: >
  Define how dependency spec packs are hydrated into installable constellation_* packages
  through Constellation.PackageTemplate using a mirror codegen layer.

core_law:
  dependency_birth_pipeline: dependency_spec_pack -> dependency_codegen_mirror_pack -> PackageTemplate_overlay -> installable_constellation_package
  node_birth_pipeline: node_spec_pack -> Golden_Repo_codegen -> runnable_node_repo
  no_crossing_pipelines: true

package_template_role:
  repo: cryptoxdog/Constellation.PackageTemplate
  role: canonical_dependency_package_foundation
  provides:
    - pyproject_base
    - config_base
    - errors_base
    - health_base
    - logging_base
    - protocols_base
    - retry_tracing_helpers
    - tests_base
    - Makefile
    - AGENTS
    - README_pattern
  process:
    - clone_template
    - rename_capability
    - verify_renamed_scaffold
    - apply_unique_logic_overlay
    - verify_package_birth

mirror_codegen_role:
  definition: >
    The mirror pack is the dependency-side equivalent of Golden Repo codegen.
    It loads a dependency spec pack, validates it, plans a PackageTemplate overlay,
    renders/patches the scaffold, and verifies the resulting dependency package.
  must_be_deterministic: true
  must_not_generate_nodes: true

required_mirror_components:
  contracts:
    - dependency_codegen_contract.yaml
  models:
    - codegen/models/dependency_pack.py
  loaders:
    - codegen/loaders/dependency_pack_loader.py
  validators:
    - codegen/validators/dependency_pack_validator.py
  planners:
    - codegen/planners/package_template_overlay_planner.py
  renderers:
    - codegen/renderers/pyproject_patch_renderer.py
    - codegen/renderers/public_api_renderer.py
    - codegen/renderers/module_renderer.py
    - codegen/renderers/test_renderer.py
  tools:
    - tools/verify_dependency_birth.py
  examples:
    - examples/dependency_spec_packs/chassis/
  tests:
    - tests/dependency_birth/test_chassis_dependency_birth_smoke.py

input_dependency_spec_pack:
  required_files:
    - dependency.yaml
    - public_api.yaml
    - modules.yaml
    - config.yaml
    - errors.yaml
    - runtime_contract.yaml
    - dependencies.yaml
    - tests.yaml
    - forbidden_terms.yaml
    - codegen.yaml
    - handoff_to_package_template.md
    - README.md

codegen_yaml_required_sections:
  - template_source
  - overlay_mode
  - placeholder_replacements
  - generated_files
  - patched_files
  - forbidden_files
  - verification_phases

hydration_flow:
  load:
    - read_dependency_spec_pack
    - parse_all_required_files
    - normalize_package_identity
  validate:
    - required_files_exist
    - forbidden_terms_absent
    - package_name_import_name_env_prefix_present
    - public_api_declared
    - dependencies_declared
    - module_responsibilities_declared
    - test_gates_declared
  plan_overlay:
    - placeholder_replacement_plan
    - package_dir_rename_plan
    - pyproject_patch_plan
    - public_api_patch_plan
    - unique_module_file_plan
    - test_file_plan
  apply_overlay:
    - copy_or_clone_PackageTemplate
    - replace_placeholders
    - rename_src_package_directory
    - update_pyproject
    - render_unique_modules
    - render_tests
  verify:
    phase_0_renamed_scaffold:
      - import_package
      - get_config_no_env
      - health_check_no_raise
      - base_tests_pass
    phase_1_unique_logic_overlay:
      - public_exports_import
      - unique_module_tests_pass
      - forbidden_terms_absent
      - package_install_gate_passes

verification_phase_law:
  phase_0_must_not_require_unique_runtime_exports: true
  example:
    create_app:
      belongs_in: phase_1_unique_logic_overlay
      not_phase_0_renamed_scaffold: true

constellation_chassis_overlay_target:
  target_repo: cryptoxdog/Constellation.Chassis
  package_name: constellation-chassis
  import_name: constellation_chassis
  env_prefix: L9_CHASSIS_
  born_from: cryptoxdog/Constellation.PackageTemplate
  dependency_type: runtime_adapter_dependency
  should_wrap_not_duplicate:
    - constellation_node_sdk.TransportPacket
    - constellation_node_sdk.Gate_client_helpers
    - constellation_node_sdk.runtime_primitives
  unique_logic:
    - generated_node_create_app_adapter
    - EngineLifecycle_bridge
    - HandlerRegistry_convenience_if_not_owned_by_node_sdk
    - config_defaults
    - health_extensions

sdk_boundary:
  constellation_node_sdk:
    role: reusable_node_runtime_protocol_sdk
    owns:
      - TransportPacket
      - packet_hashing_validation_signing
      - node_runtime_primitives
      - Gate_only_routing_enforcement
  Gate_SDK:
    role: Gate_API_client_SDK
    owns:
      - Gate_client
      - Gate_registration
      - Gate_auth_helpers
  constellation_chassis:
    role: generated_node_adapter_dependency
    owns:
      - opinionated_interface_for_Golden_Repo_generated_nodes
    must_not_duplicate:
      - TransportPacket
      - Gate_client_core
      - node_sdk_runtime_core

forbidden:
  - PacketEnvelope
  - packet_envelope_v1
  - l9-core
  - l9_core
  - TransportPacket_redefinition
  - Gate_client_reimplementation
  - node_domain_logic_inside_dependency_package

acceptance_gates:
  spec_gate:
    - all_required_spec_files_exist
    - forbidden_terms_absent
    - dependency_boundaries_declared
  overlay_gate:
    - PackageTemplate_overlay_plan_complete
    - no_phase_order_violation
  package_gate:
    - install_succeeds
    - zero_config_import_succeeds
    - config_safe_defaults
    - health_never_raises
    - tests_pass
```
