"""
Ditta Tudásbázis - Szakmai kifejezések és fogalmak

Ez a modul tartalmazza az összes sportspecifikus és rendszerspecifikus 
szakmai tudást, amit Dittának ismernie kell a megfelelő kommunikációhoz.

A tudás kategóriákba van szervezve:
- Általános sport tudományos fogalmak (minden sportágban használható)
- Sportág-specifikus kifejezések
- Rendszer-specifikus fogalmak (DigiT-Train funkcionalitás)
"""

# ============================================================================
# ÁLTALÁNOS SPORTTUDOMÁNYOS FOGALMAK
# ============================================================================

BIOMETRIC_TERMS = {
    "HRV": {
        "teljes_név": "Heart Rate Variability - Szívfrekvencia variabilitás",
        "rövid_magyarázat": "A szívverések közötti időbeli eltérések mértéke",
        "mit_jelent": "Magasabb érték jobb kipihentséget és regenerációt jelez. Alacsony HRV túlterhelésre vagy stresszre utalhat.",
        "normál_tartomány": {
            "fiatal_sportoló": "50-100 ms",
            "elit_sportoló": "80-150 ms",
            "felnőtt_rekreációs": "30-80 ms"
        },
        "mikor_mérjük": "Reggel, felébredés után 5 percen belül, még fekvő helyzetben",
        "mit_tegyek_ha": {
            "alacsony": "Pihenés, regeneráció, könnyű edzés vagy pihenőnap",
            "magas": "Jó lehetőség intenzív edzésre, a szervezet felkészült"
        }
    },
    
    "nyugalmi_pulzus": {
        "teljes_név": "Resting Heart Rate - RHR",
        "rövid_magyarázat": "A pulzusszám teljesen nyugalmi állapotban",
        "mit_jelent": "Alacsonyabb érték jobb kardiovaszkuláris fittséget jelez. Az edzettség növekedésével csökken.",
        "normál_tartomány": {
            "átlag_felnőtt": "60-100 bpm",
            "sportoló": "40-60 bpm",
            "elit_állóképességi": "30-40 bpm"
        },
        "figyelmeztető_jelek": {
            "hirtelen_emelkedés": "Túledzés, betegség kezdete, dehidráció",
            "tartósan_magas": "Aluledzettség vagy egészségügyi probléma"
        }
    },
    
    "vérnyomás": {
        "teljes_név": "Blood Pressure",
        "rövid_magyarázat": "A vér nyomása az erekben",
        "mértékegység": "Hgmm (higanymilliméter)",
        "formátum": "szisztolés/diasztolés, pl. 120/80",
        "normál_tartomány": "90/60 - 120/80",
        "sportolónál": "Az intenzív edzés átmenetileg növelheti, de pihenéskor normalizálódik"
    }
}

TRAINING_LOAD_TERMS = {
    "Formaindex": {
        "teljes_név": "Fitness Index - Aktuális forma szint",
        "rövid_magyarázat": "A gépi tanulási modell által számított készenléti állapot",
        "skála": "1-10, ahol 10 a csúcsforma",
        "mit_vesz_figyelembe": [
            "HRV trendek az elmúlt 7-14 napban",
            "Edzésterhelés (volumen és intenzitás)",
            "Pihenés minősége és mennyisége",
            "Korábbi teljesítmények"
        ],
        "interpretáció": {
            "9-10": "Csúcsforma, versenyképes állapot",
            "7-8": "Jó forma, intenzív edzésekre alkalmas",
            "5-6": "Átlagos állapot, közepes intenzitású edzések",
            "3-4": "Fáradtság jelei, regenerációs edzések ajánlottak",
            "1-2": "Túlterhelés veszélye, pihenés szükséges"
        },
        "frissítés": "Naponta egyszer, a reggeli biometriai mérés után"
    },
    
    "TRIMP": {
        "teljes_név": "Training Impulse - Edzésimpulzus",
        "rövid_magyarázat": "Az edzés terhelésének számszerűsített mértéke",
        "számítás": "Időtartam × Intenzitás × Súlyozási tényező",
        "mit_jelent": "Minél magasabb a TRIMP, annál nagyobb a fiziológiai terhelés"
    },
    
    "ACWR": {
        "teljes_név": "Acute:Chronic Workload Ratio - Akut/Krónikus Terhelés Arány",
        "rövid_magyarázat": "Az elmúlt hét terhelésének aránya az elmúlt 4 hét átlagához képest",
        "ideális_tartomány": "0.8 - 1.3",
        "értelmezés": {
            "kisebb_mint_0.8": "Alulterhelés, forma vesztése lehetséges",
            "0.8-1.3": "Optimális terhelés, alacsony sérüléskockázat",
            "nagyobb_mint_1.5": "Túlterhelés, magas sérüléskockázat"
        }
    }
}

