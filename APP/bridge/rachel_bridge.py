from __future__ import annotations

import json
import os
import sys

from dataclasses import asdict
from pathlib import Path
from typing import Any


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(
        encoding="utf-8"
    )


if getattr(
    sys,
    "frozen",
    False,
):
    DEFAULT_ROOT = Path(
        getattr(
            sys,
            "_MEIPASS",
            Path(
                sys.executable
            ).resolve().parent,
        )
    ).resolve()
else:
    DEFAULT_ROOT = (
        Path(__file__)
        .resolve()
        .parents[2]
    )

ROOT = Path(
    os.environ.get(
        "RACHEL_RUNTIME_ROOT"
    )
    or DEFAULT_ROOT
).expanduser().resolve()

RUNTIME_SRC = (
    ROOT
    / "RACHEL_PLATFORM"
    / "RUNTIME"
    / "SRC"
)

CORE_SRC = (
    ROOT
    / "RACHEL_CORE"
    / "src"
)


for source in (
    RUNTIME_SRC,
    CORE_SRC,
):
    value = str(source)

    if value not in sys.path:
        sys.path.insert(
            0,
            value,
        )


from runtime_paths import STATE

os.environ.setdefault(
    "RACHEL_HOME",
    str(STATE / "core"),
)

os.environ.setdefault(
    "RACHEL_MODEL_PROVIDER",
    "openai-compatible",
)

os.environ.setdefault(
    "RACHEL_MODEL_NAME",
    "qwen3:1.7b",
)

os.environ.setdefault(
    "RACHEL_MODEL_BASE_URL",
    "http://127.0.0.1:11434/v1",
)

os.environ.setdefault(
    "RACHEL_MODEL_TIMEOUT_SECONDS",
    "120",
)


def required_text(
    payload: dict[str, Any],
    key: str,
    maximum: int = 50_000,
) -> str:
    value = payload.get(key)

    if not isinstance(value, str):
        raise ValueError(
            f"{key} must be a string"
        )

    value = value.strip()

    if not value:
        raise ValueError(
            f"{key} cannot be empty"
        )

    if len(value) > maximum:
        raise ValueError(
            f"{key} exceeds {maximum} characters"
        )

    return value


def optional_text(
    payload: dict[str, Any],
    key: str,
    maximum: int = 500,
) -> str | None:
    value = payload.get(key)

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            f"{key} must be string or null"
        )

    value = value.strip()

    if not value:
        return None

    if len(value) > maximum:
        raise ValueError(
            f"{key} exceeds {maximum} characters"
        )

    return value


def required_object(
    payload: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    value = payload.get(
        key
    )

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"{key} must be an object"
        )

    return value


def optional_object(
    payload: dict[str, Any],
    key: str,
) -> dict[str, Any] | None:
    value = payload.get(
        key
    )

    if value is None:
        return None

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            f"{key} must be an object or null"
        )

    return value


def bounded_int(
    payload: dict[str, Any],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    value = payload.get(
        key,
        default,
    )

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
    ):
        raise ValueError(
            f"{key} must be an integer"
        )

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def health_snapshot() -> dict[str, Any]:
    from supervisor import (
        inspect_organ,
        organs_from_registry,
    )

    organs = [
        asdict(
            inspect_organ(item)
        )
        for item in organs_from_registry()
    ]

    available = sum(
        item["status"] == "available"
        for item in organs
    )

    return {
        "total": len(organs),
        "available": available,
        "failed": len(organs) - available,
        "items": organs,
    }


