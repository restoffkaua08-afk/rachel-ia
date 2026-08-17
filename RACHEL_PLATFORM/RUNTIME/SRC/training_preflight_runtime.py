from __future__ import annotations

import json
import sys

from pathlib import Path
from typing import Any


from runtime_paths import (
    CONFIG,
    CORE_SRC,
    PLATFORM,
    STATE,
)

if str(CORE_SRC) not in sys.path:
    sys.path.insert(
        0,
        str(CORE_SRC),
    )


from rachel_core.dataset_export import (
    DatasetExportFactory,
)

from rachel_core.training_dataset_compiler import (
    TRAINING_FORMATS,
    TrainingDatasetCompiler,
)


class TrainingPreflightError(
    RuntimeError
):
    pass


class TrainingPreflight:
    """
    Preflight somente leitura para a futura Etapa 12.

    Verifica:
    - órgão LitGPT real;
    - junction canônica do runtime;
    - estrutura mínima do source LitGPT;
    - catálogo de datasets compilados;
    - integridade de cada dataset compilado.

    Não inicia treinamento.
    Não carrega modelo.
    Não cria checkpoint.
    """

    def __init__(
        self,
        *,
        exporter: DatasetExportFactory | None = None,
        compiler: TrainingDatasetCompiler | None = None,
        registry_path: Path | None = None,
        organ_root: Path | None = None,
    ) -> None:

        self.exporter = (
            exporter
            or DatasetExportFactory(
                STATE
                / "training-exports"
            )
        )

        self.compiler = (
            compiler
            or TrainingDatasetCompiler(
                self.exporter,
                STATE
                / "compiled-training",
            )
        )

        self.registry_path = (
            Path(
                registry_path
                or (
                    CONFIG
                    / "organs.registry.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.organ_root = (
            Path(
                organ_root
                or (
                    PLATFORM
                    / "ORGAOS"
                )
            )
            .expanduser()
            .resolve()
        )

    def _registry(
        self,
    ) -> dict[str, Any]:

        if not self.registry_path.is_file():
            raise TrainingPreflightError(
                "organs.registry.json ausente."
            )

        try:
            value = json.loads(
                self.registry_path
                .read_text(
                    encoding="utf-8-sig"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise TrainingPreflightError(
                "Registry de orgaos invalido."
            ) from error

        if not isinstance(
            value,
            dict,
        ):
            raise TrainingPreflightError(
                "Registry de orgaos "
                "deve ser objeto."
            )

        return value

    def _litgpt_record(
        self,
    ) -> dict[str, Any]:

        registry = self._registry()

        organs = registry.get(
            "orgaos"
        )

        if not isinstance(
            organs,
            list,
        ):
            raise TrainingPreflightError(
                "Lista de orgaos ausente."
            )

        for item in organs:
            if not isinstance(
                item,
                dict,
            ):
                continue

            short = str(
                item.get(
                    "alias_curto"
                )
                or ""
            ).casefold()

            alias = str(
                item.get(
                    "alias"
                )
                or ""
            ).casefold()

            name = str(
                item.get(
                    "nome"
                )
                or ""
            ).casefold()

            if (
                short == "litgpt"
                or alias == "rachel.litgpt"
                or name == "litgpt"
            ):
                return item

        raise TrainingPreflightError(
            "Orgao LitGPT nao localizado."
        )

    def litgpt(
        self,
    ) -> dict[str, Any]:

        item = self._litgpt_record()

        alias_short = str(
            item.get(
                "alias_curto"
            )
            or "litgpt"
        ).strip()

        # Nao confiamos no campo absoluto "conexao"
        # do registry para portabilidade.
        source = (
            self.organ_root
            / alias_short
            / "fonte"
        ).resolve()

        pyproject = (
            source
            / "pyproject.toml"
        )

        package = (
            source
            / "litgpt"
        )

        package_init = (
            package
            / "__init__.py"
        )

        finetune_dir = (
            package
            / "finetune"
        )

        checks = {
            "registry_entry": True,
            "enabled": bool(
                item.get(
                    "habilitado",
                    False,
                )
            ),
            "connected_status": (
                str(
                    item.get(
                        "status"
                    )
                    or ""
                ).casefold()
                == "conectado"
            ),
            "source_directory": (
                source.is_dir()
            ),
            "pyproject": (
                pyproject.is_file()
            ),
            "python_package": (
                package.is_dir()
            ),
            "package_init": (
                package_init.is_file()
            ),
            "finetune_surface": (
                finetune_dir.exists()
            ),
        }

        metadata_ready = all(
            checks[
                name
            ]
            for name
            in (
                "registry_entry",
                "enabled",
                "connected_status",
            )
        )

        source_available = all(
            checks[
                name
            ]
            for name
            in (
                "source_directory",
                "pyproject",
                "python_package",
                "package_init",
            )
        )

        structural_ready = (
            metadata_ready
            and source_available
        )

        # Em um sidecar PyInstaller, os manifests
        # dos orgaos sao empacotados, mas os
        # repositorios-fonte completos nao.
        #
        # Isso nao bloqueia o Learning Engine.
        # O source fisico do LitGPT passa a ser
        # requisito somente antes da execucao
        # real da Etapa 12.
        runtime_preflight_ready = (
            metadata_ready
        )

        training_backend_available = (
            structural_ready
        )

        return {
            "organ": (
                "rachel.litgpt"
            ),
            "name": (
                item.get(
                    "nome"
                )
                or "LitGPT"
            ),
            "alias_short": (
                alias_short
            ),
            "registry_commit": (
                item.get(
                    "commit"
                )
            ),
            "registry_origin": (
                item.get(
                    "origem"
                )
            ),
            "source_path": (
                str(source)
            ),
            "source_resolution": (
                "runtime-organ-junction"
            ),
            "absolute_registry_path_ignored": (
                True
            ),
            "checks": checks,
            "metadata_ready": (
                metadata_ready
            ),
            "source_available": (
                source_available
            ),
            "structural_ready": (
                structural_ready
            ),
            "runtime_preflight_ready": (
                runtime_preflight_ready
            ),
            "training_backend_available": (
                training_backend_available
            ),
            "training_backend_required_before_execution": (
                True
            ),
            "training_execution_enabled": (
                False
            ),
            "automatic_training": (
                False
            ),
        }

    def catalog(
        self,
        limit: int = 100,
    ) -> dict[str, Any]:

        limit = max(
            1,
            min(
                200,
                int(limit),
            ),
        )

        records = (
            self.compiler
            .list(
                limit
            )
        )

        items = []

        ready = 0
        failed = 0

        for record in records:
            compiled_id = str(
                record[
                    "id"
                ]
            )

            try:
                verification = (
                    self.compiler
                    .verify(
                        compiled_id
                    )
                )

                integrity = bool(
                    verification[
                        "integrity"
                    ]
                )

                error = None

            except Exception as exc:
                verification = None
                integrity = False
                error = (
                    type(exc).__name__
                    + ": "
                    + str(exc)
                )

            is_ready = (
                integrity
                and record[
                    "state"
                ]
                == "compiled-local"
                and record[
                    "training_format"
                ]
                in TRAINING_FORMATS
            )

            if is_ready:
                ready += 1
            else:
                failed += 1

            items.append(
                {
                    "id": (
                        compiled_id
                    ),
                    "source_export_id": (
                        record[
                            "source_export_id"
                        ]
                    ),
                    "source_version_id": (
                        record[
                            "source_version_id"
                        ]
                    ),
                    "dataset_type": (
                        record[
                            "source_dataset_type"
                        ]
                    ),
                    "training_format": (
                        record[
                            "training_format"
                        ]
                    ),
                    "compiler_version": (
                        record[
                            "compiler_version"
                        ]
                    ),
                    "state": (
                        record[
                            "state"
                        ]
                    ),
                    "train_count": int(
                        record[
                            "train_count"
                        ]
                    ),
                    "eval_count": int(
                        record[
                            "eval_count"
                        ]
                    ),
                    "train_sha256": (
                        record[
                            "train_sha256"
                        ]
                    ),
                    "eval_sha256": (
                        record[
                            "eval_sha256"
                        ]
                    ),
                    "integrity": (
                        integrity
                    ),
                    "stage12_data_ready": (
                        is_ready
                    ),
                    "verification": (
                        verification
                    ),
                    "error": (
                        error
                    ),
                }
            )

        return {
            "status": (
                "ok"
                if failed == 0
                else "degraded"
            ),
            "total": (
                len(items)
            ),
            "ready": (
                ready
            ),
            "failed": (
                failed
            ),
            "items": (
                items
            ),
            "automatic_training": (
                False
            ),
            "checkpoint_created": (
                False
            ),
        }

    def report(
        self,
        limit: int = 100,
    ) -> dict[str, Any]:

        litgpt = self.litgpt()

        catalog = self.catalog(
            limit
        )

        pipeline_ready = (
            bool(
                litgpt[
                    "runtime_preflight_ready"
                ]
            )
            and catalog[
                "failed"
            ]
            == 0
        )

        training_backend_available = bool(
            litgpt[
                "training_backend_available"
            ]
        )

        training_data_available = (
            catalog[
                "ready"
            ]
            > 0
        )

        if not pipeline_ready:
            state = (
                "blocked"
            )
        elif (
            training_data_available
            and training_backend_available
        ):
            state = (
                "ready-with-data"
            )
        elif training_data_available:
            state = (
                "pipeline-ready-with-data-"
                "backend-required"
            )
        elif training_backend_available:
            state = (
                "pipeline-ready-no-data"
            )
        else:
            state = (
                "pipeline-ready-no-data-"
                "backend-external"
            )

        return {
            "status": (
                state
            ),
            "pipeline_ready": (
                pipeline_ready
            ),
            "training_data_available": (
                training_data_available
            ),
            "training_backend_available": (
                training_backend_available
            ),
            "training_backend_required_before_execution": (
                True
            ),
            "litgpt": (
                litgpt
            ),
            "catalog": (
                catalog
            ),
            "supported_training_formats": (
                sorted(
                    TRAINING_FORMATS
                )
            ),
            "stage12_execution_enabled": (
                False
            ),
            "automatic_training": (
                False
            ),
            "checkpoint_created": (
                False
            ),
            "weights_modified": (
                False
            ),
            "external_export": (
                False
            ),
        }