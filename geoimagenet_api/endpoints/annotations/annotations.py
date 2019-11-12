from collections import defaultdict
from datetime import datetime
from typing import Tuple, Dict, Union, List

import psycopg2
import psycopg2.extras
import sqlalchemy.exc
from fastapi import APIRouter, Query, Body
from sqlalchemy import and_, or_
from sqlalchemy.sql import func
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from geoimagenet_api.endpoints.images import (
    image_id_from_image_name,
    image_id_from_properties,
)
from geoimagenet_api.endpoints.users import get_logged_user_id
from geoimagenet_api.openapi_schemas import (
    AnnotationCountByStatus,
    GeoJsonFeature,
    GeoJsonFeatureCollection,
    AnnotationRequestReview,
    AnnotationStatusUpdateIds,
    AnnotationStatusUpdateTaxonomyClass,
    AnyGeojsonGeometry,
)
from geoimagenet_api.database.models import (
    Annotation as DBAnnotation,
    AnnotationStatus,
    TaxonomyClass as DBTaxonomyClass,
    ValidationEvent,
    ValidationValue,
    Image,
    Person,
)
from geoimagenet_api.endpoints.taxonomy_classes import (
    flatten_taxonomy_classes_ids,
    get_taxonomy_classes_tree,
    get_all_taxonomy_classes_ids,
)
from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.utils import geojson_stream

from .utils import DEFAULT_SRID, geojson_features_from_body, get_annotation_ids_integers


router = APIRouter()


def _serialize_geometry(geometry: AnyGeojsonGeometry, crs: int):
    """Takes a dict geojson geometry, and prepares it to  be written to the db.

    It transforms the geometry into the DEFAULT_CRS if necessary."""
    geom_string = geometry.json()
    geom = func.ST_SetSRID(func.ST_GeomFromGeoJSON(geom_string), crs)
    if crs != DEFAULT_SRID:
        geom = func.ST_Transform(geom, DEFAULT_SRID)
    return geom


@router.get(
    "/annotations", response_model=GeoJsonFeatureCollection, summary="Get as GeoJson"
)
def get(
    request: Request,
    image_name: str = None,
    status: str = None,
    taxonomy_class_id: int = None,
    review_requested: bool = None,
    current_user_only: bool = False,
    annotator_id: int = None,
    with_geometry: bool = True,
    last_updated_since: datetime = None,
    last_updated_before: datetime = None,
):
    with connection_manager.get_db_session() as session:
        fields = [
            DBAnnotation.id,
            DBAnnotation.taxonomy_class_id,
            DBTaxonomyClass.code.label("taxonomy_class_code"),
            DBAnnotation.annotator_id,
            DBAnnotation.image_id,
            Image.layer_name.label("image_name"),
            DBAnnotation.name,
            DBAnnotation.review_requested,
            DBAnnotation.status,
            DBAnnotation.updated_at,
        ]
        if with_geometry:
            fields.append(func.ST_AsGeoJSON(DBAnnotation.geometry).label("geometry"))
        query = session.query(*fields).outerjoin(Image).join(DBTaxonomyClass)
        if image_name:
            image_id = image_id_from_image_name(session, image_name)
            query = query.filter(DBAnnotation.image_id == image_id)
        if status:
            query = query.filter(DBAnnotation.status == status)
        if taxonomy_class_id is not None:
            query = query.filter(DBAnnotation.taxonomy_class_id == taxonomy_class_id)
        if review_requested is not None:
            query = query.filter(DBAnnotation.review_requested == review_requested)
        if current_user_only:
            logged_user_id = get_logged_user_id(request)
            query = query.filter(DBAnnotation.annotator_id == logged_user_id)
        elif annotator_id:
            if not session.query(Person.id).filter_by(id=annotator_id).first():
                raise HTTPException(404, f"annotator_id not found: {annotator_id}")
            query = query.filter(DBAnnotation.annotator_id == annotator_id)

        if last_updated_since:
            query = query.filter(DBAnnotation.updated_at >= last_updated_since)
        if last_updated_before:
            query = query.filter(DBAnnotation.updated_at <= last_updated_before)

        properties = [f.key for f in fields if f.key not in ["geometry", "id"]]
        stream = geojson_stream(
            query, properties=properties, with_geometry=with_geometry
        )
        data = "".join(stream)

        return Response(data, media_type="application/json")


