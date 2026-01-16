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

    def get_response(self, user, query, has_ml_access, history=None, active_role=None):
        if not has_ml_access:
            return "Ditta elemző funkcióihoz ML_ACCESS előfizetés szükséges."

        u_context = UsersContext(user)
        user_roles = u_context.roles.all()
        role_count = user_roles.count()

        # 0. Van-e szerepkör egyáltalán?
        if role_count == 0:
            return (
                f"Szia {user.first_name}! Úgy tűnik, még nincs jóváhagyott "
                "szerepköröd a rendszerben. Vedd fel a kapcsolatot a klub vezetőjével!"
            )

        # 1. SZEREPKÖR MEGHATÁROZÁSA
        role_confirmation = ""
        role_just_selected = False  # ÚJ FLAG!
        
        if active_role:
            has_this_role = user_roles.filter(role__name=active_role).exists()
            if not has_this_role:
                active_role = None
                logger.warning(f"Invalid role in session: {active_role}")
        
        if not active_role:
            active_role = self._get_active_role_from_history(history)
        
        if not active_role:
            inferred_role = self._try_infer_role_from_query(query, user_roles)
            
            if inferred_role:
                active_role = inferred_role
                role_just_selected = True  # JELÖLJÜK, hogy most választottuk ki!
                role_confirmation = (
                    f"Rendben, **{active_role}** minőségedben segítek! "
                    f"(Ha másik szerepkörödben szeretnél kérdezni, csak jelezd!)\n\n"
                )
            elif role_count > 1:
                roles_list = [r.role.name for r in user_roles]
                return self._create_role_selection_prompt(user.first_name, roles_list)
            else:
                active_role = user_roles.first().role.name
                role_just_selected = True  # Ez is új választás (implicit)
        
        # 1a. Ha kaptunk a view-ból (session-ből)
        if active_role:
            # Ellenőrizzük, hogy tényleg van ilyen szerepköre
            has_this_role = user_roles.filter(role__name=active_role).exists()
            if not has_this_role:
                # Valami hiba van a session-ben, nullázzuk
                active_role = None
                logger.warning(f"Invalid role in session: {active_role}")
        
        # 1b. Ha nincs a session-ből, nézzük a history-t
        if not active_role:
            active_role = self._get_active_role_from_history(history)
        
        # 1c. Ha még mindig nincs, próbáljuk kitalálni a kérdésből
        if not active_role:
            inferred_role = self._try_infer_role_from_query(query, user_roles)
            
            if inferred_role:
                # Sikerült kitalálni!
                active_role = inferred_role
                # FONTOS: Mindig adjunk megerősítést!
                role_confirmation = (
                    f"Rendben, **{active_role}** minőségedben segítek! "
                    f"(Ha másik szerepkörödben szeretnél kérdezni, csak jelezd!)\n\n"
                )
            elif role_count > 1:
                # Több szerepkör van, nem tudjuk melyik kell - kérjünk választást
                roles_list = [r.role.name for r in user_roles]
                return self._create_role_selection_prompt(user.first_name, roles_list)
            else:
                # Csak egy szerepkör van - automatikus
                active_role = user_roles.first().role.name
                # Nem kell megerősítés, mert nyilvánvaló

        # 2. CÉLPONT AZONOSÍTÁSA
        target_info = u_context.identify_target(query, active_role=active_role)
        target_user = target_info['user']
        target_name = target_info['name']
        
        # 3. BIZTONSÁGI ELLENŐRZÉS
        if active_role == "Szülő" and target_user != user:
            # A 'child' helyett 'user'-re kell szűrni, mert a UserRole-ban 
            # a sportoló a 'user' mezőben van!
            if not u_context.children.filter(user=target_user).exists():
                return "Szülőként csak a saját gyermekeid adatait láthatod. Kérlek, írd le a gyermek nevét pontosan!"
                
        # === IDE TEDD A BIZTONSÁGI ELLENŐRZÉST ===
        if active_role == "Szülő" and target_user != user:
            if not u_context.children.filter(user=target_user).exists(): 
                return "Szülőként csak a saját gyermekeid adatait láthatod. Kérlek, írd le a gyermek nevét pontosan!"

        # 4. RELEVÁNS TUDÁS ÖSSZEGYŰJTÉSE
        target_sport = self._get_primary_sport(target_user)
        relevant_knowledge = get_relevant_knowledge(
            sport_name=target_sport,
            context_app='ml_engine',
            user_roles=[active_role]
        )
        
        # Edző/vezető esetén hozzáadjuk a rendszer-specifikus tudást
        if active_role in ["Edző", "Egyesületi vezető"]:
            relevant_knowledge.update(SYSTEM_TERMS)

        # 5. ADATOK ELŐKÉSZÍTÉSE
        audit = u_context.get_data_availability([target_user])
        asm = AssessmentInterpreter(user)
        bill = BillingInterpreter(target_user)
        tlog = TrainingLogInterpreter(target_user)
        bio = BiometricInterpreter(target_user)
        diag = DiagnosticsInterpreter(target_user)
        ml = MLEngineInterpreter(target_user)

        context_data = {
            "details": u_context.get_target_details(target_user, active_role=active_role),
            "relevant_terms": format_knowledge_for_prompt(relevant_knowledge),
            "audit": audit,
            "assessments": asm.get_assessment_summary(target_user=target_user),
            "billing": bill.get_billing_status(),
            "training": tlog.get_training_summary(),
            "biometrics": bio.get_biometric_summary(),
            "diagnostics": diag.get_diagnostics_summary(),
            "ml_results": ml.get_ml_predictions(),
            "active_role": active_role,
            "family_info": self._get_family_context(u_context, target_user, active_role)
        }

        # 6. SZÜLŐI GYEREKEK ÖSSZEGZÉSE (ÚJ!)
        # Ez azért kell, mert ha szülő kérdez általánosan ("hogy állnak a gyerekek"),
        # akkor nem egy konkrét gyereket célzunk meg, hanem az összeset
        if active_role == "Szülő":
            children_summary = u_context.get_children_summary()
            context_data["children_summary"] = children_summary
            
            # DEBUG logolás a konzolba
            print(f"=" * 50)
            print(f"[ANALYST DEBUG] Active role: {active_role}")
            print(f"[ANALYST DEBUG] Children summary found.")
            print(f"=" * 50)
        
        # 7. EDZŐ/VEZETŐ CSAPAT ÖSSZEGZÉSE
        if active_role in ["Edző", "Egyesületi vezető"] and target_user == user:
            if hasattr(u_context, 'get_club_athletes_summary'):
                context_data["team_summary"] = u_context.get_club_athletes_summary()

        # 8. PROMPT ÉPÍTÉSE
        generated_prompt = self._build_orchestrator_prompt(
            user, target_info['name'], context_data, 
            u_context.get_roles_string(), query, active_role, 
            False, relevant_knowledge
        )

        # 9. VÁLASZ GENERÁLÁSA
        response = self._generate(generated_prompt)

        # 10. HIÁNYZÓ TUDÁS ELLENŐRZÉSE
        if "[MISSED]" in response:
            self._save_missed_knowledge(user, query, target_info, context_data['details'])
            return (
                "Saját bevallásom szerint erről még nincs elég információm a rendszerben. "
                "Jelzem a fejlesztőknek!"
            )

        # 11. SZEREPKÖR-MEGERŐSÍTÉS HOZZÁADÁSA
        response_with_metadata = {
            'text': response,
            'metadata': {}
        }
        
        # Ha most választottuk ki a szerepkört, jelezzük a view-nak!
        if role_just_selected:
            response_with_metadata['metadata']['selected_role'] = active_role
            response_with_metadata['metadata']['role_changed'] = True
        
        # Kompatibilitás: ha csak szöveget várnak, adjuk vissza
        # DE a view tudja kezelni a dict-et is!
        if role_confirmation:
            response = role_confirmation + response
        
        # A view-ban fogjuk eldönteni, hogy mentjük-e
        return response  # Egyelőre maradjon egyszerű string
    
    def _get_primary_sport(self, user):
        """Meghatározza a felhasználó elsődleges sportágát."""
        from users.models import UserRole
        
        role = UserRole.objects.filter(
            user=user,
            role__name='Sportoló',
            status='approved'
        ).first()
        
        return role.sport.name if role else None

    def _get_active_role_from_history(self, history):
        """
        Megnézi a beszélgetés előzményeiben, hogy volt-e már kiválasztott szerepkör.
        """
        if not history:
            return None
        
        for message in reversed(history):
            if isinstance(message, dict) and 'selected_role' in message.get('metadata', {}):
                return message['metadata']['selected_role']
        
        return None

    def _try_infer_role_from_query(self, query, user_roles):
        query_normalized = query.lower().strip()
        
        role_synonyms = {
            'Edző': ['edző', 'edzőként', 'edzői', 'coach'],
            'Sportoló': ['sportoló', 'sportolóként', 'sportolói', 'versenyző'],
            'Egyesületi vezető': ['vezető', 'vezetőként', 'egyesületi vezető', 'klubvezető'],
            'Szülő': ['szülő', 'szülőként', 'szülői', 'anyaként', 'apaként']
        }
        
        # 1. DIREKT SZEREPKÖR-VÁLASZTÁS
        for role in user_roles:
            role_name = role.role.name
            synonyms = role_synonyms.get(role_name, [role_name.lower()])
            
            if query_normalized in synonyms:
                return role_name
            
            for synonym in synonyms:
                if query_normalized.startswith(synonym):
                    return role_name
        
        # 2. KONTEXTUS ALAPÚ FELISMERÉS
        role_keywords = {
            'Sportoló': ['edzésem', 'teljesítményem', 'eredményem', 'formám', 'versenyem'],
            'Edző': ['sportolóim', 'tanítványaim', 'csapatom', 'edzésterv', 'versenyzőim'],
            'Egyesületi vezető': ['klub', 'egyesület', 'statisztika', 'áttekintés', 'költségvetés'],
            'Szülő': [
                'gyermekem', 'gyerekem', 'gyerekek', 'gyermekek',
                'fiam', 'lányom', 'gyereke', 'gyerekeim',
                'hogy áll', 'hogy állnak'  # "hogy állnak a gyerekek" típusú kérdések
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
        Létrehoz egy barátságos üzenetet, ami bekéri a szerepkör választást.
        JAVÍTOTT: Konkrétabb példákkal
        """
        roles_formatted = " vagy ".join([f"**{r}**" for r in roles_list])
        
        # Egyedi példák generálása a szerepkörök alapján
        examples = []
        if "Edző" in roles_list:
            examples.append("'Edzőként'")
        if "Szülő" in roles_list:
            examples.append("'Szülőként'")
        if "Sportoló" in roles_list:
            examples.append("'Sportolóként'")
        if "Egyesületi vezető" in roles_list:
            examples.append("'Vezetőként'")
        
        examples_str = " vagy ".join(examples[:2])  # Maximum 2 példa
        
        return (
            f"Szia {first_name}! 👋\n\n"
            f"Látom, hogy több szerepköröd is van a rendszerben: {roles_formatted}. "
            f"Ahhoz, hogy a legpontosabb információkat tudjam neked adni, "
            f"kérlek mondd meg, hogy most melyik minőségedben segíthetek! Hogy a szükséges adatokat előkészítsem\n\n"
            f"💡 Például egyszerűen csak írd be: {examples_str}"
        )

    def _get_family_context(self, u_context, target_user, active_role):
        if active_role in ["Edző", "Sportvezető", "Egyesületi vezető"] and target_user != u_context.user:
            from users.models import ParentChild
            parents = ParentChild.objects.filter(child=target_user, status='approved')
            parent_names = ", ".join([p.parent.get_full_name() for p in parents])
            return f"A sportoló szülei: {parent_names if parent_names else 'Nincs rögzítve'}"
        return ""

    def _build_orchestrator_prompt(self, user, target_name, data, roles_str, 
                                query, active_role, is_first, relevant_knowledge):
        
        knowledge_str = format_knowledge_for_prompt(relevant_knowledge, max_terms=10)

        prompt_lines = [
            "Te Ditta vagy, a DigiT-Train legmagasabb szintű AI elemzője.",
            f"SZAKMAI FOGALMAK: {data.get('relevant_terms', 'Nincs.')}",
            f"UI NAVIGÁCIÓ: {UI_NAVIGATION_MAP}",
            f"KI KÉRDEZ: {user.get_full_name()} (Aktív szerepkör: {active_role})",
        ]

        # === SZÜLŐI KONTEXTUS ===
        if active_role == "Szülő" and "children_summary" in data:
            children_summary = data['children_summary']
            
            # Ellenőrizzük, van-e tényleges gyerek
            if "Nincs regisztrált gyermeked" in children_summary:
                # NINCS GYEREK - Speciális válasz
                prompt_lines.extend([
                    "\n=== SZÜLŐI KONTEXTUS ===",
                    "A felhasználó SZÜLŐ szerepkörben van, DE nincs még gyerek hozzárendelve a rendszerben.",
                    "\n=== FELADATOD ===",
                    "Barátságosan magyarázd el, hogy a szülői funkciók használatához először:",
                    "1. Regisztrálni kell a gyereket a rendszerben (SportolóKént)",
                    "2. Létre kell hozni a szülő-gyerek kapcsolatot",
                    "3. A gyereknek jóvá kell hagynia a kapcsolatot",
                    "",
                    "Mondd el lépésről lépésre, hogy mit tegyen:",
                    "- Ha a gyerek már regisztrált: Profil > Családi kapcsolatok > Szülő hozzáadása",
                    "- Ha még nincs regisztrálva: Regisztráció SportolóKént, majd a fenti lépések",
                    "",
                    "Légy támogató és bíztató! NE írd ki a [MISSED] szót!",
                    f"\nKÉRDÉS: '{query}'"
                ])
            else:
                # VAN GYEREK - Normális elemzés
                prompt_lines.extend([
                    "\n=== SZÜLŐI ÖSSZEFOGLALÓ ===",
                    f"{children_summary}",
                    "\n=== FELADATOD ===",
                    "A felhasználó SZÜLŐ minőségében kérdez. Gyermeke(i) felől érdeklődik.",
                    "",
                    "AMIT MINDIG ELLENŐRIZZ:",
                    "1. Minden gyerek mérte-e magát ma reggel? (súly, HRV)",
                    "2. Volt-e edzésük ma? Hogyan bírták?",
                    "3. Milyen a formaindex? Ha 5 alatt van, AZONNAL jelezd!",
                    "4. Van-e valamelyik gyereknél figyelmeztető jel?",
                    "",
                    "AMIT TANÁCSOLJ A SZÜLŐNEK:",
                    "- Ha nincs reggeli mérés: 'Emlékeztesd [Név]-t, hogy mérje meg magát!'",
                    "- Ha alacsony a forma: 'Ma pihenőnapot javaslok [Név]-nek.'",
                    "- Ha magas intenzitású edzés volt: 'Figyelj a hidratációra!'",
                    "- Ha jó a forma: 'Szuper munka! [Név] remek állapotban van!'",
                    "",
                    "HANGNEM: Támogató, gondoskodó, szakmai. NE a gyereknek beszélj, hanem a SZÜLŐNEK!",
                    f"\nKÉRDÉS: '{query}'"
                ])
        
        # === EDZŐ/VEZETŐ CSAPAT KONTEXTUS ===
        elif "team_summary" in data:
            prompt_lines.extend([
                "\n=== CSAPAT ÖSSZEFOGLALÓ ===",
                f"{data['team_summary']}",
                "\n=== FELADATOD ===",
                "Edzőként/vezetőként válaszolj!",
                "Mivel nem mondott konkrét nevet, sorold fel a sportolókat.",
                "Kérdezd meg: 'Kiről szeretnél részletes elemzést?'",
                f"\nKÉRDÉS: '{query}'"
            ])
        
        # === EGYÉNI SPORTOLÓ KONTEXTUS ===
        else:
            prompt_lines.extend([
                f"\n=== CÉLPONT: {target_name} ===",
                f"Kontextus: {data['details']}",
                f"Edzések: {data['training']}",
                f"Biometria: {data['biometrics']}",
                f"ML eredmények: {data['ml_results']}",
                "\n=== FELADATOD ===",
                "Elemezd részletesen a sportoló adatait!",
                "Használd az ML eredményeket a tanácsadáshoz.",
                f"\nKÉRDÉS: '{query}'"
            ])

        prompt_lines.extend([
            "\n=== SZABÁLY ===",
            "Ha EGYÁLTALÁN nem tudsz válaszolni (pl. nincs adat), írd le: [MISSED]",
            "DE ha tudsz segíteni (pl. magyarázni, hogy mit kell tenni), akkor NE írd ki a [MISSED]-et!"
        ])
        
        return "\n".join(prompt_lines)

    def _save_missed_knowledge(self, user, query, target_info, details):
        DittaMissedQuery.objects.create(user=user, query=query, context_app="AnalystPersona")