RECOVERY_TERMS = {
    "regeneráció": {
        "rövid_magyarázat": "A szervezet helyreállítási folyamata az edzésterhelés után",
        "típusok": {
            "passzív": "Teljes pihenés, alvás",
            "aktív": "Alacsony intenzitású mozgás (séta, úszás, kerékpár)",
            "specifikus": "Nyújtás, masszázs, hideg-meleg terápia"
        },
        "fontosság": "Az edzés hatása a regeneráció során alakul ki. Nincs regeneráció = nincs fejlődés."
    },
    
    "alvásminőség": {
        "rövid_magyarázat": "Az alvás mélysége és hatékonysága",
        "ideális": "7-9 óra éjszakánként sportoló esetén, minimum 20% mély alvás",
        "hatás_a_teljesítményre": "Rossz alvás csökkenti a HRV-t, rontja a reakcióidőt és a döntéshozatalt"
    }
}

# ============================================================================
# SPORTÁG-SPECIFIKUS KIFEJEZÉSEK
# ============================================================================

COMBAT_SPORTS_TERMS = {
    "birkózás": {
        "állótechnika": "A mérkőzés állva történő fázisa, dobások és kontroll",
        "földtechnika": "A földön történő küzdelem, szorítások és fordítások",
        "kilépés": "Sárga zóna érintése, büntetőpont",
        "passivitás": "A támadó játék hiánya, figyelmeztető ponttal járhat"
    },
    
    "judo": {
        "ippon": "Tökéletes dobás vagy szorítás, azonnali győzelem",
        "wazari": "Közel tökéletes technika, fél pont",
        "ne-waza": "Földharc, szorítások és feszítések",
        "tachi-waza": "Állótechnika, dobások"
    }
}

TEAM_SPORTS_TERMS = {
    "labdarúgás": {
        "presszing": "Ellenfél labdaszerzést célzó aktív nyomása",
        "kontra": "Gyors ellentámadás labdaszerzés után",
        "letámadás": "Az ellenfél felépítő játékának megzavarása",
        "zónás_védelem": "Területalapú védekezés, nem emberalapú"
    },
    
    "kosárlabda": {
        "pick_and_roll": "Labdavezető játékost segítő blokk és leválás",
        "zónavédelem": "Területi alapú védekezés",
        "gyorsindítás": "Labdaszerzés utáni azonnali támadás",
        "tripla_duplázás": "Két statisztikai kategóriában elért kétjegyű szám"
    }
}

ENDURANCE_SPORTS_TERMS = {
    "futás": {
        "laktát_küszöb": "Az az intenzitás, ahol a tejsav termelődés meghaladja a lebontását",
        "VO2max": "A maximális oxigénfelvevő képesség, az állóképesség fő mutatója",
        "tempó_futás": "Közepesen kemény tempó, ami kb. 30-60 percig fenntartható",
        "könnyű_futás": "Nagyon alacsony intenzitás, beszélgetve is végezhető"
    },
    
    "úszás": {
        "szakaszidő": "Egy meghatározott távolságra mért idő (pl. 50m)",
        "fordulótechnika": "A falról történő elrugaszkodás és víz alatti csúszás",
        "tempó_tartás": "Egyenletes sebességű úszás hosszú távon",
        "interval_edzés": "Ismétlések meghatározott pihenővel"
    }
}

# ============================================================================
# RENDSZER-SPECIFIKUS FOGALMAK (DigiT-Train)
# ============================================================================

