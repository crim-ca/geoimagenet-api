import re
from pathlib import Path
from typing import List


class ImageData:
    """Data structure containing a list of images with its metadata.

    The folder name for the images will always be of the format {sensor_name}_{bands}_{bits}.
    Example: PLEIADES_RGBN_16

    The filenames can be anything, as long as any convention is respected within each image type.
    This is because the pairing of different images filenames depending on bands and bits
    is done using the smallest levenshtein distance.
    """

    re_bits = re.compile(r"^[1-9]\d*$")

    def __init__(
        self, sensor_name: str, bands: str, bits: str, images_list: List[Path]
    ):
        if not sensor_name.isupper():
            raise ValueError(
                f"'sensor_name' must be all caps in folder name: {sensor_name}"
            )
        if not bands.isupper():
            raise ValueError(f"'bands' must be all caps in folder name: {bands}")
        if not self.re_bits.match(bits):
            raise ValueError(f"'bits' must be an integer in folder name: {bits}")
        self.sensor_name = sensor_name
        self.bands = bands
        self.bits = int(bits)
        self.images_list = images_list

    def workspace_names(self, bands=None):
        names = []
        bands_list = [self.bands]
        if bands:
            bands_list = [bands]
        elif self.bands == "RGBN":
            bands_list = ["RGB", "NRG"]
        for bands in bands_list:
            names.append(f"{self.sensor_name}_{bands}")
        return names
