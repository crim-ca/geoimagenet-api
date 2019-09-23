from pathlib import Path

from geoimagenet_api.geoserver_setup.utils import (
    find_date,
    load_image_trace_geometry,
    _find_image_trace,
)


def test_find_date():
    assert find_date("test 2018-01-02 something else") == "20180102"
    assert find_date("01-11-2018") == "20181101"
    assert find_date("20120912") == "20120912"
    assert find_date("12-09-2012") == "20120912"


def test_find_image_trace():
    images_folder = Path(__file__).parent / "data"
    image_filename_stem = "Pleiades_20120912_RGB_50cm_8bits_AOI_35_Montreal_QC"
    trace = _find_image_trace(images_folder, "PLEIADES", image_filename_stem)

    assert str(trace).endswith(
        "PLEIADES_CONTOURS/Pleiades_20120912_RGBN_50cm_16bits_AOI_35_Montreal_QC_trace.shp"
    )


def test_load_image_trace():
    images_folder = Path(__file__).parent / "data"
    image_filename_stem = "Pleiades_20120912_RGB_50cm_8bits_AOI_35_Montreal_QC"
    wkt = load_image_trace_geometry(images_folder, "PLEIADES", image_filename_stem)
    assert wkt.startswith("POLYGON")
