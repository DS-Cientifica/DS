from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PerfilUsuario


@receiver(post_save, sender=User)
def criar_perfil(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.create(user=instance, empresa="DS Científica")


@receiver(post_save, sender=User)
def salvar_perfil(sender, instance, **kwargs):
    perfil, created = PerfilUsuario.objects.get_or_create(
        user=instance,
        defaults={"empresa": "DS Científica"},
    )
    if not perfil.empresa:
        perfil.empresa = "DS Científica"
    perfil.save()
