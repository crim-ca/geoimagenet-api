from pathlib import Path

from geoimagenet_api.geoserver_setup import images_names_utils
from geoimagenet_api.geoserver_setup.utils import (
    find_date,
    find_image_trace,
    wkt_multipolygon_to_polygon,
)


def test_find_date():
    assert find_date("test 2018-01-02 something else") == "20180102"
    assert find_date("01-11-2018") == "20181101"
    assert find_date("20120912") == "20120912"
    assert find_date("12-09-2012") == "20120912"


def test_find_image_trace():
    images_folder = Path(__file__).parent / "data"
    image_filename_stem = "Pleiades_20120912_RGB_50cm_8bits_AOI_35_Montreal_QC"
    trace = find_image_trace(images_folder, "PLEIADES", image_filename_stem)

    assert str(trace).endswith(
        "PLEIADES_CONTOURS/Pleiades_20120912_RGBN_50cm_16bits_AOI_35_Montreal_QC_trace.shp"
    )


def test_load_image_trace():
    images_folder = Path(__file__).parent / "data"
    image_filename_stem = "Pleiades_20120912_RGB_50cm_8bits_AOI_35_Montreal_QC"
    wkt = load_image_trace_geometry(images_folder, "PLEIADES", image_filename_stem)
    assert wkt.startswith("POLYGON")


def test_re_match_pleides_8_bits_rgb():
    m = images_names_utils.re_pleiades.match(
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB"
    )
    assert m.group("date") == "20130630"
    assert m.group("bands") == "RGB"
    assert m.group("bits") == "8"
    assert m.group("city") == "Lethbridge"
    assert m.group("province") == "AB"
    assert m.group("trace") is None
    assert m.group("bbox") is None


def test_re_match_pleides_16_bits_rgb():
    m = images_names_utils.re_pleiades.match(
        "Pleiades_20130630_RGB_50cm_16bits_AOI_16_Lethbridge_AB"
    )
    assert m.group("date") == "20130630"
    assert m.group("bands") == "RGB"
    assert m.group("bits") == "16"
    assert m.group("city") == "Lethbridge"
    assert m.group("province") == "AB"
    assert m.group("trace") is None
    assert m.group("bbox") is None


def test_re_match_pleides_16_bits_rgbn():
    m = images_names_utils.re_pleiades.match(
        "Pleiades_20130630_RGBN_50cm_16bits_AOI_16_Lethbridge_AB"
    )
    print(m.groups())
    assert m.group("date") == "20130630"
    assert m.group("bands") == "RGBN"
    assert m.group("bits") == "16"
    assert m.group("city") == "Lethbridge"
    assert m.group("province") == "AB"
    assert m.group("trace") is None
    assert m.group("bbox") is None


def test_re_match_pleides_8_bits_rgbn():
    m = images_names_utils.re_pleiades.match(
        "Pleiades_20130630_RGBN_50cm_8bits_AOI_16_Lethbridge_AB"
    )
    assert m.group("date") == "20130630"
    assert m.group("bands") == "RGBN"
    assert m.group("bits") == "8"
    assert m.group("city") == "Lethbridge"
    assert m.group("province") == "AB"
    assert m.group("trace") is None
    assert m.group("bbox") is None


def test_re_match_pleides_8_bits_rgbn_trace():
    m = images_names_utils.re_pleiades.match(
        "Pleiades_20130630_RGBN_50cm_8bits_AOI_16_Lethbridge_AB_trace"
    )
    assert m.group("date") == "20130630"
    assert m.group("bands") == "RGBN"
    assert m.group("bits") == "8"
    assert m.group("city") == "Lethbridge"
    assert m.group("province") == "AB"
    assert m.group("trace") == "trace"
    assert m.group("bbox") is None


def test_re_match_pleides_8_bits_rgbn_bbox():
    m = images_names_utils.re_pleiades.match(
        "Pleiades_20130630_RGBN_50cm_8bits_AOI_16_Lethbridge_AB_bbox"
    )
    assert m.group("date") == "20130630"
    assert m.group("bands") == "RGBN"
    assert m.group("bits") == "8"
    assert m.group("city") == "Lethbridge"
    assert m.group("province") == "AB"
    assert m.group("trace") is None
    assert m.group("bbox") == "bbox"


def test_compare_name():
    assert images_names_utils.compare_name(
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB",
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB",
    )
    assert images_names_utils.compare_name(
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB",
        "Pleiades_20130630_RGB_50cm_16bits_AOI_16_Lethbridge_AB",
    )
    assert images_names_utils.compare_name(
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB",
        "Pleiades_20130630_RGBN_50cm_8bits_AOI_16_Lethbridge_AB",
    )
    assert images_names_utils.compare_name(
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB",
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB_trace",
    )
    assert images_names_utils.compare_name(
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB",
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB_bbox",
    )
    assert images_names_utils.compare_name(
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB",
        "Pleiades_20130630_NRG_50cm_8bits_AOI_16_Lethbridge_AB",
    )
    assert not images_names_utils.compare_name(
        "Pleiades_20130630_RGB_50cm_8bits_AOI_16_Lethbridge_AB",
        "Pleiades_20130630_RGB_50cm_8bits_AOI_35_Montreal_AB",
    )