@router.put("/annotations", status_code=204, summary="Modify")
def put(
    request: Request,
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection] = Body(...),
    srid: int = DEFAULT_SRID,
):
    logged_user_id = get_logged_user_id(request)

    with connection_manager.get_db_session() as session:
        features = geojson_features_from_body(body)
        for feature in features:
            properties = feature.properties
            geometry = feature.geometry

            if feature.id is None:
                raise HTTPException(400, "Property 'id' is required")

            id_ = get_annotation_ids_integers([feature.id])[0]

            annotation = session.query(DBAnnotation).filter_by(id=id_).first()
            if not annotation:
                raise HTTPException(404, f"Annotation id not found: {id_}")
            if annotation.annotator_id != logged_user_id:
                raise HTTPException(
                    403, "You are trying to update an annotation another user created."
                )

            geom = _serialize_geometry(geometry, srid)

            # Notes:
            # You can't change the annotator_id of an annotation
            # Use specific endpoints to change the status (ex: /annotations/release)
            annotation.taxonomy_class_id = properties.taxonomy_class_id

            annotation.image_id = image_id_from_properties(session, properties)
            annotation.geometry = geom
        try:
            session.commit()
        except sqlalchemy.exc.IntegrityError as e:  # pragma: no cover
            raise HTTPException(400, f"Error: {e}")

    return Response(status_code=204)


@router.post(
    "/annotations", response_model=List[int], status_code=201, summary="Create"
)
def post(
    request: Request,
    body: Union[GeoJsonFeature, GeoJsonFeatureCollection] = Body(...),
    srid: int = DEFAULT_SRID,
):
    return post_annotations(request, body, srid)


@router.get(
    "/annotations/counts/{taxonomy_class_id}",
    response_model=Dict[str, AnnotationCountByStatus],
    status_code=200,
    summary="Get counts",
)
def counts(
    request: Request,
    taxonomy_class_id: int,
    group_by_image: bool = Query(
        False, description="Group by taxonomy class id or by image_name"
    ),
    current_user_only: bool = Query(
        False, description="If true, count only the current user's annotations"
    ),
    with_taxonomy_children: bool = Query(
        True, description="Include the children of the provided taxonomy class id"
    ),
    review_requested: bool = Query(
        None, description="Filter annotations by the review_requested attribute"
    ),
):
    """Return annotation counts for the given taxonomy class along with its children.
    If group_by_image is True, the counts are grouped by image name instead of
    taxonomy class.
    """

    with connection_manager.get_db_session() as session:
        taxo = get_taxonomy_classes_tree(session, taxonomy_class_id=taxonomy_class_id)
        if not taxo:
            raise HTTPException(
                404, f"Taxonomy class id not found: {taxonomy_class_id}"
            )

        if with_taxonomy_children:
            taxonomy_class_ids = flatten_taxonomy_classes_ids(taxo)
        else:
            taxonomy_class_ids = [taxonomy_class_id]

        annotation_count_dict = defaultdict(AnnotationCountByStatus)

        if group_by_image:
            group_by_field = Image.layer_name
        else:
            group_by_field = DBAnnotation.taxonomy_class_id

        query = session.query(
            group_by_field,
            DBAnnotation.status.name,
            func.count(DBAnnotation.id).label("annotation_count"),
        )
        if group_by_image:
            query = query.select_from(DBAnnotation).join(
                Image, Image.id == DBAnnotation.image_id
            )
        query = (
            query.filter(DBAnnotation.taxonomy_class_id.in_(taxonomy_class_ids))
            .group_by(group_by_field)
            .group_by(DBAnnotation.status.name)
        )

        if current_user_only:
            logged_user_id = get_logged_user_id(request)
            query = query.filter(DBAnnotation.annotator_id == logged_user_id)

        if review_requested is not None:
            query = query.filter(DBAnnotation.review_requested == review_requested)

        for group_by_field_name, status, count in query:
            setattr(annotation_count_dict[str(group_by_field_name)], status, count)

        if not group_by_image:
            # add annotation count to parent objects
            def recurse_add_counts(obj):
                for o in obj.children:
                    annotation_count_dict[str(obj.id)] += recurse_add_counts(o)
                return annotation_count_dict[str(obj.id)]

            recurse_add_counts(taxo)

        return annotation_count_dict


