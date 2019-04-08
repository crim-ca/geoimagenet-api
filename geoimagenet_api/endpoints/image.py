import os

from sqlalchemy import func, String, cast, alias
from sqlalchemy.orm import Query, Session

from geoimagenet_api.database.models import Image, Annotation


def query_rgbn_16_bit_image(session: Session) -> Query:
    """Get an image filename in another bit format, using levenshtein distance and folder names.

    The image table contains one row for each file.
    The with the filename, the row also contains information about:
      - sensor_name
      - bands
      - number of bits
    Given an image id, this function finds the corresponding 16 bit image file path.
    The returned value is a sqlalchemy Query object, so it can be used as a subquery.

    The folder name will always be of the format {sensor_name}_{bands}_{bits}.
    Example: PLEIADES_RGBN_16
    See: :class:`geoimagenet_api.geoserver_setup.main.ImageData`
    """
    image_alias = alias(Image)

    subquery = (
        session.query(
            func.concat(
                image_alias.c.sensor_name,
                "_",
                image_alias.c.bands,
                "_",
                cast(image_alias.c.bits, String),
                os.path.sep,
                image_alias.c.filename,
            ).label("image_name_16_bits")
        )
        .filter(image_alias.c.bits == 16)
        .filter(image_alias.c.bands == "RGBN")
        .filter(image_alias.c.sensor_name == Image.sensor_name)
        .order_by(func.levenshtein(Image.filename, image_alias.c.filename))
        .limit(1)
        .subquery()
    )

    query = session.query(Image.id.label("image_id"), subquery.c.image_name_16_bits).subquery()
    return query
