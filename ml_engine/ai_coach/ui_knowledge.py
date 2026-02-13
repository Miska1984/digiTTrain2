"""
UI Tudásbázis - Ditta számára

Ez a fájl tartalmazza az összes olyan információt, amit Dittának tudnia kell
a DigiT-Train felületéről, hogy navigálni tudja a felhasználókat.

FRISSÍTVE: Base.html alapján teljes menüstruktúra
"""

# ============================================================================
# TELJES NAVIGÁCIÓS STRUKTÚRA (base.html alapján)
# ============================================================================

UI_NAVIGATION_MAP = {
    # === VEZÉRLŐPULT ===
    'role_dashboard': {
        'leírás': '⚙️ Szerepkörök kezelése - Itt válthatsz szerepkörök között és kérhetsz újakat',
        'lokáció': 'Vezérlőpult menü → Szerepkörök kezelése',
        'url_name': 'users:role_dashboard',
        'gombok': ['Új szerepkör igénylése', 'Aktív szerepkör váltás'],
        'vizuális_jel': 'fas fa-cogs ikon a menüben',
        'mikor_használd': 'Ha új szerepkört szeretnél (Sportoló, Edző, Szülő, stb.)',
        'szerepkör': 'Mindenki'
    },
    
    'pending_roles': {
        'leírás': '✅ Jóváhagyások - Várakozó szerepkör-kérések kezelése',
        'lokáció': 'Vezérlőpult menü → Jóváhagyások',
        'url_name': 'users:pending_roles',
        'gombok': ['Jóváhagyás', 'Elutasítás'],
        'vizuális_jel': 'Piros badge ha van várakozó kérés',
        'mikor_használd': 'Ha edző/vezető vagy és valaki csatlakozni szeretne',
        'szerepkör': 'Edző, Egyesületi vezető'
    },
    
    'sharing_center': {
        'leírás': '🔐 Megosztási központ - Adatvédelmi beállítások kezelése',
        'lokáció': 'Vezérlőpult menü → Megosztási központ',
        'url_name': 'data_sharing:sharing_center',
        'gombok': ['Megosztás módosítása', 'Új megosztás', 'Megosztás visszavonása'],
        'vizuális_jel': 'Táblázat zöld/piros jelzőfényekkel',
        'mikor_használd': 'Ha edződdel vagy szülőddel szeretnél adatokat megosztani',
        'szerepkör': 'Mindenki'
    },
    
    # === SPORTOLÓ FUNKCIÓK ===
    'athlete_dashboard': {
        'leírás': '⚽ Adat Összefoglaló - Sportoló központi adatnézet',
        'lokáció': 'Sportoló menü → Adat Összefoglaló',
        'url_name': 'biometric_data:athlete_dashboard',
        'gombok': ['Grafikonok megtekintése', 'Adatok exportálása'],
        'vizuális_jel': 'Grafikonok és statisztikák',
        'mikor_használd': 'Áttekintés a biometriai adataidról',
        'szerepkör': 'Sportoló'
    },
    
    'morning_check': {
        'leírás': '🌅 Reggeli mérések - Napi HRV, súly, alvás rögzítése',
        'lokáció': 'Sportoló menü → Reggeli mérések',
        'url_name': 'biometric_data:morning_check',
        'gombok': ['Mérés rögzítése', 'HRV adatok importálása'],
        'mezők': ['Reggeli súly', 'Ébredési pulzus', 'Alvásidő', 'HRV érték'],
        'vizuális_jel': 'Kék panel szív ikonnal',
        'mikor_használd': 'Minden reggel, felébredés után 5 perccel',
        'szerepkör': 'Sportoló'
    },
    
    'after_training': {
        'leírás': '🌙 Esti mérések - Edzés utáni visszajelzések',
        'lokáció': 'Sportoló menü → Esti mérések',
        'url_name': 'biometric_data:after_training',
        'gombok': ['Edzés értékelése', 'Fáradtság rögzítése'],
        'mezők': ['Edzés intenzitás', 'Fáradtság szint', 'Megjegyzések'],
        'mikor_használd': 'Edzés után, pihenés előtt',
        'szerepkör': 'Sportoló'
    },
    
    'occasional_measurements': {
        'leírás': '📊 Eseti mérések - Testösszetétel és egyéb mérések',
        'lokáció': 'Sportoló menú → Eseti mérések',
        'url_name': 'biometric_data:occasional_measurements',
        'gombok': ['Új mérés rögzítése'],
        'mezők': ['Testzsír %', 'Izomtömeg', 'Vérnyomás'],
        'mikor_használnd': 'Havi vagy negyedéves felmérésekkor',
        'szerepkör': 'Sportoló'
    },
    
    'add_running_performance': {
        'leírás': '🏃 Futás teljesítmény - Futás specifikus adatok',
        'lokáció': 'Sportoló menü → Futás teljesítmény',
        'url_name': 'biometric_data:add_running_performance',
        'gombok': ['Futás rögzítése'],
        'mezők': ['Távolság (km)', 'Idő', 'Átlag pulzus', 'Tempo'],
        'mikor_használd': 'Futóedzések után',
        'szerepkör': 'Sportoló'
    },
    
    'ml_dashboard': {
        'leírás': '📈 Forma Előrejelzés - ML Engine formaindex',
        'lokáció': 'Sportoló menü → Forma Előrejelzés',
        'url_name': 'ml_engine:dashboard',
        'gombok': ['Formaindex részletek', 'Trend elemzés', 'Predikciók'],
        'vizuális_jel': 'Narancssárga panel grafikonokkal',
        'követelmény': '🔒 ML_ACCESS előfizetés szükséges',
        'mit_látsz': 'Formaindex (1-10), túlterhelés figyelmeztetés, pihenésajánlás',
        'frissülés': 'Naponta egyszer, reggeli mérés után',
        'szerepkör': 'Sportoló (ML előfizetéssel)'
    },
    
    'athlete_diagnostics': {
        'leírás': '🎯 Általános elemzés - AI-alapú mozgáselemzés',
        'lokáció': 'Sportoló menü → Általános elemzés',
        'url_name': 'diagnostics:athlete_diagnostics',
        'gombok': ['Videó feltöltése', 'Korábbi elemzések'],
        'követelmény': '1 kredit/videó',
        'mikor_használd': 'Technika ellenőrzéshez',
        'szerepkör': 'Sportoló'
    },
    
    'anthropometry_profile': {
        'leírás': '📏 Antropometriai Profil - Testméretek és arányok',
        'lokáció': 'Sportoló menü → Antropometriai Profil',
        'url_name': 'diagnostics_jobs:anthropometry_profile_view',
        'gombok': ['Adatok frissítése', 'Korábbi mérések'],
        'mezők': ['Testmagasság', 'Nyúlás', 'Végtaghosszok'],
        'mikor_használd': 'Félévente vagy növekedési ciklusokban',
        'szerepkör': 'Sportoló'
    },
    
    # === SZÜLŐ FUNKCIÓK ===
    'parent_dashboard': {
        'leírás': '👨‍👩‍👧 Gyermek(ek) adatai - Szülői áttekintés',
        'lokáció': 'Szülő menü → Gyermek(ek) adatai',
        'url_name': 'data_sharing:parent_dashboard',
        'gombok': ['Gyermek kiválasztása', 'Részletek megtekintése'],
        'mit_látsz': 'Gyermekek biometriai adatai, edzéslátogatottság, forma',
        'mikor_használd': 'Napi követéshez, állapot ellenőrzéshez',
        'szerepkör': 'Szülő'
    },
    
    # === EDZŐ FUNKCIÓK ===
    'add_unregistered_athlete': {
        'leírás': '➕ Sportoló felvitele - Új sportoló hozzáadása',
        'lokáció': 'Edző menü → Sportoló felvitele',
        'url_name': 'data_sharing:add_unregistered_athlete',
        'gombok': ['Regisztrált sportoló hozzáadása', 'Placeholder létrehozása'],
        'mezők': ['Név', 'Születési dátum', 'Sportág'],
        'mikor_használd': 'Új sportoló érkezik a csapatba',
        'szerepkör': 'Edző'
    },
    
    'coach_dashboard': {
        'leírás': '👔 Sportolóim - Edzői áttekintő',
        'lokáció': 'Edző menü → Sportolóim',
        'url_name': 'data_sharing:coach_dashboard',
        'gombok': ['Sportoló kiválasztása', 'Csoportos nézet'],
        'mit_látsz': 'Sportolók biometriai összefoglalója, formaindex, jelenlét',
        'mikor_használd': 'Napi tervezéshez, egyéni követéshez',
        'szerepkör': 'Edző'
    },
    
    'manage_schedules': {
        'leírás': '📅 Edzés tervezés - Naptár és jelenléti ívek',
        'lokáció': 'Edző menü → Edzés tervezés',
        'url_name': 'data_sharing:manage_schedules',
        'gombok': ['Új edzés létrehozása', 'Jelenléti ív megnyitása'],
        'vizuális_jel': 'Naptár nézet',
        'mikor_használd': 'Edzések tervezésekor, jelenlét rögzítésekor',
        'szerepkör': 'Edző'
    },
    
    'attendance_sheet': {
        'leírás': '✅ Jelenléti ív - Edzéslátogatás rögzítése',
        'lokáció': 'Edzés tervezés → Naptár edzés → Jelenléti ív',
        'url_name': 'training_log:attendance_sheet',
        'gombok': ['Jelenlét mentése', 'Exportálás PDF-be'],
        'checkboxok': ['Jelen van', 'Sérült', 'Vendég'],
        'mikor_használd': 'Minden edzés elején vagy végén',
        'szerepkör': 'Edző'
    },
    
    # === EGYESÜLETI VEZETŐ FUNKCIÓK ===
    'leader_dashboard': {
        'leírás': '👑 Biometrikus adatok - Vezetői áttekintés',
        'lokáció': 'Egyesületi Vezető menü → Biometrikus adatok',
        'url_name': 'data_sharing:leader_dashboard',
        'gombok': ['Csoportos statisztikák', 'Exportálás'],
        'mit_látsz': 'Klub összes sportolójának áttekintése',
        'mikor_használd': 'Jelentések készítéséhez, átfogó elemzéshez',
        'szerepkör': 'Egyesületi vezető'
    },
    
    # === PÉNZÜGYEK ===
    'billing_dashboard': {
        'leírás': '💰 Pénzügyi vezérlőpult - Egyenleg és előfizetések',
        'lokáció': 'Pénzügyek menü → Pénzügyi vezérlőpult',
        'url_name': 'billing:billing_dashboard',
        'gombok': ['Egyenleg megtekintése', 'Tranzakciók'],
        'mit_látsz': 'Kredit egyenleg, aktív előfizetések, lejárati dátumok',
        'mikor_használd': 'Egyenleg ellenőrzéshez',
        'szerepkör': 'Mindenki'
    },
    
    'billing_purchase': {
        'leírás': '🛒 Vásárlás - Kredit és előfizetés vásárlás',
        'lokáció': 'Pénzügyek menú → Vásárlás',
        'url_name': 'billing:billing_purchase',
        'gombok': ['Kredit vásárlása', 'ML_ACCESS előfizetés', 'Fizetési előzmények'],
        'fizetés': 'SimplePay - biztonságos magyar fizetési rendszer',
        'árak': {
            'ML_ACCESS_havi': '2990 Ft/hó',
            'ML_ACCESS_éves': '29990 Ft/év (2 hónap ingyen)',
            'kredit_csomag_kis': '10 kredit - 990 Ft',
            'kredit_csomag_közepes': '50 kredit - 3990 Ft',
            'kredit_csomag_nagy': '100 kredit - 6990 Ft'
        },
        'mikor_használd': 'Ha elemzéseket szeretnél vagy videó diagnosztikát',
        'szerepkör': 'Mindenki'
    },
    
    'ad_credit_earn': {
        'leírás': '📺 Kredit Szerzés - Hirdetések nézése kreditért',
        'lokáció': 'Pénzügyek menú → Kredit Szerzés',
        'url_name': 'billing:ad_credit_earn',
        'gombok': ['Hirdetés megtekintése'],
        'jutalom': '1-3 kredit hirdetésenként',
        'mikor_használnd': 'Ha ingyen szeretnél krediteket szerezni',
        'szerepkör': 'Mindenki'
    },
    
    # === PROFIL ===
    'edit_profile': {
        'leírás': '👤 Profil szerkesztése - Személyes adatok módosítása',
        'lokáció': 'Jobb felső sarok → Profil ikon (személy ikon)',
        'url_name': 'users:edit_profile',
        'gombok': ['Profilkép feltöltése', 'Adatok mentése', 'Jelszó módosítása'],
        'mezők': ['Keresztnév', 'Vezetéknév', 'Születési dátum', 'Email'],
        'vizuális_jel': 'bi bi-person-circle ikon',
        'mikor_használd': 'Profil frissítéséhez, képcsere',
        'szerepkör': 'Mindenki'
    },
    
    # === VIDEÓ DIAGNOSZTIKA ===
    'diagnostic_upload': {
        'leírás': '📹 Videó diagnosztika feltöltés - MediaPipe mozgáselemzés',
        'lokáció': 'Diagnosztika menü → Új elemzés',
        'url_name': 'diagnostics:upload_video',
        'gombok': ['Videó feltöltése', 'Elemzés indítása', 'Korábbi elemzések'],
        'vizuális_jel': 'Lila panel kamera ikonnal',
        'követelmények': 'MP4 formátum, maximum 2 perc, jó megvilágítás',
        'költség': '1 kredit/videó',
        'mikor_használd': 'Technika ellenőrzéshez, edzés utáni visszanézéshez',
        'szerepkör': 'Sportoló, Edző'
    },
    
    # === EDZÉSNAPLÓ ===
    'training_log': {
        'leírás': '🏋️ Edzésnapló - Edzések rögzítése és elemzése',
        'lokáció': 'Főoldal → Edzésnapló',
        'url_name': 'training_log:log_list',
        'gombok': ['Új edzés', 'Naptár nézet', 'Statisztikák'],
        'vizuális_jel': 'Zöld panel naptár ikonnal',
        'rögzíthető_adatok': ['Időtartam', 'Intenzitás', 'Sportág', 'Megjegyzés'],
        'mikor_használd': 'Minden edzés után a pontos terheléskép érdekében',
        'szerepkör': 'Sportoló, Edző'
    },
    
    # === FELMÉRÉSEK ===
    'assessment_center': {
        'leírás': '🎯 Felmérések - Fizikai és pszichológiai tesztek',
        'lokáció': 'Főoldal → Felmérések',
        'url_name': 'assessment:assessment_list',
        'gombok': ['Új felmérés indítása', 'Eredmények', 'Összehasonlítás'],
        'vizuális_jel': 'Türkiz panel listák ikonnal',
        'típusok': ['Fizikai kondíció', 'Mentális állapot', 'Helyzetfelmérés'],
        'mikor_használnd': 'Havi rendszerességgel vagy felkészülési ciklusok elején',
        'szerepkör': 'Sportoló, Edző'
    }
}

