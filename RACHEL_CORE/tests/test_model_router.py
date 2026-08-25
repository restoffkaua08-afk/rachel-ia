import unittest

from rachel_core.adapters.model_router import ModelProfile, ModelRouter, PrivacyPolicy
from rachel_core.domain.enums import Role
from rachel_core.domain.errors import ModelError
from rachel_core.domain.models import Message, ModelResponse


class FakeProvider:
    def __init__(self, provider_name, model_name, *, fail=False):
        self.provider_name = provider_name
        self.model_name = model_name
        self.fail = fail
        self.generate_calls = 0
        self.stream_calls = 0
        self.health_calls = 0

    def health(self):
        self.health_calls += 1
        return {
            "available": not self.fail,
            "reachable": not self.fail,
            "provider": self.provider_name,
            "model": self.model_name,
            "model_available": not self.fail,
        }

    def generate(self, messages, system_prompt):
        self.generate_calls += 1
        if self.fail:
            raise ModelError("provider offline")
        return ModelResponse(
            content=f"response:{self.model_name}",
            provider=self.provider_name,
            model=self.model_name,
        )

    def generate_stream(self, messages, system_prompt):
        self.stream_calls += 1
        if self.fail:
            raise ModelError("provider offline")
        yield f"stream:{self.model_name}"


def user_message(content):
    return Message(conversation_id="test", role=Role.USER, content=content)


class ModelRouterTests(unittest.TestCase):
    def setUp(self):
        self.local = FakeProvider("local", "local-fast")
        self.cloud = FakeProvider("cloud", "cloud-reasoning")
        self.profiles = (
            ModelProfile(
                name="fast",
                provider="local",
                task_types=("fast", "general"),
                local=True,
                priority=10,
            ),
            ModelProfile(
                name="reasoning",
                provider="cloud",
                task_types=("reasoning", "coding"),
                local=False,
                priority=10,
            ),
            ModelProfile(
                name="local-fallback",
                provider="local",
                task_types=("reasoning", "coding", "vision"),
                local=True,
                priority=100,
            ),
        )

    def router(self, mode="hybrid", *, allow_sensitive_cloud=False):
        return ModelRouter(
            providers={"local": self.local, "cloud": self.cloud},
            profiles=self.profiles,
            policy=PrivacyPolicy(
                mode=mode,
                protect_pii=True,
                allow_cloud_for_sensitive_data=allow_sensitive_cloud,
            ),
        )

    def test_short_chat_uses_fast_local_profile(self):
        router = self.router("hybrid")

        response = router.generate([user_message("Olá, tudo bem?")], None)

        self.assertEqual("local", response.provider)
        self.assertEqual("fast", router.last_route.profile)
        self.assertEqual("fast", router.last_route.task_type)
        self.assertEqual(1, self.local.generate_calls)
        self.assertEqual(0, self.cloud.generate_calls)

    def test_planner_uses_reasoning_cloud_when_hybrid_and_not_sensitive(self):
        router = self.router("hybrid")

        response = router.generate(
            [user_message("Analise o projeto e planeje a correção em várias etapas")],
            "Você é o planejador de ferramentas da Rachel.",
        )

        self.assertEqual("cloud", response.provider)
        self.assertEqual("reasoning", router.last_route.profile)
        self.assertEqual("reasoning", router.last_route.task_type)
        self.assertEqual(1, self.cloud.generate_calls)

    def test_local_only_uses_exact_reasoning_fallback_and_never_calls_cloud(self):
        router = self.router("local-only")

        response = router.generate(
            [user_message("Planeje uma arquitetura completa para este sistema")],
            None,
        )
        health = router.health()

        self.assertEqual("local", response.provider)
        self.assertEqual("local-fallback", router.last_route.profile)
        self.assertEqual("reasoning", router.last_route.task_type)
        self.assertTrue(router.last_route.local)
        self.assertEqual(0, self.cloud.generate_calls)
        self.assertEqual(0, self.cloud.health_calls)
        self.assertIn("local", health["providers"])
        self.assertNotIn("cloud", health["providers"])

    def test_hybrid_routes_sensitive_content_to_local(self):
        router = self.router("hybrid")

        response = router.generate(
            [
                user_message(
                    "Planeje a migração e considere meu email kaua@example.com durante a análise"
                )
            ],
            None,
        )

        self.assertEqual("local", response.provider)
        self.assertEqual("local-fallback", router.last_route.profile)
        self.assertTrue(router.last_route.sensitive)
        self.assertEqual(0, self.cloud.generate_calls)

    def test_cloud_failure_falls_back_to_local_without_claiming_success_from_cloud(self):
        self.cloud.fail = True
        router = self.router("hybrid")

        response = router.generate(
            [user_message("Planeje e compare profundamente esta arquitetura")],
            None,
        )

        self.assertEqual("local", response.provider)
        self.assertEqual(1, self.cloud.generate_calls)
        self.assertEqual(1, self.local.generate_calls)
        self.assertTrue(router.last_route.local)

    def test_streaming_uses_selected_profile_and_exposes_route_metadata(self):
        router = self.router("hybrid")

        chunks = list(
            router.generate_stream(
                [user_message("Refatore este código Python e explique as decisões")],
                None,
            )
        )

        self.assertEqual(["stream:cloud-reasoning"], chunks)
        self.assertEqual("cloud", router.provider_name)
        self.assertEqual("cloud-reasoning", router.model_name)
        self.assertEqual("coding", router.last_route.task_type)

    def test_sensitive_detection_covers_credentials(self):
        self.assertTrue(ModelRouter.sensitive_content("api_key=super-secret"))
        self.assertTrue(ModelRouter.sensitive_content("senha: abc123"))
        self.assertFalse(ModelRouter.sensitive_content("documentação pública do projeto"))


if __name__ == "__main__":
    unittest.main()
