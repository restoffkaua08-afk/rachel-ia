from __future__ import annotations

import json

from pathlib import Path
from typing import Any


from runtime_paths import (
    ROOT,
)

from evaluation_runtime import (
    EvaluationRuntime,
)


PLAN_SCHEMA_VERSION = 1


class EvaluationPlanRuntimeError(
    RuntimeError
):
    pass


class EvaluationPlanRuntime:
    """
    Planner read-only da Dany.

    Ele apenas calcula readiness e blockers.

    NAO:
    - executa baseline;
    - executa candidate;
    - chama Promptfoo;
    - chama DSPy;
    - gera report;
    - calcula regressao real;
    - registra decision;
    - promove modelo;
    - executa treinamento.
    """

    def __init__(
        self,
        *,
        policy_path: Path | None = None,
        evaluation: EvaluationRuntime | None = None,
    ) -> None:

        self.policy_path = (
            Path(
                policy_path
                or (
                    ROOT
                    / "RACHEL_EVALUATION"
                    / "CONFIG"
                    / "evaluation-plan-policy.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.policy = self._load_json(
            self.policy_path
        )

        self.evaluation = (
            evaluation
            or EvaluationRuntime()
        )

        self._validate()

    @staticmethod
    def _load_json(
        path: Path,
    ) -> dict[str, Any]:

        if not path.is_file():
            raise EvaluationPlanRuntimeError(
                f"Evaluation Plan Policy ausente: {path}"
            )

        try:
            value = json.loads(
                path.read_text(
                    encoding="utf-8-sig"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise EvaluationPlanRuntimeError(
                "Evaluation Plan Policy invalida."
            ) from error

        if not isinstance(
            value,
            dict,
        ):
            raise EvaluationPlanRuntimeError(
                "Evaluation Plan Policy deve ser objeto."
            )

        return value

    def _validate(
        self,
    ) -> None:

        if (
            self.policy.get(
                "schema_version"
            )
            != PLAN_SCHEMA_VERSION
        ):
            raise EvaluationPlanRuntimeError(
                "Evaluation Plan schema invalido."
            )

        if (
            self.policy.get(
                "owner"
            )
            != "dany"
        ):
            raise EvaluationPlanRuntimeError(
                "Evaluation Plan owner precisa ser Dany."
            )

        phases = self.policy.get(
            "phases"
        )

        if not isinstance(
            phases,
            list,
        ):
            raise EvaluationPlanRuntimeError(
                "Evaluation Plan phases invalido."
            )

        expected = {
            "baseline-evaluation",
            "candidate-evaluation",
            "regression-comparison",
            "promotion-decision",
        }

        actual = {
            str(
                item.get(
                    "id"
                )
            )
            for item
            in phases
            if isinstance(
                item,
                dict,
            )
        }

        if actual != expected:
            raise EvaluationPlanRuntimeError(
                "Evaluation Plan phases divergentes."
            )

        for phase in phases:

            if (
                phase.get(
                    "execution_enabled"
                )
                is not False
            ):
                raise EvaluationPlanRuntimeError(
                    "Evaluation Plan phase execution habilitada."
                )

        rules = self.policy.get(
            "rules"
        )

        for key in (
            "readiness_is_not_execution",
            "plan_is_not_authorization",
            "plan_is_not_evaluation",
            "plan_is_not_report",
            "plan_is_not_decision",
            "plan_is_not_promotion",
            "missing_evidence_must_block",
            "unknown_state_must_block",
            "numeric_thresholds_must_not_be_invented",
        ):
            if (
                rules.get(
                    key
                )
                is not True
            ):
                raise EvaluationPlanRuntimeError(
                    f"Evaluation Plan rule invalida: {key}"
                )

        execution = self.policy.get(
            "execution"
        )

        for key in (
            "plan_execution_enabled",
            "suite_execution_enabled",
            "model_execution_enabled",
            "promptfoo_invocation_enabled",
            "dspy_invocation_enabled",
            "report_generation_enabled",
            "report_write_enabled",
            "comparison_execution_enabled",
            "decision_recording_enabled",
            "promotion_execution_enabled",
            "external_publish_enabled",
            "training_execution_enabled",
            "weights_modified",
        ):
            if (
                execution.get(
                    key
                )
                is not False
            ):
                raise EvaluationPlanRuntimeError(
                    f"Evaluation Plan execution habilitada: {key}"
                )

    @staticmethod
    def _phase(
        phase_id: str,
        subject: str,
        blockers: list[str],
    ) -> dict[str, Any]:

        clean = sorted(
            set(
                blockers
            )
        )

        return {
            "id": phase_id,
            "subject": subject,
            "ready": len(
                clean
            ) == 0,
            "state": (
                "ready"
                if not clean
                else "blocked"
            ),
            "blockers": clean,
            "blocker_count": len(
                clean
            ),
            "execution_enabled": False,
        }

    def baseline_plan(
        self,
    ) -> dict[str, Any]:

        status = (
            self.evaluation.status()
        )

        baseline = status[
            "baseline"
        ]

        execution = status[
            "execution"
        ]

        blockers: list[str] = []

        if (
            baseline[
                "suite_results_available"
            ]
            is not True
        ):
            blockers.append(
                "baseline-not-evaluated"
            )

        if (
            execution[
                "suite_execution_enabled"
            ]
            is not True
        ):
            blockers.append(
                "suite-execution-disabled"
            )

        if (
            execution[
                "model_generation_enabled"
            ]
            is not True
        ):
            blockers.append(
                "model-execution-disabled"
            )

        if (
            execution[
                "promptfoo_invocation_enabled"
            ]
            is not True
        ):
            blockers.append(
                "promptfoo-invocation-disabled"
            )

        if (
            execution[
                "report_write_enabled"
            ]
            is not True
        ):
            blockers.append(
                "report-write-disabled"
            )

        return self._phase(
            "baseline-evaluation",
            baseline[
                "subject_id"
            ],
            blockers,
        )

    def candidate_plan(
        self,
    ) -> dict[str, Any]:

        status = (
            self.evaluation.status()
        )

        candidate = status[
            "candidate"
        ]

        execution = status[
            "execution"
        ]

        blockers: list[str] = []

        checkpoint = candidate[
            "checkpoint"
        ]

        if (
            checkpoint[
                "state"
            ]
            != "created"
        ):
            blockers.append(
                "candidate-checkpoint-not-created"
            )

        if (
            checkpoint[
                "verified"
            ]
            is not True
        ):
            blockers.append(
                "candidate-checkpoint-unverified"
            )

        if (
            candidate[
                "candidate_available"
            ]
            is not True
        ):
            blockers.append(
                "candidate-unavailable"
            )

        if (
            candidate[
                "evaluation"
            ][
                "suite_results_available"
            ]
            is not True
        ):
            blockers.append(
                "candidate-not-evaluated"
            )

        if (
            execution[
                "suite_execution_enabled"
            ]
            is not True
        ):
            blockers.append(
                "suite-execution-disabled"
            )

        if (
            execution[
                "model_generation_enabled"
            ]
            is not True
        ):
            blockers.append(
                "model-execution-disabled"
            )

        if (
            execution[
                "promptfoo_invocation_enabled"
            ]
            is not True
        ):
            blockers.append(
                "promptfoo-invocation-disabled"
            )

        if (
            execution[
                "report_write_enabled"
            ]
            is not True
        ):
            blockers.append(
                "report-write-disabled"
            )

        return self._phase(
            "candidate-evaluation",
            candidate[
                "model_id"
            ],
            blockers,
        )

    def regression_plan(
        self,
    ) -> dict[str, Any]:

        contracts = (
            self.evaluation.status()[
                "decision_contracts"
            ]
        )

        regression = contracts[
            "regression"
        ]

        blockers: list[str] = []

        if (
            self.evaluation.baseline[
                "suite_results_available"
            ]
            is not True
        ):
            blockers.append(
                "baseline-evaluation-report-unavailable"
            )

        if (
            self.evaluation.candidate[
                "evaluation"
            ][
                "suite_results_available"
            ]
            is not True
        ):
            blockers.append(
                "candidate-evaluation-report-unavailable"
            )

        if (
            regression[
                "comparison_available"
            ]
            is not True
        ):
            blockers.append(
                "regression-comparison-unavailable"
            )

        if (
            regression[
                "thresholds_state"
            ]
            != "calibrated"
        ):
            blockers.append(
                "thresholds-not-calibrated"
            )

        if (
            regression[
                "execution_enabled"
            ]
            is not True
        ):
            blockers.append(
                "comparison-execution-disabled"
            )

        return self._phase(
            "regression-comparison",
            (
                "qwen3:1.7b-vs-"
                "rachel-model-v0.1"
            ),
            blockers,
        )

    def promotion_plan(
        self,
    ) -> dict[str, Any]:

        status = (
            self.evaluation.status()
        )

        candidate = status[
            "candidate"
        ]

        contracts = status[
            "decision_contracts"
        ]

        decision = contracts[
            "promotion_decision"
        ]

        regression = contracts[
            "regression"
        ]

        blockers: list[str] = []

        checkpoint = candidate[
            "checkpoint"
        ]

        if (
            checkpoint[
                "state"
            ]
            != "created"
        ):
            blockers.append(
                "candidate-checkpoint-not-created"
            )

        if (
            checkpoint[
                "verified"
            ]
            is not True
        ):
            blockers.append(
                "candidate-checkpoint-unverified"
            )

        if (
            candidate[
                "candidate_available"
            ]
            is not True
        ):
            blockers.append(
                "candidate-unavailable"
            )

        if (
            candidate[
                "evaluation"
            ][
                "suite_results_available"
            ]
            is not True
        ):
            blockers.append(
                "candidate-evaluation-results-unavailable"
            )

        if (
            regression[
                "comparison_available"
            ]
            is not True
        ):
            blockers.append(
                "regression-comparison-unavailable"
            )

        if (
            regression[
                "thresholds_state"
            ]
            != "calibrated"
        ):
            blockers.append(
                "thresholds-not-calibrated"
            )

        if (
            decision[
                "decision_recording_enabled"
            ]
            is not True
        ):
            blockers.append(
                "decision-recording-disabled"
            )

        if (
            decision[
                "promotion_execution_enabled"
            ]
            is not True
        ):
            blockers.append(
                "promotion-execution-disabled"
            )

        return self._phase(
            "promotion-decision",
            candidate[
                "model_id"
            ],
            blockers,
        )

    def preview(
        self,
    ) -> dict[str, Any]:

        phases = [
            self.baseline_plan(),
            self.candidate_plan(),
            self.regression_plan(),
            self.promotion_plan(),
        ]

        all_blockers = sorted(
            {
                blocker
                for phase
                in phases
                for blocker
                in phase[
                    "blockers"
                ]
            }
        )

        ready_count = sum(
            phase[
                "ready"
            ]
            for phase
            in phases
        )

        return {
            "id": (
                self.policy[
                    "id"
                ]
            ),
            "owner": "dany",
            "state": (
                "ready"
                if ready_count == len(
                    phases
                )
                else "blocked"
            ),
            "ready": (
                ready_count
                == len(
                    phases
                )
            ),
            "phase_count": len(
                phases
            ),
            "ready_phase_count": (
                ready_count
            ),
            "blocked_phase_count": (
                len(
                    phases
                )
                - ready_count
            ),
            "phases": phases,
            "blockers": all_blockers,
            "blocker_count": len(
                all_blockers
            ),
            "thresholds_state": (
                self.evaluation
                .regression_contract[
                    "thresholds"
                ][
                    "state"
                ]
            ),
            "numeric_thresholds_defined": False,
            "read_only": True,
            "plan_is_execution": False,
            "authorization_granted": False,
            "evaluation_executed": False,
            "report_generated": False,
            "comparison_computed": False,
            "decision_recorded": False,
            "promotion_executed": False,
            "training_execution_enabled": False,
            "weights_modified": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        preview = self.preview()

        return {
            "id": preview[
                "id"
            ],
            "owner": preview[
                "owner"
            ],
            "state": preview[
                "state"
            ],
            "ready": preview[
                "ready"
            ],
            "phase_count": preview[
                "phase_count"
            ],
            "ready_phase_count": (
                preview[
                    "ready_phase_count"
                ]
            ),
            "blocked_phase_count": (
                preview[
                    "blocked_phase_count"
                ]
            ),
            "blocker_count": (
                preview[
                    "blocker_count"
                ]
            ),
            "thresholds_state": (
                preview[
                    "thresholds_state"
                ]
            ),
            "numeric_thresholds_defined": False,
            "read_only": True,
            "execution_enabled": False,
            "model_execution": False,
            "report_generated": False,
            "comparison_computed": False,
            "decision_recorded": False,
            "promotion_executed": False,
            "training_execution_enabled": False,
            "weights_modified": False,
        }
