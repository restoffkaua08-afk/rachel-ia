from __future__ import annotations

import hashlib
import json
import sys
import uuid

from pathlib import Path
from typing import Any


from runtime_paths import (
    CONFIG,
    CORE_SRC,
    STATE,
)

if str(CORE_SRC) not in sys.path:
    sys.path.insert(
        0,
        str(CORE_SRC),
    )


from rachel_core.model_contract import (
    ModelContract,
)

from rachel_core.training_run_planner import (
    TrainingRunPlanner,
)

from cognitive_runtime import (
    DanyEvaluator,
)

from security_runtime import (
    ApprovalStore,
)

from team_runtime import (
    CyberPolicy,
)


TRAINING_DRY_RUN_SCHEMA_VERSION = 1

TRAINING_DRY_RUN_TOOL = (
    "learning.training.dry_run_manifest"
)

TRAINING_DRY_RUN_EFFECT = (
    "write"
)


class TrainingExecutionGateError(
    RuntimeError
):
    pass


def _canonical_json(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
    )


def _sha256(
    value: Any,
) -> str:
    return hashlib.sha256(
        _canonical_json(
            value
        ).encode(
            "utf-8"
        )
    ).hexdigest()


class TrainingExecutionGate:
    """
    Gate entre plano de treinamento e
    uma futura execucao real.

    Nesta etapa:
    - Dany avalia o plano;
    - Cyber autoriza somente a escrita
      de um manifest de dry-run;
    - nenhuma chamada ao LitGPT ocorre;
    - nenhum peso e carregado;
    - nenhum treino e iniciado.
    """

    def __init__(
        self,
        *,
        planner: TrainingRunPlanner | None = None,
        approvals: ApprovalStore | None = None,
        evaluator: Any | None = None,
        cyber: CyberPolicy | None = None,
        root: Path | None = None,
        contract_path: Path | None = None,
        profiles_path: Path | None = None,
    ) -> None:

        self.contract_path = (
            Path(
                contract_path
                or (
                    CONFIG
                    / "rachel-model-v0.1.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.profiles_path = (
            Path(
                profiles_path
                or (
                    CONFIG
                    / "training-hardware-profiles.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.contract = (
            ModelContract.from_path(
                self.contract_path
            )
        )

        self.planner = (
            planner
            or TrainingRunPlanner(
                contract=self.contract,
                profiles_path=(
                    self.profiles_path
                ),
            )
        )

        self.approvals = (
            approvals
            or ApprovalStore()
        )

        self.evaluator = (
            evaluator
            or DanyEvaluator()
        )

        self.cyber = (
            cyber
            or CyberPolicy()
        )

        self.root = (
            Path(
                root
                or (
                    STATE
                    / "training-dry-runs"
                    / "rachel-model-v0.1"
                )
            )
            .expanduser()
            .resolve()
        )

    @staticmethod
    def _approval_arguments(
        plan: dict[str, Any],
    ) -> dict[str, Any]:

        dataset = plan[
            "compiled_dataset"
        ]

        return {
            "run_id": (
                plan[
                    "run_id"
                ]
            ),
            "plan_sha256": (
                plan[
                    "plan_sha256"
                ]
            ),
            "model_id": (
                plan[
                    "model_id"
                ]
            ),
            "base_model": (
                plan[
                    "base_model"
                ]
            ),
            "compiled_dataset_id": (
                dataset[
                    "id"
                ]
            ),
            "compiled_dataset_train_sha256": (
                dataset.get(
                    "train_sha256"
                )
            ),
            "profile_id": (
                plan[
                    "profile_id"
                ]
            ),
            "target": (
                "local-dry-run-manifest"
            ),
            "training_execution": (
                "forbidden"
            ),
        }

    def _dany(
        self,
        plan: dict[str, Any],
    ) -> dict[str, Any]:

        content = json.dumps(
            plan,
            ensure_ascii=False,
            sort_keys=True,
        )

        report = (
            self.evaluator
            .evaluate(
                content
            )
        )

        return {
            "accepted": bool(
                report.accepted
            ),
            "score": int(
                report.score
            ),
            "issues": [
                str(issue)
                for issue
                in report.issues
            ],
            "checks": {
                str(
                    name
                ): bool(
                    passed
                )
                for (
                    name,
                    passed,
                )
                in report.checks.items()
            },
        }

    def review(
        self,
        compiled_dataset: dict[str, Any],
        *,
        profile_id: str = (
            "qwen3-1.7b-lora-minimum"
        ),
        observed_hardware: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        plan = self.planner.plan(
            compiled_dataset,
            profile_id=profile_id,
            observed_hardware=(
                observed_hardware
            ),
        )

        dany = self._dany(
            plan
        )

        if not dany[
            "accepted"
        ]:
            state = (
                "dany-rejected"
            )
        elif plan[
            "execution_allowed"
        ]:
            state = (
                "plan-valid-execution-still-disabled"
            )
        else:
            state = (
                "plan-valid-blocked"
            )

        return {
            "state": state,
            "plan": plan,
            "dany": dany,
            "dry_run_only": True,
            "training_execution_enabled": False,
            "litgpt_invoked": False,
            "weights_downloaded": False,
            "training_started": False,
            "checkpoint_created": False,
            "weights_modified": False,
            "external_export": False,
        }

    def request_dry_run(
        self,
        compiled_dataset: dict[str, Any],
        *,
        profile_id: str = (
            "qwen3-1.7b-lora-minimum"
        ),
        observed_hardware: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        review = self.review(
            compiled_dataset,
            profile_id=profile_id,
            observed_hardware=(
                observed_hardware
            ),
        )

        if not review[
            "dany"
        ][
            "accepted"
        ]:
            raise TrainingExecutionGateError(
                "Dany rejeitou o plano "
                "de treinamento."
            )

        decision = self.cyber.check(
            TRAINING_DRY_RUN_EFFECT
        )

        if (
            decision.allowed
            or not decision.approval_required
        ):
            raise TrainingExecutionGateError(
                "Cyber policy inesperada "
                "para dry-run write."
            )

        plan = review[
            "plan"
        ]

        approval = (
            self.approvals
            .request(
                TRAINING_DRY_RUN_TOOL,
                TRAINING_DRY_RUN_EFFECT,
                decision.risk,
                self._approval_arguments(
                    plan
                ),
                (
                    "Autorizar materializacao "
                    "local de manifest de dry-run "
                    "do Rachel Model v0.1. "
                    "Esta autorizacao nao permite "
                    "executar treinamento."
                ),
            )
        )

        return {
            "state": (
                "approval-required"
            ),
            "review": review,
            "approval": approval,
            "training_execution_enabled": False,
            "training_started": False,
            "weights_modified": False,
        }

    def manifest_path(
        self,
        run_id: str,
    ) -> Path:

        clean = str(
            run_id
        ).strip()

        if (
            not clean
            or "/"
            in clean
            or "\\"
            in clean
            or clean.startswith(
                "."
            )
        ):
            raise TrainingExecutionGateError(
                "run_id invalido."
            )

        return (
            self.root
            / clean
            / "manifest.json"
        )

    def materialize_dry_run(
        self,
        compiled_dataset: dict[str, Any],
        approval_id: str,
        *,
        profile_id: str = (
            "qwen3-1.7b-lora-minimum"
        ),
        observed_hardware: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        review = self.review(
            compiled_dataset,
            profile_id=profile_id,
            observed_hardware=(
                observed_hardware
            ),
        )

        if not review[
            "dany"
        ][
            "accepted"
        ]:
            raise TrainingExecutionGateError(
                "Dany rejeitou o plano."
            )

        plan = review[
            "plan"
        ]

        target = self.manifest_path(
            plan[
                "run_id"
            ]
        )

        if target.exists():
            raise TrainingExecutionGateError(
                "Dry-run manifest ja existe."
            )

        consumed = (
            self.approvals
            .consume(
                approval_id,
                TRAINING_DRY_RUN_TOOL,
                TRAINING_DRY_RUN_EFFECT,
                self._approval_arguments(
                    plan
                ),
            )
        )

        manifest = {
            "schema_version": (
                TRAINING_DRY_RUN_SCHEMA_VERSION
            ),
            "kind": (
                "rachel-training-dry-run"
            ),
            "model_id": (
                plan[
                    "model_id"
                ]
            ),
            "run_id": (
                plan[
                    "run_id"
                ]
            ),
            "plan_sha256": (
                plan[
                    "plan_sha256"
                ]
            ),
            "plan_state": (
                plan[
                    "state"
                ]
            ),
            "plan": plan,
            "dany": (
                review[
                    "dany"
                ]
            ),
            "cyber": {
                "status": (
                    consumed[
                        "status"
                    ]
                ),
                "effect": (
                    consumed[
                        "effect"
                    ]
                ),
                "risk": (
                    consumed[
                        "risk"
                    ]
                ),
                "authorization": (
                    "cyber-consumed"
                ),
            },
            "execution": {
                "dry_run_only": True,
                "execution_allowed": False,
                "training_execution_enabled": False,
                "litgpt_invoked": False,
                "weights_downloaded": False,
                "training_started": False,
                "checkpoint_created": False,
                "weights_modified": False,
                "external_export": False,
            },
        }

        manifest_sha256 = (
            _sha256(
                manifest
            )
        )

        manifest[
            "manifest_sha256"
        ] = manifest_sha256

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = (
            target.parent
            / (
                ".manifest."
                + uuid.uuid4().hex
                + ".tmp"
            )
        )

        try:
            temporary.write_text(
                json.dumps(
                    manifest,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )

            temporary.replace(
                target
            )
        finally:
            if temporary.exists():
                temporary.unlink()

        stored = json.loads(
            target.read_text(
                encoding="utf-8"
            )
        )

        stored_hash = (
            stored.pop(
                "manifest_sha256"
            )
        )

        if (
            _sha256(
                stored
            )
            != stored_hash
        ):
            raise TrainingExecutionGateError(
                "Integridade do dry-run "
                "manifest falhou."
            )

        return {
            "state": (
                "dry-run-materialized"
            ),
            "run_id": (
                plan[
                    "run_id"
                ]
            ),
            "manifest": (
                str(
                    target
                )
            ),
            "manifest_sha256": (
                manifest_sha256
            ),
            "plan_sha256": (
                plan[
                    "plan_sha256"
                ]
            ),
            "plan_state": (
                plan[
                    "state"
                ]
            ),
            "dany": (
                review[
                    "dany"
                ]
            ),
            "cyber": {
                "status": (
                    consumed[
                        "status"
                    ]
                ),
                "effect": (
                    consumed[
                        "effect"
                    ]
                ),
                "risk": (
                    consumed[
                        "risk"
                    ]
                ),
            },
            "training_execution_enabled": False,
            "litgpt_invoked": False,
            "weights_downloaded": False,
            "training_started": False,
            "checkpoint_created": False,
            "weights_modified": False,
            "external_export": False,
        }

    def verify_manifest(
        self,
        run_id: str,
    ) -> dict[str, Any]:

        target = self.manifest_path(
            run_id
        )

        if not target.is_file():
            raise TrainingExecutionGateError(
                "Dry-run manifest nao encontrado."
            )

        try:
            value = json.loads(
                target.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise TrainingExecutionGateError(
                "Dry-run manifest invalido."
            ) from error

        expected = value.get(
            "manifest_sha256"
        )

        unsigned = dict(
            value
        )

        unsigned.pop(
            "manifest_sha256",
            None,
        )

        actual = _sha256(
            unsigned
        )

        execution = value.get(
            "execution"
        )

        safe_execution = (
            isinstance(
                execution,
                dict,
            )
            and bool(
                execution.get(
                    "dry_run_only"
                )
            )
            and not bool(
                execution.get(
                    "execution_allowed"
                )
            )
            and not bool(
                execution.get(
                    "training_started"
                )
            )
            and not bool(
                execution.get(
                    "weights_modified"
                )
            )
        )

        integrity = (
            isinstance(
                expected,
                str,
            )
            and len(
                expected
            )
            == 64
            and expected
            == actual
        )

        return {
            "run_id": run_id,
            "manifest": str(
                target
            ),
            "integrity": integrity,
            "safe_execution": (
                safe_execution
            ),
            "manifest_sha256": (
                expected
            ),
            "training_started": False,
            "weights_modified": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        manifests = []

        if self.root.is_dir():
            manifests = sorted(
                self.root.glob(
                    "*/manifest.json"
                )
            )

        return {
            "status": "ok",
            "root": str(
                self.root
            ),
            "dry_run_manifests": len(
                manifests
            ),
            "dany_required": True,
            "cyber_required": True,
            "cyber_effect": (
                TRAINING_DRY_RUN_EFFECT
            ),
            "cyber_tool": (
                TRAINING_DRY_RUN_TOOL
            ),
            "training_execution_enabled": False,
            "litgpt_invoked": False,
            "automatic_training": False,
            "checkpoint_created": False,
            "weights_modified": False,
            "external_export": False,
        }