def dashboard() -> dict[str, Any]:
    from bran_cognitive import CognitiveMemory
    from cognitive_runtime import NedCognitiveBridge
    from security_panel import SecurityPanel
    from voice_diagnostics import doctor
    from learning_engine_runtime import (
        LearningDatasetReviewService,
    )
    from learning_export_runtime import (
        LearningDatasetExportService,
    )
    from training_dataset_runtime import (
        TrainingDatasetService,
    )
    from training_preflight_runtime import (
        TrainingPreflight,
    )
    from model_runtime import (
        RachelModelRuntime,
    )
    from training_run_runtime import (
        TrainingRunRuntime,
    )
    from training_execution_gate import (
        TrainingExecutionGate,
    )
    from samwell_runtime import (
        SamwellRuntime,
    )
    from training_backend_provisioning import (
        TrainingBackendProvisioning,
    )
    from evaluation_runtime import (
        EvaluationRuntime,
    )
    from evaluation_plan_runtime import (
        EvaluationPlanRuntime,
    )
    from agent_runtime import (
        AgentRuntime,
    )

    return {
        "runtime": NedCognitiveBridge().status(),
        "cyber": SecurityPanel().snapshot(
            status="pending",
            limit=50,
        ),
        "memory": CognitiveMemory().status(),
        "voice": doctor(
            include_hardware=False
        ),
        "learning_datasets": (
            LearningDatasetReviewService()
            .status()
        ),
        "learning_exports": (
            LearningDatasetExportService()
            .status()
        ),
        "training_datasets": (
            TrainingDatasetService()
            .status()
        ),
        "training_preflight": (
            TrainingPreflight()
            .report(
                limit=50
            )
        ),
        "rachel_model": (
            RachelModelRuntime()
            .status()
        ),
        "training_run": (
            TrainingRunRuntime()
            .status()
        ),
        "training_execution_gate": (
            TrainingExecutionGate()
            .status()
        ),
        "samwell": (
            SamwellRuntime()
            .status()
        ),
        "training_backend_provisioning": (
            TrainingBackendProvisioning()
            .status()
        ),
        "evaluation": (
            EvaluationRuntime()
            .status()
        ),
        "evaluation_plan": (
            EvaluationPlanRuntime()
            .status()
        ),
        "agent": (
            AgentRuntime()
            .status()
        ),
        "health": health_snapshot(),
    }


