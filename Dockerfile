FROM python:3.6-alpine
LABEL Description="GeoImageNet API" Vendor="CRIM" Maintainer="david.caron@crim.ca"

WORKDIR /code
COPY geoimagenet_api/__init__.py geoimagenet_api/__about__.py ./geoimagenet_api/
COPY requirements* setup.py README.md ./

RUN apk update && \
    apk add postgresql-libs && \
    apk add --virtual .build-deps gcc musl-dev postgresql-dev && \
    pip install --upgrade pip setuptools gunicorn && \
    pip install --no-cache-dir -e . && \
    apk --purge del .build-deps

COPY . .

RUN pip install --no-dependencies -e .

EXPOSE 8080

CMD ["gunicorn", "--bind=0.0.0.0:8080", "--workers=4", "geoimagenet_api:application"]
