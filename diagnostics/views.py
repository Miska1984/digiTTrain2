import json
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from diagnostics_jobs.models import DiagnosticJob
from diagnostics_jobs.cloud_tasks import enqueue_diagnostic_job
from diagnostics_jobs.tasks import run_diagnostic_job
from .forms import GeneralDiagnosticUploadForm
from billing.models import UserCreditBalance, AlgorithmPricing, TransactionHistory


User = get_user_model()


@csrf_exempt
def create_diagnostic_job(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "POST metódus szükséges"}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        sport_type = data.get("sport_type", "general")
        job_type = data.get("job_type", "general")
        video_url = data.get("video_url")

        if not all([user_id, sport_type, job_type, video_url]):
            return JsonResponse({"success": False, "error": "Hiányzó kötelező mező"}, status=400)

        user = User.objects.filter(id=user_id).first()
        if not user:
            return JsonResponse({"success": False, "error": "Felhasználó nem található"}, status=404)

        # 🔹 1. Lekérjük az algoritmus árát (pl. sport_type alapján)
        algorithm_key = f"{sport_type}_{job_type}".lower()
        algo_price = AlgorithmPricing.objects.filter(algorithm_name=algorithm_key).first()
        cost = algo_price.cost_per_run if algo_price else 10  # fallback 10 credit

        # 🔹 2. Ellenőrizzük a balance-ot
        balance_obj, _ = UserCreditBalance.objects.get_or_create(user=user)
        if balance_obj.balance_amount < cost:
            return JsonResponse({
                "success": False,
                "error": f"Nincs elegendő Credit (szükséges: {cost}, elérhető: {balance_obj.balance_amount})"
            }, status=403)

        # 🔹 3. Lefoglaljuk a creditet
        balance_obj.balance_amount -= cost
        balance_obj.save(update_fields=["balance_amount"])

        TransactionHistory.objects.create(
            user=user,
            transaction_type="ALGO_RUN",
            amount=-cost,
            description=f"Gépi látásos elemzés ({sport_type}) lefoglalva",
            is_pending=True,
        )

        # 🔹 4. DiagnosticJob létrehozása
        job = DiagnosticJob.objects.create(
            user=user,
            sport_type=sport_type,
            job_type=job_type,
            video_url=video_url,
        )

        try:
            task_name = enqueue_diagnostic_job(job.id)
            msg = f"Feladat ütemezve: {task_name}"
        except Exception as e:
            msg = f"Helyi fejlesztés: Task nem ütemezhető ({e})"

        return JsonResponse({
            "success": True,
            "job_id": job.id,
            "status": job.status,
            "video_url": job.video_url,
            "message": msg,
            "credit_reserved": cost,
        })

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

