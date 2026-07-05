# L9 Coding Kernel: Bundle and Node Extras

```yaml
kernel_id: l9.coding.bundle_node_extras
kernel_name: L9 Bundle and Node Extras Kernel
version: 1.0.0
status: canonical_candidate
artifact_type: prompt_compiled
purpose: >
  Prevent confusion between node extras and constellation-bundle. Define where each lives,
  what each owns, and how one-command installation works without creating a bloated master SDK.

node_extras:
  definition: >
    Optional dependency groups declared inside a generated node repo's pyproject.toml.
    They are not separate code. They are install menus for node-specific capabilities.
  actual_code: false
  lives_in: generated_node_repo/pyproject.toml
  generated_by: Golden_Repo
  owns:
    - optional_dependency_groups_for_that_node
    - node_capability_install_profiles
  does_not_own:
    - implementation_code
    - shared_libraries
    - SDKs
    - runtime_logic
  install_examples:
    - pip install "memory-node[redis,observability]"
    - pip install "research-node[browser,observability]"

constellation_bundle:
  definition: >
    A real installable meta-package/repo that groups constellation-wide dependency profiles.
    It should contain almost no runtime code.
  repo: cryptoxdog/Constellation.Bundle
  package_name: constellation-bundle
  import_name: constellation_bundle
  born_by: cryptoxdog/Constellation.PackageTemplate
  subtype: meta_package
  actual_code: minimal
  owns:
    - pyproject_optional_dependencies
    - install_profiles
    - dependency_matrix_docs
    - profile_introspection_helpers_optional
  must_not_own:
    - runtime_logic
    - TransportPacket
    - Gate_client
    - generated_node_handlers
    - domain_logic
    - observability_implementation
    - cache_implementation
    - config_loader_implementation
  install_examples:
    - pip install "constellation-bundle[node-base]"
    - pip install "constellation-bundle[observability]"
    - pip install "constellation-bundle[all]"

when_to_use:
  node_extras:
    use_when: dependency_set_is_specific_to_one_generated_node
    examples:
      - memory-node[redis]
      - research-node[browser]
      - compliance-node[policy]
  constellation_bundle:
    use_when: dependency_set_is_cross_constellation_or_operator_convenience
    examples:
      - constellation-bundle[node-base]
      - constellation-bundle[dev-tools]
      - constellation-bundle[all]

canonical_bundle_profiles:
  node-base:
    includes:
      - constellation-chassis>=0.1.0
      - constellation-node-sdk>=1.0.0
  gate:
    includes:
      - Gate_SDK>=1.0.0
  observability:
    includes:
      - constellation-observability>=0.1.0
  config:
    includes:
      - constellation-config>=0.1.0
  cache:
    includes:
      - constellation-cache>=0.1.0
  policy:
    includes:
      - constellation-policy>=0.1.0
  ingest:
    includes:
      - constellation-ingest>=0.1.0
  node-full:
    includes:
      - constellation-chassis>=0.1.0
      - constellation-node-sdk>=1.0.0
      - constellation-observability>=0.1.0
      - constellation-config>=0.1.0
  all:
    includes:
      - node-base
      - gate
      - observability
      - config
      - cache
      - policy
      - ingest
      - dev-tools

bundle_filetree:
  root: Constellation.Bundle/
  files:
    - README.md
    - AGENTS.md
    - pyproject.toml
    - Makefile
    - LICENSE
    - src/constellation_bundle/__init__.py
    - src/constellation_bundle/_version.py
    - src/constellation_bundle/profiles.py
    - tests/unit/test_profiles.py
    - tests/packaging/test_extras_declared.py
    - docs/install_profiles.md
    - docs/dependency_matrix.md

minimal_runtime_code_policy:
  allowed:
    - INSTALL_PROFILES_constant
    - get_install_profile_read_only_helper
    - version_export
  forbidden:
    - network_calls
    - config_loading
    - Gate_client
    - node_runtime
    - package_install_automation_at_import_time

anti_patterns:
  - putting_node_code_inside_bundle
  - making_bundle_depend_on_all_packages_by_default
  - treating_node_extras_as_files_or_repos
  - making_one_master_SDK_that_installs_everything_by_default
  - hiding_domain_dependencies_inside_chassis
```
