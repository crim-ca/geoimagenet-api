FROM python:3.7-alpine

LABEL Description="GeoImageNet API" Vendor="CRIM" Maintainer="david.caron@crim.ca"

WORKDIR /code

COPY requirements.txt .

RUN echo "http://mirror.leaseweb.com/alpine/edge/testing" >> /etc/apk/repositories && \
    apk update && \
    apk add postgresql-libs && \
    apk add --virtual .build-deps postgresql-dev gcc musl-dev make && \
    pip install --upgrade pip setuptools gunicorn && \
    pip install --no-cache-dir -r requirements.txt && \
    apk --purge del .build-deps postgresql-dev gcc musl-dev make

COPY geoimagenet_api/__init__.py geoimagenet_api/__about__.py ./geoimagenet_api/
COPY requirements* setup.py README.md ./

RUN pip install --no-cache-dir -e .

EXPOSE 8080

COPY . .

CMD gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080 geoimagenet_api:application
