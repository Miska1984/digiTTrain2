# users_context.py

from users.models import UserRole, ParentChild, User
from data_sharing.models import BiometricSharingPermission
from billing.models import UserSubscription
from django.utils import timezone
from datetime import date
from django.db.models import Q

class UsersContext:
    def __init__(self, user):
        self.user = user
        
        # Aktív, jóváhagyott szerepkörök (Sportoló, Edző, Szülő, Sportvezető, stb.)
        self.roles = UserRole.objects.filter(
            user=user, 
            status='approved'
        ).select_related('role', 'club', 'sport')
        
        # === GYEREKEK LEKÉRÉSE A USERROLE TÁBLÁBÓL ===
        # A UserRole táblában a gyerek a 'user' mezőben van,
        # és a szülő a 'parent' mezőben!
        self.children = UserRole.objects.filter(
            parent=user,  # Ahol a jelenlegi user a parent
            role__name='Sportoló',  # És a gyerek Sportoló szerepkörben van
            status='approved'
        ).select_related('user__profile')  # A 'user' mező a gyerek!

    def identify_target(self, query, active_role=None):
        """
        Beazonosítja a beszélgetés alanyát a kérdés és az aktív szerepkör alapján.
        """
        query_l = query.lower()
        
        # 1. SZÜLŐI KONTEXTUS
        if active_role == "Szülő":
            for child_role in self.children:
                # FONTOS: UserRole-ban a gyerek a 'user' mezőben van!
                child = child_role.user
                if child.profile.first_name.lower() in query_l or child.last_name.lower() in query_l:
                    return {'user': child, 'name': child.get_full_name(), 'is_placeholder': False}
            
            if ("gyermek" in query_l or "gyerek" in query_l) and self.children.count() == 1:
                child = self.children.first().user  # <-- NEM .child hanem .user!
                return {'user': child, 'name': child.get_full_name(), 'is_placeholder': False}

        # 2. EDZŐI / VEZETŐI KONTEXTUS
        if active_role in ["Edző", "Sportvezető", "Egyesületi vezető"]:
            user_clubs = self.roles.values_list('club', flat=True)
            club_members = User.objects.filter(
                user_roles__club__in=user_clubs,
                user_roles__role__name='Sportoló'
            ).filter(
                Q(profile__first_name__icontains=query) | 
                Q(profile__last_name__icontains=query) |
                Q(first_name__icontains=query)
            ).distinct()
            
            if club_members.count() == 1:
                member = club_members.first()
                return {'user': member, 'name': member.get_full_name(), 'is_placeholder': False}

        # 3. ALAPÉRTELMEZETT: Saját maga
        return {'user': self.user, 'name': "Saját profil", 'is_placeholder': False}

    def get_club_athletes_summary(self):
        """
        Vezetőknek és edzőnek: lista a klub sportolóiról.
        """
        from biometric_data.models import WeightData, RunningPerformance
        from ml_engine.models import UserPredictionResult
        from django.utils import timezone
        
        user_clubs = self.roles.values_list('club', flat=True)
        athletes = User.objects.filter(
            user_roles__club__in=user_clubs,
            user_roles__role__name='Sportoló'
        ).select_related('profile').distinct()
        
        if not athletes.exists():
            return "Nincsenek regisztrált sportolók a klubodban."
            
        summary_list = []
        today = timezone.now().date()

        for a in athletes:
            morning_weight_entry = WeightData.objects.filter(
                user=a, 
                workout_date=today
            ).first()
            
            weight_status = f"✅ ({morning_weight_entry.morning_weight}kg)" if morning_weight_entry else "❌"
            
            run_entry = RunningPerformance.objects.filter(
                user=a, 
                run_date=today
            ).first()
            
            if run_entry:
                run_status = f"🏃 ({run_entry.run_distance_km}km, {run_entry.run_avg_hr} bpm)"
            else:
                run_status = "⚪"
            
            ml_res = UserPredictionResult.objects.filter(user=a).order_by('-predicted_at').first()
            fi_value = f"{round(ml_res.form_score, 1)}" if ml_res else "N/A"
            
            summary_list.append(
                f"{a.get_full_name()} | Súly: {weight_status} | Edzés: {run_status} | Formaindex: {fi_value}"
            )
            
        return summary_list

    def get_data_availability(self, target_users):
        """Ellenőrzi a megosztásokat és ML előfizetéseket."""
        report = {"osszesen": len(target_users), "nincs_megosztas": [], "nincs_ml_access": []}
        
        for u in target_users:
            full_name = u.get_full_name()
            if u != self.user:
                shared = BiometricSharingPermission.objects.filter(
                    user=u, target_user=self.user, enabled=True
                ).exists()
                if not shared:
                    report["nincs_megosztas"].append(full_name)

            has_ml = UserSubscription.objects.filter(
                user=u, sub_type='ML_ACCESS', active=True, expiry_date__gte=timezone.now()
            ).exists()
            if not has_ml:
                report["nincs_ml_access"].append(full_name)
                
        return report

    def get_target_details(self, target_user, active_role=None):
        profile = getattr(target_user, 'profile', None)
        details = {
            "teljes_nev": target_user.get_full_name(),
            "eletkor": self._calculate_age(profile),
            "szerepkorok": self.get_roles_string(target_user),
            "kontextus": f"Jelenleg {active_role} minőségedben vizsgálod őt." if active_role else ""
        }

        # Vezetői/Edzői extra: szülők lekérése
        if active_role in ["Edző", "Sportvezető", "Egyesületi vezető"] and target_user != self.user:
            # UserRole táblából keressük a szülőt
            parent_roles = UserRole.objects.filter(
                user=target_user, 
                role__name='Sportoló',
                status='approved',
                parent__isnull=False
            ).select_related('parent')
            
            if parent_roles.exists():
                details["szulok"] = [pr.parent.get_full_name() for pr in parent_roles]

        return details

    def get_roles_string(self, target_user=None):
        u = target_user or self.user
        roles = UserRole.objects.filter(user=u, status='approved').select_related('role', 'club')
        return ", ".join([f"{r.club.short_name} - {r.role.name}" for r in roles])
    
    def get_children_summary(self):
        """
        Szülőknek: gyermekeik napi összefoglalója.
        JAVÍTVA: UserRole alapú lekérdezés!
        """
        from biometric_data.models import WeightData, RunningPerformance
        from ml_engine.models import UserPredictionResult
        from django.utils import timezone
        
        if not self.children.exists():
            return "Nincs regisztrált gyermeked a rendszerben."
        
        summary_list = []
        today = timezone.now().date()
        
        for child_role in self.children:
            child = child_role.user
            
            # --- JAVÍTOTT NÉVLEKÉRÉS (Last Name a Profile-ból) ---
            # 1. Megpróbáljuk a Profile-ból a last_name-et (mivel ezt kérted)
            # 2. Ha az nincs, megpróbáljuk a Profile-ból a first_name-et
            # 3. Ha az sincs, a User modell alap nevei
            # 4. Végső eset: username
            
            profile = getattr(child, 'profile', None)
            
            if profile and profile.last_name and profile.last_name.strip():
                child_name = profile.last_name.strip()
            elif profile and profile.first_name and profile.first_name.strip():
                child_name = profile.first_name.strip()
            elif child.get_full_name().strip():
                child_name = child.get_full_name().strip()
            else:
                child_name = child.username

            # DEBUG - Ezzel ellenőrizheted a konzolban
            print(f"[CHILDREN SUMMARY DEBUG] Name resolved for ID {child.id}: {child_name}")
            
            # 1. Reggeli mérés
            morning_weight = WeightData.objects.filter(
                user=child,
                workout_date=today
            ).first()
            
            if morning_weight:
                weight_status = f"✅ ({morning_weight.morning_weight}kg)"
            else:
                weight_status = "❌ Még nem mért ma"
            
            # 2. Edzésadat
            run_entry = RunningPerformance.objects.filter(
                user=child,
                run_date=today
            ).first()
            
            if run_entry:
                run_status = f"🏃 {run_entry.run_distance_km}km, {run_entry.run_avg_hr} bpm"
            else:
                run_status = "⚪ Még nem volt edzés ma"
            
            # 3. Formaindex
            ml_res = UserPredictionResult.objects.filter(
                user=child
            ).order_by('-predicted_at').first()
            
            if ml_res:
                fi_value = round(ml_res.form_score, 1)
                if fi_value >= 8:
                    fi_status = f"🟢 {fi_value} - Kiváló forma!"
                elif fi_value >= 6:
                    fi_status = f"🟡 {fi_value} - Jó forma"
                elif fi_value >= 4:
                    fi_status = f"🟠 {fi_value} - Közepes, figyelj rá!"
                else:
                    fi_status = f"🔴 {fi_value} - Pihenésre van szükség!"
            else:
                fi_status = "⚪ N/A - Nincs elég adat"
            
            summary_list.append(
                f"**{child_name}** ({self._calculate_age(child.profile)} éves)\n"
                f"  → Reggeli mérés: {weight_status}\n"
                f"  → Mai edzés: {run_status}\n"
                f"  → Formaindex: {fi_status}"
            )
        
        result = "\n\n".join(summary_list)
        
        # DEBUG
        print(f"[CHILDREN SUMMARY DEBUG] Final result:\n{result}")
        
        return result

    def _calculate_age(self, profile):
        if profile and profile.date_of_birth:
            today = date.today()
            return today.year - profile.date_of_birth.year - (
                (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
            )
        return "Nincs megadva"