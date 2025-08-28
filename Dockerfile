FROM python:3.12

ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

COPY requirements.txt /workspace/

RUN pip install -r requirements.txt

COPY . /workspace/

# Django settings
ENV DJANGO_SETTINGS_MODULE=digiTTrain2.production

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "digiTTrain2.wsgi"]