# ============================================================================
# NAVIGÁCIÓS ÚTVONALAK TÉMÁK SZERINT
# ============================================================================

NAVIGATION_PATHS = {
    'biometria': {
        'kezdőlap': [
            '⚽ Sportoló menú → 🌅 Reggeli mérések',
            '⚽ Sportoló menú → 📊 Adat Összefoglaló'
        ],
        'reggeli_mérés': '⚽ Sportoló menú → 🌅 Reggeli mérések → Mérés rögzítése',
        'esti_mérés': '⚽ Sportoló menú → 🌙 Esti mérések → Edzés értékelése'
    },
    'edzésnapló': [
        '📅 Főoldal középső sáv → Edzésnapló',
        '👔 Edző menü → 📅 Edzés tervezés'
    ],
    'profil': [
        '👤 Jobb felső sarok → Profil ikon',
        '⚙️ Bal oldali menü legalja → Beállítások'
    ],
    'pénzügyek': [
        '💰 Pénzügyek menü → 🛒 Vásárlás',
        '💰 Pénzügyek menü → 💳 Pénzügyi vezérlőpult'
    ],
    'megosztás': [
        '⚙️ Vezérlőpult menü → 🔐 Megosztási központ',
        '👤 Profil → 🔐 Adatvédelem'
    ]
}

