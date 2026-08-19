import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "RACHEL_PLATFORM" / "RUNTIME" / "SRC"))
import pytest
from arya_runtime import run, safe_cwd

class AryaTests(unittest.TestCase):
    def test_workspace_is_allowed(self):
        # safe_cwd(None) resolve para WORKSPACE da RACHEL quando setado
        # e cai para ROOT quando não há override. Ambos devem ser aceitos.
        result = safe_cwd(None)
        self.assertIn(str(result), (str(ROOT), str(ROOT / "WORKSPACE")))
    def test_outside_workspace_is_blocked(self):
        with self.assertRaises(ValueError): safe_cwd(str(ROOT.parent))

    # Marcados como xfail: o comportamento atual de arya_runtime exige
    # aprovação Cyber explícita para qualquer execução. Esses testes
    # assumem allowlist antigo (read-only sem aprovação). Serão reescritos
    # na Etapa 4 (tool runtime profissional) com tools tipadas em vez de
    # arya.run genérico.
    @pytest.mark.xfail(reason="arya.run agora exige aprovação Cyber; testes serão migrados para tools tipadas na Etapa 4", strict=False)
    def test_read_only_python_runs_without_approval(self):
        result = run(sys.executable, ["--version"], None, False)
        self.assertEqual(result["returncode"], 0)

    @pytest.mark.xfail(reason="arya.run agora exige aprovação Cyber; testes serão migrados para tools tipadas na Etapa 4", strict=False)
    def test_git_accepts_option_arguments(self):
        result = run("git", ["status", "--short"], None, False)
        self.assertEqual(result["returncode"], 0)

if __name__ == "__main__": unittest.main()
