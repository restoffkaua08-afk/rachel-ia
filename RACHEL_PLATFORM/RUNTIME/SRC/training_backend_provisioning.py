from __future__ import annotations

import json
import re
import tomllib

from pathlib import Path
from typing import Any


from runtime_paths import (
    CONFIG,
    PLATFORM,
)


from model_runtime import (
    RachelModelRuntime,
)

from samwell_runtime import (
    SamwellRuntime,
)


SCHEMA_VERSION = 1


class TrainingBackendProvisioningError(
    RuntimeError
):
    pass


class TrainingBackendProvisioning:

    def __init__(
        self,
        *,
        contract_path: Path | None = None,
        samwell: SamwellRuntime | None = None,
        model_runtime: Any | None = None,
    ) -> None:

        self.contract_path = (
            Path(
                contract_path
                or (
                    CONFIG
                    / "training-backend-provisioning.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.contract = (
            self._load()
        )

        self.samwell = (
            samwell
            or SamwellRuntime()
        )

        self.model_runtime = (
            model_runtime
            or RachelModelRuntime()
        )

        self._cross_validate()

    def _load(
        self,
    ) -> dict[str, Any]:

        if not self.contract_path.is_file():
            raise TrainingBackendProvisioningError(
                "Training backend contract ausente."
            )

        try:
            value = json.loads(
                self.contract_path.read_text(
                    encoding="utf-8-sig"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise TrainingBackendProvisioningError(
                "Training backend contract invalido."
            ) from error

        if (
            not isinstance(
                value,
                dict,
            )
            or value.get(
                "schema_version"
            )
            != SCHEMA_VERSION
            or value.get(
                "owner"
            )
            != "samwell"
        ):
            raise TrainingBackendProvisioningError(
                "Contrato de provisioning invalido."
            )

        return value

    def _cross_validate(
        self,
    ) -> None:

        model = (
            self.model_runtime
            .status()
        )

        if (
            model[
                "model"
            ][
                "model_id"
            ]
            != self.contract[
                "model"
            ][
                "model_id"
            ]
        ):
            raise TrainingBackendProvisioningError(
                "Model ID divergente."
            )

        if (
            model[
                "model"
            ][
                "base_model_repository"
            ]
            != self.contract[
                "model"
            ][
                "base_repository"
            ]
        ):
            raise TrainingBackendProvisioningError(
                "Base model divergente."
            )

        samwell_training = (
            self.samwell
            .catalog[
                "environments"
            ][
                "training"
            ]
        )

        if (
            samwell_training[
                "python_relative"
            ]
            != self.contract[
                "environment"
            ][
                "python_relative"
            ]
        ):
            raise TrainingBackendProvisioningError(
                "Training Runtime divergente."
            )

    @staticmethod
    def _normalize_requirement(
        value: str,
    ) -> str:

        return re.sub(
            r"\s+",
            "",
            value,
        ).casefold()

    def litgpt_source_status(
        self,
    ) -> dict[str, Any]:

        source = (
            PLATFORM
            / "ORGAOS"
            / "litgpt"
            / "fonte"
        ).resolve()

        pyproject = (
            source
            / "pyproject.toml"
        )

        if not pyproject.is_file():
            return {
                "available": False,
                "source": str(source),
                "version": None,
                "version_match": False,
                "python_requirement_match": False,
                "core_constraints_match": False,
            }

        try:
            value = tomllib.loads(
                pyproject.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            tomllib.TOMLDecodeError,
        ) as error:
            raise TrainingBackendProvisioningError(
                "LitGPT pyproject invalido."
            ) from error

        project = value.get(
            "project",
            {},
        )

        dependencies = project.get(
            "dependencies",
            [],
        )

        normalized_actual = {
            self._normalize_requirement(
                str(item)
            )
            for item
            in dependencies
        }

        normalized_expected = {
            self._normalize_requirement(
                str(item)
            )
            for item
            in self.contract[
                "litgpt"
            ][
                "core_constraints"
            ]
        }

        actual_version = str(
            project.get(
                "version"
            )
            or ""
        )

        actual_python = str(
            project.get(
                "requires-python"
            )
            or ""
        )

        expected_version = (
            self.contract[
                "litgpt"
            ][
                "version"
            ]
        )

        expected_python = (
            self.contract[
                "litgpt"
            ][
                "requires_python"
            ]
        )

        missing_constraints = sorted(
            normalized_expected
            - normalized_actual
        )

        return {
            "available": True,
            "source": str(source),
            "version": actual_version,
            "expected_version": expected_version,
            "version_match": (
                actual_version
                == expected_version
            ),
            "python_requirement": actual_python,
            "expected_python_requirement": expected_python,
            "python_requirement_match": (
                actual_python
                == expected_python
            ),
            "core_constraints_match": (
                len(
                    missing_constraints
                )
                == 0
            ),
            "missing_constraints": (
                missing_constraints
            ),
        }

    def plan(
        self,
    ) -> dict[str, Any]:

        host = self.contract[
            "target_host"
        ]

        environment = self.contract[
            "environment"
        ]

        source_weights = self.contract[
            "source_weights"
        ]

        checkpoint = self.contract[
            "checkpoint"
        ]

        model = (
            self.model_runtime
            .status()
        )

        samwell = (
            self.samwell
            .provision_plan(
                "training"
            )
        )

        litgpt = (
            self.litgpt_source_status()
        )

        blockers: list[str] = []

        if (
            host[
                "selection_state"
            ]
            != "selected"
        ):
            blockers.append(
                "training-host-unselected"
            )

        if (
            environment[
                "creation_state"
            ]
            != "created"
        ):
            blockers.append(
                "training-environment-not-created"
            )

        if not samwell[
            "mode_ready"
        ]:
            blockers.append(
                "training-dependencies-unavailable"
            )

        if not host[
            "exact_versions_locked"
        ]:
            blockers.append(
                "training-versions-not-locked"
            )

        if (
            source_weights[
                "state"
            ]
            != "downloaded"
        ):
            blockers.append(
                "base-weights-not-downloaded"
            )

        if (
            checkpoint[
                "state"
            ]
            != "created"
        ):
            blockers.append(
                "litgpt-checkpoint-not-created"
            )

        if not model[
            "training_preflight"
        ][
            "training_data_available"
        ]:
            blockers.append(
                "training-data-unavailable"
            )

        if not self.contract[
            "security"
        ][
            "training_execution_enabled"
        ]:
            blockers.append(
                "training-execution-disabled"
            )

        if (
            litgpt[
                "available"
            ]
            and (
                not litgpt[
                    "version_match"
                ]
                or not litgpt[
                    "python_requirement_match"
                ]
                or not litgpt[
                    "core_constraints_match"
                ]
            )
        ):
            blockers.append(
                "litgpt-source-contract-mismatch"
            )

        phases = [
            {
                "order": index,
                "id": phase[
                    "id"
                ],
                "effect": phase[
                    "effect"
                ],
                "mutation": bool(
                    phase[
                        "mutation"
                    ]
                ),
                "requires_cyber": bool(
                    phase[
                        "requires_cyber"
                    ]
                ),
                "state": "blocked",
            }
            for index, phase
            in enumerate(
                self.contract[
                    "provisioning_phases"
                ],
                start=1,
            )
        ]

        return {
            "id": self.contract[
                "id"
            ],
            "owner": "samwell",
            "state": (
                "blocked"
                if blockers
                else "ready-for-explicit-provisioning"
            ),
            "target_host": host,
            "environment": environment,
            "litgpt_source": litgpt,
            "samwell_training_plan": samwell,
            "phases": phases,
            "blockers": sorted(
                set(
                    blockers
                )
            ),
            "provisioning_execution_enabled": False,
            "command_generation_enabled": False,
            "training_execution_enabled": False,
            "weights_modified": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        plan = self.plan()

        return {
            "contract": {
                "id": self.contract[
                    "id"
                ],
                "owner": self.contract[
                    "owner"
                ],
                "state": self.contract[
                    "state"
                ],
            },

            "model": self.contract[
                "model"
            ],

            "strategy": self.contract[
                "training_strategy"
            ],

            "litgpt": self.contract[
                "litgpt"
            ],

            "environment": self.contract[
                "environment"
            ],

            "target_host": self.contract[
                "target_host"
            ],

            "hardware_policy": self.contract[
                "hardware_policy"
            ],

            "artifacts": {
                "source_weights": self.contract[
                    "source_weights"
                ],
                "checkpoint": self.contract[
                    "checkpoint"
                ],
                "outputs": self.contract[
                    "outputs"
                ],
            },

            "security": self.contract[
                "security"
            ],

            "plan": plan,

            "contract_only": True,
            "provisioning_execution_enabled": False,
            "command_generation_enabled": False,
            "automatic_install": False,
            "automatic_download": False,
            "automatic_conversion": False,
            "automatic_training": False,
            "training_execution_enabled": False,
            "checkpoint_created": False,
            "weights_modified": False,
        }
