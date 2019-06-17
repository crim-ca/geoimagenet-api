import pytest

from geoimagenet_api.utils import make_codes_from_name


def test_make_codes_from_name1():
    name = "Marécage"
    expected = [
        'MARE',
        'MRCG',
        'MARE',
        'MARC',
        'MARA',
        'MARG',
        'MARE',
        'MAEC',
        'MAEA',
        'MAEG',
    ]
    assert list(make_codes_from_name(name))[:10] == expected


def test_make_codes_from_name2():
    name = "Bog - non arboré"
    expected = ['BONA',
                'BOGN',
                'BGNN',
                'BGNR',
                'BGNB',
                'BGNR',
                'BGNR',
                'BGNB',
                'BGNR',
                'BGRB',
                ]
    assert list(make_codes_from_name(name))[:10] == expected


def test_make_codes_from_name3():
    name = "Hydrographie surfacique"
    expected = ['HYDS',
                'HYDR',
                'HYDR',
                'HYDG',
                'HYDR',
                'HYDP',
                'HYDH',
                'HYDS',
                'HYDR',
                'HYDF']
    assert list(make_codes_from_name(name))[:10] == expected


def test_make_codes_from_name4():
    name = "Fen"
    expected = [
        "FENN",
    ]
    assert list(make_codes_from_name(name)) == expected
