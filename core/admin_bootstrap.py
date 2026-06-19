import os

from django.contrib.auth import get_user_model


def ensure_admin_user():
    username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "").strip()
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()

    if not username or not password:
        return False

    user_model = get_user_model()
    user, created = user_model.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "is_staff": True,
            "is_superuser": True,
        },
    )

    changed = False

    if email and user.email != email:
        user.email = email
        changed = True

    if not user.is_staff:
        user.is_staff = True
        changed = True

    if not user.is_superuser:
        user.is_superuser = True
        changed = True

    if created or not user.check_password(password):
        user.set_password(password)
        changed = True

    if changed:
        user.save()

    return created or changed
