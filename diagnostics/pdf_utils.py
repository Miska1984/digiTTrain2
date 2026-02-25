# diagnostics/pdf_utils.py

import os
import logging
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.storage import default_storage
from weasyprint import HTML, CSS
from datetime import datetime
from urllib.parse import urljoin
from typing import Union

logger = logging.getLogger(__name__)

TEMPLATE_MAP = {
    "SQUAT_ASSESSMENT": "diagnostics/reports/squat_details.html",
    "POSTURE_ASSESSMENT": "diagnostics/reports/posture_details.html",
    "SHOULDER_CIRCUMDUCTION": "diagnostics/reports/shoulder_circumduction_details.html",
    "VERTICAL_JUMP": "diagnostics/reports/vertical_jump_details.html",
    "SINGLE_LEG_STANCE_LEFT": "diagnostics/reports/single_leg_stance_details.html",
    "SINGLE_LEG_STANCE_RIGHT": "diagnostics/reports/single_leg_stance_details.html",
}

REPORT_TEMPLATE = "diagnostics/report_template.html"

def generate_pdf_report(job, analysis_data, output_dir=None) -> Union[str, None]:
    try:
        # FONTOS: Import helyben, hogy ne omoljon össze a Celery
        from users.models import UserRole 

        template_name = TEMPLATE_MAP.get(job.job_type, "diagnostics/reports/generic_details.html")
        logger.info(f"📄 PDF generálás indítása: {job.id}")

        # Sportág lekérése
        sport_name = "Általános"
        try:
            user_role = UserRole.objects.filter(user=job.user, status='approved').select_related('sport').first()
            if user_role and user_role.sport:
                sport_name = user_role.sport.name
        except: pass

        # Név (Magyar sorrend)
        user_display_name = job.user.username
        try:
            p = job.user.profile
            if p.last_name and p.first_name:
                user_display_name = f"{p.last_name} {p.first_name}"
        except: pass

        # PONTZÁM KINYERÉSE (Ez a rész felel a pontokért!)
        # Megnézzük a metrics-ben, ha ott nincs, akkor az analysis_data gyökerében
        m = analysis_data.get('metrics', {})
        p_score = m.get('posture_score') or analysis_data.get('posture_score', '--')

        current_date_str = datetime.now().strftime('%Y.%m.%d')

        context = {
            "job": job,
            "analysis": analysis_data,
            "full_name": user_display_name,
            "sport_name": sport_name,
            "posture_score": p_score,  # <--- Új, közvetlen változó!
            "date": current_date_str,
            "current_date": current_date_str,
        }

        # Belső rész renderelése
        section_html = render_to_string(template_name, context)
        context["section_html"] = section_html

        # Fő sablon renderelése
        html_content = render_to_string(REPORT_TEMPLATE, context)
        
        # PDF mentési útvonal
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"job_{job.id}_{job.job_type.lower()}_report_{timestamp}.pdf"
        temp_pdf_path = os.path.join("/tmp", pdf_filename)
        
        # Base URL a képeknek
        base_url = urljoin('file:///', str(settings.BASE_DIR) + '/')

        # WeasyPrint futtatása
        HTML(string=html_content, base_url=base_url).write_pdf(temp_pdf_path)
        
        # Mentés GCS-re
        target_path = f"jobs/{job.id}/reports/{pdf_filename}"
        with open(temp_pdf_path, 'rb') as f:
            path_in_storage = default_storage.save(target_path, f)
            
        pdf_url = default_storage.url(path_in_storage)
        os.remove(temp_pdf_path)
        
        return pdf_url
        
    except Exception as e:
        logger.error(f"❌ PDF hiba: {str(e)}", exc_info=True)
        return None