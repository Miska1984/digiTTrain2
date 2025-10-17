import os
from datetime import datetime
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML

def generate_pdf_report(user, report_data):
    """
    Profi sportdiagnosztikai PDF generálás.
    A fájl automatikusan mentődik a /media/reports/ alá.
    """

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = os.path.join(settings.MEDIA_ROOT, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    pdf_filename = f"general_report_{user.id}_{timestamp}.pdf"
    pdf_path = os.path.join(reports_dir, pdf_filename)

    # HTML sablon renderelése
    html_content = render_to_string("diagnostics/report_template.html", {
        "user": user,
        "timestamp": datetime.now().strftime("%Y.%m.%d %H:%M"),
        "report_data": report_data,
        "logo_url": os.path.join(settings.STATIC_URL, "images/digitrain_logo.png"),
    })

    # PDF generálás WeasyPrint segítségével
    HTML(string=html_content, base_url=settings.BASE_DIR).write_pdf(pdf_path)

    # Elérési út visszaadása (MEDIA_URL alapján)
    return os.path.join(settings.MEDIA_URL, "reports", pdf_filename)
