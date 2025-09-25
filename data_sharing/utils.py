# data_sharing/utils.py
from django.apps import apps
from django.conf import settings
from .models import BiometricSharingPermission


def get_model_display_name(app_name, table_name):
    """Model felhasználóbarát neve"""
    try:
        model = apps.get_model(app_label=app_name, model_name=table_name)
        return model._meta.verbose_name
    except LookupError:
        return table_name


def get_shareable_models():
    """A settings.SHAREABLE_DATA_MODELS lekérése"""
    return getattr(settings, 'SHAREABLE_DATA_MODELS', {})


def build_sharing_matrix(data_owner, target_users):
    """
    Megépíti az adatmegosztási mátrixot egy sportolóhoz.
    """
    shareable_models = get_shareable_models()
    matrix_rows = []

    for app_name, table_names in shareable_models.items():
        for table_name in table_names:
            row_data = {
                'app_name': app_name,
                'table_name': table_name,
                'display_name': get_model_display_name(app_name, table_name),
                'permissions': {}
            }
            for target in target_users:
                permission = BiometricSharingPermission.objects.filter(
                    user=data_owner,
                    target_user=target['user'],
                    app_name=app_name,
                    table_name=table_name
                ).first()
                row_data['permissions'][str(target['user'].id)] = permission.enabled if permission else False
            matrix_rows.append(row_data)

    return matrix_rows
