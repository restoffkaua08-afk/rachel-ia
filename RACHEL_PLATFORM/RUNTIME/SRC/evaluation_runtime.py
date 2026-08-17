from __future__ import annotations

import json

from pathlib import Path
from typing import Any


from runtime_paths import (
    ROOT,
)


EVALUATION_SCHEMA_VERSION = 1
SUITE_SCHEMA_VERSION = 1


class EvaluationRuntimeError(
    RuntimeError
):
    pass


class EvaluationRuntime:
    """
    Runtime somente leitura da Dany.

    Responsabilidades atuais:

    - carregar policy;
    - carregar suite registry;
    - validar contratos;
    - listar suites;
    - descrever suites;
    - expor estado de elegibilidade.

    Este runtime NAO:

    - executa modelos;
    - chama Promptfoo;
    - chama DSPy;
    - grava reports;
    - promove modelos;
    - inicia treinamento.
    """

    def __init__(
        self,
        *,
        policy_path: Path | None = None,
        registry_path: Path | None = None,
        dany_manifest_path: Path | None = None,
    ) -> None:

        evaluation_root = (
            ROOT
            / "RACHEL_EVALUATION"
        )

        self.policy_path = (
            Path(
                policy_path
                or (
                    evaluation_root
                    / "CONFIG"
                    / "evaluation-promotion-policy.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.registry_path = (
            Path(
                registry_path
                or (
                    evaluation_root
                    / "CONFIG"
                    / "evaluation-suites.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.baseline_path = (
            evaluation_root
            / "CONFIG"
            / "evaluation-baseline.json"
        ).resolve()

        self.candidate_path = (
            evaluation_root
            / "CONFIG"
            / "evaluation-candidate.json"
        ).resolve()

        self.dany_manifest_path = (
            Path(
                dany_manifest_path
                or (
                    ROOT
                    / "RACHEL_PLATFORM"
                    / "MEMBROS"
                    / "ST-Dany"
                    / "member.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.policy = (
            self._load_json(
                self.policy_path,
                "Evaluation policy",
            )
        )

        self.registry = (
            self._load_json(
                self.registry_path,
                "Evaluation suite registry",
            )
        )

        self.baseline = (
            self._load_json(
                self.baseline_path,
                "Baseline manifest",
            )
        )

        self.candidate = (
            self._load_json(
                self.candidate_path,
                "Candidate manifest",
            )
        )

        self.dany = (
            self._load_json(
                self.dany_manifest_path,
                "Dany manifest",
            )
        )

        self._validate()

    @staticmethod
    def _load_json(
        path: Path,
        label: str,
    ) -> dict[str, Any]:

        if not path.is_file():
            raise EvaluationRuntimeError(
                f"{label} ausente: {path}"
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
            raise EvaluationRuntimeError(
                f"{label} invalido."
            ) from error

        if not isinstance(
            value,
            dict,
        ):
            raise EvaluationRuntimeError(
                f"{label} deve ser objeto."
            )

        return value

    def _validate(
        self,
    ) -> None:

        if (
            self.policy.get(
                "schema_version"
            )
            != EVALUATION_SCHEMA_VERSION
        ):
            raise EvaluationRuntimeError(
                "Evaluation policy schema invalido."
            )

        if (
            self.registry.get(
                "schema_version"
            )
            != SUITE_SCHEMA_VERSION
        ):
            raise EvaluationRuntimeError(
                "Suite registry schema invalido."
            )

        if (
            self.policy.get(
                "owner"
            )
            != "dany"
        ):
            raise EvaluationRuntimeError(
                "Evaluation owner precisa ser Dany."
            )

        if (
            self.registry.get(
                "owner"
            )
            != "dany"
        ):
            raise EvaluationRuntimeError(
                "Suite registry owner precisa ser Dany."
            )

        for label, manifest in (
            ("baseline", self.baseline),
            ("candidate", self.candidate),
        ):
            if (
                manifest.get(
                    "schema_version"
                )
                != 1
            ):
                raise EvaluationRuntimeError(
                    f"Schema invalido: {label}"
                )

            if (
                manifest.get(
                    "owner"
                )
                != "dany"
            ):
                raise EvaluationRuntimeError(
                    f"Owner invalido: {label}"
                )

        if (
            self.dany.get(
                "id"
            )
            != "dany"
        ):
            raise EvaluationRuntimeError(
                "Manifesto Dany invalido."
            )

        organs = {
            str(item).casefold()
            for item
            in self.dany.get(
                "orgaos",
                []
            )
        }

        for required in (
            "promptfoo",
            "dspy",
        ):
            if required not in organs:
                raise EvaluationRuntimeError(
                    f"Dany sem orgao requerido: {required}"
                )

        policy_baseline = (
            self.policy[
                "subjects"
            ][
                "temporary_runtime"
            ]
        )

        policy_candidate = (
            self.policy[
                "subjects"
            ][
                "rachel_model"
            ]
        )

        if (
            self.baseline[
                "subject_id"
            ]
            != policy_baseline[
                "id"
            ]
        ):
            raise EvaluationRuntimeError(
                "Baseline manifest diverge da policy."
            )

        if (
            self.baseline[
                "promotable_as_rachel_model"
            ]
            is not False
        ):
            raise EvaluationRuntimeError(
                "Baseline temporario nao pode ser "
                "promovido como Rachel Model."
            )

        if (
            self.candidate[
                "model_id"
            ]
            != policy_candidate[
                "id"
            ]
        ):
            raise EvaluationRuntimeError(
                "Candidate manifest diverge da policy."
            )

        if (
            self.candidate[
                "base_repository"
            ]
            != policy_candidate[
                "base_repository"
            ]
        ):
            raise EvaluationRuntimeError(
                "Candidate base diverge da policy."
            )

        if (
            self.candidate[
                "checkpoint"
            ][
                "state"
            ]
            != policy_candidate[
                "checkpoint_state"
            ]
        ):
            raise EvaluationRuntimeError(
                "Candidate checkpoint diverge."
            )

        if (
            self.candidate[
                "candidate_available"
            ]
            != policy_candidate[
                "candidate_available"
            ]
        ):
            raise EvaluationRuntimeError(
                "Candidate availability diverge."
            )

        if (
            self.candidate[
                "training"
            ][
                "weights_modified"
            ]
            is not False
        ):
            raise EvaluationRuntimeError(
                "Candidate weights_modified invalido."
            )

        layers = self.policy.get(
            "evaluation_layers"
        )

        if not isinstance(
            layers,
            list,
        ):
            raise EvaluationRuntimeError(
                "evaluation_layers invalido."
            )

        suites = self.registry.get(
            "suites"
        )

        if not isinstance(
            suites,
            list,
        ):
            raise EvaluationRuntimeError(
                "suites invalido."
            )

        policy_ids = {
            str(
                item.get(
                    "id"
                )
            )
            for item
            in layers
            if isinstance(
                item,
                dict,
            )
        }

        suite_ids = [
            str(
                item.get(
                    "id"
                )
            )
            for item
            in suites
            if isinstance(
                item,
                dict,
            )
        ]

        if len(
            suite_ids
        ) != len(
            set(
                suite_ids
            )
        ):
            raise EvaluationRuntimeError(
                "Suite IDs duplicados."
            )

        if set(
            suite_ids
        ) != policy_ids:
            raise EvaluationRuntimeError(
                "Suite registry diverge de evaluation_layers."
            )

        for suite in suites:

            if not isinstance(
                suite,
                dict,
            ):
                raise EvaluationRuntimeError(
                    "Suite invalida."
                )

            if (
                suite.get(
                    "owner"
                )
                != "dany"
            ):
                raise EvaluationRuntimeError(
                    "Suite sem owner Dany."
                )

            if (
                suite.get(
                    "thresholds"
                )
                is not None
            ):
                raise EvaluationRuntimeError(
                    "Threshold numerico foi definido antes da calibracao."
                )

            if (
                suite.get(
                    "execution_enabled"
                )
                is not False
            ):
                raise EvaluationRuntimeError(
                    "Suite execution habilitada."
                )

        execution = self.registry.get(
            "execution"
        )

        if not isinstance(
            execution,
            dict,
        ):
            raise EvaluationRuntimeError(
                "Registry execution invalido."
            )

        for key in (
            "suite_execution_enabled",
            "model_generation_enabled",
            "promptfoo_invocation_enabled",
            "dspy_invocation_enabled",
            "report_write_enabled",
            "promotion_execution_enabled",
            "training_execution_enabled",
            "weights_modified",
        ):
            if (
                execution.get(
                    key
                )
                is not False
            ):
                raise EvaluationRuntimeError(
                    f"Execution flag habilitada: {key}"
                )

        promotion = self.policy.get(
            "promotion_policy"
        )

        if not isinstance(
            promotion,
            dict,
        ):
            raise EvaluationRuntimeError(
                "Promotion policy invalida."
            )

        if (
            promotion.get(
                "thresholds_state"
            )
            != "not-calibrated"
        ):
            raise EvaluationRuntimeError(
                "Thresholds deveriam estar not-calibrated."
            )

        if (
            promotion.get(
                "candidate_checkpoint_available"
            )
            is not False
        ):
            raise EvaluationRuntimeError(
                "Candidate checkpoint apareceu indevidamente."
            )

    def list_suites(
        self,
    ) -> list[dict[str, Any]]:

        items = []

        for suite in self.registry[
            "suites"
        ]:

            items.append(
                {
                    "id": suite[
                        "id"
                    ],
                    "name": suite[
                        "name"
                    ],
                    "runner": suite[
                        "runner"
                    ],
                    "state": suite[
                        "state"
                    ],
                    "requires_model_execution": (
                        bool(
                            suite[
                                "requires_model_execution"
                            ]
                        )
                    ),
                    "requires_promptfoo": (
                        bool(
                            suite[
                                "requires_promptfoo"
                            ]
                        )
                    ),
                    "requires_dspy": (
                        bool(
                            suite[
                                "requires_dspy"
                            ]
                        )
                    ),
                    "execution_enabled": False,
                }
            )

        return items

    def suite(
        self,
        suite_id: str,
    ) -> dict[str, Any]:

        clean = str(
            suite_id
        ).strip()

        if not clean:
            raise EvaluationRuntimeError(
                "suite_id vazio."
            )

        for suite in self.registry[
            "suites"
        ]:
            if (
                suite[
                    "id"
                ]
                == clean
            ):
                return dict(
                    suite
                )

        raise EvaluationRuntimeError(
            f"Suite desconhecida: {clean}"
        )

    def baseline_status(
        self,
    ) -> dict[str, Any]:

        return {
            "manifest_id": (
                self.baseline[
                    "id"
                ]
            ),
            "subject_id": (
                self.baseline[
                    "subject_id"
                ]
            ),
            "id": (
                self.baseline[
                    "subject_id"
                ]
            ),
            "provider": (
                self.baseline[
                    "provider"
                ]
            ),
            "role": (
                self.baseline[
                    "role"
                ]
            ),
            "state": (
                self.baseline[
                    "state"
                ]
            ),
            "promotable_as_rachel_model": False,
            "metrics_available": (
                self.baseline[
                    "metrics_available"
                ]
            ),
            "suite_results_available": (
                self.baseline[
                    "suite_results_available"
                ]
            ),
            "model_execution_enabled": False,
        }

    def candidate_status(
        self,
    ) -> dict[str, Any]:

        return {
            # "id" preserva compatibilidade com 13/1B.
            "id": (
                self.candidate[
                    "model_id"
                ]
            ),

            # "model_id" e a chave explicita nova.
            "model_id": (
                self.candidate[
                    "model_id"
                ]
            ),

            "manifest_id": (
                self.candidate[
                    "id"
                ]
            ),

            "base_repository": (
                self.candidate[
                    "base_repository"
                ]
            ),

            "state": (
                self.candidate[
                    "state"
                ]
            ),

            "checkpoint_state": (
                self.candidate[
                    "checkpoint"
                ][
                    "state"
                ]
            ),

            # "available" preserva compatibilidade 13/1B.
            "available": (
                self.candidate[
                    "candidate_available"
                ]
            ),

            "candidate_available": (
                self.candidate[
                    "candidate_available"
                ]
            ),

            "checkpoint": dict(
                self.candidate[
                    "checkpoint"
                ]
            ),

            "training": dict(
                self.candidate[
                    "training"
                ]
            ),

            "evaluation": dict(
                self.candidate[
                    "evaluation"
                ]
            ),

            "promotion": dict(
                self.candidate[
                    "promotion"
                ]
            ),
        }

    def promotion_eligibility(
        self,
    ) -> dict[str, Any]:

        promotion = (
            self.policy[
                "promotion_policy"
            ]
        )

        checkpoint = (
            self.candidate[
                "checkpoint"
            ]
        )

        blockers: list[str] = []

        if (
            checkpoint[
                "state"
            ]
            != "created"
        ):
            blockers.append(
                "candidate-checkpoint-not-created"
            )

        if not self.candidate[
            "candidate_available"
        ]:
            blockers.append(
                "candidate-unavailable"
            )

        if not checkpoint[
            "verified"
        ]:
            blockers.append(
                "candidate-checkpoint-unverified"
            )

        if (
            self.candidate[
                "evaluation"
            ][
                "suite_results_available"
            ]
            is not True
        ):
            blockers.append(
                "evaluation-results-unavailable"
            )

        if (
            promotion[
                "thresholds_state"
            ]
            != "calibrated"
        ):
            blockers.append(
                "thresholds-not-calibrated"
            )

        if not promotion[
            "promotion_execution_enabled"
        ]:
            blockers.append(
                "promotion-execution-disabled"
            )

        return {
            "eligible": False,
            "state": "blocked",
            "candidate": (
                self.candidate[
                    "model_id"
                ]
            ),
            "blockers": sorted(
                set(
                    blockers
                )
            ),
            "automatic_promotion": False,
            "promotion_execution_enabled": False,
            "weights_modified": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        execution = (
            self.registry[
                "execution"
            ]
        )

        baseline = (
            self.baseline_status()
        )

        candidate = (
            self.candidate_status()
        )

        return {
            "member": {
                "id": "dany",
                "name": (
                    self.dany.get(
                        "nome",
                        "Dany",
                    )
                ),
                "sector": (
                    self.dany.get(
                        "setor",
                        "ST-Dany",
                    )
                ),
                "role": (
                    self.dany.get(
                        "cargo"
                    )
                ),
            },

            "evaluation": {
                "policy_id": (
                    self.policy[
                        "id"
                    ]
                ),
                "registry_id": (
                    self.registry[
                        "id"
                    ]
                ),
                "state": (
                    self.registry[
                        "state"
                    ]
                ),
                "suite_count": len(
                    self.registry[
                        "suites"
                    ]
                ),
            },

            # Alias legado 13/1B.
            "temporary_baseline": {
                "id": baseline[
                    "subject_id"
                ],
                "role": baseline[
                    "role"
                ],
                "promotable_as_rachel_model": (
                    baseline[
                        "promotable_as_rachel_model"
                    ]
                ),
            },

            # Contrato detalhado novo.
            "baseline": baseline,

            # Candidate preserva "id"/"available"
            # e adiciona model_id/manifest/checkpoint.
            "candidate": candidate,

            "suites": (
                self.list_suites()
            ),

            "promotion": (
                self.promotion_eligibility()
            ),

            "capabilities": {
                "read_policy": True,
                "read_baseline_manifest": True,
                "read_candidate_manifest": True,
                "list_suites": True,
                "describe_suite": True,
                "inspect_promotion_eligibility": True,

                "execute_suite": False,
                "execute_model": False,
                "invoke_promptfoo": False,
                "invoke_dspy": False,
                "write_report": False,
                "promote_model": False,
                "train_model": False,
            },

            "execution": {
                **execution,
                "automatic_promotion": False,
            },

            "read_only": True,
            "filesystem_mutation": False,
            "model_execution": False,
            "report_written": False,
            "promotion_executed": False,
            "training_execution_enabled": False,
            "weights_modified": False,
        }
