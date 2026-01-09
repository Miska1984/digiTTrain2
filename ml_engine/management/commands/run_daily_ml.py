from django.core.management.base import BaseCommand
from ml_engine.tasks import (
    generate_user_features, 
    train_form_prediction_model, 
    predict_form_for_active_subscribers
)

class Command(BaseCommand):
    help = "Lefuttatja a teljes napi ML folyamatot"

    def handle(self, *args, **options):
        self.stdout.write("1. Feature generálás indítása...")
        generate_user_features()
        
        self.stdout.write("2. Modell tréning indítása...")
        train_form_prediction_model()
        
        self.stdout.write("3. Predikciók generálása...")
        predict_form_for_active_subscribers()
        
        self.stdout.write("✅ A napi ML folyamat sikeresen befejeződött.")