from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

from pathlib import Path
from typing import Any


from runtime_paths import (
    CONFIG,
    PLATFORM,
    ROOT,
)


SAMWELL_SCHEMA_VERSION = 2


class SamwellError(
    RuntimeError
):
    pass


class SamwellRuntime:

    def __init__(
        self,
        *,
        catalog_path: Path | None = None,
    ) -> None:

        self.catalog_path = (
            Path(
                catalog_path
                or (
                    CONFIG
                    / "samwell.dependencies.json"
                )
            )
            .expanduser()
            .resolve()
        )

        self.catalog = (
            self._load_catalog()
        )

    def _load_catalog(
        self,
    ) -> dict[str, Any]:

        if not self.catalog_path.is_file():
            raise SamwellError(
                "Catalogo Samwell ausente."
            )

        try:
            value = json.loads(
                self.catalog_path.read_text(
                    encoding="utf-8-sig"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise SamwellError(
                "Catalogo Samwell invalido."
            ) from error

        if (
            not isinstance(
                value,
                dict,
            )
            or value.get(
                "schema_version"
            )
            != SAMWELL_SCHEMA_VERSION
            or value.get(
                "member"
            )
            != "samwell"
        ):
            raise SamwellError(
                "Contrato Samwell invalido."
            )

        return value

    def _environment(
        self,
        environment_id: str,
    ) -> dict[str, Any]:

        value = (
            self.catalog[
                "environments"
            ].get(
                environment_id
            )
        )

        if not isinstance(
            value,
            dict,
        ):
            raise SamwellError(
                "Ambiente desconhecido: "
                + environment_id
            )

        return value

    def _environment_python(
        self,
        environment_id: str,
    ) -> Path | None:

        environment = (
            self._environment(
                environment_id
            )
        )

        relative = environment.get(
            "python_relative"
        )

        if not relative:
            return None

        return (
            ROOT
            / str(relative)
        ).resolve()

    @staticmethod
    def _first_line(
        text: str,
    ) -> str | None:

        for line in text.splitlines():
            clean = line.strip()

            if clean:
                return clean[:500]

        return None

    @staticmethod
    def _run(
        executable: str,
        args: list[str],
    ) -> dict[str, Any]:

        try:
            process = subprocess.run(
                [
                    executable,
                    *args,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                check=False,
            )

            return {
                "available": True,
                "returncode": (
                    process.returncode
                ),
                "version": (
                    SamwellRuntime._first_line(
                        process.stdout
                    )
                    or SamwellRuntime._first_line(
                        process.stderr
                    )
                ),
            }

        except (
            OSError,
            subprocess.SubprocessError,
        ) as error:

            return {
                "available": False,
                "returncode": None,
                "version": (
                    type(error).__name__
                    + ": "
                    + str(error)
                ),
            }

    def _environment_python_probe(
        self,
        environment_id: str,
    ) -> dict[str, Any]:

        python = (
            self._environment_python(
                environment_id
            )
        )

        if (
            python is None
            or not python.is_file()
        ):
            return {
                "available": False,
                "environment": environment_id,
                "path": (
                    str(python)
                    if python
                    else None
                ),
                "version": None,
            }

        result = self._run(
            str(python),
            [
                "-c",
                (
                    "import platform;"
                    "print(platform.python_version())"
                ),
            ],
        )

        return {
            "environment": environment_id,
            "path": str(python),
            **result,
        }

    def _environment_package_probe(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:

        environment_id = str(
            record[
                "environment"
            ]
        )

        python = (
            self._environment_python(
                environment_id
            )
        )

        if (
            python is None
            or not python.is_file()
        ):
            return {
                "available": False,
                "environment": environment_id,
                "python": (
                    str(python)
                    if python
                    else None
                ),
                "module": record.get(
                    "module"
                ),
                "version": None,
            }

        module = str(
            record[
                "module"
            ]
        )

        distribution = str(
            record.get(
                "distribution"
            )
            or module
        )

        script = (
            "import importlib.util,importlib.metadata;"
            f"m={module!r};"
            f"d={distribution!r};"
            "s=importlib.util.find_spec(m);"
            "print('MISSING' if s is None else "
            "importlib.metadata.version(d))"
        )

        result = self._run(
            str(python),
            [
                "-c",
                script,
            ],
        )

        version = result.get(
            "version"
        )

        available = (
            bool(
                result.get(
                    "available"
                )
            )
            and result.get(
                "returncode"
            )
            == 0
            and version != "MISSING"
        )

        return {
            "available": available,
            "environment": environment_id,
            "python": str(python),
            "module": module,
            "version": (
                version
                if available
                else None
            ),
        }

    @staticmethod
    def _resolve_command(
        record: dict[str, Any],
    ) -> str | None:

        localappdata = (
            os.environ.get(
                "LOCALAPPDATA"
            )
        )

        if localappdata:
            for relative in record.get(
                "localappdata_candidates",
                [],
            ):
                candidate = (
                    Path(localappdata)
                    / str(relative)
                )

                if candidate.is_file():
                    return str(
                        candidate.resolve()
                    )

        for name in record.get(
            "names",
            [],
        ):
            found = shutil.which(
                str(name)
            )

            if found:
                return found

        return None

    def _command_probe(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:

        executable = (
            self._resolve_command(
                record
            )
        )

        if executable is None:
            return {
                "available": False,
                "path": None,
                "version": None,
            }

        result = self._run(
            executable,
            [
                str(item)
                for item
                in record.get(
                    "args",
                    [],
                )
            ],
        )

        return {
            "path": executable,
            **result,
        }

    @staticmethod
    def _organ_probe(
        record: dict[str, Any],
    ) -> dict[str, Any]:

        alias = str(
            record[
                "alias"
            ]
        )

        source = (
            PLATFORM
            / "ORGAOS"
            / alias
            / "fonte"
        ).resolve()

        return {
            "available": (
                source.is_dir()
                and (
                    source
                    / "pyproject.toml"
                ).is_file()
            ),
            "path": str(source),
            "alias": alias,
        }

    @staticmethod
    def _portable_probe(
    ) -> dict[str, Any]:

        if bool(
            getattr(
                sys,
                "frozen",
                False,
            )
        ):
            return {
                "available": True,
                "running_frozen": True,
                "path": str(
                    Path(
                        sys.executable
                    ).resolve()
                ),
                "external_python_required": False,
            }

        binaries = (
            ROOT
            / "APP"
            / "src-tauri"
            / "binaries"
        )

        candidates = (
            sorted(
                binaries.glob(
                    "rachel-backend-*.exe"
                )
            )
            if binaries.is_dir()
            else []
        )

        selected = (
            candidates[-1]
            if candidates
            else None
        )

        return {
            "available": (
                selected is not None
            ),
            "running_frozen": False,
            "path": (
                str(
                    selected.resolve()
                )
                if selected
                else None
            ),
            "external_python_required": False,
        }

    def dependency(
        self,
        dependency_id: str,
    ) -> dict[str, Any]:

        record = next(
            (
                item
                for item
                in self.catalog[
                    "dependencies"
                ]
                if item.get(
                    "id"
                )
                == dependency_id
            ),
            None,
        )

        if not isinstance(
            record,
            dict,
        ):
            raise SamwellError(
                "Dependencia desconhecida: "
                + dependency_id
            )

        probe_type = str(
            record[
                "type"
            ]
        )

        if probe_type == "environment-python":
            result = (
                self._environment_python_probe(
                    str(
                        record[
                            "environment"
                        ]
                    )
                )
            )

        elif probe_type == "environment-package":
            result = (
                self._environment_package_probe(
                    record
                )
            )

        elif probe_type == "command":
            result = (
                self._command_probe(
                    record
                )
            )

        elif probe_type == "portable-sidecar":
            result = (
                self._portable_probe()
            )

        elif probe_type == "organ-source":
            result = (
                self._organ_probe(
                    record
                )
            )

        else:
            raise SamwellError(
                "Probe desconhecido: "
                + probe_type
            )

        return {
            "id": dependency_id,
            "type": probe_type,
            "informational_only": bool(
                record.get(
                    "informational_only"
                )
            ),
            **result,
        }

    def audit(
        self,
    ) -> dict[str, Any]:

        items = [
            self.dependency(
                str(
                    record[
                        "id"
                    ]
                )
            )
            for record
            in self.catalog[
                "dependencies"
            ]
        ]

        return {
            "member_id": "samwell",
            "status": "ok",
            "items": items,
            "total": len(items),
            "available": sum(
                bool(
                    item.get(
                        "available"
                    )
                )
                for item
                in items
            ),
            "missing": sum(
                not bool(
                    item.get(
                        "available"
                    )
                )
                for item
                in items
            ),
            "system_mutation": False,
            "automatic_install": False,
            "automatic_update": False,
            "automatic_remove": False,
            "automatic_repair": False,
        }

    def mode(
        self,
        mode_id: str,
        *,
        audit: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        mode = (
            self.catalog[
                "modes"
            ].get(
                mode_id
            )
        )

        if not isinstance(
            mode,
            dict,
        ):
            raise SamwellError(
                "Modo desconhecido: "
                + mode_id
            )

        current = (
            audit
            or self.audit()
        )

        by_id = {
            item[
                "id"
            ]: item
            for item
            in current[
                "items"
            ]
        }

        required = [
            str(item)
            for item
            in mode.get(
                "required",
                [],
            )
        ]

        optional = [
            str(item)
            for item
            in mode.get(
                "optional",
                [],
            )
        ]

        missing = [
            dependency
            for dependency
            in required
            if not bool(
                by_id.get(
                    dependency,
                    {},
                ).get(
                    "available"
                )
            )
        ]

        return {
            "mode": mode_id,
            "ready": (
                len(missing) == 0
            ),
            "required": required,
            "optional": optional,
            "missing": missing,
        }

    def provision_plan(
        self,
        mode_id: str,
    ) -> dict[str, Any]:

        current = self.audit()

        mode = self.mode(
            mode_id,
            audit=current,
        )

        actions = [
            {
                "dependency": dependency,
                "effect": "install",
                "requires_cyber": True,
                "execution_enabled": False,
            }
            for dependency
            in mode[
                "missing"
            ]
        ]

        return {
            "member_id": "samwell",
            "mode": mode_id,
            "mode_ready": mode[
                "ready"
            ],
            "missing": mode[
                "missing"
            ],
            "actions": actions,
            "plan_only": True,
            "requires_cyber": True,
            "execution_enabled": False,
            "automatic_install": False,
            "automatic_update": False,
            "automatic_remove": False,
            "automatic_repair": False,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        audit = self.audit()

        modes = {
            mode_id: self.mode(
                mode_id,
                audit=audit,
            )
            for mode_id
            in self.catalog[
                "modes"
            ]
        }

        by_id = {
            item[
                "id"
            ]: item
            for item
            in audit[
                "items"
            ]
        }

        return {
            "member": {
                "id": "samwell",
                "name": "Samwell",
                "sector": (
                    "Dependencias, Ambientes "
                    "e Portabilidade"
                ),
                "state": "operational",
            },

            "portable_runtime": {
                "internal_term": "frozen",
                "display_name": "Portable Runtime",
                "managed_by": "samwell",
                "external_python_required": False,
                **self._portable_probe(),
            },

            "audit": audit,
            "modes": modes,

            "environment_isolation": {
                "packaging_torch_available": bool(
                    by_id.get(
                        "packaging-torch",
                        {},
                    ).get(
                        "available"
                    )
                ),

                "training_torch_available": bool(
                    by_id.get(
                        "training-torch",
                        {},
                    ).get(
                        "available"
                    )
                ),

                "packaging_torch_does_not_enable_training": True,
            },

            "requires_cyber_for_mutation": True,
            "execution_enabled": False,
            "automatic_install": False,
            "automatic_update": False,
            "automatic_remove": False,
            "automatic_repair": False,
            "training_execution_enabled": False,
            "weights_modified": False,
        }
