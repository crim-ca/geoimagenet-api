from geoimagenet_api.geoserver_setup.utils import find_date


def test_find_date():
    assert find_date("test 2018-01-02 something else") == "20180102"
    assert find_date("01-11-2018") == "20181101"
    assert find_date("20120912") == "20120912"
    assert find_date("12-09-2012") == "20120912"
