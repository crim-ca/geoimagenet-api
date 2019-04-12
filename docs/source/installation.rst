************
Installation
************

**Python >= 3.7 is required.**

Install the library with::

  python setup.py install

For development, install also::

  pip install -r requirements_dev.txt

Run a local development server with::

 uvicorn geoimagenet_api:application

**GeoImageNet Annotation API** uses the `FastAPI <https://fastapi.tiangolo.com/>`_ framework,
which depends on `Pydantic <https://pydantic-docs.helpmanual.io/>`_
and `Starlette <https://www.starlette.io/>`_
