import re
from dataclasses import dataclass
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


@dataclass
class ImageInfo:
    """Data structure similar to `ImageData` but without images_list.

    More suitable when the images folder is not local and can't be iterated upon."""
    sensor_name: str
    bands: str
    bits: int

    @classmethod
    def from_workspace_name(cls, name: str, bits=8):
        """Workspace name must be like: PLEIADES_RGB"""
        splits = name.upper().split("_")
        if not len(splits) == 2:
            raise ValueError("Workspace name must be of the form {sensor_name}_{bands}")
        sensor_name, bands = splits
        other_bands = bands
        for b in "RGBN":
            other_bands = other_bands.replace(b, "")
        if other_bands:
            raise ValueError(f"Band format not recognized: {bands}")
        return cls(sensor_name=sensor_name, bands=bands, bits=bits)

    def workspace_names(self, bands=None):
        return [f"{self.sensor_name}_{self.bands}"]
