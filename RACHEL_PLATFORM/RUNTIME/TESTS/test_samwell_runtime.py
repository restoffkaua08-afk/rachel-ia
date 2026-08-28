from __future__ import annotations

import json
import sys
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

RUNTIME = (
    ROOT
    / "RACHEL_PLATFORM"
    / "RUNTIME"
    / "SRC"
)

if str(RUNTIME) not in sys.path:
    sys.path.insert(
        0,
        str(RUNTIME),
    )


from samwell_runtime import (
    SamwellRuntime,
)

from team_runtime import (
    NedRouter,
)


class SamwellRuntimeTests(
    unittest.TestCase
):

    def service(self):
        return SamwellRuntime()

    def test_member_manifest(self):

        path = (
            ROOT
            / "RACHEL_PLATFORM"
            / "MEMBROS"
            / "ST-Samwell"
            / "member.json"
        )

        member = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )

        self.assertEqual(
            "samwell",
            member[
                "id"
            ],
        )

        self.assertTrue(
            member[
                "requer_autorizacao"
            ]
        )

    def test_portable_runtime_owner(self):

        portable = (
            self.service()
            .status()[
                "portable_runtime"
            ]
        )

        self.assertEqual(
            "frozen",
            portable[
                "internal_term"
            ],
        )

        self.assertEqual(
            "Portable Runtime",
            portable[
                "display_name"
            ],
        )

        self.assertEqual(
            "samwell",
            portable[
                "managed_by"
            ],
        )

        self.assertFalse(
            portable[
                "external_python_required"
            ]
        )

    def test_status_is_lightweight_and_does_not_call_audit(self):

        service = self.service()

        def forbidden_audit():
            raise AssertionError(
                "status() must not execute deep audit"
            )

        service.audit = forbidden_audit

        status = service.status()

        self.assertEqual(
            "lightweight",
            status[
                "status_mode"
            ],
        )

        self.assertFalse(
            status[
                "deep_audit_performed"
            ]
        )

        self.assertFalse(
            status[
                "audit"
            ][
                "performed"
            ]
        )

        self.assertEqual(
            "not-run",
            status[
                "audit"
            ][
                "status"
            ],
        )

        self.assertFalse(
            status[
                "environment_isolation"
            ][
                "availability_evaluated"
            ]
        )

        for mode in status[
            "modes"
        ].values():
            self.assertFalse(
                mode[
                    "evaluated"
                ]
            )
            self.assertIsNone(
                mode[
                    "ready"
                ]
            )

    def test_deep_status_evaluates_modes_from_explicit_audit(self):

        service = self.service()

        records = [
            {
                "id": str(record["id"]),
                "type": str(record["type"]),
                "informational_only": bool(
                    record.get(
                        "informational_only"
                    )
                ),
                "available": True,
            }
            for record in service.catalog[
                "dependencies"
            ]
        ]

        deterministic_audit = {
            "member_id": "samwell",
            "status": "ok",
            "items": records,
            "total": len(records),
            "available": len(records),
            "missing": 0,
            "system_mutation": False,
            "automatic_install": False,
            "automatic_update": False,
            "automatic_remove": False,
            "automatic_repair": False,
        }

        service.audit = lambda: deterministic_audit

        status = service.deep_status()

        self.assertEqual(
            "deep",
            status[
                "status_mode"
            ],
        )

        self.assertTrue(
            status[
                "deep_audit_performed"
            ]
        )

        self.assertTrue(
            status[
                "environment_isolation"
            ][
                "availability_evaluated"
            ]
        )

        self.assertEqual(
            0,
            status[
                "audit"
            ][
                "missing"
            ]
        )

        for mode in status[
            "modes"
        ].values():
            self.assertTrue(
                mode[
                    "ready"
                ]
            )
            self.assertEqual(
                [],
                mode[
                    "missing"
                ]
            )

    def test_packaging_and_training_are_isolated(self):

        status = (
            self.service()
            .status()
        )

        isolation = status[
            "environment_isolation"
        ]

        self.assertTrue(
            isolation[
                "packaging_torch_does_not_enable_training"
            ]
        )

        self.assertFalse(
            isolation[
                "availability_evaluated"
            ]
        )

        self.assertIsNone(
            isolation[
                "packaging_torch_available"
            ]
        )

        self.assertIsNone(
            isolation[
                "training_torch_available"
            ]
        )

    def test_training_uses_dedicated_environment(self):

        environment = (
            self.service()
            .catalog[
                "environments"
            ][
                "training"
            ]
        )

        self.assertEqual(
            (
                "AMBIENTES/training/"
                "Scripts/python.exe"
            ),
            environment[
                "python_relative"
            ],
        )

    def test_training_does_not_use_packaging_torch(self):

        required = (
            self.service()
            .catalog[
                "modes"
            ][
                "training"
            ][
                "required"
            ]
        )

        self.assertIn(
            "training-torch",
            required,
        )

        self.assertNotIn(
            "packaging-torch",
            required,
        )

    def test_provision_plan_is_safe(self):

        plan = (
            self.service()
            .provision_plan(
                "training"
            )
        )

        self.assertTrue(
            plan[
                "plan_only"
            ]
        )

        self.assertTrue(
            plan[
                "requires_cyber"
            ]
        )

        self.assertFalse(
            plan[
                "execution_enabled"
            ]
        )

        self.assertFalse(
            plan[
                "automatic_install"
            ]
        )

        for action in plan[
            "actions"
        ]:
            self.assertTrue(
                action[
                    "requires_cyber"
                ]
            )

            self.assertFalse(
                action[
                    "execution_enabled"
                ]
            )

    def test_no_mutation_methods(self):

        service = self.service()

        for method in (
            "install",
            "update",
            "remove",
            "repair",
            "execute",
        ):
            self.assertFalse(
                hasattr(
                    service,
                    method,
                )
            )

    def test_ned_routes_to_samwell(self):

        members = (
            NedRouter()
            .route(
                "verifique dependencias "
                "e ambiente da Rachel"
            )
        )

        self.assertIn(
            "samwell",
            members,
        )


if __name__ == "__main__":
    unittest.main()
