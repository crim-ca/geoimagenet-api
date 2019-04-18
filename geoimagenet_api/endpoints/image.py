import os

from sqlalchemy import func, String, cast
from sqlalchemy.orm import Query, Session, aliased
from starlette.exceptions import HTTPException

from geoimagenet_api.database.models import Image
from geoimagenet_api.openapi_schemas import AnnotationProperties


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
    image_alias1 = aliased(Image)
    image_alias2 = aliased(Image)

    # subquery = (
    #     session.query(
    #         func.concat(
    #             image_alias2.sensor_name,
    #             "_",
    #             image_alias2.bands,
    #             "_",
    #             cast(image_alias2.bits, String),
    #             os.path.sep,
    #             image_alias2.filename,
    #         ).label("image_name_16_bits")
    #     )
    #     .filter(image_alias2.bits == 16)
    #     .filter(image_alias2.bands == "RGBN")
    #     .filter(image_alias2.sensor_name == Image.sensor_name)
    #     .order_by(func.levenshtein(image_alias1.filename, image_alias2.filename))
    #     .limit(1)
    #     .subquery()
    # )
    #
    # query = session.query(
    #     image_alias1.id.label("image_id"), subquery.c.image_name_16_bits
    # )

    image_name_16_bits = func.concat(
        image_alias2.sensor_name,
        "_",
        image_alias2.bands,
        "_",
        cast(image_alias2.bits, String),
        os.path.sep,
        image_alias2.filename,
        image_alias2.extension,
    ).label("image_name")

    id_with_16_bit_name = (
        session.query(image_alias1.id.label("image_id"), image_name_16_bits)
        .filter(image_alias2.bits == 16)
        .filter(image_alias2.bands == "RGBN")
        .filter(image_alias2.sensor_name == image_alias1.sensor_name)
        .distinct(image_alias1.id)
        .order_by(
            image_alias1.id,
            func.levenshtein(image_alias1.filename, image_alias2.filename),
        )
    ).subquery("id_with_16_bit_name")
    return id_with_16_bit_name


def image_id_from_properties(session: Session, properties: AnnotationProperties) -> int:
    """Get the image id from the properties image_name, or image_id if it exists."""
    if not properties.image_id and not properties.image_name:
        raise HTTPException(
            400, f"The annotation properties must have one of image_name or image_id."
        )

    if properties.image_name:
        image_id = image_id_from_image_name(session, properties.image_name)
    else:
        image_id = properties.image_id

    return image_id


def image_id_from_image_name(session: Session, image_name: str):
    image_id = session.query(Image.id).filter(Image.layer_name == image_name).scalar()
    if not image_id:
        raise HTTPException(400, f"Image layer name not found: {image_name}")
    return image_id
