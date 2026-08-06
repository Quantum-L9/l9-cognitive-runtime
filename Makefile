# Thin consumer Makefile — delegates PR gates to Cursor-Governance.
# See: https://github.com/Quantum-L9/Cursor-Governance AGENTS.md §2.2
#
# Usage (from this repo):
#   make pr
#   make pr PR_BASE=origin/feat/mcp-003 PR_REMEDIATE=0
#   make pr-check PR_BASE=origin/main

PR_BASE ?= origin/main
OPEN_PR ?= 1
PR_REMEDIATE ?= 0
PR_MYPY_STRICT ?= 0
PR_SECURITY_ADVISORY ?= 0

.PHONY: pr pr-check pr-security

pr:
	$(MAKE) -C "$(HOME)/.cursor-governance" pr \
		WS="$(CURDIR)" \
		PR_BASE="$(PR_BASE)" \
		OPEN_PR="$(OPEN_PR)" \
		PR_REMEDIATE="$(PR_REMEDIATE)" \
		PR_MYPY_STRICT="$(PR_MYPY_STRICT)" \
		PR_SECURITY_ADVISORY="$(PR_SECURITY_ADVISORY)"

pr-check:
	$(MAKE) -C "$(HOME)/.cursor-governance" pr-check \
		WS="$(CURDIR)" \
		PR_BASE="$(PR_BASE)" \
		PR_MYPY_STRICT="$(PR_MYPY_STRICT)" \
		PR_SECURITY_ADVISORY="$(PR_SECURITY_ADVISORY)"

pr-security:
	$(MAKE) -C "$(HOME)/.cursor-governance" pr-security \
		WS="$(CURDIR)" \
		PR_BASE="$(PR_BASE)" \
		PR_SECURITY_ADVISORY="$(PR_SECURITY_ADVISORY)"
