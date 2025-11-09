# diagnostics/pdf_utils.py

import os
import logging
import shutil
from django.conf import settings
from django.template.loader import render_to_string
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from weasyprint import HTML, CSS
from datetime import datetime
from urllib.parse import urljoin
from typing import Union

logger = logging.getLogger(__name__)

# HTML sablonok mozgástípusokhoz
TEMPLATE_MAP = {
    "SQUAT_ASSESSMENT": "diagnostics/reports/squat_details.html",
    "POSTURE_ASSESSMENT": "diagnostics/reports/posture_details.html",
    "SHOULDER_CIRCUMDUCTION": "diagnostics/reports/shoulder_circumduction_details.html",
    "VERTICAL_JUMP": "diagnostics/reports/vertical_jump_details.html",
    "SINGLE_LEG_STANCE_LEFT": "diagnostics/reports/single_leg_stance_details.html",
    "SINGLE_LEG_STANCE_RIGHT": "diagnostics/reports/single_leg_stance_details.html",
}

# Alapsablon
REPORT_TEMPLATE = "diagnostics/report_template.html"


def generate_pdf_report(job, analysis_data, output_dir=None) -> Union[str, None]:
    """
    PDF riport generálása egy elemzett mozgás alapján, majd GCS-re feltöltése.

    :param job: DiagnosticJob objektum
    :param analysis_data: dict (az elemzés eredménye)
    :param output_dir: Nem használt, a /tmp könyvtárat használjuk.
    :return: a PDF fájl GCS URL-je, vagy None hiba esetén
    """
    try:
        # 1. Sablon meghatározása
        template_name = TEMPLATE_MAP.get(job.job_type, "diagnostics/reports/generic_details.html")

        logger.info(f"📄 PDF generálása sablonból: {template_name}")

        # 2. Részletes mozgásspecifikus szekció renderelése
        # Ezzel generáljuk a beágyazandó HTML-t a fő sablonhoz
        section_html = render_to_string(template_name, {"analysis": analysis_data, "job": job})

        # 3. 🔑 Fő sablon környezetének (context) összeállítása: A JAVÍTÁS EZ!
        # Átadjuk a 'job' objektumot, hogy a fő sablon hozzáférhessen a 'job.user'-hez.
        context = {
            "job": job, # <-- A [user] hiba megoldása
            "analysis_data": analysis_data,
            "user": job.user,
            "section_html": section_html,
            "current_date": datetime.now().strftime('%Y.%m.%d %H:%M'),
        }

        # 4. Fő sablon renderelése
        html_content = render_to_string(REPORT_TEMPLATE, context)
        
        # 5. CSS betöltése
        css = None
        try:
            # A WeasyPrint megköveteli a STATIC_ROOT-ból való betöltést (ha létezik)
            css_path = os.path.join(settings.STATIC_ROOT, 'diagnostics/css/pdf_report.css')
            if settings.STATIC_ROOT and os.path.exists(css_path):
                 css = CSS(filename=css_path) 
            else:
                 logger.warning("⚠️ Nem sikerült betölteni a PDF CSS fájlt (vagy nem létezik).")
        except Exception:
            logger.warning("⚠️ Hiba a PDF CSS fájl betöltése közben.")
            
        # 6. WeasyPrint Base URL a statikus fájlokhoz (Képek, CSS)
        # Ez biztosítja, hogy a sablonban lévő relatív útvonalak feloldhatók legyenek
        base_url_for_weasyprint = urljoin('file:///', str(settings.BASE_DIR))


        # 7. PDF generálása Helyi /tmp fájlba WeasyPrinttel
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"job_{job.id}_{job.job_type.lower()}_report_{timestamp}.pdf"
        temp_pdf_path = os.path.join("/tmp", pdf_filename)
        
        logger.info(f"💾 PDF generálása a /tmp-be: {temp_pdf_path}")
        
        if css:
            HTML(string=html_content, base_url=base_url_for_weasyprint).write_pdf(temp_pdf_path, stylesheets=[css])
        else:
            HTML(string=html_content, base_url=base_url_for_weasyprint).write_pdf(temp_pdf_path)
        
        
        # 8. Feltöltés a default_storage-ba (GCS)
        target_path = f"jobs/{job.id}/reports/{pdf_filename}"
        
        logger.info(f"⬆️ PDF feltöltése GCS-re: {target_path}")
        
        with open(temp_pdf_path, 'rb') as pdf_file:
            # A default_storage.save() feltölti a GCS-re
            path_in_storage = default_storage.save(target_path, pdf_file)
            
        # default_storage.url() -> visszaadja a teljes GCS URL-t
        pdf_url = default_storage.url(path_in_storage)
        logger.info(f"✅ PDF feltöltve GCS-re: {pdf_url}")
        
        # 9. Tisztítás
        os.remove(temp_pdf_path)
        
        return pdf_url
        
    except Exception as e:
        logger.error(f"❌ PDF generálás/feltöltés kritikus hiba: {e}", exc_info=True)
        return None