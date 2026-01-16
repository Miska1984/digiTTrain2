# ml_engine/ai_coach/navigator.py
from .base_persona import BasePersona
from django.urls import reverse
from datetime import date

class NavigatorPersona(BasePersona):
    UI_MAP = {
        'biometrics_morning_check': {
            'gombok': ['Mérés rögzítése', 'HRV adatok importálása'],
            'mezők': ['Reggeli súly', 'Ébredési pulzus', 'Alvásidő'],
            'helyszín': 'a kék színű mérések panelen'
        },
        'sharing_center': {
            'gombok': ['Megosztás módosítása', 'Összes engedélyezése'],
            'leírás': 'egy táblázat, ahol a sorok a méréstípusok, az oszlopok a személyek'
        },
        'billing_purchase': {
            'gombok': ['Kredit vásárlása', 'ML_ACCESS előfizetés', 'Kupon beváltása'],
            'fizetés': 'SimplePay vagy bankkártyás fizetés érhető el'
        },
        'attendance_sheet': {
            'gombok': ['Jelenlét mentése', 'Exportálás PDF-be'],
            'checkboxok': ['Jelen van', 'Sérült', 'Vendég']
        }
    }

    def get_response(self, user, context_app, query=None):
        profile = getattr(user, 'profile', None)
        has_profile_name = bool(profile.first_name and profile.last_name) if profile else False
        is_adult = user.is_adult
        
        has_role = user.user_roles.filter(status='approved').exists()
        pending_role = user.user_roles.filter(status='pending').exists()
        
        if query:
            # Dinamikus URL-ek a promptba építéshez
            billing_url = reverse('billing:billing_purchase')
            sharing_url = reverse('data_sharing:sharing_center')
            attendance_url = reverse('data_sharing:manage_schedules') # A naptárnézet/jelenléti ívekhez
            
            display_name = profile.last_name if has_profile_name else user.username
            ui_info = self.UI_MAP.get(context_app, "Általános nézet, nincsenek specifikus gombnevek.")

            # Biometrikus adat ellenőrzés az import helyben hagyásával (circular import elkerülése)
            from biometric_data.models import WeightData
            has_today_data = WeightData.objects.filter(user=user, workout_date=date.today()).exists()

            prompt = (
                f"Te Ditta vagy, a DigiT-Train személyi asszisztense. "
                f"A felhasználó egy {'felnőtt' if is_adult else '18 év alatti sportoló'}. "
                f"Név: {display_name}. Aktuális oldal: '{context_app}'. "
                f"AKTUÁLIS OLDAL TECHNIKAI ADATAI (SZÓTÁR): {ui_info}\n"
                "KÜLDETÉSED:\n"
                "1. PONTOSSÁG: Ha navigációban segítesz, KIZÁRÓLAG a fenti szótárban szereplő gombneveket és helyszínleírásokat használd!\n"
                f"Kérdés: '{query}'. "
                "\nFELADATAID:\n"
                "1. SEGÍTŐ ASSZISZTENS: Segíts a felhasználónak kiigazodni a programban.\n"
                "2. ELEMZÉSRE VALÓ UTALÁS: Ha a felhasználó elemzést kér, irányítsd az "
                f"<a href='{billing_url}' class='fw-bold'>ML előfizetésre</a>.\n"
                "3. EDZÉSTERVEZÉS: Mondd meg, hogy ez az edző feladata.\n"
                "4. ETIKA: Trágárság esetén kérj tiszteletet.\n"
                "5. ROBOT MÓD ÉS MÉRÉSEK: Magyarázd el: Az Edző végzi a manuális felméréseket (pl. Cooper-teszt, ugrások) "
                "a placeholder sportolóknak. A cél, hogy később mindenki maga töltse a saját biometriáját.\n"
                "6. ELŐFIZETÉS: ML_ACCESS, ANALYSIS, AD_FREE.\n"
                "7. ADATVÉDELEM: <a href='{sharing_url}'>Sharing Center</a> fontossága.\n"
                "8. EDZÉSNAPLÓ ÉS TESZTEK: Az edzők a jelenléti ív mellett az állapotfelméréseket is rögzíthetik. "
                "Mondd el, hogy a mentés után ezek az adatok azonnal látszanak a sportoló profilján is.\n"
                "Válaszolj röviden, segítőkészen, magyarul!"
            )
            return self._generate(prompt)

        return self._get_smart_welcome(user, context_app, has_profile_name, has_role, pending_role)

    def _get_smart_welcome(self, user, context_app, has_profile_name, has_role, pending_role):
        profile_url = reverse('users:edit_profile') 
        role_url = reverse('users:role_dashboard')
        pending_list_url = reverse('core:main_page') 

        display_name = user.profile.last_name if hasattr(user, 'profile') and user.profile.last_name else user.username

        # 1. Speciális eset: Főoldali jóváhagyási feladatok
        if context_app == 'main_page_has_pending_tasks':
            return (
                f"Szia {display_name}! Úgy látom, **jóváhagyásra váró kéréseid érkeztek**. "
                f"Kérlek, nézd meg a <a href='{pending_list_url}' class='fw-bold text-danger'>főoldali értesítéseidet</a>, "
                "hogy mindenki tudja folytatni a munkát!"
            )

        # 2. Robot mód üdvözlések
        role_instructions = {
            'create_coach': "Személyi asszisztens üzemmód: Edzői jelentkezés. Segítek kiválasztani a klubodat és a sportágadat.",
            'create_athlete': "Személyi asszisztens üzemmód: Sportoló regisztráció. Segítek megtalálni a klubodat és az edződet.",
            'create_parent': "Személyi asszisztens üzemmód: Szülői fiók. Segítek összekapcsolni a profilodat a gyermekedével.",
            'create_club_and_leader_role': "Személyi asszisztens üzemmód: Egyesületi vezető. Segítek létrehozni a klubodat.",
        }

        if context_app in role_instructions:
            return f"Szia {display_name}! {role_instructions[context_app]}"

        # 3. Profil hiány
        if not has_profile_name:
            return f"Szia {user.username}! Ditta vagyok. Kérlek, add meg a neved a <a href='{profile_url}'>Profilodnál</a> a könnyebb navigáció érdekében!"
        
        # 4. Biometrikus adatok
        biometric_instructions = {
            'biometrics_morning_check': "Itt tudod rögzíteni a reggeli méréseidet. A testsúly és a HRV adatok segítik az elemzést!",
            'biometrics_dashboard': "Ez a te személyes adat-központod. Itt látod a grafikonokat.",
            'add_running_performance': "Itt tudod rögzíteni a futás teljesítményedet.",
            'occasional_measurements': "Eseti mérések és testösszetétel rögzítése.",
            'after_training': "Esti mérések és edzés utáni visszajelzések.",
        }

        if context_app in biometric_instructions:
            return f"Szia {display_name}! {biometric_instructions[context_app]}"
        
        # 5. Billing
        billing_instructions = {
            'billing_dashboard': "Itt látod az egyenlegedet. Segíthetek választani a csomagok közül?",
            'billing_purchase': "Válassz egy csomagot! Az **ML_ACCESS** biztosítja a legmélyebb elemzéseket.",
            'ad_view': "Nézz meg egy hirdetést ingyen kreditpontokért!",
        }

        if context_app in billing_instructions:
            return f"Szia {display_name}! {billing_instructions[context_app]}"
        
        # 6. Adatmegosztás, Edzésnapló, Vezető
        sharing_instructions = {
            'sharing_center': "Ez az Adatmegosztási Központ. Itt szabályozhatod, ki láthatja a méréseidet.",
            'shared_data_view': "Itt látod azon sportolóid listáját, akik megosztották veled méréseiket.",
            'manage_schedules': "Itt tudod kezelni az edzéstervedet. Kattints egy időpontra a jelenléti ívhez!",
            'attendance_sheet': "A jelenléti ívnél jelöld a hiányzókat, sérülteket vagy vendégjátékosokat!",
            'leader_dashboard': "Klubvezetői nézet: Áttekintheted a klub összes edzőjét és sportolóját.",
            'parent_dashboard': "Szülői felület: Kövesd nyomon gyermekeid látogatottságát és fejlődését.",
        }

        if context_app in sharing_instructions:
            return f"Szia {display_name}! {sharing_instructions[context_app]}"

        # 7. Szerepkör hiánya
        if not has_role and not pending_role:
            return f"Szia {display_name}! Válasszunk egy szerepkört a <a href='{role_url}'>Vezérlőpultban</a>!"
        
        if pending_role:
            return f"Szia {display_name}! A jelentkezésedet rögzítettük, várjuk a vezető jóváhagyását."

        return f"Szia {display_name}! Ditta vagyok, a segítőd. Melyik funkciót keresed?"