# ============================================================================
# GYAKORI KÉRDÉSEK ÉS VÁLASZOK
# ============================================================================

FAQ_SHORTCUTS = {
    'hogyan_mérjek_hrv': {
        'rövid': '🌅 Reggel, felébredés után, még ágyban, ujjadat a kamera fölé tartva.',
        'részletes': '⚽ Sportoló menú → 🌅 Reggeli mérések → Ujjadat 60 másodpercig a kamera fölé. Fontos: felébredés után 5-10 percen belül, még fekvésben.'
    },
    'mi_az_formaindex': {
        'rövid': '📈 ML Engine által számított forma 1-10 skálán.',
        'részletes': '🔒 ML_ACCESS előfizetéssel látható. 8+ kiváló, 5-7 átlagos, 5 alatt pihenés kell. Naponta frissül reggeli mérés után.'
    },
    'mennyibe_kerül': {
        'kredit': '💰 10 kredit: 990 Ft | 50 kredit: 3990 Ft | 100 kredit: 6990 Ft',
        'ml_access': '🔒 ML_ACCESS: 2990 Ft/hó vagy 29990 Ft/év (2 hónap ingyen)',
        'mi_kell_mihez': '📹 Videó diagnosztika: 1 kredit/videó | 📈 ML elemzések: ML_ACCESS előfizetés'
    },
    'hol_profil': {
        'rövid': '👤 Jobb felső sarok → Profil ikon',
        'részletes': '👤 Jobb felső sarokban a személy ikon → Profil szerkesztése → Profilkép feltöltése'
    },
    'hol_reggeli_mérés': {
        'rövid': '⚽ Sportoló menü → 🌅 Reggeli mérések',
        'részletes': '⚽ Sportoló menü → 🌅 Reggeli mérések → Mérés rögzítése gomb'
    },
    'hol_kredit_vásárlás': {
        'rövid': '💰 Pénzügyek menü → 🛒 Vásárlás',
        'részletes': '💰 Pénzügyek menú → 🛒 Vásárlás → Kredit csomagok → SimplePay fizetés'
    },
    'hol_sportolóim': {
        'rövid': '👔 Edző menü → 📋 Sportolóim',
        'részletes': '👔 Edző menú → 📋 Sportolóim → Sportoló kiválasztása → Részletes adatok'
    },
    'hol_gyerekeim': {
        'rövid': '👨‍👩‍👧 Szülő menü → 👶 Gyermek(ek) adatai',
        'részletes': '👨‍👩‍👧 Szülő menú → 👶 Gyermek(ek) adatai → Gyermek kiválasztása'
    },
    'hol_megosztás': {
        'rövid': '⚙️ Vezérlőpult → 🔐 Megosztási központ',
        'részletes': '⚙️ Vezérlőpult menü → 🔐 Megosztási központ → Megosztás módosítása'
    }
}

