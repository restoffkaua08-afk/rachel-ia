# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
    copy_metadata,
)


ROOT = (
    Path(SPECPATH)
    .resolve()
    .parents[1]
)

APP = (
    ROOT
    / "APP"
)

PLATFORM = (
    ROOT
    / "RACHEL_PLATFORM"
)

SRC = (
    PLATFORM
    / "RUNTIME"
    / "SRC"
)

CORE = (
    ROOT
    / "RACHEL_CORE"
    / "src"
)

BRIDGE = (
    APP
    / "bridge"
    / "rachel_bridge.py"
)


datas = [
    (
        str(
            PLATFORM
            / "CONFIG"
        ),
        "RACHEL_PLATFORM/CONFIG",
    ),
    (
        str(
            SRC
        ),
        "RACHEL_PLATFORM/RUNTIME/SRC",
    ),
    (
        str(
            CORE
        ),
        "RACHEL_CORE/src",
    ),
]


scripts_dir = (
    PLATFORM
    / "SCRIPTS"
)

if scripts_dir.is_dir():
    datas.append(
        (
            str(
                scripts_dir
            ),
            "RACHEL_PLATFORM/SCRIPTS",
        )
    )


tools_dir = (
    PLATFORM
    / "TOOLS"
)

if tools_dir.is_dir():
    datas.append(
        (
            str(
                tools_dir
            ),
            "RACHEL_PLATFORM/TOOLS",
        )
    )


organ_root = (
    PLATFORM
    / "ORGAOS"
)

if organ_root.is_dir():

    for manifest in sorted(
        organ_root.glob(
            "*/organ.json"
        )
    ):
        datas.append(
            (
                str(
                    manifest
                ),
                (
                    "RACHEL_PLATFORM/"
                    "ORGAOS/"
                    + manifest.parent.name
                ),
            )
        )


member_root = (
    PLATFORM
    / "MEMBROS"
)

if member_root.is_dir():

    for member in sorted(
        item
        for item
        in member_root.iterdir()
        if item.is_dir()
    ):

        for metadata in sorted(
            member.glob(
                "*.json"
            )
        ):
            datas.append(
                (
                    str(
                        metadata
                    ),
                    (
                        "RACHEL_PLATFORM/"
                        "MEMBROS/"
                        + member.name
                    ),
                )
            )

        readme = (
            member
            / "README.md"
        )

        if readme.is_file():
            datas.append(
                (
                    str(
                        readme
                    ),
                    (
                        "RACHEL_PLATFORM/"
                        "MEMBROS/"
                        + member.name
                    ),
                )
            )

        member_organs = (
            member
            / "ORGAOS"
        )

        if member_organs.is_dir():

            for manifest in sorted(
                member_organs.glob(
                    "*/organ.json"
                )
            ):
                datas.append(
                    (
                        str(
                            manifest
                        ),
                        (
                            "RACHEL_PLATFORM/"
                            "MEMBROS/"
                            + member.name
                            + "/ORGAOS/"
                            + manifest.parent.name
                        ),
                    )
                )


hiddenimports = [
    path.stem
    for path
    in SRC.glob(
        "*.py"
    )
]


try:
    hiddenimports.extend(
        collect_submodules(
            "rachel_core"
        )
    )
except Exception:
    pass


binaries = []


packages = [
    "numpy",
    "sounddevice",
    "_sounddevice_data",
    "faster_whisper",
    "ctranslate2",
    "tokenizers",
    "av",
    "docling",
    "docling_core",
    "docling_ibm_models",
]


for package in packages:

    try:
        (
            package_datas,
            package_binaries,
            package_hidden,
        ) = collect_all(
            package
        )

        datas.extend(
            package_datas
        )

        binaries.extend(
            package_binaries
        )

        hiddenimports.extend(
            package_hidden
        )

    except Exception:
        pass


for distribution in [
    "numpy",
    "sounddevice",
    "faster-whisper",
    "ctranslate2",
    "tokenizers",
    "av",
    "docling",
    "docling-core",
    "docling-ibm-models",
]:

    try:
        datas.extend(
            copy_metadata(
                distribution
            )
        )

    except Exception:
        pass


hiddenimports = sorted(
    set(
        hiddenimports
    )
)


a = Analysis(
    [
        str(
            BRIDGE
        )
    ],
    pathex=[
        str(
            SRC
        ),
        str(
            CORE
        ),
    ],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)


pyz = PYZ(
    a.pure
)


exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="rachel-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