@csrf_exempt
def run_diagnostic_job_view(request):
    """Cloud Task vagy lokális hívás a diagnosztikai job lefuttatására."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body)
        job_id = payload.get("job_id")
        if not job_id:
            return JsonResponse({"error": "Missing job_id"}, status=400)

        # 🔹 1️⃣ Lekérjük a job-ot
        job = DiagnosticJob.objects.get(id=job_id)
        user = job.user

        # 🔹 2️⃣ Megkeressük a PENDING credit tranzakciót ehhez a userhez
        tx = TransactionHistory.objects.filter(
            user=user,
            transaction_type="ALGO_RUN",
            is_pending=True
        ).order_by('-timestamp').first()

        # Ha nincs ilyen, az sem baj — csak logoljuk
        if not tx:
            print(f"[WARN] Nincs függő ALGO_RUN tranzakció a felhasználóhoz: {user}")

        # 🔹 3️⃣ Lefuttatjuk az elemzést
        try:
            run_diagnostic_job(job_id)
            job.refresh_from_db()

            # 🔹 4️⃣ Ha sikeres, lezárjuk a tranzakciót
            if tx:
                tx.is_pending = False
                tx.description += " ✅ Elemzés sikeresen befejezve"
                tx.save(update_fields=["is_pending", "description"])

            return JsonResponse({
                "success": True,
                "job_id": job.id,
                "status": job.status,
                "result": job.result
            })

        except Exception as e:
            # 🔹 5️⃣ Ha az elemzés HIBÁS → credit visszatérítés
            print(f"[ERROR] Elemzési hiba: {e}")

            if tx:
                # Visszaírjuk a felhasználó creditjét
                balance, _ = UserCreditBalance.objects.get_or_create(user=user)
                balance.balance_amount += abs(tx.amount)  # mivel amount negatív volt
                balance.save(update_fields=["balance_amount"])

                tx.is_pending = False
                tx.description += f" ❌ Elemzés sikertelen, refundálva ({abs(tx.amount)} Cr)"
                tx.amount = 0  # a refund után már ne legyen levonva
                tx.save(update_fields=["is_pending", "description", "amount"])

            job.status = "failed"
            job.save(update_fields=["status"])

            return JsonResponse({"error": str(e)}, status=500)

    except DiagnosticJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def job_status(request, job_id):
    """
    Egy adott diagnosztikai feladat státuszának és eredményének lekérdezése.
    """
    try:
        job = DiagnosticJob.objects.get(id=job_id)
        data = {
            "job_id": job.id,
            "status": job.status,
            "result": job.result or {},
            "created_at": job.created_at,
            "completed_at": job.completed_at,
        }
        return JsonResponse(data, status=200)
    except DiagnosticJob.DoesNotExist:
        return JsonResponse({"error": "Job not found"}, status=404)
    
@csrf_exempt
def list_diagnostic_jobs(request):
    """
    Összes diagnosztikai job lekérdezése (opcionálisan user_id szerint szűrve).
    """
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    user_id = request.GET.get("user_id")

    jobs = DiagnosticJob.objects.all().order_by("-created_at")
    if user_id:
        jobs = jobs.filter(user_id=user_id)

    data = {
        "jobs": [
            {
                "id": j.id,
                "user": j.user.username if j.user else None,
                "sport_type": j.sport_type,
                "job_type": j.job_type,
                "status": j.status,
                "created_at": j.created_at,
                "completed_at": j.completed_at,
            }
            for j in jobs
        ]
    }

    return JsonResponse(data, status=200)

@login_required
def diagnostics_dashboard(request):
    user = request.user
    jobs = DiagnosticJob.objects.filter(user=user).order_by('-created_at')

    analyses = [
        {"key": "posture", "title": "Teljes testtartás elemzés", "gif": "/static/diagnostics/gifs/posture.gif", "description": "A testtartás és gerinc szögének elemzése."},
        {"key": "balance", "title": "Egyensúly és stabilitás teszt", "gif": "/static/diagnostics/gifs/balance.gif", "description": "Egyensúly középpont és stabilitás mérése."},
        {"key": "squat", "title": "Guggolás mozgásanalízis", "gif": "/static/diagnostics/gifs/squat.gif", "description": "A térd és csípő szögek vizsgálata mozgás közben."},
        {"key": "running", "title": "Futómozgás elemzés", "gif": "/static/diagnostics/gifs/running.gif", "description": "Lépéshossz, ritmus és szimmetria elemzése."},
        {"key": "shoulder", "title": "Vállmobilitás és karstabilitás elemzés", "gif": "/static/diagnostics/gifs/shoulder.gif", "description": "A váll és könyök ízületek mozgásterjedelmének mérése."},
    ]

    return render(request, "diagnostics/athlete_diagnostics.html", {
        "jobs": jobs,
        "analyses": analyses,
    })

@login_required
def upload_general_video(request):
    """
    Videó feltöltése általános (nem sportspecifikus) mozgáselemzéshez.
    A fájl MEDIA_ROOT/videos/general_diagnostics/szimetria_videok/ alá kerül.
    """
    if request.method == "POST":
        uploaded_file = request.FILES.get("video_file")
        if not uploaded_file:
            return render(request, "diagnostics/upload_instructions.html", {
                "error": "Nem választottál ki videófájlt!",
            })

        user = request.user

        # Mentési útvonal (local + GCS kompatibilis)
        file_path = f"videos/general_diagnostics/szimetria_videok/{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
        saved_path = default_storage.save(file_path, ContentFile(uploaded_file.read()))

        # Mentett videó abszolút URL
        video_url = default_storage.url(saved_path)

        # Új DiagnosticJob létrehozása
        job = DiagnosticJob.objects.create(
            user=user,
            sport_type="general",
            job_type="general",
            video_url=video_url,
        )

        # Cloud Task ütemezés
        try:
            enqueue_diagnostic_job(job.id)
        except Exception as e:
            print(f"[DEBUG] Local dev: Task nem ütemezhető ({e})")

        return render(request, "diagnostics/upload_instructions.html", {
            "success": True,
            "video_url": video_url,
            "job_id": job.id,
        })

    return render(request, "diagnostics/upload_instructions.html")

@login_required
def upload_general_video(request):
    """
    Általános elemzéshez videó feltöltése (gépi látás).
    - Fejlesztési környezetben (Codespaces): automatikusan futtatja az elemzést.
    - Production: csak ütemezett futtatás.
    """
    if request.method == "POST":
        form = GeneralDiagnosticUploadForm(request.POST, request.FILES)
        if form.is_valid():
            video_file = form.cleaned_data['video']
            notes = form.cleaned_data.get('notes', '')

            # 📁 Mentési útvonal: media/videos/general_diagnostics/
            upload_dir = os.path.join(settings.MEDIA_ROOT, "videos", "general_diagnostics")
            os.makedirs(upload_dir, exist_ok=True)

            file_path = os.path.join(upload_dir, video_file.name)
            with open(file_path, 'wb+') as destination:
                for chunk in video_file.chunks():
                    destination.write(chunk)

            # 🌐 Videó URL (media könyvtárból)
            video_url = f"{settings.MEDIA_URL}videos/general_diagnostics/{video_file.name}"

            # 🧩 DiagnosticJob létrehozása
            job = DiagnosticJob.objects.create(
                user=request.user,
                sport_type="general",
                job_type="general",
                video_url=video_url,
                status="pending",
                result=None
            )

            messages.info(request, f"A videó feltöltése sikerült! Az elemzés előkészítés alatt...")

            # ⚙️ Fejlesztési mód esetén futtassuk automatikusan
            if settings.DEBUG:
                try:
                    messages.info(request, "Fejlesztői mód észlelve — az elemzés automatikusan indul.")
                    run_diagnostic_job(job.id)
                    job.refresh_from_db()

                    if job.status == "completed":
                        messages.success(request, f"Elemzés befejezve! Eredmény: {job.result or 'n/a'}")
                    else:
                        messages.warning(request, f"Elemzés folyamatban... (státusz: {job.status})")
                except Exception as e:
                    messages.error(request, f"Hiba történt az automatikus elemzés során: {e}")
            else:
                # Productionban csak ütemezés történne
                messages.info(request, "Elemzés ütemezve, feldolgozás 1-5 órán belül várható.")

            return redirect("diagnostics:athlete_diagnostics")

    else:
        form = GeneralDiagnosticUploadForm()

    context = {
        "form": form,
        "page_title": "Általános elemzés – Videó feltöltése"
    }
    return render(request, "diagnostics/upload_general_video.html", context)

