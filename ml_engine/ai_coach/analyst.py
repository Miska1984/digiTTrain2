import logging
from django.utils import timezone
from .base_persona import BasePersona
from .app_interpreters.users_context import UsersContext
from .app_interpreters.assessment_interpreter import AssessmentInterpreter
from .app_interpreters.billing_interpreter import BillingInterpreter
from .app_interpreters.training_log_interpreter import TrainingLogInterpreter
from .app_interpreters.biometric_interpreter import BiometricInterpreter
from .app_interpreters.diagnostics_interpreter import DiagnosticsInterpreter
from .app_interpreters.ml_engine_interpreter import MLEngineInterpreter
from ml_engine.models import DittaMissedQuery
from .ui_knowledge import UI_NAVIGATION_MAP, NAVIGATION_PATHS, FAQ_SHORTCUTS, ERROR_EXPLANATIONS
from .knowledge_base import get_relevant_knowledge, format_knowledge_for_prompt, SYSTEM_TERMS

logger = logging.getLogger(__name__)

class AnalystPersona(BasePersona):
    """
    Analyst (Guru) mód - CSAK ML_ACCESS előfizetőknek
    
    Feladatai:
    1. Navigációs kérdések → ui_knowledge.py alapján (UGYANÚGY mint Navigator!)
    2. Szakmai/elemző kérdések → Interpreterekkel mélyreható elemzés
    3. Ismeretlen kérdések → [MISSED] jelzés fejlesztőknek
    """

    def get_response(self, user, query, has_ml_access, history=None, active_role=None):
        """
        Analyst válasz generálása.
        
        Args:
            user: Felhasználó
            query: Kérdés
            has_ml_access: Van-e ML előfizetése
            history: Beszélgetés előzmények
            active_role: Aktív szerepkör (ha van)
        
        Returns:
            str: Ditta elemző válasza
        """
        # Biztonsági ellenőrzés
        if not has_ml_access:
            return "🔒 Ditta elemző funkcióihoz ML_ACCESS előfizetés szükséges."

        # Felhasználó szerepköreinek lekérése
        u_context = UsersContext(user)
        user_roles_obj = u_context.roles.all()
        role_count = user_roles_obj.count()
        
        # Szerepkörök listája (string formátumban a base_persona használatához)
        user_roles = [role.role.name for role in user_roles_obj]

        # Van-e szerepkör egyáltalán?
        if role_count == 0:
            return (
                f"👋 Szia {user.first_name}! Még nincs jóváhagyott szerepköröd. "
                "⚙️ Vezérlőpult → Szerepkörök kezelése"
            )

        # === KÉRDÉS TÍPUS ALAPÚ ROUTING ===
        
        # 1. NAVIGÁCIÓS KÉRDÉS? → ui_knowledge.py (UGYANÚGY mint Navigator!)
        if self.is_navigation_question(query):
            return self.answer_navigation_question(query, user_roles)
        
        # 2. SZAKMAI/ELEMZŐ KÉRDÉS → Interpreter-alapú mélyreható elemzés
        # (Ez a Guru mód erőssége!)
        
        # === SZEREPKÖR MEGHATÁROZÁSA ===
        role_confirmation = ""
        role_just_selected = False
        
        if active_role:
            has_this_role = user_roles_obj.filter(role__name=active_role).exists()
            if not has_this_role:
                active_role = None
                logger.warning(f"Invalid role in session: {active_role}")
        
        if not active_role:
            active_role = self._get_active_role_from_history(history)
        
        if not active_role:
            inferred_role = self._try_infer_role_from_query(query, user_roles_obj)
            
            if inferred_role:
                active_role = inferred_role
                role_just_selected = True
                role_confirmation = (
                    f"Rendben, **{active_role}** minőségedben segítek! "
                    f"(Ha másik szerepkörödben szeretnél kérdezni, csak jelezd!)\n\n"
                )
            elif role_count > 1:
                return self._create_role_selection_prompt(user.first_name, user_roles)
            else:
                active_role = user_roles[0]
                role_just_selected = True

        # === CÉLPONT AZONOSÍTÁSA ===
        target_info = u_context.identify_target(query, active_role=active_role)
        target_user = target_info['user']
        target_name = target_info['name']
        
        # === BIZTONSÁGI ELLENŐRZÉS ===
        if active_role == "Szülő" and target_user != user:
            if not u_context.children.filter(user=target_user).exists():
                return "👨‍👩‍👧 Szülőként csak a saját gyermekeid adatait láthatod. Írd le a gyermek nevét pontosan!"

        # === RELEVÁNS TUDÁS ÖSSZEGYŰJTÉSE ===
        target_sport = self._get_primary_sport(target_user)
        relevant_knowledge = get_relevant_knowledge(
            sport_name=target_sport,
            context_app='ml_engine',
            user_roles=[active_role]
        )
        
        # Edző/vezető esetén rendszer-specifikus tudás
        if active_role in ["Edző", "Egyesületi vezető"]:
            relevant_knowledge.update(SYSTEM_TERMS)

        # === ADATOK ELŐKÉSZÍTÉSE (INTERPRETEREK) ===
        audit = u_context.get_data_availability([target_user])
        asm = AssessmentInterpreter(user)
        bill = BillingInterpreter(target_user)
        tlog = TrainingLogInterpreter(target_user)
        bio = BiometricInterpreter(target_user)
        diag = DiagnosticsInterpreter(target_user)
        ml = MLEngineInterpreter(target_user)
        ml_raw_results = ml.get_ml_predictions()

        # ÚJ: Értékek normalizálása, hogy ne legyen 51/10-es hallucináció
        # Ha a predikció 0-100 közötti, leosztjuk 10-zel a 10-es skálához
        try:
            # Feltételezve, hogy a ml_results-ban van egy 'predicted_value'
            if isinstance(ml_raw_results, dict) and 'predicted_value' in ml_raw_results:
                raw_val = float(ml_raw_results['predicted_value'])
                # Kerekített 10-es skála (pl. 61.56 -> 6.2)
                ml_raw_results['display_score'] = round(min(raw_val / 10, 10.0), 1)
        except:
            pass

        context_data = {
            "details": u_context.get_target_details(target_user, active_role=active_role),
            "relevant_terms": format_knowledge_for_prompt(relevant_knowledge),
            "audit": audit,
            "ml_results": ml_raw_results,
            "assessments": asm.get_assessment_summary(target_user=target_user),
            "billing": bill.get_billing_status(),
            "training": tlog.get_training_summary(),
            "biometrics": bio.get_biometric_summary(),
            "diagnostics": diag.get_diagnostics_summary(),
            "ml_results": ml.get_ml_predictions(),
            "active_role": active_role,
            "family_info": self._get_family_context(u_context, target_user, active_role)
        }

        # === SZÜLŐI GYEREKEK ÖSSZEGZÉSE ===
        if active_role == "Szülő":
            children_summary = u_context.get_children_summary()
            context_data["children_summary"] = children_summary
            
            logger.info(f"[ANALYST] Szülői összefoglaló előkészítve: {active_role}")
        
        # === EDZŐ/VEZETŐ CSAPAT ÖSSZEGZÉSE ===
        if active_role in ["Edző", "Egyesületi vezető"] and target_user == user:
            if hasattr(u_context, 'get_club_athletes_summary'):
                context_data["team_summary"] = u_context.get_club_athletes_summary()

        # === PROMPT ÉPÍTÉSE ===
        generated_prompt = self._build_orchestrator_prompt(
            user, target_info['name'], context_data, 
            ", ".join(user_roles), query, active_role, 
            is_first=(history is None or len(history) == 0),
            relevant_knowledge=relevant_knowledge
        )

        # === VÁLASZ GENERÁLÁSA ===
        raw_response = self._generate(generated_prompt)
        
        # === MISSED QUERY ELLENŐRZÉS ===
        if "[MISSED]" in raw_response:
            self._save_missed_knowledge(user, query, target_info, context_data["details"])
            raw_response = raw_response.replace("[MISSED]", "").strip()
            
            # Barátságos fallback üzenet
            if not raw_response:
                raw_response = (
                    "🤔 Ezt még tanulom! Jeleztem a fejlesztőknek, "
                    "hogy legközelebb tudjak segíteni."
                )
        
        # === SZEREPKÖR MEGERŐSÍTÉS HOZZÁADÁSA (ha szükséges) ===
        final_response = role_confirmation + raw_response
        
        return final_response

    # ============================================================================
    # SEGÉDFÜGGVÉNYEK
    # ============================================================================

    def _get_primary_sport(self, target_user):
        """Lekéri a felhasználó elsődleges sportágát."""
        try:
            from users.models import UserRole
            primary_role = UserRole.objects.filter(
                user=target_user, 
                status='approved'
            ).select_related('sport').first()
            
            if primary_role and primary_role.sport:
                return primary_role.sport.name
        except Exception as e:
            logger.error(f"Error getting primary sport: {e}")
        
        return None

    def _get_active_role_from_history(self, history):
        """
        Megpróbálja kitalálni a szerepkört a beszélgetés előzményekből.
        
        Args:
            history: Beszélgetés előzmények (lista dict-ekkel)
        
        Returns:
            str or None: Szerepkör neve vagy None
        """
        if not history:
            return None
        
        # Keresünk szerepkör-specifikus kulcsszavakat az előzményekben
        role_keywords = {
            'Sportoló': ['edzésem', 'teljesítményem', 'formám', 'versenyem'],
            'Edző': ['sportolóim', 'tanítványaim', 'csapatom', 'edzésterv'],
            'Szülő': ['gyermekem', 'gyerekem', 'fiam', 'lányom', 'gyerekeim'],
            'Egyesületi vezető': ['klub', 'egyesület', 'statisztika']
        }
        
        # Utolsó 3 üzenet vizsgálata
        recent_messages = history[-3:] if len(history) >= 3 else history
        
        for msg in reversed(recent_messages):
            content = msg.get('content', '').lower()
            
            for role_name, keywords in role_keywords.items():
                if any(keyword in content for keyword in keywords):
                    return role_name
        
        return None

    def _try_infer_role_from_query(self, query, user_roles):
        """
        Megpróbálja kitalálni a szerepkört a kérdésből.
        
        Args:
            query: Felhasználó kérdése
            user_roles: UserRole QuerySet
        
        Returns:
            str or None: Szerepkör neve vagy None
        """
        if not query:
            return None
        
        query_normalized = query.lower().strip()
        
        # Szerepkör szinonimák
        role_synonyms = {
            'Sportoló': ['sportoló', 'sportolóként', 'versenyzőként'],
            'Edző': ['edző', 'edzőként', 'coach'],
            'Szülő': ['szülő', 'szülőként', 'anyaként', 'apaként'],
            'Egyesületi vezető': ['vezető', 'vezetőként', 'klubvezető']
        }
        
        # 1. Direkt szerepkör-választás
        for role in user_roles:
            role_name = role.role.name
            synonyms = role_synonyms.get(role_name, [role_name.lower()])
            
            if query_normalized in synonyms:
                return role_name
            
            for synonym in synonyms:
                if query_normalized.startswith(synonym):
                    return role_name
        
        # 2. Kontextus alapú felismerés
        role_keywords = {
            'Sportoló': ['edzésem', 'teljesítményem', 'eredményem', 'formám', 'versenyem'],
            'Edző': ['sportolóim', 'tanítványaim', 'csapatom', 'edzésterv', 'versenyzőim'],
            'Egyesületi vezető': ['klub', 'egyesület', 'statisztika', 'áttekintés'],
            'Szülő': [
                'gyermekem', 'gyerekem', 'gyerekek', 'gyermekek',
                'fiam', 'lányom', 'gyerekeim',
                'hogy áll', 'hogy állnak'
            ]
        }
        
        matched_roles = []
        
        for role in user_roles:
            role_name = role.role.name
            keywords = role_keywords.get(role_name, [])
            
            if any(keyword in query_normalized for keyword in keywords):
                matched_roles.append(role_name)
        
        # Csak akkor adjunk vissza szerepkört, ha PONTOSAN egy egyezett
        if len(matched_roles) == 1:
            return matched_roles[0]
        
        return None

    def _create_role_selection_prompt(self, first_name, roles_list):
        """
        Szerepkör választást kérő barátságos üzenet.
        
        Args:
            first_name: Felhasználó keresztneve
            roles_list: Szerepkörök listája (string-ek)
        
        Returns:
            str: Választást kérő üzenet
        """
        roles_formatted = " vagy ".join([f"**{r}**" for r in roles_list])
        
        # Példák generálása
        examples = []
        role_examples = {
            'Edző': "'Edzőként'",
            'Szülő': "'Szülőként'",
            'Sportoló': "'Sportolóként'",
            'Egyesületi vezető': "'Vezetőként'"
        }
        
        for role in roles_list:
            if role in role_examples:
                examples.append(role_examples[role])
        
        examples_str = " vagy ".join(examples[:2])
        
        return (
            f"👋 Szia {first_name}!\n\n"
            f"Több szerepköröd van: {roles_formatted}. "
            f"Melyik minőségedben segíthetek?\n\n"
            f"💡 Példa: {examples_str}"
        )

    def _get_family_context(self, u_context, target_user, active_role):
        """Családi kontextus (szülők) lekérése edzőknek/vezetőknek."""
        if active_role in ["Edző", "Sportvezető", "Egyesületi vezető"] and target_user != u_context.user:
            from users.models import UserRole
            
            # Szülők keresése a UserRole táblában
            parent_roles = UserRole.objects.filter(
                user=target_user,
                role__name='Sportoló',
                status='approved',
                parent__isnull=False
            ).select_related('parent')
            
            if parent_roles.exists():
                parent_names = ", ".join([pr.parent.get_full_name() for pr in parent_roles])
                return f"👨‍👩‍👧 Szülők: {parent_names}"
        
        return ""

    def _build_orchestrator_prompt(self, user, target_name, data, roles_str, 
                                query, active_role, is_first, relevant_knowledge):
        """
        GURU mód központi prompt építés - ÖSSZEFÜGGÉS-KERESŐ ELEMZÉS
        
        Szabályok:
        - Max 8-10 mondat komplex elemzésnél
        - Emoji + Bullet pont + Strukturált formátum
        - Keresd az összefüggéseket (edzés ↔ HRV, alvás ↔ forma)
        - Direktebb edzőnek, lágyabb szülőnek
        - Támogató vezető felé (ne bíráló!)
        - Jelezd ha hiányzik adat (ne találj ki!)
        """
        
        knowledge_str = format_knowledge_for_prompt(relevant_knowledge, max_terms=10)

        # === ALAPVETŐ KONTEXTUS ===
        prompt_lines = [
            "Te Ditta vagy, a DigiT-Train AI GURU elemzője (ML előfizetőknek).",
            "",
            "=== KRITIKUS SZABÁLYOK ===",
            "- A formaindex pontszáma SOHA nem haladhatja meg a 10-et!",
            "- Ha az ML adat 61.5, azt 6.2/10-ként interpretáld!",
            "- Ne írj ki matematikai képtelenségeket (pl. 51/10).",
            "",
            "=== ALAPELVEK ===",
            "1. ADATVEZÉRELT: Csak a rendelkezésre álló adatokra támaszkodj!",
            "2. ÖSSZEFÜGGÉS-KERESŐ: Keress kapcsolatokat (edzés→HRV, alvás→forma, stb.)",
            "3. STRUKTURÁLT: Emoji + Bullet pontok + Címkék (🟢🟡🔴 / ✅❌⚠️)",
            "4. NE TALÁLJ KI ADATOT: Ha nincs adat, jelezd mi hiányzik!",
            "5. NE LÉPD TÚL KOMPETENCIÁD: Tanács igen, konkrét edzésterv NEM!",
            "",
            f"=== SZAKMAI FOGALMAK ===",
            f"{data.get('relevant_terms', 'Nincs.')}",
            "",
            f"=== KI KÉRDEZ ===",
            f"{user.get_full_name()} (Szerepkör: {active_role})",
        ]

        # ============================================================================
        # SZEREPKÖR-SPECIFIKUS PROMPTOK
        # ============================================================================

        # === 1. SZÜLŐ MÓD - LÁGY, MEGNYUGTATÓ, GONDOSKODÓ ===
        if active_role == "Szülő" and "children_summary" in data:
            children_summary = data['children_summary']
            
            if "Nincs regisztrált gyermeked" in children_summary:
                # NINCS GYEREK
                prompt_lines.extend([
                    "\n=== SZÜLŐI KONTEXTUS ===",
                    "A felhasználó Szülő, DE még nincs gyerek hozzárendelve.",
                    "",
                    "=== FELADATOD ===",
                    "Lágy, segítőkész hangnemben magyarázd el a lépéseket:",
                    "1. Gyerek regisztrálása Sportolóként",
                    "2. Szülő-gyerek kapcsolat létrehozása",
                    "3. Jóváhagyás",
                    "",
                    "Légy bíztató! 🌟 NE írd ki a [MISSED] szót!",
                    f"\nKÉRDÉS: '{query}'"
                ])
            else:
                # VAN GYEREK - NORMÁLIS ELEMZÉS
                prompt_lines.extend([
                    "\n=== GYEREKEK MAI ÁLLAPOTA ===",
                    f"{children_summary}",
                    "",
                    "=== SZÜLŐI MÓD SZABÁLYOK ===",
                    "HANGNEM: Lágy, megnyugtató, gondoskodó 😊",
                    "FORMÁTUM: Strukturált (emoji + címkék)",
                    "HOSSZ: Max 8-10 mondat",
                    "",
                    "AMIT ELLENŐRIZZ gyerekenként:",
                    "✅ Reggeli mérés megtörtént-e? (súly, HRV)",
                    "🏃 Volt-e edzés? Hogyan bírta?",
                    "📊 Formaindex: 🟢8-10 / 🟡5-7 / 🔴1-4",
                    "😴 Alvás minősége és mennyisége",
                    "⚠️ Van-e figyelmeztető jel?",
                    "",
                    "TANÁCSOK (lágy megfogalmazással!):",
                    "- Ha nincs mérés: 'Ha van idő, emlékeztesd...'",
                    "- Ha alacsony forma: 'Talán egy kis extra pihenés jót tenne...'",
                    "- Ha minden rendben: '🌟 Remek munka! [Név] szuper állapotban van!'",
                    "",
                    "ÖSSZEFÜGGÉSEK:",
                    "- Ha látsz mintát (pl. hétfői edzés után mindig fáradt), jelezd!",
                    "- Ha javulás van, gratulálj és mondd el mi segített!",
                    "",
                    "FONTOS: NE riogasd a szülőt! Mindig adj reményt és konkrét tippeket.",
                    f"\nKÉRDÉS: '{query}'"
                ])
        
        # === 2. EDZŐ MÓD - DIREKTEBB, DÖNTÉSTÁMOGATÓ ===
        elif active_role == "Edző":
            if "team_summary" in data:
                # CSAPAT ÖSSZEFOGLALÓ
                prompt_lines.extend([
                    "\n=== CSAPAT ÖSSZEFOGLALÓ ===",
                    f"{data['team_summary']}",
                    "",
                    "=== EDZŐI MÓD SZABÁLYOK ===",
                    "HANGNEM: Direktebb, szakmai, döntéstámogató 💼",
                    "FORMÁTUM: Strukturált, tömör",
                    "HOSSZ: Max 8-10 mondat",
                    "",
                    "HA ÁLTALÁNOS KÉRDÉS (pl. 'hogy állnak a sportolók'):",
                    "- Sorold fel őket (név + formaindex + főbb adatok)",
                    "- Kérdezd meg: 'Kiről szeretnél részletes elemzést?'",
                    "",
                    "HA ÖSSZEHASONLÍTÁS (pl. 'Sanyika vagy Pistike ki játsszon?'):",
                    "1. Objektív adatok mindkettőről:",
                    "   - Forma (🟢🟡🔴)",
                    "   - HRV trend",
                    "   - Edzéslátogatás",
                    "   - Teljesítmény tesztek (ha van)",
                    "2. Összehasonlítás (%-ok, konkrét számok)",
                    "3. VÉLEMÉNY: Ki jobb választás MOST (adat alapján)",
                    "4. FIGYELMEZTETÉS: 'Ez csak az adatok - te ismered a taktikát is!'",
                    "",
                    "ÖSSZEFÜGGÉSEK:",
                    "- Keress mintákat (pl. melyik edzéstípus után jobb a regeneráció)",
                    "- Jelezd ha valaki mindig hétfőn gyengébb",
                    "- Ha látod hogy valami MŰKÖDIK, mondd el mit!",
                    "",
                    f"\nKÉRDÉS: '{query}'"
                ])
            else:
                # EGYÉNI SPORTOLÓ ELEMZÉS
                prompt_lines.extend([
                    f"\n=== SPORTOLÓ: {target_name} ===",
                    f"📋 Alapadatok: {data['details']}",
                    f"🏃 Edzések: {data['training']}",
                    f"📊 Biometria: {data['biometrics']}",
                    f"🎯 ML eredmények: {data['ml_results']}",
                    f"🔍 Diagnosztika: {data.get('diagnostics', 'Nincs.')}",
                    "",
                    "=== EDZŐI ELEMZÉS SZABÁLYOK ===",
                    "HANGNEM: Direktebb, szakmai",
                    "FORMÁTUM: Strukturált",
                    "HOSSZ: Max 8-10 mondat",
                    "",
                    "AMIT ELEMEZZ:",
                    "1. JELENLEGI ÁLLAPOT:",
                    "   - Forma (🟢8-10 / 🟡5-7 / 🔴1-4)",
                    "   - HRV trend (javul/romlik/stabil)",
                    "   - Edzéslátogatás (rendszeresség)",
                    "",
                    "2. ÖSSZEFÜGGÉSEK (ez a legfontosabb!):",
                    "   - Melyik edzés után jobb/rosszabb a HRV?",
                    "   - Alvás hatása a formára",
                    "   - Hétvégi regeneráció hatékonysága",
                    "   - Ha találsz mintát (pl. 'hétfői nehéz edzés után mindig 3 nap regeneráció kell'), MONDD EL!",
                    "",
                    "3. JAVASLATOK:",
                    "   - Konkrét, rövidtávú (pl. 'ma pihenőnap', 'hétfőn könnyű edzés')",
                    "   - DE! Nem konkrét edzésterv, csak irány!",
                    "   - Ha látod mi MŰKÖDÖTT korábban, hivatkozz rá!",
                    "",
                    "4. ADATHIÁNY:",
                    "   - Ha nincs elég adat, jelezd MIT kell mérni",
                    "   - Pl. 'Még 3 napig mérj HRV-t, utána tudok trendet mutatni'",
                    "",
                    "PÉLDA ELEMZÉS:",
                    "🟡 Forma: 6.2/10 - Átlagos",
                    "📈 HRV trend: Csökkenő (-12% az elmúlt 3 napban)",
                    "🔍 Összefüggés: Kedd nehéz edzés után (2.5h) még csütörtökön is fáradt",
                    "💡 Javaslat: Keddi terhelés csökkentése vagy szerdai pihenőnap",
                    "",
                    f"\nKÉRDÉS: '{query}'"
                ])
        
        # === 3. EGYESÜLETI VEZETŐ MÓD - TÁMOGATÓ, NEM BÍRÁLÓ ===
        elif active_role == "Egyesületi vezető":
            prompt_lines.extend([
                "\n=== VEZETŐI ÁTTEKINTÉS ===",
                f"Csapat: {data.get('team_summary', 'Nincs csapat összefoglaló.')}",
                "",
                "=== VEZETŐI MÓD SZABÁLYOK ===",
                "HANGNEM: Támogató, megoldás-orientált 🤝",
                "FORMÁTUM: Strukturált, objektív",
                "HOSSZ: Max 8-10 mondat",
                "",
                "FONTOS ALAPELV: NE BÍRÁLD AZ EDZŐT!",
                "- Ha hiányos az adat → Mi lehet az oka? (technikai? időhiány?)",
                "- Adj TÁMOGATÓ javaslatokat (infrastruktúra, eszköz, képzés)",
                "",
                "PÉLDA ROSSZ válasz:",
                "❌ 'Az edző nem tölti ki rendesen a jelenléti íveket. Ez felelőtlenség!'",
                "",
                "PÉLDA JÓ válasz:",
                "✅ Adatminőség elemzés:",
                "📊 Balázs edző (foci U14): 40%-os kitöltés",
                "🔍 Lehetséges okok:",
                "1. Nincs WiFi a pályán?",
                "2. Nincs ideje edzés után?",
                "3. Nem egyértelmű a felület?",
                "💡 Támogatási javaslatok:",
                "- WiFi kiépítés",
                "- Tablet beszerzés",
                "- Mobil-barát felület",
                "- Személyes beszélgetés: 'Miben tudok segíteni?'",
                "",
                "ADATELEMZÉS:",
                "- Statisztikák (hány % tölti ki az edzők közül)",
                "- Trendek (javul/romlik)",
                "- Összefüggések (pl. téli időszakban rosszabb)",
                "",
                f"\nKÉRDÉS: '{query}'"
            ])
        
        # === 4. SPORTOLÓ MÓD - SZEMÉLYES, MOTIVÁLÓ ===
        else:
            prompt_lines.extend([
                f"\n=== SAJÁT ADATOK: {target_name} ===",
                f"📊 Biometria: {data['biometrics']}",
                f"🏃 Edzések: {data['training']}",
                f"📈 ML eredmények: {data['ml_results']}",
                "",
                "=== SPORTOLÓ MÓD SZABÁLYOK ===",
                "HANGNEM: Személyes, motiváló, támogató 💪",
                "FORMÁTUM: Strukturált, érthető",
                "HOSSZ: Max 8-10 mondat",
                "",
                "AMIT ELEMEZZ:",
                "1. JELENLEGI ÁLLAPOT:",
                "   - Forma (érthető magyarázattal)",
                "   - HRV mit jelent NEKED (ne csak a szám!)",
                "   - Mi változott az elmúlt napokban",
                "",
                "2. ÖSSZEFÜGGÉSEK (személyes!):",
                "   - 'A pénteki könnyű edzés után szombaton mindig jobb a HRV-d'",
                "   - 'Amikor 8 órát alszol, 15%-kal jobb a formád'",
                "   - 'Hétfői nehéz edzés után 3 napig regenerálódsz'",
                "",
                "3. JAVASLATOK:",
                "   - Rövid, konkrét (ma/holnap mit csinálj)",
                "   - Motiváló (ne csak 'pihenj'!)",
                "   - Ha jól megy, gratulálj! 🌟",
                "",
                "4. ADATHIÁNY:",
                "   - Ha hiányzik mérés, mondd meg mit és miért fontos",
                "",
                "PÉLDA ELEMZÉS:",
                "📊 A HRV-d ma 42 ms, heti átlagod 50 ms",
                "📉 16%-os csökkenés - ez fáradtságot jelezhet",
                "🔍 Összefüggés: Tegnap 2 órás nehéz edzés volt",
                "💡 Javaslat: Ma pihenőnap vagy max 30 perc könnyű mozgás",
                "🎯 Holnapra várhatóan helyreáll, ha jól kialszod magad!",
                "",
                f"\nKÉRDÉS: '{query}'"
            ])

        # === KÖZÖS SZABÁLYOK (minden szerepkörhöz) ===
        prompt_lines.extend([
            "\n=== VÁLASZ FORMÁTUM ===",
            "EMOJI használat (következetesen!):",
            "🟢 Kiváló (8-10) | 🟡 Átlagos (5-7) | 🔴 Gyenge (1-4)",
            "✅ Rendben | ❌ Probléma | ⚠️ Figyelem",
            "📊 Adat | 📈 Javulás | 📉 Romlás | 💡 Javaslat",
            "",
            "STRUKTÚRA:",
            "1. Név/Cím (ha több személy)",
            "2. Jelenlegi állapot (emoji-kkal)",
            "3. Összefüggések/Trendek",
            "4. Javaslat/Tanács",
            "",
            "ADATHIÁNY KEZELÉSE:",
            "- Ha nincs adat → 'Nincs elég [X] adat az elemzéshez'",
            "- Mondd meg MIT kell mérni és MIÉRT",
            "- NE találj ki adatot soha!",
            "",
            "=== [MISSED] SZABÁLY ===",
            "Csak akkor írd ki, ha TELJESEN tanácstalan vagy:",
            "- Nincs semmilyen adat ÉS",
            "- Nem tudsz segíteni még magyarázattal sem",
            "",
            "DE! Ha van bármilyen adat, vagy tudsz tanácsot adni → NE írd ki a [MISSED]-et!",
        ])
        
        return "\n".join(prompt_lines)

    def _save_missed_knowledge(self, user, query, target_info, details):
        """Ismeretlen kérdés naplózása a DittaMissedQuery modellbe."""
        try:
            DittaMissedQuery.objects.create(
                user=user, 
                query=query, 
                context_app="AnalystPersona"
            )
            logger.info(f"[MISSED QUERY] User: {user.username}, Query: {query}")
        except Exception as e:
            logger.error(f"Error saving missed query: {e}")