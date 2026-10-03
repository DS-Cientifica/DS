import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase

from .configuration import (
    DEVELOPMENT_SECRET_PREFIX,
    database_password_from_environment,
    secret_key_from_environment,
)


class SecureConfigurationTests(SimpleTestCase):
    def test_debug_usa_secret_key_configurada(self):
        self.assertEqual(
            secret_key_from_environment(
                debug=True,
                environ={"DJANGO_SECRET_KEY": "valor-configurado-apenas-de-teste"},
            ),
            "valor-configurado-apenas-de-teste",
        )

    def test_producao_exige_secret_key_externa(self):
        with self.assertRaises(ImproperlyConfigured):
            secret_key_from_environment(debug=False, environ={})

    def test_producao_usa_secret_key_configurada(self):
        self.assertEqual(
            secret_key_from_environment(
                debug=False,
                environ={"DJANGO_SECRET_KEY": "valor-configurado-apenas-de-teste"},
            ),
            "valor-configurado-apenas-de-teste",
        )

    def test_desenvolvimento_pode_usar_chave_explicitamente_local(self):
        primeira = secret_key_from_environment(debug=True, environ={})
        segunda = secret_key_from_environment(debug=True, environ={})

        self.assertTrue(primeira.startswith(DEVELOPMENT_SECRET_PREFIX))
        self.assertEqual(primeira, segunda)

    def test_producao_sem_database_url_exige_senha_externa(self):
        with self.assertRaises(ImproperlyConfigured):
            database_password_from_environment(
                debug=False,
                database_url="",
                environ={},
            )

    def test_database_url_dispensa_fallback_de_senha(self):
        self.assertEqual(
            database_password_from_environment(
                debug=False,
                database_url="postgresql://configurado-externamente",
                environ={},
            ),
            "",
        )

    def test_banco_local_usa_senha_configurada_externamente(self):
        self.assertEqual(
            database_password_from_environment(
                debug=True,
                database_url="",
                environ={"DB_PASSWORD": "senha-local-apenas-de-teste"},
            ),
            "senha-local-apenas-de-teste",
        )


class NormalRequestPrivilegeTests(TestCase):
    def test_requisicao_normal_nao_cria_superusuario(self):
        with patch.dict(
            os.environ,
            {
                "DJANGO_SUPERUSER_USERNAME": "bootstrap-inexistente",
                "DJANGO_SUPERUSER_PASSWORD": "valor-apenas-de-teste",
            },
        ):
            response = self.client.get("/admin/login/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            get_user_model().objects.filter(username="bootstrap-inexistente").exists()
        )

    def test_requisicao_normal_nao_promove_usuario_existente(self):
        user = get_user_model().objects.create_user(
            username="usuario-comum",
            password="valor-apenas-de-teste",
        )

        with patch.dict(
            os.environ,
            {
                "DJANGO_SUPERUSER_USERNAME": user.username,
                "DJANGO_SUPERUSER_PASSWORD": "outro-valor-apenas-de-teste",
            },
        ):
            response = self.client.get("/admin/login/")

        self.assertEqual(response.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
