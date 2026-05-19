from django.db import models


class Documento(models.Model):

    TIPO_CHOICES = (
        ("procedimento", "Procedimento"),
        ("instrucao", "Instrução"),
        ("norma", "Norma"),
        ("metodo", "Método"),
        ("formulario", "Formulário"),
        ("outros", "Outros"),
    )

    codigo = models.CharField(max_length=50)
    titulo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES)

    arquivo = models.FileField(upload_to="documentos/")

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"
