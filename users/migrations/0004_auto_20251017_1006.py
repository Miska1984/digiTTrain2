# users/migrations/0004_auto_20251017_1006.py

from django.db import migrations

def create_initial_roles_and_sports(apps, schema_editor):
    # Fontos: A modelleket a migrációs környezetből kell lekérni (apps.get_model)
    Role = apps.get_model('users', 'Role')
    Sport = apps.get_model('users', 'Sport')
    
    # ROLE CHOICES ADATOK
    ROLE_CHOICES = [
        ('Egyesületi vezető', 'Egyesületi vezető'),
        ('Edző', 'Edző'),
        ('Sportoló', 'Sportoló'),
        ('Szülő', 'Szülő'),
    ]

    for name, _ in ROLE_CHOICES:
        # get_or_create-et használunk, hogy ne próbálja újra létrehozni, ha már létezik
        Role.objects.get_or_create(
            name=name, 
            defaults={'description': f'{name} szerepkör'}
        )
    
    # SPORT CHOICES ADATOK
    SPORT_CHOICES = [
        ('Kosárlabda', 'Kosárlabda'),
        ('Birkózás', 'Birkózás'),
        ('Labdarúgás', 'Labdarúgás'),
        ('Kézilabda', 'Kézilabda'),
        ('Vízilabda', 'Vízilabda'),
        ('Röplabda', 'Röplabda'),
        ('Asztalitenisz', 'Asztalitenisz'),
        ('Úszás', 'Úszás'),
    ]

    for name, _ in SPORT_CHOICES:
        Sport.objects.get_or_create(name=name)

def reverse_initial_roles_and_sports(apps, schema_editor):
    # A visszaállító (rollback) funkció
    Role = apps.get_model('users', 'Role')
    Sport = apps.get_model('users', 'Sport')

    # Csak az általunk beillesztett adatok törlése
    Role.objects.filter(name__in=['Egyesületi vezető', 'Edző', 'Sportoló', 'Szülő']).delete()
    Sport.objects.filter(name__in=['Kosárlabda', 'Birkózás', 'Labdarúgás', 'Kézilabda', 
                                    'Vízilabda', 'Röplabda', 'Asztalitenisz', 'Úszás']).delete()
    

class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_alter_role_description'), # A 0003 a függőség
    ]

    operations = [
        # Ez a sor futtatja le a fenti Python kódot
        migrations.RunPython(create_initial_roles_and_sports, reverse_initial_roles_and_sports),
    ]