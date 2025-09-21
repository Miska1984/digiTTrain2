# users/management/commands/populate_initial_data.py
from django.core.management.base import BaseCommand
from users.models import Role, Sport

class Command(BaseCommand):
    help = 'Adatok feltöltése az adatbázisba a ROLE_CHOICES és SPORT_CHOICES alapján.'

    def handle(self, *args, **options):
        # Szerepkörök feltöltése
        self.stdout.write(self.style.NOTICE("Szerepkörök feltöltése..."))
        for name, _ in Role.ROLE_CHOICES:
            role, created = Role.objects.get_or_create(name=name, defaults={'description': ''})
            if created:
                self.stdout.write(self.style.SUCCESS(f"✅ Szerepkör hozzáadva: '{name}'"))
            else:
                self.stdout.write(self.style.NOTICE(f"➡️ Szerepkör már létezik: '{name}'"))

        # Sportágak feltöltése
        self.stdout.write(self.style.NOTICE("\nSportágak feltöltése..."))
        for name, _ in Sport.SPORT_CHOICES:
            sport, created = Sport.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"✅ Sportág hozzáadva: '{name}'"))
            else:
                self.stdout.write(self.style.NOTICE(f"➡️ Sportág már létezik: '{name}'"))

        self.stdout.write(self.style.SUCCESS("\nAdatfeltöltés kész!"))