SYSTEM_TERMS = {
    "MediaPipe": {
        "teljes_név": "Google MediaPipe Framework",
        "rövid_magyarázat": "Gépi látás alapú mozgáselemző technológia",
        "mit_csinál": "Azonosítja az emberi test kulcspontjait videón, és elemzi a mozgást",
        "pontosság": "33 testpontos modell, valós idejű feldolgozás",
        "felhasználás_a_rendszerben": "Videó diagnosztika, technika elemzés, pózus vizsgálat",
        "korlátok": "Jó megvilágítás szükséges, frontális vagy oldalnézet ajánlott"
    },
    
    "kredit_rendszer": {
        "rövid_magyarázat": "Használatalapú fizetési egység a DigiT-Train-ben",
        "mire_kell": "Videó diagnosztika (1 kredit/videó), speciális elemzések",
        "vásárlás": "10/50/100 kredites csomagok, illetve ML_ACCESS-el korlátlan lekérdezés",
        "érvényesség": "A kreditek nem járnak le, bármikor felhasználhatók"
    },
    
    "ML_ACCESS_előfizetés": {
        "rövid_magyarázat": "Havidíjas csomag a fejlett gépi tanulási funkciókhoz",
        "mit_tartalmaz": [
            "Formaindex számítás és trend elemzés",
            "Korlátlan Ditta elemző lekérdezés",
            "Prediktív elemzések (sérülésrizikó, forma előrejelzés)",
            "Részletes biometriai riportok",
            "Összehasonlító elemzések (sportolók, időszakok)"
        ],
        "ár": "Havi 2990 Ft vagy éves 29990 Ft (2 hónap ingyen)",
        "lemondás": "Bármikor, hátralévő időszak végéig érvényes marad"
    }
}

# ============================================================================
# DINAMIKUS SZÓTÁR ÉPÍTŐ FÜGGVÉNYEK
# ============================================================================

def get_relevant_knowledge(sport_name=None, context_app=None, user_roles=None):
    """
    Összegyűjti a releváns tudást a kontextus alapján.
    
    Args:
        sport_name: A sportág neve (pl. "Birkózás", "Labdarúgás")
        context_app: Az alkalmazás területe (pl. "biometrics", "ml_engine")
        user_roles: A felhasználó szerepkörei (pl. ["Edző", "Sportoló"])
    
    Returns:
        Dict: A releváns kifejezések összesített szótára
    """
    relevant_knowledge = {}
    
    # Általános biometriai kifejezések mindig kellenek
    if context_app in ['biometrics', 'ml_engine', 'diagnostics']:
        relevant_knowledge.update(BIOMETRIC_TERMS)
        relevant_knowledge.update(TRAINING_LOAD_TERMS)
        relevant_knowledge.update(RECOVERY_TERMS)
    
    # Rendszer-specifikus tudás
    if context_app in ['ml_engine', 'diagnostics', 'billing']:
        relevant_knowledge.update(SYSTEM_TERMS)
    
    # Sportág-specifikus tudás
    if sport_name:
        sport_category = _get_sport_category(sport_name)
        
        if sport_category == 'COMBAT':
            sport_lower = sport_name.lower()
            if sport_lower in COMBAT_SPORTS_TERMS:
                relevant_knowledge.update(COMBAT_SPORTS_TERMS[sport_lower])
        
        elif sport_category == 'TEAM':
            sport_lower = sport_name.lower()
            if sport_lower in TEAM_SPORTS_TERMS:
                relevant_knowledge.update(TEAM_SPORTS_TERMS[sport_lower])
        
        elif sport_category == 'ENDURANCE':
            sport_lower = sport_name.lower()
            if sport_lower in ENDURANCE_SPORTS_TERMS:
                relevant_knowledge.update(ENDURANCE_SPORTS_TERMS[sport_lower])
    
    return relevant_knowledge

def _get_sport_category(sport_name):
    """Meghatározza a sportág kategóriáját."""
    # Itt lekérdezheted az adatbázisból is
    from users.models import Sport
    try:
        sport = Sport.objects.get(name=sport_name)
        return sport.category
    except Sport.DoesNotExist:
        return None

def format_knowledge_for_prompt(knowledge_dict, max_terms=15):
    """
    Formázza a tudást úgy, hogy belefférjen a prompt-ba anélkül, 
    hogy túl hosszú lenne.
    
    Args:
        knowledge_dict: A kifejezések szótára
        max_terms: Maximum hány kifejezést írjon bele (token limit miatt)
    
    Returns:
        str: Formázott string a prompt-hoz
    """
    formatted_lines = []
    
    for i, (term, definition) in enumerate(knowledge_dict.items()):
        if i >= max_terms:
            formatted_lines.append(f"... és még {len(knowledge_dict) - max_terms} további kifejezés")
            break
        
        if isinstance(definition, dict):
            # Ha részletes definíció van, csak a lényeget vesszük
            short_def = definition.get('rövid_magyarázat', str(definition))
        else:
            short_def = definition
        
        formatted_lines.append(f"- {term}: {short_def}")
    
    return "\n".join(formatted_lines)