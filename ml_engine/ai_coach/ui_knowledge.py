"""
UI Tudásbázis - Ditta számára

Ez a fájl tartalmazza az összes olyan információt, amit Dittának tudnia kell
a DigiT-Train felületéről, hogy navigálni tudja a felhasználókat.
"""

# Gombok és funkciók térképe
UI_NAVIGATION_MAP = {
    'biometrics_morning_check': {
        'leírás': 'Reggeli állapotfelmérés - itt rögzítheted a napi HRV és egyéb biometriai adatokat',
        'lokáció': 'Főoldal > Biometria menü > Reggeli ellenőrzés',
        'gombok': ['Mérés rögzítése', 'Előzmények megtekintése'],
        'vizuális_jel': 'kék panel szív ikonnal',
        'mikor_használd': 'Minden reggel, felébredés után 5 perccel'
    },
    'sharing_center': {
        'leírás': 'Adatmegosztás kezelése - itt állíthatod be, ki láthassa az adataidat',
        'lokáció': 'Profil > Adatvédelem > Megosztási központ',
        'gombok': ['Megosztás módosítása', 'Új megosztás', 'Megosztás visszavonása'],
        'vizuális_jel': 'táblázat zöld/piros jelzőfényekkel',
        'mikor_használd': 'Ha edződdel vagy szülőddel szeretnél adatokat megosztani'
    },
    'billing_purchase': {
        'leírás': 'Kredit és előfizetés vásárlás',
        'lokáció': 'Profil > Pénztárca > Vásárlás',
        'gombok': ['Kredit vásárlása', 'ML_ACCESS előfizetés', 'Fizetési előzmények'],
        'fizetés': 'SimplePay - biztonságos magyar fizetési rendszer',
        'árak': {
            'ML_ACCESS_havi': '2990 Ft/hó',
            'ML_ACCESS_éves': '29990 Ft/év (2 hónap ingyen)',
            'kredit_csomag_kis': '10 kredit - 990 Ft',
            'kredit_csomag_közepes': '50 kredit - 3990 Ft',
            'kredit_csomag_nagy': '100 kredit - 6990 Ft'
        },
        'mikor_használd': 'Ha elemzéseket szeretnél vagy videó diagnosztikát'
    },
    'diagnostic_upload': {
        'leírás': 'Videó diagnosztika feltöltés - mozgáselemzés MediaPipe technológiával',
        'lokáció': 'Főoldal > Diagnosztika menü > Új elemzés',
        'gombok': ['Videó feltöltése', 'Elemzés indítása', 'Korábbi elemzések'],
        'vizuális_jel': 'lila panel kamera ikonnal',
        'követelmények': 'MP4 formátum, maximum 2 perc, jó megvilágítás',
        'költség': '1 kredit/videó',
        'mikor_használd': 'Technika ellenőrzéshez, edzés utáni visszanézéshez'
    },
    'ml_dashboard': {
        'leírás': 'ML Engine - gépi tanulási elemzések és formaindex',
        'lokáció': 'Főoldal > ML Engine',
        'gombok': ['Formaindex részletek', 'Trend elemzés', 'Predikciók'],
        'vizuális_jel': 'narancssárga panel grafikonokkal',
        'követelmény': 'ML_ACCESS előfizetés szükséges',
        'mit_látsz': 'Formaindex (1-10), túlterhelés figyelmeztetés, pihenésajánlás',
        'frissülés': 'Naponta egyszer, reggeli mérés után'
    },
    'training_log': {
        'leírás': 'Edzésnapló - edzések rögzítése és elemzése',
        'lokáció': 'Főoldal > Edzésnapló',
        'gombok': ['Új edzés', 'Naptár nézet', 'Statisztikák'],
        'vizuális_jel': 'zöld panel naptár ikonnal',
        'rögzíthető_adatok': ['időtartam', 'intenzitás', 'sportág', 'megjegyzés'],
        'mikor_használd': 'Minden edzés után a pontos terheléskép érdekében'
    },
    'assessment_center': {
        'leírás': 'Felmérések - fizikai és pszichológiai tesztek',
        'lokáció': 'Főoldal > Felmérések',
        'gombok': ['Új felmérés indítása', 'Eredmények', 'Összehasonlítás'],
        'vizuális_jel': 'türkiz panel listák ikonnal',
        'típusok': ['Fizikai kondíció', 'Mentális állapot', 'Helyzetfelmérés'],
        'mikor_használd': 'Havi rendszerességgel vagy felkészülési ciklusok elején'
    }
}

# Navigációs útvonalak témák szerint
NAVIGATION_PATHS = {
    'biometria_kezdőlap': [
        'Főoldal bal felső menü > Biometria ikon',
        'vagy Főoldal > "Ma még nem mértem" figyelmeztetés',
    ],
    'edzésnapló_kezdőlap': [
        'Főoldal középső sáv > Edzésnapló',
        'vagy bal oldali menü > Edzés ikon'
    ],
    'profil_beállítások': [
        'Jobb felső sarok > Profilkép kattintás',
        'vagy bal oldali menü legalja > Beállítások'
    ]
}

# Gyakori kérdések és válaszok
FAQ_SHORTCUTS = {
    'hogyan_mérjek_hrv': {
        'rövid': 'Reggel, felébredés után, még ágyban, ujjadat a kamera fölé tartva.',
        'részletes': 'Biometria menü > Reggeli ellenőrzés > Ujjadat tartsd a telefon kamerája fölé 60 másodpercig. A flash segít a mérésben. Fontos: még felébredés után 5-10 percen belül végezd el, mielőtt felkelnél vagy innál.'
    },
    'mi_az_formaindex': {
        'rövid': 'A gépi tanulási modell által számított aktuális formád 1-10 skálán.',
        'részletes': 'A formaindex az ML Engine szívműködési adatokból, edzésterhelésből és pihenésből számol. 8 felett kiváló forma, 5-7 átlagos, 5 alatt pihenésre van szükség. Naponta frissül a reggeli mérés után.'
    },
    'mennyibe_kerül': {
        'kredit': '10 kredit 990 Ft, 50 kredit 3990 Ft, 100 kredit 6990 Ft',
        'ml_access': 'Havi 2990 Ft vagy éves 29990 Ft (2 hónap ingyen)',
        'mi_kell_mihez': 'Videó diagnosztika: 1 kredit/videó. ML elemzések: ML_ACCESS előfizetés.'
    }
}

# Hibaüzenetek értelmezése
ERROR_EXPLANATIONS = {
    'no_ml_access': {
        'probléma': 'Nincs ML_ACCESS előfizetésed',
        'megoldás': 'Profil > Pénztárca > ML_ACCESS előfizetés vásárlása',
        'mivel_jár': 'Formaindex, predikciók, részletes elemzések, korlátlan lekérdezés'
    },
    'no_credits': {
        'probléma': 'Elfogytak a kreditjeid',
        'megoldás': 'Profil > Pénztárca > Kredit vásárlás',
        'mit_tudsz_csinálni': 'Videó diagnosztika indítása'
    },
    'no_data_shared': {
        'probléma': 'A sportoló nem osztotta meg veled az adatait',
        'megoldás': 'Kérd meg a sportolót vagy szülőt, hogy: Profil > Adatvédelem > Megosztási központ > Add hozzá a neved',
        'jogosultság': 'Edző vagy szülő lehet megosztási célpont'
    }
}