# ============================================================================
# HIBAÜZENETEK ÉRTELMEZÉSE
# ============================================================================

ERROR_EXPLANATIONS = {
    'no_ml_access': {
        'probléma': '🔒 Nincs ML_ACCESS előfizetésed',
        'megoldás': '💰 Pénzügyek → 🛒 Vásárlás → ML_ACCESS előfizetés',
        'mivel_jár': '📈 Formaindex, predikciók, részletes elemzések, korlátlan lekérdezés'
    },
    'no_credits': {
        'probléma': '💳 Elfogytak a kreditjeid',
        'megoldás': '💰 Pénzügyek → 🛒 Vásárlás → Kredit csomagok',
        'mit_tudsz_csinálni': '📹 Videó diagnosztika indítása'
    },
    'no_data_shared': {
        'probléma': '🔐 A sportoló nem osztotta meg veled az adatait',
        'megoldás': 'Kérd meg a sportolót/szülőt: ⚙️ Vezérlőpult → 🔐 Megosztási központ → Add hozzá a neved',
        'jogosultság': '👔 Edző vagy 👨‍👩‍👧 Szülő lehet megosztási célpont'
    },
    'no_role': {
        'probléma': '⚠️ Nincs aktív szerepköröd',
        'megoldás': '⚙️ Vezérlőpult → Szerepkörök kezelése → Szerepkör igénylése',
        'típusok': '⚽ Sportoló, 👔 Edző, 👨‍👩‍👧 Szülő, 👑 Egyesületi vezető'
    }
}

# ============================================================================
# SZEREPKÖR → MENÜ MAPPING
# ============================================================================

ROLE_MENUS = {
    'Sportoló': [
        'athlete_dashboard', 'morning_check', 'after_training', 
        'occasional_measurements', 'add_running_performance', 
        'ml_dashboard', 'athlete_diagnostics', 'anthropometry_profile'
    ],
    'Szülő': [
        'parent_dashboard'
    ],
    'Edző': [
        'add_unregistered_athlete', 'coach_dashboard', 'manage_schedules', 
        'attendance_sheet'
    ],
    'Egyesületi vezető': [
        'leader_dashboard'
    ],
    'Mindenki': [
        'role_dashboard', 'pending_roles', 'sharing_center',
        'billing_dashboard', 'billing_purchase', 'ad_credit_earn',
        'edit_profile'
    ]
}