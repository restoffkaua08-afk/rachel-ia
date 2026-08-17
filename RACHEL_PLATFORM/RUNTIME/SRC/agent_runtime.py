from __future__ import annotations

import ast
import json

from pathlib import Path
from typing import Any


from runtime_paths import ROOT


class AgentRuntimeError(
    RuntimeError
):
    pass


class AgentRuntime:
    """
    Agent Runtime read-only.

    Esta camada NAO importa nem instancia:

    - TaskOrchestrator;
    - NedTaskPlanner;
    - TaskExecutor;
    - ToolCoordinator;
    - ApprovalStore.

    Ela inspeciona contratos e codigo-fonte
    estaticamente para evitar qualquer efeito.
    """

    def __init__(
        self,
        *,
        root: Path | None = None,
    ) -> None:

        self.root = Path(
            root
            or ROOT
        ).resolve()

        self.agent_root = (
            self.root
            / "RACHEL_AGENT"
        )

        self.platform = (
            self.root
            / "RACHEL_PLATFORM"
        )

        self.runtime_src = (
            self.platform
            / "RUNTIME"
            / "SRC"
        )

        self.platform_config = (
            self.platform
            / "CONFIG"
        )

        self.policy_path = (
            self.agent_root
            / "CONFIG"
            / "agent-runtime-policy.json"
        )

        self.tools_registry_path = (
            self.platform_config
            / "tools.registry.json"
        )

        self.approval_policy_path = (
            self.platform_config
            / "approval.policy.json"
        )

        self.autonomy_budget_policy_path = (
            self.agent_root
            / "CONFIG"
            / "autonomy-budget-policy.json"
        )

        self.execution_envelope_policy_path = (
            self.agent_root
            / "CONFIG"
            / "execution-envelope-policy.json"
        )

        self.policy = self._load_json(
            self.policy_path
        )

        self.tools_registry = self._load_json(
            self.tools_registry_path
        )

        self.approval_policy = self._load_json(
            self.approval_policy_path
        )

        self.autonomy_budget_policy = (
            self._load_json(
                self.autonomy_budget_policy_path
            )
        )

        self.execution_envelope_policy = (
            self._load_json(
                self.execution_envelope_policy_path
            )
        )

        self._validate_policy()

    @staticmethod
    def _load_json(
        path: Path,
    ) -> dict[str, Any]:

        if not path.is_file():
            raise AgentRuntimeError(
                f"Required JSON is missing: {path}"
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
            raise AgentRuntimeError(
                f"Invalid JSON: {path}"
            ) from error

        if not isinstance(
            value,
            dict,
        ):
            raise AgentRuntimeError(
                f"JSON root must be an object: {path}"
            )

        return value

    @staticmethod
    def _parse_python(
        path: Path,
    ) -> ast.Module:

        if not path.is_file():
            raise AgentRuntimeError(
                f"Python dependency missing: {path}"
            )

        try:
            source = path.read_text(
                encoding="utf-8-sig"
            )

            return ast.parse(
                source,
                filename=str(
                    path
                ),
            )
        except (
            OSError,
            SyntaxError,
        ) as error:
            raise AgentRuntimeError(
                f"Cannot inspect Python dependency: {path}"
            ) from error

    @staticmethod
    def _classes(
        module: ast.Module,
    ) -> dict[str, set[str]]:

        output: dict[
            str,
            set[str],
        ] = {}

        for node in module.body:

            if not isinstance(
                node,
                ast.ClassDef,
            ):
                continue

            methods = {
                item.name
                for item
                in node.body
                if isinstance(
                    item,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                )
            }

            output[
                node.name
            ] = methods

        return output

    @staticmethod
    def _literal_assignment(
        module: ast.Module,
        name: str,
    ) -> Any:

        for node in module.body:

            if isinstance(
                node,
                ast.Assign,
            ):

                for target in node.targets:

                    if (
                        isinstance(
                            target,
                            ast.Name,
                        )
                        and target.id == name
                    ):

                        try:
                            return ast.literal_eval(
                                node.value
                            )
                        except (
                            ValueError,
                            TypeError,
                        ) as error:
                            raise AgentRuntimeError(
                                f"{name} is not statically inspectable."
                            ) from error

            if (
                isinstance(
                    node,
                    ast.AnnAssign,
                )
                and isinstance(
                    node.target,
                    ast.Name,
                )
                and node.target.id == name
                and node.value is not None
            ):

                try:
                    return ast.literal_eval(
                        node.value
                    )
                except (
                    ValueError,
                    TypeError,
                ) as error:
                    raise AgentRuntimeError(
                        f"{name} is not statically inspectable."
                    ) from error

        raise AgentRuntimeError(
            f"Static assignment not found: {name}"
        )

    def _validate_policy(
        self,
    ) -> None:

        if (
            self.policy.get(
                "schema_version"
            )
            != 1
        ):
            raise AgentRuntimeError(
                "Agent policy schema is invalid."
            )

        if (
            self.policy.get(
                "stage"
            )
            != 14
        ):
            raise AgentRuntimeError(
                "Agent policy stage is invalid."
            )

        if (
            self.policy.get(
                "owner"
            )
            != "rachel"
        ):
            raise AgentRuntimeError(
                "Agent policy owner must be Rachel."
            )

        if (
            self.policy.get(
                "mode"
            )
            != "governed-autonomy"
        ):
            raise AgentRuntimeError(
                "Agent policy mode is invalid."
            )

        architecture = self.policy.get(
            "architecture"
        )

        if not isinstance(
            architecture,
            dict,
        ):
            raise AgentRuntimeError(
                "Agent architecture is missing."
            )

        expected_roles = {
            "coordinator": "rachel",
            "planner": "ned",
            "executor": "ned",
            "tool_coordinator": "arya",
            "authorization": "cyber",
        }

        for key, expected in (
            expected_roles.items()
        ):

            if (
                architecture.get(
                    key
                )
                != expected
            ):
                raise AgentRuntimeError(
                    f"Invalid Agent role: {key}"
                )

        execution = self.policy.get(
            "execution"
        )

        if not isinstance(
            execution,
            dict,
        ):
            raise AgentRuntimeError(
                "Agent execution contract is missing."
            )

        for key, value in (
            execution.items()
        ):

            if value is not False:
                raise AgentRuntimeError(
                    f"Execution unexpectedly enabled: {key}"
                )

        self._validate_budget_policy()
        self._validate_execution_envelope_policy()

    def _validate_budget_policy(
        self,
    ) -> None:

        policy = (
            self.autonomy_budget_policy
        )

        if (
            policy.get(
                "schema_version"
            )
            != 1
        ):
            raise AgentRuntimeError(
                "Autonomy budget schema is invalid."
            )

        if (
            policy.get(
                "owner"
            )
            != "rachel"
        ):
            raise AgentRuntimeError(
                "Autonomy budget owner must be Rachel."
            )

        if (
            policy.get(
                "state"
            )
            != "contract-defined"
        ):
            raise AgentRuntimeError(
                "Autonomy budget contract is not defined."
            )

        if (
            policy.get(
                "strategy"
            )
            != "explicit-per-goal-no-default"
        ):
            raise AgentRuntimeError(
                "Autonomy budget strategy is invalid."
            )

        if (
            policy.get(
                "defaults_allowed"
            )
            is not False
        ):
            raise AgentRuntimeError(
                "Autonomy budget defaults must be disabled."
            )

        if (
            policy.get(
                "goal_budget_required_before_execution"
            )
            is not True
        ):
            raise AgentRuntimeError(
                "Explicit goal budget must be required."
            )

        dimensions = (
            policy.get(
                "dimensions"
            )
        )

        if not isinstance(
            dimensions,
            list,
        ):
            raise AgentRuntimeError(
                "Autonomy budget dimensions are invalid."
            )

        expected = {
            "maximum_iterations",
            "maximum_tool_calls",
            "wall_clock_limit_seconds",
            "maximum_consecutive_failures",
        }

        actual = {
            str(
                item.get(
                    "id",
                    "",
                )
            )
            for item
            in dimensions
            if isinstance(
                item,
                dict,
            )
        }

        if actual != expected:
            raise AgentRuntimeError(
                "Autonomy budget dimensions are incomplete."
            )

        for item in dimensions:

            if (
                item.get(
                    "required"
                )
                is not True
            ):
                raise AgentRuntimeError(
                    "Every budget dimension must be required."
                )

            if (
                item.get(
                    "default"
                )
                is not None
            ):
                raise AgentRuntimeError(
                    "Budget dimensions cannot have defaults."
                )

    def _validate_execution_envelope_policy(
        self,
    ) -> None:

        policy = (
            self.execution_envelope_policy
        )

        if (
            policy.get(
                "schema_version"
            )
            != 1
        ):
            raise AgentRuntimeError(
                "Execution envelope schema is invalid."
            )

        if (
            policy.get(
                "owner"
            )
            != "rachel"
        ):
            raise AgentRuntimeError(
                "Execution envelope owner must be Rachel."
            )

        if (
            policy.get(
                "state"
            )
            != "contract-defined-execution-disabled"
        ):
            raise AgentRuntimeError(
                "Execution envelope state is invalid."
            )

        task_executor = (
            policy.get(
                "task_executor"
            )
        )

        if not isinstance(
            task_executor,
            dict,
        ):
            raise AgentRuntimeError(
                "Execution envelope task executor contract is missing."
            )

        if (
            task_executor.get(
                "existing_limit_parameter"
            )
            != "maximum_steps"
        ):
            raise AgentRuntimeError(
                "Execution envelope must reuse maximum_steps."
            )

        if (
            task_executor.get(
                "maximum_completed_steps_per_slice"
            )
            != 1
        ):
            raise AgentRuntimeError(
                "Execution slice must remain one completed step."
            )

        if (
            task_executor.get(
                "new_executor_required"
            )
            is not False
        ):
            raise AgentRuntimeError(
                "Execution envelope cannot require another executor."
            )

        execution = (
            policy.get(
                "execution"
            )
        )

        if not isinstance(
            execution,
            dict,
        ):
            raise AgentRuntimeError(
                "Execution envelope execution flags are missing."
            )

        for key, value in execution.items():

            if value is not False:
                raise AgentRuntimeError(
                    f"Execution envelope unexpectedly enabled: {key}"
                )

    def budgets(
        self,
    ) -> dict[str, Any]:

        policy = (
            self.autonomy_budget_policy
        )

        dimensions = [
            {
                "id": str(
                    item[
                        "id"
                    ]
                ),
                "required": bool(
                    item[
                        "required"
                    ]
                ),
                "default": (
                    item.get(
                        "default"
                    )
                ),
                "unit": str(
                    item[
                        "unit"
                    ]
                ),
            }
            for item
            in policy[
                "dimensions"
            ]
        ]

        return {
            "id": policy[
                "id"
            ],
            "state": policy[
                "state"
            ],
            "strategy": policy[
                "strategy"
            ],
            "contract_ready": True,
            "defaults_allowed": False,
            "explicit_per_goal_budget_required": True,
            "goal_budget_resolved": False,
            "goal_budget_materialized": False,
            "dimension_count": len(
                dimensions
            ),
            "dimensions": dimensions,
            "runtime_accounting_enabled": False,
            "budget_enforcement_enabled": False,
            "execution_enabled": False,
            "read_only": True,
        }

    def execution_envelope(
        self,
    ) -> dict[str, Any]:

        policy = (
            self.execution_envelope_policy
        )

        task_executor = (
            policy[
                "task_executor"
            ]
        )

        return {
            "id": policy[
                "id"
            ],
            "state": policy[
                "state"
            ],
            "contract_ready": True,
            "existing_limit_parameter": (
                task_executor[
                    "existing_limit_parameter"
                ]
            ),
            "maximum_completed_steps_per_slice": (
                task_executor[
                    "maximum_completed_steps_per_slice"
                ]
            ),
            "single_step_slice_required": True,
            "new_executor_required": False,
            "checkpoint_required": True,
            "observation_required": True,
            "state_revalidation_required": True,
            "authorization_revalidation_required": True,
            "budget_revalidation_required": True,
            "automatic_continue": False,
            "automatic_retry": False,
            "automatic_replan": False,
            "execution_enabled": False,
            "read_only": True,
        }

    def dependencies(
        self,
    ) -> dict[str, Any]:

        specs = [
            {
                "id": "task-runtime",
                "path": (
                    self.runtime_src
                    / "task_runtime.py"
                ),
                "classes": {
                    "TaskOrchestrator": {
                        "status",
                    },
                },
            },
            {
                "id": "task-planner",
                "path": (
                    self.runtime_src
                    / "task_planner.py"
                ),
                "classes": {
                    "PlanValidator": {
                        "validate",
                    },
                    "NedTaskPlanner": {
                        "create",
                    },
                    "PlanStore": set(),
                },
            },
            {
                "id": "task-executor",
                "path": (
                    self.runtime_src
                    / "task_executor.py"
                ),
                "classes": {
                    "TaskExecutor": {
                        "status",
                        "execute",
                    },
                },
            },
            {
                "id": "tools-runtime",
                "path": (
                    self.runtime_src
                    / "tools_runtime.py"
                ),
                "classes": {
                    "ToolCoordinator": {
                        "list_tools",
                        "inspect",
                        "invoke",
                    },
                },
            },
            {
                "id": "cyber-runtime",
                "path": (
                    self.runtime_src
                    / "security_runtime.py"
                ),
                "classes": {
                    "ApprovalStore": {
                        "request",
                        "decide",
                        "consume",
                        "list",
                    },
                },
            },
        ]

        items: list[
            dict[str, Any]
        ] = []

        for spec in specs:

            path = Path(
                spec[
                    "path"
                ]
            )

            item: dict[
                str,
                Any,
            ] = {
                "id": spec[
                    "id"
                ],
                "path": str(
                    path
                    .relative_to(
                        self.root
                    )
                ).replace(
                    "\\",
                    "/",
                ),
                "exists": (
                    path.is_file()
                ),
                "syntax_valid": False,
                "classes": {},
                "missing_classes": [],
                "missing_methods": [],
                "available": False,
            }

            if not path.is_file():

                items.append(
                    item
                )

                continue

            try:
                module = (
                    self._parse_python(
                        path
                    )
                )

                item[
                    "syntax_valid"
                ] = True

                classes = self._classes(
                    module
                )

                for class_name, required_methods in (
                    spec[
                        "classes"
                    ].items()
                ):

                    actual_methods = (
                        classes.get(
                            class_name
                        )
                    )

                    if actual_methods is None:

                        item[
                            "missing_classes"
                        ].append(
                            class_name
                        )

                        continue

                    missing_methods = sorted(
                        required_methods
                        - actual_methods
                    )

                    item[
                        "classes"
                    ][
                        class_name
                    ] = {
                        "present": True,
                        "required_methods": sorted(
                            required_methods
                        ),
                        "missing_methods": (
                            missing_methods
                        ),
                    }

                    for method in (
                        missing_methods
                    ):

                        item[
                            "missing_methods"
                        ].append(
                            f"{class_name}.{method}"
                        )

                item[
                    "available"
                ] = (
                    item[
                        "syntax_valid"
                    ]
                    and not item[
                        "missing_classes"
                    ]
                    and not item[
                        "missing_methods"
                    ]
                )

            except AgentRuntimeError:

                item[
                    "syntax_valid"
                ] = False

            items.append(
                item
            )

        available_count = sum(
            1
            for item
            in items
            if item[
                "available"
            ]
        )

        return {
            "inspection_mode": "static-ast",
            "operational_imports_performed": False,
            "dependency_count": len(
                items
            ),
            "available_count": (
                available_count
            ),
            "all_available": (
                available_count
                == len(
                    items
                )
            ),
            "items": items,
        }

    def effect_policies(
        self,
    ) -> dict[str, Any]:

        path = (
            self.runtime_src
            / "task_planner.py"
        )

        module = (
            self._parse_python(
                path
            )
        )

        raw = (
            self._literal_assignment(
                module,
                "EFFECTS",
            )
        )

        if not isinstance(
            raw,
            dict,
        ):
            raise AgentRuntimeError(
                "Task Planner EFFECTS must be a dictionary."
            )

        items: list[
            dict[str, Any]
        ] = []

        for effect, value in (
            raw.items()
        ):

            if (
                not isinstance(
                    effect,
                    str,
                )
                or not isinstance(
                    value,
                    tuple,
                )
                or len(
                    value
                )
                != 2
            ):
                raise AgentRuntimeError(
                    "Invalid Task Planner EFFECTS contract."
                )

            risk = str(
                value[
                    0
                ]
            )

            approval_required = (
                value[
                    1
                ]
            )

            if not isinstance(
                approval_required,
                bool,
            ):
                raise AgentRuntimeError(
                    "Invalid approval flag in EFFECTS."
                )

            items.append(
                {
                    "effect": effect,
                    "risk": risk,
                    "approval_required": (
                        approval_required
                    ),
                }
            )

        items.sort(
            key=lambda item: (
                item[
                    "effect"
                ]
            )
        )

        return {
            "source": (
                "task_planner.EFFECTS"
            ),
            "static_inspection": True,
            "count": len(
                items
            ),
            "items": items,
        }

    def authority_map(
        self,
    ) -> dict[str, Any]:

        effect_contract = (
            self.effect_policies()
        )

        effect_map = {
            item[
                "effect"
            ]: item
            for item
            in effect_contract[
                "items"
            ]
        }

        tools = self.tools_registry.get(
            "tools"
        )

        if not isinstance(
            tools,
            list,
        ):
            raise AgentRuntimeError(
                "Tools registry has no tools array."
            )

        registered_tools: list[
            dict[str, Any]
        ] = []

        unknown_effects: list[
            str
        ] = []

        for raw_tool in tools:

            if not isinstance(
                raw_tool,
                dict,
            ):
                raise AgentRuntimeError(
                    "Invalid tool registry entry."
                )

            name = str(
                raw_tool.get(
                    "name",
                    "",
                )
            )

            member = str(
                raw_tool.get(
                    "member",
                    "",
                )
            )

            effect = str(
                raw_tool.get(
                    "effect",
                    "",
                )
            )

            policy = (
                effect_map.get(
                    effect
                )
            )

            if policy is None:

                unknown_effects.append(
                    effect
                )

                risk = "unknown"
                approval_required = True

            else:

                risk = str(
                    policy[
                        "risk"
                    ]
                )

                approval_required = bool(
                    policy[
                        "approval_required"
                    ]
                )

            registered_tools.append(
                {
                    "name": name,
                    "member": member,
                    "effect": effect,
                    "risk": risk,
                    "approval_required": (
                        approval_required
                    ),
                }
            )

        authority_policy = (
            self.policy[
                "authority"
            ]
        )

        blockers: list[
            str
        ] = []

        if (
            self.tools_registry.get(
                "default_policy"
            )
            != "deny"
        ):
            blockers.append(
                "tool-registry-not-deny-by-default"
            )

        if (
            authority_policy.get(
                "deny_by_default"
            )
            is not True
        ):
            blockers.append(
                "agent-policy-not-deny-by-default"
            )

        if (
            authority_policy.get(
                "cyber_authorization_required"
            )
            is not True
        ):
            blockers.append(
                "cyber-authorization-not-required"
            )

        if (
            self.approval_policy.get(
                "single_use"
            )
            is not True
        ):
            blockers.append(
                "approvals-not-single-use"
            )

        if (
            self.approval_policy.get(
                "bind_tool"
            )
            is not True
        ):
            blockers.append(
                "approvals-not-bound-to-tool"
            )

        if (
            self.approval_policy.get(
                "bind_arguments"
            )
            is not True
        ):
            blockers.append(
                "approvals-not-bound-to-arguments"
            )

        if (
            self.approval_policy.get(
                "store_argument_values"
            )
            is not False
        ):
            blockers.append(
                "approval-argument-values-stored"
            )

        if (
            authority_policy.get(
                "global_approve_all_allowed"
            )
            is not False
        ):
            blockers.append(
                "global-approve-all-not-forbidden"
            )

        if (
            authority_policy.get(
                "self_approval_allowed"
            )
            is not False
        ):
            blockers.append(
                "self-approval-not-forbidden"
            )

        if unknown_effects:

            blockers.append(
                "unknown-tool-effects"
            )

        blockers = sorted(
            set(
                blockers
            )
        )

        return {
            "coordinator": "rachel",
            "planner": "ned",
            "executor": "ned",
            "tools": "arya",
            "authorization": "cyber",
            "default_tool_policy": (
                self.tools_registry.get(
                    "default_policy"
                )
            ),
            "approval_policy": {
                "single_use": (
                    self.approval_policy.get(
                        "single_use"
                    )
                ),
                "bind_tool": (
                    self.approval_policy.get(
                        "bind_tool"
                    )
                ),
                "bind_arguments": (
                    self.approval_policy.get(
                        "bind_arguments"
                    )
                ),
                "store_argument_values": (
                    self.approval_policy.get(
                        "store_argument_values"
                    )
                ),
            },
            "effect_policy_count": (
                effect_contract[
                    "count"
                ]
            ),
            "effect_policies": (
                effect_contract[
                    "items"
                ]
            ),
            "tool_count": len(
                registered_tools
            ),
            "registered_tools": (
                registered_tools
            ),
            "unknown_effects": sorted(
                set(
                    unknown_effects
                )
            ),
            "ready": not blockers,
            "blockers": blockers,
            "blocker_count": len(
                blockers
            ),
            "inspection_only": True,
            "approval_created": False,
            "approval_consumed": False,
        }

    @staticmethod
    def _phase(
        phase_id: str,
        blockers: list[str],
    ) -> dict[str, Any]:

        clean = sorted(
            set(
                blockers
            )
        )

        return {
            "id": phase_id,
            "ready": not clean,
            "state": (
                "ready"
                if not clean
                else "blocked"
            ),
            "blockers": clean,
            "blocker_count": len(
                clean
            ),
        }

    def readiness(
        self,
    ) -> dict[str, Any]:

        dependencies = (
            self.dependencies()
        )

        authority = (
            self.authority_map()
        )

        policy_blockers: list[
            str
        ] = []

        if (
            self.policy.get(
                "state"
            )
            != "contract-defined-execution-disabled"
        ):
            policy_blockers.append(
                "unexpected-policy-state"
            )

        dependency_blockers: list[
            str
        ] = []

        if not dependencies[
            "all_available"
        ]:

            dependency_blockers.append(
                "runtime-dependencies-incomplete"
            )

        authority_blockers = list(
            authority[
                "blockers"
            ]
        )

        budget_blockers: list[
            str
        ] = []

        budget_contract = (
            self.budgets()
        )

        execution_envelope = (
            self.execution_envelope()
        )

        if (
            budget_contract.get(
                "contract_ready"
            )
            is not True
        ):
            budget_blockers.append(
                "autonomy-budget-contract-not-ready"
            )

        if (
            execution_envelope.get(
                "contract_ready"
            )
            is not True
        ):
            budget_blockers.append(
                "execution-envelope-contract-not-ready"
            )

        execution = self.policy[
            "execution"
        ]

        execution_blockers: list[
            str
        ] = []

        checks = [
            (
                "agent_runtime_execution_enabled",
                "agent-runtime-execution-disabled",
            ),
            (
                "agent_loop_execution_enabled",
                "agent-loop-execution-disabled",
            ),
            (
                "goal_decomposition_enabled",
                "goal-decomposition-disabled",
            ),
            (
                "task_execution_enabled_by_agent",
                "task-execution-by-agent-disabled",
            ),
            (
                "tool_execution_enabled_by_agent",
                "tool-execution-by-agent-disabled",
            ),
        ]

        for key, blocker in checks:

            if (
                execution.get(
                    key
                )
                is not True
            ):

                execution_blockers.append(
                    blocker
                )

        phases = [
            self._phase(
                "contract-integrity",
                policy_blockers,
            ),
            self._phase(
                "runtime-dependencies",
                dependency_blockers,
            ),
            self._phase(
                "authority-boundaries",
                authority_blockers,
            ),
            self._phase(
                "autonomy-budgets",
                budget_blockers,
            ),
            self._phase(
                "agent-execution",
                execution_blockers,
            ),
        ]

        blockers = sorted(
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
            1
            for phase
            in phases
            if phase[
                "ready"
            ]
        )

        return {
            "state": (
                "ready"
                if ready_count
                == len(
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
            "blockers": blockers,
            "blocker_count": len(
                blockers
            ),
            "execution_enabled": False,
        }

    def capabilities(
        self,
    ) -> dict[str, bool]:

        return {
            "read_status": True,
            "inspect_authority": True,
            "inspect_dependencies": True,
            "inspect_readiness": True,
            "inspect_blockers": True,
            "inspect_tool_registry": True,
            "execute_goal": False,
            "decompose_goal": False,
            "create_task_plan": False,
            "execute_task_plan": False,
            "invoke_tool": False,
            "request_approval": False,
            "consume_approval": False,
            "browser_navigation": False,
            "background_loop": False,
            "unattended_execution": False,
            "external_publish": False,
            "credential_use": False,
            "self_modification": False,
            "self_update": False,
            "train_model": False,
        }

    def blockers(
        self,
    ) -> list[str]:

        return list(
            self.readiness()[
                "blockers"
            ]
        )

    def status(
        self,
    ) -> dict[str, Any]:

        dependencies = (
            self.dependencies()
        )

        authority = (
            self.authority_map()
        )

        readiness = (
            self.readiness()
        )

        return {
            "id": (
                "rachel-agent-runtime-read-only-v1"
            ),
            "owner": "rachel",
            "mode": "governed-autonomy",
            "state": "inspection-only",
            "available": True,
            "read_only": True,
            "filesystem_mutation": False,
            "database_access": False,
            "model_access": False,
            "operational_runtime_imports": False,
            "goal_execution": False,
            "task_execution": False,
            "tool_execution": False,
            "approval_creation": False,
            "approval_consumption": False,
            "browser_execution": False,
            "background_execution": False,
            "unattended_execution": False,
            "external_effect": False,
            "self_modification": False,
            "training_execution": False,
            "weights_modified": False,
            "dependencies": {
                "count": (
                    dependencies[
                        "dependency_count"
                    ]
                ),
                "available": (
                    dependencies[
                        "available_count"
                    ]
                ),
                "all_available": (
                    dependencies[
                        "all_available"
                    ]
                ),
            },
            "authority": {
                "ready": (
                    authority[
                        "ready"
                    ]
                ),
                "tool_count": (
                    authority[
                        "tool_count"
                    ]
                ),
                "effect_policy_count": (
                    authority[
                        "effect_policy_count"
                    ]
                ),
                "default_policy": (
                    authority[
                        "default_tool_policy"
                    ]
                ),
            },
            "browser": {
                "state": (
                    self.policy[
                        "browser"
                    ][
                        "integration_state"
                    ]
                ),
                "execution_enabled": False,
            },
            "budgets": {
                "contract_ready": (
                    self.budgets()[
                        "contract_ready"
                    ]
                ),
                "strategy": (
                    self.budgets()[
                        "strategy"
                    ]
                ),
                "dimension_count": (
                    self.budgets()[
                        "dimension_count"
                    ]
                ),
                "defaults_allowed": False,
                "goal_budget_resolved": False,
                "execution_enabled": False,
            },
            "execution_envelope": {
                "contract_ready": (
                    self.execution_envelope()[
                        "contract_ready"
                    ]
                ),
                "maximum_completed_steps_per_slice": (
                    self.execution_envelope()[
                        "maximum_completed_steps_per_slice"
                    ]
                ),
                "automatic_continue": False,
                "execution_enabled": False,
            },
            "readiness": {
                "ready": (
                    readiness[
                        "ready"
                    ]
                ),
                "state": (
                    readiness[
                        "state"
                    ]
                ),
                "phase_count": (
                    readiness[
                        "phase_count"
                    ]
                ),
                "ready_phase_count": (
                    readiness[
                        "ready_phase_count"
                    ]
                ),
                "blocked_phase_count": (
                    readiness[
                        "blocked_phase_count"
                    ]
                ),
                "blocker_count": (
                    readiness[
                        "blocker_count"
                    ]
                ),
                "blockers": (
                    readiness[
                        "blockers"
                    ]
                ),
            },
            "capabilities": (
                self.capabilities()
            ),
        }
