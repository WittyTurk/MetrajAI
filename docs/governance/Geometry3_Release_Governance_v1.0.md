# Geometry3 Release Governance v1.0

Status: Accepted
Scope: Milestone Release Operations
Applies To: Geometry3 (All Engines)

## Purpose

This document defines the mandatory release operation procedure for every Geometry3 milestone.
The goal is repeatable, auditable, and stable releases.

## Governance Principles

1. Architecture consistency over ad-hoc changes.
2. Validator evidence before release decisions.
3. Milestone completeness before tagging.
4. Frozen modules are changed only for bug fix, performance, or validator-driven correction.
5. Architecture-first thinking remains, but delivery focus is now implementation-heavy.

## Focus Policy

- Architecture: 20%
- Implementation: 80%

## Release Checklist v1.0

### 1. Sprint Completed

- All sprint-scope tasks are completed.
- Sprint reports are archived.
- No open blocker remains.

### 2. Compile Health

- Project compiles.
- No traceback.
- No unhandled exception in milestone flows.

### 3. Validator Control

- Geometry Validator: PASS
- Building Validator: PASS
- Milestone-specific validators: PASS
- Integration tests: PASS

### 4. ADR Control

- New code complies with ADR-001 to ADR-010.
- No unmanaged technical debt is introduced.
- If debt exists, it is recorded in architecture-notes.md.

### 5. Architecture Control

- Builder to Validator discipline is preserved.
- Entity and Value Object separation is preserved.
- Pure Builder rule (ADR-006) is not violated.
- Entity reference rule (ADR-007) is not violated.

### 6. Architecture Snapshot

A milestone-end architecture summary is mandatory for each release.

Example snapshot:

- Geometry Engine: Frozen
- Building Engine: Frozen or In Progress
- Semantic Engine: Not Started or In Progress
- Quantity Engine: Not Started or In Progress
- Cost Engine: Not Started

### 7. Git Operations

- Milestone branch is up to date.
- Milestone branch is merged into main.
- Annotated tag is created.
- Tag is pushed to origin.

Reference commands:

```bash
git tag -a vX.Y.Z -m "Milestone Title"
git push origin vX.Y.Z
```

### 8. Release Notes

Each release must include these sections:

- Version
- Title
- Included
- Not Included
- Known Limitations
- Architecture Snapshot
- Status

### 9. Next Milestone Readiness

- New milestone branch is created.
- Roadmap is updated.
- Sprint plan is prepared.
- Frozen modules remain untouched except approved change types.

## Milestone Git Flow Standard

main -> milestone/* -> merge to main -> annotated tag -> release notes -> next milestone/*

## Freeze Policy

When a milestone is declared complete, related modules are frozen.
Allowed changes after freeze:

- Bug fix
- Performance optimization
- Validator-evidence correction

## Architecture Stability Policy

- Do not add new ADRs unless strictly necessary.
- Do not introduce new engine layers unless strictly necessary.
- Place new work inside the existing architecture.

## Release Exit Gates

A release is approved only if all are true:

1. ADR compliance: PASS
2. Builder and Validator discipline: PASS
3. Regression checks: PASS
4. Next milestone readiness: PASS
