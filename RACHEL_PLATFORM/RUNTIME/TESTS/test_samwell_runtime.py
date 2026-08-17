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

        if isolation[
            "packaging_torch_available"
        ]:
            self.assertFalse(
                status[
                    "modes"
                ][
                    "training"
                ][
                    "ready"
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