def post_annotations(
    request,
    body,
    srid,
    *,
    trust_status=False,
    trust_annotator_id=False,
    raise_outside_image=True,
) -> List[int]:
    """

    :param request: request instance
    :param body: POST content
    :param srid: EPSG code
    :param trust_status: Insert the provided status and review_requested field, not the defaults for new annotations
    :param trust_annotator_id: Insert the provided annotator_id in the annotation properties, not the logged user id
    :param raise_outside_image: Raise an error when an annotation is outside all of the images
    :return: A list of written annotation ids
    """
    logged_user_id = get_logged_user_id(request)

    with connection_manager.get_db_session() as session:
        taxonomy_class_dict = dict(
            session.query(DBTaxonomyClass.code, DBTaxonomyClass.id)
        )
        taxonomy_class_ids = set(taxonomy_class_dict.values())

        images_dict = dict(session.query(Image.layer_name, Image.id))
        image_ids = set(images_dict.values())

    features = geojson_features_from_body(body)

    # configure feature properties
    for feature in features:
        props = feature.properties

        props.annotator_id = (
            props.annotator_id
            if trust_annotator_id and props.annotator_id
            else logged_user_id
        )

        if props.taxonomy_class_code:
            if props.taxonomy_class_code not in taxonomy_class_dict:
                raise HTTPException(
                    404, f"taxonomy_class_code not found: {props.taxonomy_class_code}"
                )
            props.taxonomy_class_id = taxonomy_class_dict[props.taxonomy_class_code]
        elif props.taxonomy_class_id:
            if props.taxonomy_class_id not in taxonomy_class_ids:
                raise HTTPException(
                    404, f"taxonomy_class_id not found: {props.taxonomy_class_id}"
                )
            props.taxonomy_class_id = props.taxonomy_class_id
        else:
            raise HTTPException(
                400, f"One of taxonomy_class_id or taxonomy_class_code required"
            )

        props.status = (
            props.status.value if trust_status else AnnotationStatus.new.value
        )
        props.review_requested = props.review_requested if trust_status else False

        if props.image_name:
            if props.image_name not in images_dict:
                raise HTTPException(404, f"image_name not found: {props.image_name}")
            props.image_id = images_dict[props.image_name]
        elif props.image_id is not None:
            if props.image_id not in image_ids:
                raise HTTPException(404, f"image_id not found: {props.image_id}")
            props.image_id = props.image_id

    geom_template = f"ST_SetSRID(ST_GeomFromGeoJSON(%s), {srid})"
    if srid != DEFAULT_SRID:
        geom_template = f"ST_Transform({geom_template}, {DEFAULT_SRID})"

    # configure image ids with image bounding boxes
    values = []
    for n, f in enumerate(features):
        geom = geom_template % f"'{f.geometry.json()}'"
        values.append(f"({geom}, {n})")

    with connection_manager.get_db_session() as session:
        rows = session.execute(
            """
            with geometry_list (geometry, sort_order) as (
                values {}
            )
            select array_agg(image.id)
            from image
                right join geometry_list on ST_Contains(image.trace, geometry_list.geometry)
            group by geometry_list.sort_order
            order by geometry_list.sort_order;
        """.format(
                ", ".join(values)
            )
        )
        feature_image_ids = [q[0] for q in rows]

    for feature, image_ids in zip(features, feature_image_ids):
        image_id = feature.properties.image_id
        if image_id:
            if image_id not in image_ids:
                raise HTTPException(
                    400,
                    f"One of the annotations is not contained within the given image",
                )
        elif image_ids:
            feature.properties.image_id = image_ids[0]
        elif raise_outside_image:
            raise HTTPException(
                400, f"One of the annotations is not contained within an image"
            )

    def _make_values(feature: GeoJsonFeature):
        return (
            feature.properties.annotator_id,
            feature.geometry.json(),
            feature.properties.taxonomy_class_id,
            feature.properties.status,
            feature.properties.review_requested,
            feature.properties.image_id,
        )

    template = f"(%s, {geom_template}, %s, %s, %s, %s)"

    connection = connection_manager.engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            fields = "annotator_id, geometry, taxonomy_class_id, status, review_requested, image_id"
            result = psycopg2.extras.execute_values(
                cursor,
                f"INSERT INTO annotation ({fields}) VALUES %s RETURNING id;",
                map(_make_values, features),
                template=template,
                page_size=100,
                fetch=True,
            )
            written_ids = [r[0] for r in result]
            connection.commit()
    except psycopg2.IntegrityError as e:  # pragma: no cover
        raise HTTPException(400, f"Error: {e}")
    finally:
        connection.close()

    return written_ids