def execute(
    payload: dict[str, Any],
) -> dict[str, Any]:

    action = payload.get(
        "action"
    )


    if action == "runtime_paths":
        from runtime_paths import (
            describe_paths,
        )

        return describe_paths()


    if action == "document_engine_status":
        from docling_adapter import (
            status,
        )

        return status()


    if action == "dashboard":
        return dashboard()


    if action == "status":
        from cognitive_runtime import NedCognitiveBridge

        return NedCognitiveBridge().status()


    if action == "chat":
        from cognitive_runtime import NedCognitiveBridge

        return NedCognitiveBridge().chat(
            required_text(
                payload,
                "content",
            ),
            optional_text(
                payload,
                "conversation_id",
            ),
        )


    if action == "assist":
        from cognitive_runtime import NedCognitiveBridge

        return NedCognitiveBridge().assist(
            required_text(
                payload,
                "content",
            ),
            optional_text(
                payload,
                "conversation_id",
            ),
            approval_id=optional_text(
                payload,
                "approval_id",
                maximum=200,
            ),
        )


    if action == "security_snapshot":
        from security_panel import SecurityPanel

        return SecurityPanel().snapshot(
            status="pending",
            limit=bounded_int(
                payload,
                "limit",
                50,
                1,
                100,
            ),
        )


    if action == "security_decide":
        from security_panel import SecurityPanel

        approval_id = required_text(
            payload,
            "approval_id",
            200,
        )

        allow = payload.get(
            "allow"
        )

        if not isinstance(
            allow,
            bool,
        ):
            raise ValueError(
                "allow must be boolean"
            )

        confirmation = required_text(
            payload,
            "confirmation",
            500,
        )

        panel = SecurityPanel()

        card = panel.show(
            approval_id
        )

        mode = (
            "approve"
            if allow
            else "deny"
        )

        expected = (
            card
            .get("confirmation", {})
            .get(mode)
        )

        if (
            not isinstance(
                expected,
                str,
            )
            or confirmation != expected
        ):
            raise ValueError(
                "Explicit Cyber confirmation does not match"
            )

        return panel.decide(
            approval_id,
            allow,
        )


    if action == "learning_status":
        from rachel_core.bootstrap import build_container

        return (
            build_container()
            .learning
            .status()
        )


    if action == "learning_recent":
        from rachel_core.bootstrap import build_container

        limit = bounded_int(
            payload,
            "limit",
            20,
            1,
            100,
        )

        learning = (
            build_container()
            .learning
        )

        return {
            "status": (
                learning.status()
            ),
            "experiences": (
                learning.recent(
                    limit
                )
            ),
            "events": (
                learning.recent_events(
                    limit
                )
            ),
            "feedback": (
                learning.recent_feedback(
                    limit
                )
            ),
        }


    if action == "learning_feedback":
        from rachel_core.bootstrap import build_container

        experience_id = required_text(
            payload,
            "experience_id",
            200,
        )

        verdict = required_text(
            payload,
            "verdict",
            30,
        ).casefold()

        if verdict not in {
            "accepted",
            "rejected",
            "corrected",
        }:
            raise ValueError(
                "verdict must be accepted, rejected or corrected"
            )

        correction_text = optional_text(
            payload,
            "correction_text",
            maximum=50_000,
        )

        note = optional_text(
            payload,
            "note",
            maximum=5_000,
        )

        learning = (
            build_container()
            .learning
        )

        feedback_id = (
            learning
            .capture_feedback(
                experience_id=(
                    experience_id
                ),
                verdict=verdict,
                correction_text=(
                    correction_text
                ),
                note=note,
                metadata={
                    "source": (
                        "desktop-bridge"
                    ),
                    "explicit_user_feedback": True,
                },
            )
        )

        return {
            "feedback_id": (
                feedback_id
            ),
            "experience_id": (
                experience_id
            ),
            "verdict": verdict,
            "automatic_training": False,
        }


    if action == "learning_dataset_status":
        from learning_engine_runtime import (
            LearningDatasetReviewService,
        )

        return (
            LearningDatasetReviewService()
            .status(
                bounded_int(
                    payload,
                    "limit",
                    100,
                    1,
                    200,
                )
            )
        )


    if action == "learning_dataset_versions":
        from learning_engine_runtime import (
            LearningDatasetReviewService,
        )

        service = (
            LearningDatasetReviewService()
        )

        dataset_type = optional_text(
            payload,
            "dataset_type",
            maximum=100,
        )

        return {
            "items": (
                service.factory
                .list_versions(
                    dataset_type=(
                        dataset_type
                    ),
                    limit=bounded_int(
                        payload,
                        "limit",
                        50,
                        1,
                        200,
                    ),
                )
            ),
            "automatic_training": False,
            "automatic_promotion": False,
            "external_export": False,
        }


    if action == "learning_dataset_review":
        from learning_engine_runtime import (
            LearningDatasetReviewService,
        )

        version_id = required_text(
            payload,
            "version_id",
            300,
        )

        return (
            LearningDatasetReviewService()
            .review(
                version_id
            )
        )


    if action == "learning_dataset_request_export":
        from learning_engine_runtime import (
            LearningDatasetReviewService,
        )

        version_id = required_text(
            payload,
            "version_id",
            300,
        )

        return (
            LearningDatasetReviewService()
            .request_export(
                version_id
            )
        )


    if action == "learning_dataset_approve_export":
        from learning_engine_runtime import (
            LearningDatasetReviewService,
        )

        version_id = required_text(
            payload,
            "version_id",
            300,
        )

        approval_id = required_text(
            payload,
            "approval_id",
            200,
        )

        return (
            LearningDatasetReviewService()
            .approve_export(
                version_id,
                approval_id,
            )
        )


    if action == "learning_dataset_review_history":
        from learning_engine_runtime import (
            LearningDatasetReviewService,
        )

        version_id = required_text(
            payload,
            "version_id",
            300,
        )

        service = (
            LearningDatasetReviewService()
        )

        return {
            "version_id": version_id,
            "items": (
                service.factory
                .review_history(
                    version_id,
                    limit=bounded_int(
                        payload,
                        "limit",
                        50,
                        1,
                        200,
                    ),
                )
            ),
        }


    if action == "learning_export_status":
        from learning_export_runtime import (
            LearningDatasetExportService,
        )

        return (
            LearningDatasetExportService()
            .status()
        )


    if action == "learning_export_list":
        from learning_export_runtime import (
            LearningDatasetExportService,
        )

        service = (
            LearningDatasetExportService()
        )

        return {
            "items": (
                service.exporter
                .list_exports(
                    bounded_int(
                        payload,
                        "limit",
                        50,
                        1,
                        200,
                    )
                )
            ),
            "automatic_training": False,
            "external_export": False,
        }


    if action == "learning_export_plan":
        from learning_export_runtime import (
            LearningDatasetExportService,
        )
        from rachel_core.dataset_export import (
            DEFAULT_SPLIT_SEED,
        )

        version_id = required_text(
            payload,
            "version_id",
            300,
        )

        split_seed = (
            optional_text(
                payload,
                "split_seed",
                maximum=200,
            )
            or DEFAULT_SPLIT_SEED
        )

        return (
            LearningDatasetExportService()
            .plan(
                version_id,
                eval_percent=(
                    bounded_int(
                        payload,
                        "eval_percent",
                        10,
                        0,
                        50,
                    )
                ),
                split_seed=(
                    split_seed
                ),
            )
        )


    if action == "learning_export_request":
        from learning_export_runtime import (
            LearningDatasetExportService,
        )
        from rachel_core.dataset_export import (
            DEFAULT_SPLIT_SEED,
        )

        version_id = required_text(
            payload,
            "version_id",
            300,
        )

        split_seed = (
            optional_text(
                payload,
                "split_seed",
                maximum=200,
            )
            or DEFAULT_SPLIT_SEED
        )

        return (
            LearningDatasetExportService()
            .request_local_export(
                version_id,
                eval_percent=(
                    bounded_int(
                        payload,
                        "eval_percent",
                        10,
                        0,
                        50,
                    )
                ),
                split_seed=(
                    split_seed
                ),
            )
        )


    if action == "learning_export_execute":
        from learning_export_runtime import (
            LearningDatasetExportService,
        )
        from rachel_core.dataset_export import (
            DEFAULT_SPLIT_SEED,
        )

        version_id = required_text(
            payload,
            "version_id",
            300,
        )

        approval_id = required_text(
            payload,
            "approval_id",
            200,
        )

        split_seed = (
            optional_text(
                payload,
                "split_seed",
                maximum=200,
            )
            or DEFAULT_SPLIT_SEED
        )

        return (
            LearningDatasetExportService()
            .export_local(
                version_id,
                approval_id,
                eval_percent=(
                    bounded_int(
                        payload,
                        "eval_percent",
                        10,
                        0,
                        50,
                    )
                ),
                split_seed=(
                    split_seed
                ),
            )
        )


    if action == "learning_export_verify":
        from learning_export_runtime import (
            LearningDatasetExportService,
        )

        export_id = required_text(
            payload,
            "export_id",
            300,
        )

        service = (
            LearningDatasetExportService()
        )

        return (
            service.exporter
            .verify_export(
                export_id
            )
        )


    if action == "training_compiled_status":
        from training_dataset_runtime import (
            TrainingDatasetService,
        )

        return (
            TrainingDatasetService()
            .status()
        )


    if action == "training_compiled_list":
        from training_dataset_runtime import (
            TrainingDatasetService,
        )

        service = (
            TrainingDatasetService()
        )

        return {
            "items": (
                service.compiler
                .list(
                    bounded_int(
                        payload,
                        "limit",
                        50,
                        1,
                        200,
                    )
                )
            ),
            "automatic_training": False,
            "checkpoint_created": False,
            "external_export": False,
        }


    if action == "training_compile_plan":
        from training_dataset_runtime import (
            TrainingDatasetService,
        )

        export_id = required_text(
            payload,
            "export_id",
            300,
        )

        training_format = optional_text(
            payload,
            "training_format",
            maximum=50,
        )

        return (
            TrainingDatasetService()
            .plan(
                export_id,
                training_format=(
                    training_format
                ),
            )
        )


    if action == "training_compile_request":
        from training_dataset_runtime import (
            TrainingDatasetService,
        )

        export_id = required_text(
            payload,
            "export_id",
            300,
        )

        training_format = optional_text(
            payload,
            "training_format",
            maximum=50,
        )

        return (
            TrainingDatasetService()
            .request_compile(
                export_id,
                training_format=(
                    training_format
                ),
            )
        )


    if action == "training_compile_execute":
        from training_dataset_runtime import (
            TrainingDatasetService,
        )

        export_id = required_text(
            payload,
            "export_id",
            300,
        )

        approval_id = required_text(
            payload,
            "approval_id",
            200,
        )

        training_format = optional_text(
            payload,
            "training_format",
            maximum=50,
        )

        return (
            TrainingDatasetService()
            .compile(
                export_id,
                approval_id,
                training_format=(
                    training_format
                ),
            )
        )


    if action == "training_compiled_verify":
        from training_dataset_runtime import (
            TrainingDatasetService,
        )

        compiled_id = required_text(
            payload,
            "compiled_id",
            300,
        )

        service = (
            TrainingDatasetService()
        )

        return (
            service.compiler
            .verify(
                compiled_id
            )
        )


    if action == "training_preflight":
        from training_preflight_runtime import (
            TrainingPreflight,
        )

        return (
            TrainingPreflight()
            .report(
                limit=bounded_int(
                    payload,
                    "limit",
                    100,
                    1,
                    200,
                )
            )
        )


    if action == "training_litgpt_preflight":
        from training_preflight_runtime import (
            TrainingPreflight,
        )

        return (
            TrainingPreflight()
            .litgpt()
        )


    if action == "training_catalog":
        from training_preflight_runtime import (
            TrainingPreflight,
        )

        return (
            TrainingPreflight()
            .catalog(
                limit=bounded_int(
                    payload,
                    "limit",
                    100,
                    1,
                    200,
                )
            )
        )


    if action == "evaluation_status":
        from evaluation_runtime import (
            EvaluationRuntime,
        )

        return (
            EvaluationRuntime()
            .status()
        )


    if action == "evaluation_suites":
        from evaluation_runtime import (
            EvaluationRuntime,
        )

        return {
            "items": (
                EvaluationRuntime()
                .list_suites()
            ),
            "execution_enabled": False,
        }


    if action == "evaluation_suite":
        from evaluation_runtime import (
            EvaluationRuntime,
        )

        suite_id = required_text(
            payload,
            "suite_id",
            200,
        )

        return (
            EvaluationRuntime()
            .suite(
                suite_id
            )
        )


    if action == "evaluation_promotion_eligibility":
        from evaluation_runtime import (
            EvaluationRuntime,
        )

        return (
            EvaluationRuntime()
            .promotion_eligibility()
        )


    if action == "evaluation_plan_status":
        from evaluation_plan_runtime import (
            EvaluationPlanRuntime,
        )

        return (
            EvaluationPlanRuntime()
            .status()
        )


    if action == "evaluation_plan_preview":
        from evaluation_plan_runtime import (
            EvaluationPlanRuntime,
        )

        return (
            EvaluationPlanRuntime()
            .preview()
        )


    if action == "samwell_training_backend_status":
        from training_backend_provisioning import (
            TrainingBackendProvisioning,
        )

        return (
            TrainingBackendProvisioning()
            .status()
        )


    if action == "samwell_training_backend_plan":
        from training_backend_provisioning import (
            TrainingBackendProvisioning,
        )

        return (
            TrainingBackendProvisioning()
            .plan()
        )


    if action == "samwell_status":
        from samwell_runtime import (
            SamwellRuntime,
        )

        return (
            SamwellRuntime()
            .status()
        )


    if action == "samwell_audit":
        from samwell_runtime import (
            SamwellRuntime,
        )

        return (
            SamwellRuntime()
            .audit()
        )


    if action == "samwell_provision_plan":
        from samwell_runtime import (
            SamwellRuntime,
        )

        mode = (
            optional_text(
                payload,
                "mode",
                maximum=100,
            )
            or "development"
        )

        return (
            SamwellRuntime()
            .provision_plan(
                mode
            )
        )


    if action == "model_status":
        from model_runtime import (
            RachelModelRuntime,
        )

        return (
            RachelModelRuntime()
            .status()
        )


    if action == "training_run_status":
        from training_run_runtime import (
            TrainingRunRuntime,
        )

        return (
            TrainingRunRuntime()
            .status()
        )


    if action == "training_run_preview":
        from training_run_runtime import (
            TrainingRunRuntime,
        )

        profile_id = (
            optional_text(
                payload,
                "profile_id",
                maximum=200,
            )
            or (
                "qwen3-1.7b-lora-minimum"
            )
        )

        return (
            TrainingRunRuntime()
            .preview(
                profile_id
            )
        )


    if action == "training_dry_run_status":
        from training_execution_gate import (
            TrainingExecutionGate,
        )

        return (
            TrainingExecutionGate()
            .status()
        )


    if action == "training_dry_run_review":
        from training_execution_gate import (
            TrainingExecutionGate,
        )

        compiled_dataset = (
            required_object(
                payload,
                "compiled_dataset",
            )
        )

        profile_id = (
            optional_text(
                payload,
                "profile_id",
                maximum=200,
            )
            or (
                "qwen3-1.7b-lora-minimum"
            )
        )

        observed_hardware = (
            optional_object(
                payload,
                "observed_hardware",
            )
        )

        return (
            TrainingExecutionGate()
            .review(
                compiled_dataset,
                profile_id=profile_id,
                observed_hardware=(
                    observed_hardware
                ),
            )
        )


    if action == "training_dry_run_request":
        from training_execution_gate import (
            TrainingExecutionGate,
        )

        compiled_dataset = (
            required_object(
                payload,
                "compiled_dataset",
            )
        )

        profile_id = (
            optional_text(
                payload,
                "profile_id",
                maximum=200,
            )
            or (
                "qwen3-1.7b-lora-minimum"
            )
        )

        observed_hardware = (
            optional_object(
                payload,
                "observed_hardware",
            )
        )

        return (
            TrainingExecutionGate()
            .request_dry_run(
                compiled_dataset,
                profile_id=profile_id,
                observed_hardware=(
                    observed_hardware
                ),
            )
        )


    if action == "training_dry_run_materialize":
        from training_execution_gate import (
            TrainingExecutionGate,
        )

        compiled_dataset = (
            required_object(
                payload,
                "compiled_dataset",
            )
        )

        approval_id = required_text(
            payload,
            "approval_id",
            200,
        )

        profile_id = (
            optional_text(
                payload,
                "profile_id",
                maximum=200,
            )
            or (
                "qwen3-1.7b-lora-minimum"
            )
        )

        observed_hardware = (
            optional_object(
                payload,
                "observed_hardware",
            )
        )

        return (
            TrainingExecutionGate()
            .materialize_dry_run(
                compiled_dataset,
                approval_id,
                profile_id=profile_id,
                observed_hardware=(
                    observed_hardware
                ),
            )
        )


    if action == "training_dry_run_verify":
        from training_execution_gate import (
            TrainingExecutionGate,
        )

        run_id = required_text(
            payload,
            "run_id",
            300,
        )

        return (
            TrainingExecutionGate()
            .verify_manifest(
                run_id
            )
        )


    if action == "agent_status":
        from agent_runtime import (
            AgentRuntime,
        )

        return (
            AgentRuntime()
            .status()
        )


    if action == "agent_dependencies":
        from agent_runtime import (
            AgentRuntime,
        )

        return (
            AgentRuntime()
            .dependencies()
        )


    if action == "agent_authority":
        from agent_runtime import (
            AgentRuntime,
        )

        return (
            AgentRuntime()
            .authority_map()
        )


    if action == "agent_readiness":
        from agent_runtime import (
            AgentRuntime,
        )

        return (
            AgentRuntime()
            .readiness()
        )


    if action == "agent_blockers":
        from agent_runtime import (
            AgentRuntime,
        )

        service = AgentRuntime()

        items = (
            service.blockers()
        )

        return {
            "items": items,
            "count": len(
                items
            ),
            "ready": False,
            "read_only": True,
            "execution_enabled": False,
        }


    if action == "agent_budgets":
        from agent_runtime import (
            AgentRuntime,
        )

        return (
            AgentRuntime()
            .budgets()
        )


    if action == "agent_execution_envelope":
        from agent_runtime import (
            AgentRuntime,
        )

        return (
            AgentRuntime()
            .execution_envelope()
        )


    if action == "memory_status":
        from bran_cognitive import CognitiveMemory

        return CognitiveMemory().status()


    if action == "memory_search":
        from bran_cognitive import CognitiveMemory

        return {
            "items": CognitiveMemory().search(
                required_text(
                    payload,
                    "query",
                    5_000,
                ),
                bounded_int(
                    payload,
                    "limit",
                    10,
                    1,
                    50,
                ),
            )
        }


    if action == "voice_status":
        from voice_diagnostics import doctor

        include_hardware = payload.get(
            "include_hardware",
            True,
        )

        if not isinstance(
            include_hardware,
            bool,
        ):
            raise ValueError(
                "include_hardware must be boolean"
            )

        return doctor(
            include_hardware=include_hardware
        )


    if action == "health":
        return health_snapshot()


    raise ValueError(
        f"Unsupported action: {action}"
    )


def load_request() -> dict[str, Any]:

    if (
        len(sys.argv) == 3
        and sys.argv[1]
        == "--request-file"
    ):
        request_path = Path(
            sys.argv[2]
        ).expanduser().resolve()

        payload = json.loads(
            request_path.read_text(
                encoding="utf-8"
            )
        )

    elif len(sys.argv) == 1:
        payload = json.load(
            sys.stdin
        )

    else:
        raise ValueError(
            "Usage: rachel-backend "
            "[--request-file PATH]"
        )

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Bridge request must be an object"
        )

    return payload


def main() -> int:
    try:
        payload = load_request()

        result = execute(
            payload
        )

        print(
            json.dumps(
                {
                    "ok": True,
                    "payload": result,
                },
                ensure_ascii=False,
            )
        )

        return 0

    except Exception as error:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "type": type(error).__name__,
                        "message": str(error),
                    },
                },
                ensure_ascii=False,
            )
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
