from typing import List

import pytest

from geoimagenet_api.database.connection import connection_manager
from geoimagenet_api.database.models import Image, Annotation
from geoimagenet_api.endpoints.image import query_rgbn_16_bit_image
from tests.test_annotations import write_annotation, _clean_annotation_session


def write_image(sensor_name, bands, bits, filename, extension, *, session=None):
    def _write(_session):
        image = Image(
            sensor_name=sensor_name,
            bands=bands,
            bits=bits,
            filename=filename,
            extension=extension,
        )
        _session.add(image)
        _session.commit()
        _session.refresh(image)
        _session.expunge(image)

        return image

    if session is not None:
        return _write(session)
    else:
        with connection_manager.get_db_session() as session:
            return _write(session)


@pytest.fixture
def pleiades_images(request) -> List[Image]:
    images_list = """
    Pleiades_20120912_RGBN_50cm_8bits_AOI_35_Montreal_QC
    Pleiades_20140609_RGBN_50cm_8bits_AOI_35_Montreal_QC
    Pleiades_20150614_RGBN_50cm_8bits_AOI_21_GrandeRiviere_QC
    Pleiades_20120912_RGBN_50cm_8bits_AOI_5_Edmunston_NB
    Pleiades_20140715_RGBN_50cm_8bits_AOI_8_Kelowna_BC
    Pleiades_20150615_RGBN_50cm_8bits_AOI_11_Halifax_NS
    Pleiades_20120913_RGBN_50cm_8bits_AOI_27_StJohns_NL
    Pleiades_20140731_RGBN_50cm_8bits_AOI_17_PrinceGeorge_BC
    Pleiades_20150619_RGBN_50cm_8bits_AOI_30_Toronto_ON
    Pleiades_20121006_RGBN_50cm_8bits_AOI_34_Vancouver_BC
    Pleiades_20140914_RGBN_50cm_8bits_AOI_18_ChiselLake_MB
    Pleiades_20150807_RGBN_50cm_8bits_AOI_2_Aklavik_NWT
    Pleiades_20130609_RGBN_50cm_8bits_AOI_29_Ottawa_ON
    Pleiades_20140914_RGBN_50cm_8bits_AOI_34_Vancouver_BC
    Pleiades_20150813_RGBN_50cm_8bits_AOI_24_Chilliwack_BC
    Pleiades_20130628_RGBN_50cm_8bits_AOI_32_Calgary_AB
    Pleiades_20141012_RGBN_50cm_8bits_AOI_14_Prespatou_BC
    Pleiades_20150813_RGBN_50cm_8bits_AOI_31_Winnipeg_MB
    Pleiades_20130630_RGBN_50cm_8bits_AOI_16_Lethbridge_AB
    Pleiades_20141025_RGBN_50cm_8bits_AOI_1_Sherbrooke_QC
    Pleiades_20150817_RGBN_50cm_8bits_AOI_12_Carbonear_NL
    Pleiades_20130703_RGBN_50cm_8bits_AOI_23_Regina_SK
    Pleiades_20150503_RGBN_50cm_8bits_AOI_10_Windsor_QC
    Pleiades_20150831_RGBN_50cm_8bits_AOI_3_Iqaluit_NU
    Pleiades_20130715_RGBN_50cm_8bits_AOI_28_Quebec_QC
    Pleiades_20150503b_RGBN_50cm_8bits_AOI_10_Windsor_QC
    Pleiades_20150909_RGBN_50cm_8bits_AOI_13_FortResolution_NWT
    Pleiades_20130801_RGBN_50cm_8bits_AOI_19_FortMacKay_AB
    Pleiades_20150517_RGBN_50cm_8bits_AOI_30_Toronto_ON
    Pleiades_20150917_RGBN_50cm_8bits_AOI_5_Edmunston_NB
    Pleiades_20130806_RGBN_50cm_8bits_AOI_9_Firebag_AB
    Pleiades_20150517_RGBN_50cm_8bits_AOI_6_Newmarket_ON
    Pleiades_20151010_RGBN_50cm_8bits_AOI_35_Montreal_QC
    Pleiades_20130822_RGBN_50cm_8bits_AOI_22_Kamloops_BC
    Pleiades_20150519_RGBN_50cm_8bits_AOI_4_Kingston_ON
    Pleiades_20160620_RGBN_50cm_8bits_AOI_25_Sorel_QC
    Pleiades_20130906_RGBN_50cm_8bits_AOI_7_PrinceRupert_BC
    Pleiades_20150606_RGBN_50cm_8bits_AOI_30_Toronto_ON
    Pleiades_20140609_RGBN_50cm_8bits_AOI_15_HayRiver_NWT
    Pleiades_20150607_RGBN_50cm_8bits_AOI_21_GrandeRiviere_QC
    """
    images = []
    with connection_manager.get_db_session() as session:
        for line in images_list.split("\n"):
            filename_8 = line.strip()
            if filename_8:
                image = write_image(
                    "PLEIADES", "RGBN", 8, filename_8, ".tif", session=session
                )
                images.append(image)

                filename_16 = filename_8.replace("8bits", "16bits")
                image = write_image(
                    "PLEIADES", "RGBN", 16, filename_16, ".tif", session=session
                )
                images.append(image)
        session.expunge_all()

    def finalizer():
        with connection_manager.get_db_session() as session:
            image_ids = [i.id for i in images]
            session.query(Image).filter(Image.id.in_(image_ids)).delete(
                synchronize_session=False
            )
            session.commit()

    request.addfinalizer(finalizer)
    return images


def test_get_rgbn_16_bit_image_prespatou(pleiades_images):
    with _clean_annotation_session() as session:
        name = "Pleiades_20141012_RGBN_50cm_8bits_AOI_14_Prespatou_BC"
        prespatou_8_id = next(i.id for i in pleiades_images if i.filename == name)
        write_annotation(session=session, image_id=prespatou_8_id)

        id_with_16_bit_name = query_rgbn_16_bit_image(session)

        query = session.query(id_with_16_bit_name.c.image_name).filter(
            id_with_16_bit_name.c.image_id == prespatou_8_id
        )

        result = query.all()

        assert len(result) == 1
        assert (
            result[0].image_name
            == "PLEIADES_RGBN_16/Pleiades_20141012_RGBN_50cm_16bits_AOI_14_Prespatou_BC"
        )
