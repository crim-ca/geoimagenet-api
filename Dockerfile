FROM python:3.6-alpine
LABEL Description="GeoImageNet API" Vendor="CRIM" Maintainer="david.caron@crim.ca"

WORKDIR /code
COPY requirements.txt .

RUN apk update && \
    apk add postgresql-libs && \
    apk add --virtual .build-deps gcc musl-dev postgresql-dev && \
    pip install --upgrade pip gunicorn && \
    pip install -r requirements.txt --no-cache-dir && \
    apk --purge del .build-deps

COPY . .

RUN python setup.py develop

EXPOSE 8080

CMD ["gunicorn", "--bind=0.0.0.0:8080", "--workers=4", "geoimagenet_api:application"]