def test_find_matching_name():
    names_list = [
        "Pleiades_20120912_RGBN_50cm_16bits_AOI_35_Montreal_QC_trace",
        "Pleiades_20141025_RGBN_50cm_16bits_AOI_1_Sherbrooke_QC_trace",
        "Pleiades_20120912_RGBN_50cm_16bits_AOI_5_Edmunston_NB_trace",
        "Pleiades_20150503_RGBN_50cm_16bits_AOI_10_Windsor_QC_trace",
        "Pleiades_20120913_RGBN_50cm_16bits_AOI_27_StJohns_NL_trace",
        "Pleiades_20150503b_RGBN_50cm_16bits_AOI_10_Windsor_QC_trace",
        "Pleiades_20121006_RGBN_50cm_16bits_AOI_34_Vancouver_BC_trace",
        "Pleiades_20150517_RGBN_50cm_16bits_AOI_30_Toronto_ON_trace",
        "Pleiades_20130609_RGBN_50cm_16bits_AOI_29_Ottawa_ON_trace",
        "Pleiades_20150517_RGBN_50cm_16bits_AOI_6_Newmarket_ON_trace",
        "Pleiades_20130628_RGBN_50cm_16bits_AOI_32_Calgary_AB_trace",
        "Pleiades_20150519_RGBN_50cm_16bits_AOI_4_Kingston_ON_trace",
        "Pleiades_20130630_RGBN_50cm_16bits_AOI_16_Lethbridge_AB_trace",
        "Pleiades_20150606_RGBN_50cm_16bits_AOI_30_Toronto_ON_trace",
        "Pleiades_20130703_RGBN_50cm_16bits_AOI_23_Regina_SK_trace",
        "Pleiades_20150607_RGBN_50cm_16bits_AOI_21_GrandeRiviere_QC_trace",
        "Pleiades_20130715_RGBN_50cm_16bits_AOI_28_Quebec_QC_trace",
        "Pleiades_20150614_RGBN_50cm_16bits_AOI_21_GrandeRiviere_QC_trace",
        "Pleiades_20130801_RGBN_50cm_16bits_AOI_19_FortMacKay_AB_trace",
        "Pleiades_20150615_RGBN_50cm_16bits_AOI_11_Halifax_NS_trace",
        "Pleiades_20130806_RGBN_50cm_16bits_AOI_9_Firebag_AB_trace",
        "Pleiades_20150619_RGBN_50cm_16bits_AOI_30_Toronto_ON_trace",
        "Pleiades_20130822_RGBN_50cm_16bits_AOI_22_Kamloops_BC_trace",
        "Pleiades_20150807_RGBN_50cm_16bits_AOI_2_Aklavik_NWT_trace",
        "Pleiades_20130906_RGBN_50cm_16bits_AOI_7_PrinceRupert_BC_trace",
        "Pleiades_20150813_RGBN_50cm_16bits_AOI_24_Chilliwack_BC_trace",
        "Pleiades_20140609_RGBN_50cm_16bits_AOI_15_HayRiver_NWT_trace",
        "Pleiades_20150813_RGBN_50cm_16bits_AOI_31_Winnipeg_MB_trace",
        "Pleiades_20140609_RGBN_50cm_16bits_AOI_35_Montreal_QC_trace",
        "Pleiades_20150817_RGBN_50cm_16bits_AOI_12_Carbonear_NL_trace",
        "Pleiades_20140715_RGBN_50cm_16bits_AOI_8_Kelowna_BC_trace",
        "Pleiades_20150831_RGBN_50cm_16bits_AOI_3_Iqaluit_NU_trace",
        "Pleiades_20140731_RGBN_50cm_16bits_AOI_17_PrinceGeorge_BC_trace",
        "Pleiades_20150909_RGBN_50cm_16bits_AOI_13_FortResolution_NWT_trace",
        "Pleiades_20140914_RGBN_50cm_16bits_AOI_18_ChiselLake_MB_trace",
        "Pleiades_20150917_RGBN_50cm_16bits_AOI_5_Edmunston_NB_trace",
        "Pleiades_20140914_RGBN_50cm_16bits_AOI_34_Vancouver_BC_trace",
        "Pleiades_20151010_RGBN_50cm_16bits_AOI_35_Montreal_QC_trace",
        "Pleiades_20141012_RGBN_50cm_16bits_AOI_14_Prespatou_BC_trace",
        "Pleiades_20160620_RGBN_50cm_16bits_AOI_25_Sorel_QC_trace",
    ]
    image_name = "Pleiades_20150517_NRG_50cm_8bits_AOI_6_Newmarket_ON"
    assert (
        images_names_utils.find_matching_name(image_name, names_list)
        == "Pleiades_20150517_RGBN_50cm_16bits_AOI_6_Newmarket_ON_trace"
    )


def test_multipolygon_wkt():
    multipolygon = (
        "SRID=3857;MULTIPOLYGON (((20 35, 10 30, 10 10, 30 5, 45 20, 20 35),"
        "(30 20, 20 15, 20 25, 30 20)),"
        "((40 40, 20 45, 45 30, 40 40)))"
    )

    polygon = wkt_multipolygon_to_polygon(multipolygon)
    assert polygon == "SRID=3857;POLYGON ((20 35, 10 30, 10 10, 30 5, 45 20, 20 35))"
