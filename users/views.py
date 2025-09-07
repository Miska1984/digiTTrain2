# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from .forms import UserRegistrationForm, ProfileForm, UserUpdateForm
from .models import Profile

User = get_user_model()

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user) # Automatikus bejelentkezés regisztráció után
            username = form.cleaned_data.get('username')
            messages.success(request, f'Sikeres regisztráció, {username}! Most már bejelentkezve vagy.')
            return redirect('core:main_page')
    else:
        form = UserRegistrationForm()
    return render(request, 'users/register.html', {'form': form})


@login_required
def edit_profile(request):
    """
    Ez a nézet kezeli a felhasználó profiljának szerkesztését,
    beleértve a felhasználói adatok és a profilkép frissítését.
    """
    # Profil lekérdezése vagy létrehozása a felhasználóhoz
    profile, created = Profile.objects.get_or_create(user=request.user)
    if created:
        # Ha új profil jön létre, biztosítjuk, hogy a user hozzá legyen rendelve
        profile.user = request.user
        profile.save()

    # Ha POST kérés érkezik (űrlap beküldése)
    if request.method == "POST":
        # Felhasználói űrlap inicializálása a POST adatokkal és a felhasználó példánnyal
        user_form = UserUpdateForm(request.POST, instance=request.user)
        # Profil űrlap inicializálása a POST adatokkal, a feltöltött fájlokkal és a profillal
        profile_form = ProfileForm(request.POST, request.FILES, instance=profile)

        # Ha mindkét űrlap érvényes
        if user_form.is_valid() and profile_form.is_valid():
            # Profil példány mentése commit=False-al, hogy belenyúlhassunk még mentés előtt
            instance = profile_form.save(commit=False)

            # Debug: Ellenőrizzük, hogy érkezett-e fájl a request.FILES-ben
            uploaded_file = request.FILES.get("profile_picture")
            if uploaded_file:
                print(f"📸 Feltöltött fájl a POST-ban: {uploaded_file.name}")
            else:
                # Ha nem érkezett fájl, de a űrlap valid, az azt jelenti, hogy nincs új kép feltöltve
                # Ebben az esetben a korábbi képet nem szabad törölni, csak ha explicitly törölték
                # Az `instance.profile_picture` ebben az esetben a régi értéket fogja tartalmazni
                print("ℹ️ Nincs új fájl a request.FILES-ben (vagy nem történt képváltás).")
                # Ha a profile_picture mező üres lett (törölve lett), akkor azt is kezelni kell
                if not profile.profile_picture and not uploaded_file:
                     print("ℹ️ A képmező üres volt, és nem töltöttek fel újat.")
                elif profile.profile_picture and not uploaded_file:
                     print(f"ℹ️ Meglévő kép van: {profile.profile_picture.name}, de új nincs feltöltve.")

            # Biztosítjuk, hogy a mentett profil a megfelelő felhasználóhoz tartozzon
            instance.user = request.user

            # A profile_picture mező állapotának ellenőrzése és loggolása
            # A Django és a storages backend gondoskodik arról, hogy a fájl GCS-be kerüljön
            if instance.profile_picture:
                print(f"✅ Mentett fájl neve: {instance.profile_picture.name}")
                try:
                    # Megpróbáljuk lekérni a fájl URL-jét. Ez már a GCS-ből fog jönni.
                    file_url = instance.profile_picture.url
                    print(f"🌍 Mentett fájl URL: {file_url}")
                except Exception as e:
                    # Ha nem tudjuk lekérni az URL-t, valami baj van a GCS eléréssel vagy a konfigurációval
                    print(f"⚠️ Nem tudtam lekérni az URL-t a mentett fájlhoz: {e}")
                    # Itt jelezhetnénk egy specifikusabb hibát a felhasználónak
                    messages.error(request, f"⚠️ Hiba történt a kép mentésekor: {e}")
                    return redirect("users:edit_profile") # Visszatérünk az űrlaphoz hiba esetén
            else:
                # Ha a profile_picture mező üres maradt (akár törlés, akár nem feltöltés miatt)
                print("⚠️ A profilpéldányban nincs kép mező beállítva!")
                # Ha törlés történt, és a korábbi kép mező nem lett törölve a modellben
                # Biztosítani kell, hogy a kép eltávolításra kerüljön a GCS-ből is, ha ez a cél
                # (Ez általában a Django-storages backend feladata, ha jól van konfigurálva)

            # Végleges mentés az adatbázisba. Itt történik a fájl tényleges mentése (GCS-be)
            instance.save()

            # Felhasználói adatok mentése
            user_form.save()

            # Sikeres üzenet megjelenítése
            messages.success(request, "✅ A profil sikeresen frissítve!")
            # Átirányítás az edit_profile oldalra az aktuális állapot megjelenítéséhez
            return redirect("users:edit_profile")
        else:
            # Ha az űrlapok nem érvényesek, megjelenítjük a hibákat
            print("❌ Form hiba:", user_form.errors, profile_form.errors)
            messages.error(request, "⚠️ Hiba történt! Ellenőrizd az űrlap adatait.")
            # Maradunk az űrlapon, hogy a felhasználó javíthassa a hibákat

    # Ha GET kérés érkezik, vagy az űrlap nem volt érvényes,
    # inicializáljuk az űrlapokat a jelenlegi adatokkal
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.profile) # A korábbi kép is betöltődik ide

    # Az űrlapok és a felhasználó kontextusban átadása a template-nek
    return render(request, "users/edit_profile.html", {
        "user_form": user_form,
        "profile_form": profile_form,
    })
