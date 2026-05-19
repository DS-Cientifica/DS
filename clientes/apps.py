from django.apps import AppConfig


class ClientesConfig(AppConfig):
    name = 'clientes'

    def ready(self):
        import clientes.signals
