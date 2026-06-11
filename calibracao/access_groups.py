def apply_default_access_groups(Group, Permission):
    def perms_for(models_by_app, actions):
        query = None
        for app_label, models in models_by_app.items():
            for model in models:
                codenames = [f"{action}_{model}" for action in actions]
                current = Permission.objects.filter(
                    content_type__app_label=app_label,
                    content_type__model=model,
                    codename__in=codenames,
                )
                query = current if query is None else (query | current)
        return query.distinct() if query is not None else Permission.objects.none()

    all_business_models = {
        "clientes": ["cliente", "contatocliente", "clienteanexo", "perfilusuario"],
        "comercial": [
            "produtoservico",
            "composicaopreco",
            "dadostecnicos",
            "produtoanexo",
            "proposta",
            "propostaanexo",
            "itemproposta",
            "crmregistro",
            "crminteracao",
            "crmticket",
        ],
        "financeiro": [
            "categoriafinanceira",
            "contapagar",
            "contareceber",
            "imposto",
            "pedidocompra",
            "pedidocompraitem",
        ],
        "calibracao": [
            "instrumento",
            "instrumentotecnico",
            "ordemservico",
            "padrao",
            "periodicidade",
            "calibracao",
            "calibracaoanexo",
            "calibracaoturbidez",
            "turbidezpadraoutilizado",
            "turbidezverificacaoponto",
            "turbidezcalibracaoponto",
            "turbidezincertezaponto",
            "calibracaocolorimetro",
            "colorimetropadraoutilizado",
            "colorimetroverificacaoponto",
            "colorimetrocalibracaoponto",
            "colorimetroincertezaponto",
            "calibracaopressao",
            "pressaopadraoutilizado",
            "pressaocalibracaoponto",
            "pressaoincertezaponto",
        ],
        "qualidade": ["documento", "documentorevisao"],
    }

    group_definitions = {
        "Administrador": {
            "models": {
                **all_business_models,
                "auth": ["user", "group"],
            },
            "actions": ("view", "add", "change", "delete"),
        },
        "Comercial": {
            "models": {
                "clientes": ["cliente", "contatocliente"],
                "comercial": [
                    "produtoservico",
                    "composicaopreco",
                    "dadostecnicos",
                    "produtoanexo",
                    "proposta",
                    "propostaanexo",
                    "itemproposta",
                    "crmregistro",
                    "crminteracao",
                    "crmticket",
                ],
            },
            "actions": ("view", "add", "change"),
        },
        "Financeiro": {
            "models": {
                "clientes": ["cliente", "contatocliente"],
                "comercial": ["proposta", "itemproposta"],
                "financeiro": [
                    "categoriafinanceira",
                    "contapagar",
                    "contareceber",
                    "imposto",
                    "pedidocompra",
                    "pedidocompraitem",
                ],
            },
            "actions": ("view", "add", "change"),
        },
        "Metrologia": {
            "models": {
                "clientes": ["cliente", "contatocliente"],
                "qualidade": ["documento"],
                "calibracao": [
                    "instrumento",
                    "instrumentotecnico",
                    "ordemservico",
                    "padrao",
                    "periodicidade",
                    "calibracao",
                    "calibracaoanexo",
                    "calibracaoturbidez",
                    "turbidezpadraoutilizado",
                    "turbidezverificacaoponto",
                    "turbidezcalibracaoponto",
                    "turbidezincertezaponto",
                    "calibracaocolorimetro",
                    "colorimetropadraoutilizado",
                    "colorimetroverificacaoponto",
                    "colorimetrocalibracaoponto",
                    "colorimetroincertezaponto",
                    "calibracaopressao",
                    "pressaopadraoutilizado",
                    "pressaocalibracaoponto",
                    "pressaoincertezaponto",
                ],
            },
            "actions": ("view", "add", "change"),
        },
        "Qualidade": {
            "models": {
                "qualidade": ["documento", "documentorevisao"],
                "calibracao": ["padrao"],
            },
            "actions": ("view", "add", "change"),
        },
        "Consulta": {
            "models": all_business_models,
            "actions": ("view",),
        },
    }

    for group_name, config in group_definitions.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        group.permissions.set(perms_for(config["models"], config["actions"]))
