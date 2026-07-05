# L9 Coding Kernel: Repo Taxonomy and Dependency Architecture

```yaml
kernel_id: l9.coding.repo_taxonomy_dependency_architecture
kernel_name: L9 Repo Taxonomy and Dependency Architecture Kernel
version: 1.0.0
status: canonical_candidate
artifact_type: prompt_compiled
purpose: >
  Classify every L9 Constellation artifact into the correct architectural bucket
  before code generation, dependency packaging, repo migration, or implementation.

authority_order:
  - user_latest_instruction
  - active_architecture_decisions
  - Constellation.PackageTemplate contract
  - Golden Repo birth contract
  - existing repo/package evidence
  - older docs and comments

classification_law:
  rule: >
    Every artifact must be classified by runtime responsibility, birth factory,
    installation behavior, and ownership boundary before implementation.
  no_unclassified_artifacts: true
  unknowns_must_be_labeled: true

artifact_classes:
  runnable_node_repo:
    definition: >
      A deployed or deployable service/node that owns domain behavior and exposes
      runtime execution through the constellation node runtime boundary.
    born_by: cryptoxdog/golden-repo
    input: node_spec_pack
    output: runnable_node_repo
    owns:
      - domain_behavior
      - engine_handlers
      - node_specific_lifecycle
      - node_specific_tests
      - node_pyproject_extras
    imports:
      - constellation_chassis
    must_not_own:
      - shared_runtime_chassis
      - Gate_client_core
      - TransportPacket_model_source
      - dependency_package_foundation
      - reusable_utility_library_logic
    examples:
      - Broker_Node
      - Memory_Node
      - Orchestrator_Node
      - Context_Node
      - Research_Node
      - Compliance_Node

  dependency_package:
    definition: >
      An installable Python package used by nodes or other packages. It provides
      reusable infrastructure, utility, adapter, or protocol logic.
    born_by: cryptoxdog/Constellation.PackageTemplate
    input: dependency_spec_pack
    output: installable_constellation_package
    naming:
      repo: Constellation.<Capability>
      pypi: constellation-<capability>
      import: constellation_<capability>
      env_prefix: L9_<CAPABILITY>_
    owns:
      - package_config
      - package_errors
      - package_health
      - reusable_capability_logic
      - unit_tests
      - package_docs
    must_not_own:
      - node_domain_handlers
      - node_codegen
      - Golden_Repo_templates
      - runtime_service_identity

  sdk:
    definition: >
      A Software Development Kit: an installable developer-facing toolkit that
      lets other code interact with a system, protocol, or API boundary.
    is_installable_package: true
    sdk_when_it_contains:
      - public_client_classes
      - models_or_types_for_a_protocol
      - helper_functions_for_external_system_interaction
      - validation_or_signing_helpers
      - examples_for_developers
    examples:
      Gate_SDK:
        owns:
          - Gate_API_client
          - Gate_registration_client
          - Gate_auth_or_request_helpers
          - Gate_request_response_helpers
        must_not_own:
          - node_server_runtime
          - generated_node_domain_logic
      constellation_node_sdk:
        owns:
          - TransportPacket_models
          - packet_validation_hashing_signing
          - reusable_node_runtime_primitives
          - Gate_only_routing_enforcement
        must_not_own:
          - generated_node_domain_logic
          - Golden_Repo_codegen

  utility_library:
    definition: >
      An installable package providing shared helper logic that is not itself a
      protocol SDK and not a runnable node.
    born_by: cryptoxdog/Constellation.PackageTemplate
    examples:
      constellation_observability:
        owns:
          - logging_helpers
          - metrics_helpers
          - tracing_helpers
      constellation_config:
        owns:
          - shared_config_loading_patterns
      constellation_cache:
        owns:
          - shared_cache_abstraction
      constellation_policy:
        owns:
          - policy_as_code_helpers
    must_not_own:
      - runtime_node_HTTP_boundary
      - domain_node_handlers
      - codegen_factory_logic

  meta_package:
    definition: >
      A real installable package whose purpose is dependency grouping through
      optional extras. It owns almost no runtime code.
    canonical_instance: constellation-bundle
    born_by: cryptoxdog/Constellation.PackageTemplate
    owns:
      - install_profiles
      - optional_dependency_groups
      - dependency_matrix_docs
      - tests_that_extras_are_declared
    must_not_own:
      - runtime_logic
      - clients
      - handlers
      - TransportPacket
      - Gate_client
      - config_loader_implementation
      - observability_implementation

  factory_repo:
    definition: >
      A repo that births other repos or packages. It is not a runtime dependency
      of generated nodes.
    examples:
      Golden_Repo:
        births: runnable_node_repos
      Constellation.PackageTemplate:
        births: dependency_packages
    must_not_be_imported_by_runtime_nodes: true

canonical_dependency_direction:
  generated_node:
    imports:
      - constellation_chassis
  constellation_chassis:
    imports:
      - constellation_node_sdk
  constellation_node_sdk:
    imports:
      - Gate_SDK
  Gate_SDK:
    imports:
      - no_constellation_chassis
      - no_generated_node_engine
      - no_golden_repo

classification_questions:
  - Does it expose a deployed /v1/execute or domain endpoint? If yes, likely node.
  - Is it installed with pip and reused by multiple nodes? If yes, dependency package.
  - Does it provide a client/protocol toolkit? If yes, SDK.
  - Does it provide shared helpers only? If yes, utility library.
  - Does it only group extras? If yes, meta-package.
  - Does it generate repos/packages? If yes, factory.

forbidden_confusions:
  - calling_optional_dependency_groups_code
  - putting_runtime_logic_inside_constellation_bundle
  - building_dependency_packages_inside_golden_repo
  - putting_node_domain_logic_inside_utility_libraries
  - letting_Gate_SDK_own_node_server_runtime
  - redefining_TransportPacket_outside_node_sdk_or_canonical_transport_source

output_format:
  classification_result:
    artifact_name: string
    artifact_class: enum
    repo_target: string
    birth_factory: string
    owns: list
    must_not_own: list
    dependencies: list
    confidence: high_or_medium_or_low
    unknowns: list
```
