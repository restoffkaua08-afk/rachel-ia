# Etapa 15 — Dependency & Portability Audit

## Status

Dependency audit:

`COMPLETE`

Environment audit:

`COMPLETE`

Portability audit:

`COMPLETE`

Architecture closure:

`PENDING`

Production readiness:

`NO`

## Submodules

Declared:

`23`

Observed:

`23`

Healthy:

`TRUE`

Uninitialized:

`0`

Diverged:

`0`

Conflicted:

`0`

## Manifests and locks

Required manifests present:

`TRUE`

Node lock available:

`TRUE`

Rust lock available:

`TRUE`

Dependency locking:

`TRUE`

## Python environments

Runtime:

`3.12.10`

Runtime pip check:

`TRUE`

Desktop sidecar:

`3.12.13`

Desktop sidecar pip check:

`FALSE`

PyInstaller:

`6.21.0`

Training Runtime provisioned:

`FALSE`

## Toolchain

| Tool | Available | Version / result |
|---|---|---|
| git | YES | git version 2.53.0.windows.3 |
| node | YES | v25.9.0 |
| npm | NO | 'C:\Program' n�o � reconhecido como um comando interno |
| pnpm | YES | 11.21.0 |
| rustc | YES | rustc 1.97.1 (8bab26f4f 2026-07-14) |
| cargo | YES | cargo 1.97.1 (c980f4866 2026-06-30) |
| ffmpeg | NO | - |
| ollama | YES | ollama version is 0.32.14 |
| gh | YES | gh version 2.97.0 (2026-07-31) |
| nvidia_smi | NO | - |

## Portable Runtime

SHA256:

`D386A244E70C75F2486BCD0FC8406249431677BA870084E1073B4223FC5A655D`

Matches validated Stage 14 artifact:

`TRUE`

Tauri sidecar contract:

`TRUE`

PyInstaller Runtime bundle:

`TRUE`

PyInstaller Agent CONFIG bundle:

`TRUE`

## Machine-specific path scan

Operational files containing absolute Windows user paths:

`1`

## Repository hygiene

Suspicious tracked secrets/build artifacts:

`0`

## Reconciliation

The 15/1C audit does not rewrite the readiness matrix automatically.

Recommended classification changes:

`1`

If this value is non-zero, the next Stage 15 command must inspect the
evidence before changing any state.

No automatic upgrade to READY is permitted.

## Safety

This audit does not:

- enable Agent execution;
- enable browser execution;
- provision Training Runtime;
- train a model;
- promote a model;
- modify model weights;
- expand permissions.
