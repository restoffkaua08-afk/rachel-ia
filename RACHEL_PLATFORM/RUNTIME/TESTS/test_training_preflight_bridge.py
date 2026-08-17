from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest

from pathlib import Path


ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

CORE_SRC = (
    ROOT
    / "RACHEL_CORE"
    / "src"
)

RUNTIME_SRC = (
    ROOT
    / "RACHEL_PLATFORM"
    / "RUNTIME"
    / "SRC"
)

BRIDGE = (
    ROOT
    / "APP"
    / "bridge"
    / "rachel_bridge.py"
)

for path in (
    CORE_SRC,
    RUNTIME_SRC,
):
    if str(path) not in sys.path:
        sys.path.insert(
            0,
            str(path),
        )


from rachel_core.dataset_export import (
    DatasetExportFactory,
)

from rachel_core.training_dataset_compiler import (
    TrainingDatasetCompiler,
)

from training_preflight_runtime import (
    TrainingPreflight,
)


class TrainingPreflightBridgeTests(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.temp = (
            tempfile
            .TemporaryDirectory()
        )

        self.root = Path(
            self.temp.name
        )

        self.state = (
            self.root
            / "STATE"
        )

        self.state.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.exporter = (
            DatasetExportFactory(
                self.state
                / "training-exports"
            )
        )

        self.compiler = (
            TrainingDatasetCompiler(
                self.exporter,
                self.state
                / "compiled-training",
            )
        )

        self.env = os.environ.copy()

        self.env[
            "RACHEL_RUNTIME_ROOT"
        ] = str(ROOT)

        self.env[
            "RACHEL_STATE_ROOT"
        ] = str(
            self.state
        )

        self.env[
            "PYTHONUTF8"
        ] = "1"

    def tearDown(
        self,
    ) -> None:
        self.temp.cleanup()

    def source_export(
        self,
        suffix: str,
    ) -> str:

        source = {
            "id": (
                "conversation-v1-"
                + suffix
            ),
            "dataset_type": (
                "conversation"
            ),
            "content_hash": (
                "a" * 64
            ),
            "item_count": 4,
            "state": (
                "approved-for-export"
            ),
        }

        items = [
            {
                "id": (
                    f"item_{suffix}_{index}"
                ),
                "content_hash": (
                    f"{index + 1:064x}"
                ),
                "payload": {
                    "user": (
                        f"pergunta {index}"
                    ),
                    "assistant": (
                        f"resposta {index}"
                    ),
                },
                "provenance": {
                    "review_state": (
                        "user_accepted"
                    ),
                },
            }
            for index
            in range(4)
        ]

        result = (
            self.exporter
            .create_export(
                source,
                items,
                eval_percent=25,
                split_seed=(
                    "preflight-"
                    + suffix
                ),
            )
        )

        return str(
            result[
                "id"
            ]
        )

    def call(
        self,
        payload: dict,
        *,
        expect_ok: bool = True,
    ) -> dict:

        request = (
            self.root
            / (
                "request-"
                + next(
                    tempfile
                    ._get_candidate_names()
                )
                + ".json"
            )
        )

        request.write_text(
            json.dumps(
                payload,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        process = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(BRIDGE),
                "--request-file",
                str(request),
            ],
            cwd=str(ROOT),
            env=self.env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )

        response = json.loads(
            process.stdout.strip()
        )

        if expect_ok:
            self.assertEqual(
                0,
                process.returncode,
                msg=(
                    process.stderr
                    + "\n"
                    + process.stdout
                ),
            )

            self.assertTrue(
                response.get(
                    "ok"
                ),
                msg=response,
            )

            return response[
                "payload"
            ]

        self.assertNotEqual(
            0,
            process.returncode,
        )

        self.assertFalse(
            response.get(
                "ok"
            )
        )

        return response[
            "error"
        ]

    def test_fake_litgpt_registry_is_portable(
        self,
    ):
        config = (
            self.root
            / "CONFIG"
        )

        organs = (
            self.root
            / "ORGAOS"
        )

        source = (
            organs
            / "litgpt"
            / "fonte"
        )

        (
            source
            / "litgpt"
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            source
            / "litgpt"
            / "__init__.py"
        ).write_text(
            "",
            encoding="utf-8",
        )

        (
            source
            / "pyproject.toml"
        ).write_text(
            "[project]\nname='litgpt'\n",
            encoding="utf-8",
        )

        config.mkdir(
            parents=True,
            exist_ok=True,
        )

        registry = (
            config
            / "organs.registry.json"
        )

        registry.write_text(
            json.dumps(
                {
                    "orgaos": [
                        {
                            "nome": "LitGPT",
                            "alias": (
                                "rachel.litgpt"
                            ),
                            "alias_curto": (
                                "litgpt"
                            ),
                            "conexao": (
                                "C:\\caminho\\antigo"
                            ),
                            "commit": "abc123",
                            "origem": (
                                "https://github.com/"
                                "Lightning-AI/litgpt.git"
                            ),
                            "status": (
                                "conectado"
                            ),
                            "habilitado": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        preflight = TrainingPreflight(
            exporter=self.exporter,
            compiler=self.compiler,
            registry_path=registry,
            organ_root=organs,
        )

        result = preflight.litgpt()

        self.assertTrue(
            result[
                "structural_ready"
            ]
        )

        self.assertTrue(
            result[
                "absolute_registry_path_ignored"
            ]
        )

        self.assertEqual(
            str(
                source.resolve()
            ),
            result[
                "source_path"
            ],
        )

    def test_frozen_metadata_only_does_not_block_pipeline(
        self,
    ):
        config = (
            self.root
            / "FROZEN_CONFIG"
        )

        organs = (
            self.root
            / "FROZEN_ORGAOS"
        )

        litgpt_organ = (
            organs
            / "litgpt"
        )

        litgpt_organ.mkdir(
            parents=True,
            exist_ok=True,
        )

        (
            litgpt_organ
            / "organ.json"
        ).write_text(
            json.dumps(
                {
                    "name": "LitGPT",
                    "alias": "rachel.litgpt",
                }
            ),
            encoding="utf-8",
        )

        config.mkdir(
            parents=True,
            exist_ok=True,
        )

        registry = (
            config
            / "organs.registry.json"
        )

        registry.write_text(
            json.dumps(
                {
                    "orgaos": [
                        {
                            "nome": "LitGPT",
                            "alias": (
                                "rachel.litgpt"
                            ),
                            "alias_curto": (
                                "litgpt"
                            ),
                            "conexao": (
                                "C:\\build-machine\\"
                                "RACHEL_PLATFORM\\"
                                "ORGAOS\\litgpt\\fonte"
                            ),
                            "commit": "abc123",
                            "origem": (
                                "https://github.com/"
                                "Lightning-AI/litgpt.git"
                            ),
                            "status": (
                                "conectado"
                            ),
                            "habilitado": True,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        preflight = TrainingPreflight(
            exporter=self.exporter,
            compiler=self.compiler,
            registry_path=registry,
            organ_root=organs,
        )

        litgpt = preflight.litgpt()

        self.assertTrue(
            litgpt[
                "metadata_ready"
            ]
        )

        self.assertFalse(
            litgpt[
                "source_available"
            ]
        )

        self.assertFalse(
            litgpt[
                "structural_ready"
            ]
        )

        self.assertTrue(
            litgpt[
                "runtime_preflight_ready"
            ]
        )

        self.assertFalse(
            litgpt[
                "training_backend_available"
            ]
        )

        report = preflight.report()

        self.assertTrue(
            report[
                "pipeline_ready"
            ]
        )

        self.assertFalse(
            report[
                "training_backend_available"
            ]
        )

        self.assertFalse(
            report[
                "stage12_execution_enabled"
            ]
        )

        self.assertFalse(
            report[
                "automatic_training"
            ]
        )

        self.assertFalse(
            report[
                "checkpoint_created"
            ]
        )

        self.assertFalse(
            report[
                "weights_modified"
            ]
        )


    def test_real_litgpt_organ_is_detected(
        self,
    ):
        result = self.call(
            {
                "action": (
                    "training_litgpt_preflight"
                ),
            }
        )

        self.assertEqual(
            "rachel.litgpt",
            result[
                "organ"
            ],
        )

        self.assertEqual(
            "litgpt",
            result[
                "alias_short"
            ],
        )

        self.assertTrue(
            result[
                "checks"
            ][
                "registry_entry"
            ]
        )

        self.assertTrue(
            result[
                "checks"
            ][
                "source_directory"
            ]
        )

        self.assertTrue(
            result[
                "checks"
            ][
                "pyproject"
            ]
        )

        self.assertTrue(
            result[
                "checks"
            ][
                "python_package"
            ]
        )

        self.assertTrue(
            result[
                "structural_ready"
            ]
        )

        self.assertFalse(
            result[
                "training_execution_enabled"
            ]
        )

    def test_desktop_compile_and_catalog_flow(
        self,
    ):
        export_id = (
            self.source_export(
                "catalog"
            )
        )

        plan = self.call(
            {
                "action": (
                    "training_compile_plan"
                ),
                "export_id": (
                    export_id
                ),
            }
        )

        self.assertEqual(
            "sft",
            plan[
                "training_format"
            ],
        )

        pending = self.call(
            {
                "action": (
                    "training_compile_request"
                ),
                "export_id": (
                    export_id
                ),
            }
        )

        approval_id = (
            pending[
                "approval"
            ][
                "id"
            ]
        )

        security = self.call(
            {
                "action": (
                    "security_snapshot"
                ),
                "limit": 50,
            }
        )

        card = next(
            item
            for item
            in security[
                "items"
            ]
            if item[
                "id"
            ]
            == approval_id
        )

        self.assertEqual(
            (
                "learning.training_dataset."
                "compile"
            ),
            card[
                "tool"
            ],
        )

        self.assertEqual(
            "MEDIUM",
            card[
                "risk_label"
            ],
        )

        self.call(
            {
                "action": (
                    "security_decide"
                ),
                "approval_id": (
                    approval_id
                ),
                "allow": True,
                "confirmation": (
                    "APROVAR "
                    + approval_id
                ),
            }
        )

        compiled = self.call(
            {
                "action": (
                    "training_compile_execute"
                ),
                "export_id": (
                    export_id
                ),
                "approval_id": (
                    approval_id
                ),
            }
        )

        self.assertEqual(
            "compiled-local",
            compiled[
                "state"
            ],
        )

        self.assertEqual(
            "consumed",
            compiled[
                "cyber"
            ][
                "status"
            ],
        )

        compiled_id = (
            compiled[
                "compiled"
            ][
                "id"
            ]
        )

        verify = self.call(
            {
                "action": (
                    "training_compiled_verify"
                ),
                "compiled_id": (
                    compiled_id
                ),
            }
        )

        self.assertTrue(
            verify[
                "integrity"
            ]
        )

        catalog = self.call(
            {
                "action": (
                    "training_catalog"
                ),
            }
        )

        self.assertEqual(
            1,
            catalog[
                "total"
            ],
        )

        self.assertEqual(
            1,
            catalog[
                "ready"
            ],
        )

        self.assertTrue(
            catalog[
                "items"
            ][0][
                "stage12_data_ready"
            ]
        )

    def test_training_preflight_never_enables_training(
        self,
    ):
        report = self.call(
            {
                "action": (
                    "training_preflight"
                ),
            }
        )

        self.assertTrue(
            report[
                "pipeline_ready"
            ]
        )

        self.assertFalse(
            report[
                "stage12_execution_enabled"
            ]
        )

        self.assertFalse(
            report[
                "automatic_training"
            ]
        )

        self.assertFalse(
            report[
                "checkpoint_created"
            ]
        )

        self.assertFalse(
            report[
                "weights_modified"
            ]
        )

        dashboard = self.call(
            {
                "action": (
                    "dashboard"
                ),
            }
        )

        self.assertIn(
            "training_datasets",
            dashboard,
        )

        self.assertIn(
            "training_preflight",
            dashboard,
        )


if __name__ == "__main__":
    unittest.main()