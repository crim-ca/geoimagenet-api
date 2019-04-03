import re
import sys
from typing import List

from setuptools import setup

assert sys.version_info >= (3, 6, 0), "geoimagenet_api requires Python 3.6+"
from pathlib import Path  # noqa E402

HERE = Path(__file__).parent


def read_setup_file(path) -> str:
    return open(HERE / path, encoding="utf8").read()


def read_requirements(path) -> List[str]:
    requirements = []
    for line in read_setup_file(path).splitlines():
        search = re.search(r'(.+)?#egg=(.+)', line)
        if search:
            url = search.group(1)
            package_name = search.group(2)
            requirements.append(f"{package_name} @ {url}")
        else:
            requirements.append(line)
    return requirements


__about__ = {}
exec(read_setup_file(Path("geoimagenet_api", "__about__.py")), __about__)

package_data = {
    "geoimagenet_api": [
        "CHANGELOG.rst",
        "openapi.yaml",
        "database/alembic.ini",
        "database/alembic/*",
        "database/alembic/**/*",
    ]
}

setup(
    name="geoimagenet_api",
    version=__about__["__version__"],
    description="GeoImageNet API to support the web mapping platform.",
    long_description=read_setup_file("README.md"),
    long_description_content_type="text/markdown",
    author=__about__["__author__"],
    author_email=__about__["__email__"],
    url="https://geoimagenet.crim.ca",
    license="TBD",
    packages=["geoimagenet_api"],
    package_data=package_data,
    python_requires=">=3.7",
    zip_safe=False,
    install_requires=read_requirements("requirements.txt"),
    tests_require=read_requirements("requirements_dev.txt"),
    test_suite="tests.tests",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3 :: Only",
    ],
    entry_points={
        "console_scripts": [
            "migrate = geoimagenet_api.database.migrations:migrate",
            "init_database = geoimagenet_api.database.migrations:init_database_data",
            "geoserver_setup = geoimagenet_api.geoserver_setup.geoserver_setup:cli",
        ]
    },
)
