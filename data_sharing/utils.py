# data_sharing/utils.py
from django.apps import apps
from django.conf import settings
from .models import DataSharingPermission
from users.models import UserRole

def get_model_display_name(app_name, table_name):
    translations = {
        'UserFeatureSnapshot': 'Aktuális forma és állapot',
        'UserPredictionResult': 'Teljesítmény előrejelzés',
        'DiagnosticJob': 'Mozgáselemzési diagnosztika',
        'Attendance': 'Edzéslátogatás és jelenlét',
        'WeightData': 'Testsúly adatok',
        'HRVandSleepData': 'HRV és Alvás adatok',
        'WorkoutFeedback': 'Edzés visszajelzések',
        'RunningPerformance': 'Futóteljesítmény',
    }
    if table_name in translations:
        return translations[table_name]
    try:
        model = apps.get_model(app_label=app_name, model_name=table_name)
        return model._meta.verbose_name
    except:
        return table_name

def get_shareable_models():
    return getattr(settings, 'SHAREABLE_DATA_MODELS', {})

def is_permission_active(permission_obj):
    """
    Kiszámolja a végleges 'enabled' állapotot a kiskorú/felnőtt logika alapján.
    """
    athlete = permission_obj.athlete
    is_adult = getattr(athlete, 'is_adult', True) 

    # 1. HA FELNŐTT: Csak a sportoló döntése számít
    if is_adult:
        return permission_obj.athlete_consent

    # 2. HA KISKORÚ: Kell a sportolói ÉS a szülői beleegyezés is
    if not (permission_obj.athlete_consent and permission_obj.parent_consent):
        return False
    
    # 3. KISKORÚ FŐKAPCSOLÓ: 
    # Megosztott-e a gyerek bármilyen adatot legalább egy szülővel?
    parent_ids = UserRole.objects.filter(
        user=athlete, 
        parent__isnull=False
    ).values_list('parent_id', flat=True).distinct()

    has_parental_main_access = DataSharingPermission.objects.filter(
        athlete=athlete,
        target_person_id__in=parent_ids,
        athlete_consent=True
    ).exists()
    
    return has_parental_main_access

def build_sharing_matrix(data_owner, target_list):
    """
    target_list: [{'user_id': 1, 'role_id': 5, 'name': 'Kovács Edző', ...}, ...]
    """
    shareable_models = get_shareable_models()
    matrix_rows = []

    # Végigmegyünk a célpontokon (minden sor egy Edző/Vezető egy adott szerepkörben)
    for target in target_list:
        row = {
            'target_user_id': target['user_id'],
            'target_user_name': target['name'],
            'target_role_id': target['role_id'],
            'target_role_name': target['role_name'],
            'target_club_name': target['club_name'],
            'cells': []
        }

        # Minden célponthoz végignézzük az összes oszlopot (adattípust)
        for app_name, table_names in shareable_models.items():
            for table_name in table_names:
                # Lekérjük az aktuális engedélyt (ha nincs, létrehozzuk alapértelmezetten False-szal)
                perm, _ = DataSharingPermission.objects.get_or_create(
                    athlete=data_owner,
                    target_person_id=target['user_id'],
                    target_role_id=target['role_id'], # MOST MÁR SZEREPKÖRRE IS SZŰRÜNK
                    app_name=app_name,
                    table_name=table_name
                )

                # A cella tartalmazza a kapcsoló állapotát
                row['cells'].append({
                    'app_name': app_name,
                    'table_name': table_name,
                    'display_name': get_model_display_name(app_name, table_name),
                    'athlete_consent': perm.athlete_consent,
                    'parent_consent': perm.parent_consent,
                    'enabled': is_permission_active(perm)
                })

        matrix_rows.append(row)

    return matrix_rows