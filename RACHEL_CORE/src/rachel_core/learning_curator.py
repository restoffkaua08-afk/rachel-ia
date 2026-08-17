from __future__ import annotations

from collections import defaultdict
from typing import Any

from .dataset_factory import (
    DATASET_TYPES,
    DatasetFactory,
)
from .ports import LearningPort
from .privacy import redact


EVENT_DATASET_MAP = {
    "planner_decision": "planning",
    "task_plan": "planning",
    "task_execution": "planning",
    "tool_result": "tool-use",
    "tool_failed": "tool-use",
}


class LearningCurator:
    """
    Curadoria entre Learning Vault e Dataset Factory.

    Regras:
    - somente leitura no Learning Vault;
    - nenhuma promocao de training_state;
    - experiencias exigem gate Dany persistido;
    - experiencias rejeitadas pelo usuario sao excluidas;
    - material de conversa exige aceite/correcao explicita;
    - correcao explicita gera preference dataset;
    - eventos estruturados so entram se ja estiverem
      explicitamente approved no Vault;
    - deduplicacao global consulta o Dataset Registry;
    - materializacao e chamada explicita.
    """

    def __init__(
        self,
        learning: LearningPort,
        factory: DatasetFactory,
        *,
        minimum_quality_score: int = 80,
    ) -> None:
        self.learning = learning
        self.factory = factory

        self.minimum_quality_score = max(
            0,
            min(
                100,
                int(
                    minimum_quality_score
                ),
            ),
        )

    @staticmethod
    def classify_event_kind(
        kind: str,
    ) -> str | None:
        return EVENT_DATASET_MAP.get(
            str(
                kind
            ).strip()
        )

    @staticmethod
    def _explicit_dataset_type(
        metadata: dict[str, Any],
    ) -> str | None:
        selected = str(
            metadata.get(
                "dataset_type",
                "",
            )
        ).strip().casefold()

        if selected in DATASET_TYPES:
            return selected

        return None

    def _experience_passes_dany(
        self,
        experience: dict[str, Any],
    ) -> bool:
        return (
            int(
                experience.get(
                    "quality_accepted"
                )
                or 0
            )
            == 1
            and int(
                experience.get(
                    "quality_score"
                )
                or 0
            )
            >= self.minimum_quality_score
        )

    @staticmethod
    def _experience_user_allowed(
        experience: dict[str, Any],
    ) -> bool:
        return (
            experience.get(
                "review_state"
            )
            in {
                "user_accepted",
                "user_corrected",
            }
        )

    def _add_candidate(
        self,
        buckets: dict[
            str,
            list[dict[str, Any]]
        ],
        seen: set[str],
        dataset_type: str,
        item: dict[str, Any],
    ) -> bool:
        digest = (
            self.factory
            .content_hash_for_item(
                item
            )
        )

        if digest in seen:
            return False

        if (
            self.factory
            .contains_content_hash(
                digest
            )
        ):
            return False

        seen.add(
            digest
        )

        buckets[
            dataset_type
        ].append(
            item
        )

        return True

    def collect(
        self,
        *,
        limit: int = 1000,
    ) -> dict[str, Any]:
        experiences = (
            self.learning
            .curation_experiences(
                limit
            )
        )

        feedback = (
            self.learning
            .curation_feedback(
                limit
            )
        )

        events = (
            self.learning
            .curation_events(
                limit
            )
        )

        feedback_by_experience: dict[
            str,
            list[dict[str, Any]]
        ] = defaultdict(list)

        for item in feedback:
            feedback_by_experience[
                str(
                    item[
                        "experience_id"
                    ]
                )
            ].append(
                item
            )

        buckets: dict[
            str,
            list[dict[str, Any]]
        ] = {
            dataset_type: []
            for dataset_type
            in DATASET_TYPES
        }

        seen: set[str] = set()

        stats = {
            "experiences_seen": (
                len(
                    experiences
                )
            ),
            "events_seen": (
                len(
                    events
                )
            ),
            "feedback_seen": (
                len(
                    feedback
                )
            ),
            "dany_rejected": 0,
            "user_not_approved": 0,
            "events_not_approved": 0,
            "duplicates": 0,
            "candidates": 0,
        }

        experience_index = {
            str(
                item[
                    "id"
                ]
            ): item
            for item
            in experiences
        }

        for experience in experiences:
            if (
                not self
                ._experience_passes_dany(
                    experience
                )
            ):
                stats[
                    "dany_rejected"
                ] += 1
                continue

            if (
                not self
                ._experience_user_allowed(
                    experience
                )
            ):
                stats[
                    "user_not_approved"
                ] += 1
                continue

            metadata = (
                experience.get(
                    "metadata"
                )
                or {}
            )

            dataset_type = (
                self
                ._explicit_dataset_type(
                    metadata
                )
                or "conversation"
            )

            assistant_content = str(
                experience.get(
                    "assistant_content",
                    "",
                )
            )

            corrections = [
                item
                for item
                in feedback_by_experience.get(
                    str(
                        experience[
                            "id"
                        ]
                    ),
                    [],
                )
                if item.get(
                    "verdict"
                )
                == "corrected"
                and item.get(
                    "correction_text"
                )
            ]

            if corrections:
                assistant_content = str(
                    corrections[-1][
                        "correction_text"
                    ]
                )

            candidate = {
                "source_kind": (
                    "experience"
                ),
                "source_id": (
                    str(
                        experience[
                            "id"
                        ]
                    )
                ),
                "payload": redact(
                    {
                        "user": (
                            experience.get(
                                "user_content",
                                "",
                            )
                        ),
                        "assistant": (
                            assistant_content
                        ),
                    }
                ),
                "provenance": redact(
                    {
                        "created_at": (
                            experience.get(
                                "created_at"
                            )
                        ),
                        "conversation_id": (
                            experience.get(
                                "conversation_id"
                            )
                        ),
                        "run_id": (
                            experience.get(
                                "run_id"
                            )
                        ),
                        "provider": (
                            experience.get(
                                "provider"
                            )
                        ),
                        "model": (
                            experience.get(
                                "model"
                            )
                        ),
                        "quality_accepted": True,
                        "quality_score": (
                            experience.get(
                                "quality_score"
                            )
                        ),
                        "review_state": (
                            experience.get(
                                "review_state"
                            )
                        ),
                        "training_state": (
                            experience.get(
                                "training_state"
                            )
                        ),
                        "dany_gate": (
                            "passed"
                        ),
                    }
                ),
            }

            if self._add_candidate(
                buckets,
                seen,
                dataset_type,
                candidate,
            ):
                stats[
                    "candidates"
                ] += 1
            else:
                stats[
                    "duplicates"
                ] += 1

        for feedback_item in feedback:
            if (
                feedback_item.get(
                    "verdict"
                )
                != "corrected"
            ):
                continue

            correction = (
                feedback_item.get(
                    "correction_text"
                )
            )

            if not correction:
                continue

            experience = (
                experience_index.get(
                    str(
                        feedback_item[
                            "experience_id"
                        ]
                    )
                )
            )

            if experience is None:
                continue

            candidate = {
                "source_kind": (
                    "feedback"
                ),
                "source_id": (
                    str(
                        feedback_item[
                            "id"
                        ]
                    )
                ),
                "payload": redact(
                    {
                        "prompt": (
                            experience.get(
                                "user_content",
                                "",
                            )
                        ),
                        "rejected_response": (
                            experience.get(
                                "assistant_content",
                                "",
                            )
                        ),
                        "preferred_response": (
                            correction
                        ),
                    }
                ),
                "provenance": redact(
                    {
                        "experience_id": (
                            feedback_item.get(
                                "experience_id"
                            )
                        ),
                        "feedback_created_at": (
                            feedback_item.get(
                                "created_at"
                            )
                        ),
                        "verdict": (
                            "corrected"
                        ),
                        "explicit_user_feedback": (
                            True
                        ),
                        "provider": (
                            experience.get(
                                "provider"
                            )
                        ),
                        "model": (
                            experience.get(
                                "model"
                            )
                        ),
                    }
                ),
            }

            if self._add_candidate(
                buckets,
                seen,
                "preference",
                candidate,
            ):
                stats[
                    "candidates"
                ] += 1
            else:
                stats[
                    "duplicates"
                ] += 1

        for event in events:
            dataset_type = (
                self.classify_event_kind(
                    str(
                        event.get(
                            "kind",
                            "",
                        )
                    )
                )
            )

            if dataset_type is None:
                continue

            if (
                event.get(
                    "training_state"
                )
                != "approved"
            ):
                stats[
                    "events_not_approved"
                ] += 1
                continue

            candidate = {
                "source_kind": (
                    "learning_event"
                ),
                "source_id": (
                    str(
                        event[
                            "id"
                        ]
                    )
                ),
                "payload": redact(
                    event.get(
                        "payload"
                    )
                    or {}
                ),
                "provenance": redact(
                    {
                        "kind": (
                            event.get(
                                "kind"
                            )
                        ),
                        "created_at": (
                            event.get(
                                "created_at"
                            )
                        ),
                        "correlation_id": (
                            event.get(
                                "correlation_id"
                            )
                        ),
                        "conversation_id": (
                            event.get(
                                "conversation_id"
                            )
                        ),
                        "parent_experience_id": (
                            event.get(
                                "parent_experience_id"
                            )
                        ),
                        "provider": (
                            event.get(
                                "provider"
                            )
                        ),
                        "model": (
                            event.get(
                                "model"
                            )
                        ),
                        "review_state": (
                            event.get(
                                "review_state"
                            )
                        ),
                        "training_state": (
                            "approved"
                        ),
                        "quality_gate": (
                            "structured-event-approved"
                        ),
                    }
                ),
            }

            if self._add_candidate(
                buckets,
                seen,
                dataset_type,
                candidate,
            ):
                stats[
                    "candidates"
                ] += 1
            else:
                stats[
                    "duplicates"
                ] += 1

        return {
            "buckets": (
                buckets
            ),
            "stats": (
                stats
            ),
            "minimum_quality_score": (
                self.minimum_quality_score
            ),
            "automatic_training": (
                False
            ),
            "automatic_promotion": (
                False
            ),
            "external_export": (
                False
            ),
        }

    def materialize(
        self,
        curated: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        buckets = (
            curated.get(
                "buckets"
            )
            or {}
        )

        versions: dict[
            str,
            dict[str, Any]
        ] = {}

        for dataset_type in sorted(
            DATASET_TYPES
        ):
            items = list(
                buckets.get(
                    dataset_type
                )
                or []
            )

            if not items:
                continue

            versions[
                dataset_type
            ] = (
                self.factory
                .create_version(
                    dataset_type,
                    items,
                    metadata={
                        **(
                            metadata
                            or {}
                        ),
                        "curated": True,
                        "curator": (
                            "rachel-learning-engine"
                        ),
                        "minimum_quality_score": (
                            self.minimum_quality_score
                        ),
                    },
                )
            )

        return versions

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "status": "ok",
            "minimum_quality_score": (
                self.minimum_quality_score
            ),
            "event_dataset_map": dict(
                EVENT_DATASET_MAP
            ),
            "automatic_training": False,
            "automatic_promotion": False,
            "external_export": False,
        }
