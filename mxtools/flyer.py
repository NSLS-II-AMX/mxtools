import os
import time as ttime
from collections import deque

import h5py
from bluesky import plan_stubs as bps
from bluesky import plans as bp
from ophyd.sim import NullStatus
from ophyd.status import SubscriptionStatus

from .scans import setup_vector_program, setup_zebra_vector_scan, zebra_daq_prep

DEFAULT_DATUM_DICT = {"data": None, "omega": None}


class MXFlyer:
    def __init__(self, vector, zebra, detector=None) -> None:
        self.name = "MXFlyer"
        self.vector = vector
        self.zebra = zebra
        self.detector = detector

        self._asset_docs_cache = deque()
        self._resource_uids = []
        self._datum_counter = None
        self._datum_ids = DEFAULT_DATUM_DICT
        self._master_file = None
        self._master_metadata = []

        self._collection_dictionary = None

    def read_configuration(self):
        return {}

    def describe_configuration(self):
        return {}

    def kickoff(self):
        self.detector.stage()
        self.vector.go.put(1)

        return NullStatus()

    def complete(self):
        def callback_motion(value, old_value, **kwargs):
            print(f"old: {old_value} -> new: {value}")
            if int(round(old_value)) == 1 and int(round(value)) == 0:
                return True
            else:
                return False

        motion_status = SubscriptionStatus(self.vector.active, callback_motion, run=False)
        return motion_status

    def describe_collect(self):
        return_dict = {}
        return_dict["primary"] = {
            f"{self.detector.name}_image": {
                "source": f"{self.detector.name}_data",
                "dtype": "array",
                "shape": [
                    self.detector.cam.num_images.get(),
                    self.detector.cam.array_size.array_size_y.get(),
                    self.detector.cam.array_size.array_size_x.get(),
                ],
                "dims": ["images", "row", "column"],
                "external": "FILESTORE:",
            },
            "omega": {
                "source": f"{self.detector.name}_omega",
                "dtype": "array",
                "shape": [self.detector.cam.num_images.get()],
                "dims": ["images"],
                "external": "FILESTORE:",
            },
        }
        return return_dict

    def collect(self):
        self.unstage()

        now = ttime.time()
        self._master_metadata = self._extract_metadata()
        data = {f"{self.detector.name}_image": self._datum_ids["data"], "omega": self._datum_ids["omega"]}
        yield {
            "data": data,
            "timestamps": {key: now for key in data},
            "time": now,
            "filled": {key: False for key in data},
        }

    # def collect_asset_docs(self):
    #     # items = list(self._asset_docs_cache)
    #     items = list(self.detector.file._asset_docs_cache)
    #     print(f"{print_now()} items:\n{items}")
    #     self.detector.file._asset_docs_cache.clear()
    #     for item in items:
    #         yield item

    def collect_asset_docs(self):

        asset_docs_cache = []

        # Get the Resource which was produced when the detector was staged.
        ((name, resource),) = self.detector.file.collect_asset_docs()

        asset_docs_cache.append(("resource", resource))
        self._datum_ids = DEFAULT_DATUM_DICT
        # Generate Datum documents from scratch here, because the detector was
        # triggered externally by the DeltaTau, never by ophyd.
        resource_uid = resource["uid"]
        # num_points = int(math.ceil(self.detector.cam.num_images.get() /
        #                 self.detector.cam.fw_num_images_per_file.get()))

        # We are currently generating only one datum document for all frames, that's why
        #   we use the 0th index below.
        #
        # Uncomment & update the line below if more datum documents are needed:
        # for i in range(num_points):

        seq_id = self.detector.cam.sequence_id.get()

        self._master_file = f"{resource['root']}/{resource['resource_path']}_{seq_id}_master.h5"
        if not os.path.isfile(self._master_file):
            raise RuntimeError(f"File {self._master_file} does not exist")

        # The pseudocode below is from Tom Caswell explaining the relationship between resource, datum, and events.
        #
        # resource = {
        #     "resource_id": "RES",
        #     "resource_kwargs": {},  # this goes to __init__
        #     "spec": "AD-EIGER-MX",
        #     ...: ...,
        # }
        # datum = {
        #     "datum_id": "a",
        #     "datum_kwargs": {"data_key": "data"},  # this goes to __call__
        #     "resource": "RES",
        #     ...: ...,
        # }
        # datum = {
        #     "datum_id": "b",
        #     "datum_kwargs": {"data_key": "omega"},
        #     "resource": "RES",
        #     ...: ...,
        # }

        # event = {...: ..., "data": {"detector_img": "a", "omega": "b"}}

        for data_key in self._datum_ids.keys():
            datum_id = f"{resource_uid}/{data_key}"
            self._datum_ids[data_key] = datum_id
            datum = {
                "resource": resource_uid,
                "datum_id": datum_id,
                "datum_kwargs": {"data_key": data_key},
            }
            asset_docs_cache.append(("datum", datum))
        return tuple(asset_docs_cache)

    def _extract_metadata(self, field="omega"):
        with h5py.File(self._master_file, "r") as hf:
            return hf.get(f"entry/sample/goniometer/{field}")[()]

    def unstage(self):
        ttime.sleep(1.0)
        self.detector.unstage()
        self.detector.cam.acquire.put(0)


def configure_detector(
    detector,
    file_prefix,
    data_directory_name
):
    yield from bps.mv(detector.file.external_name, file_prefix)
    detector.file.write_path_template = data_directory_name
 

def configure_vector(
    vector,
    angle_start,
    scanWidth,
    imgWidth,
    exposurePeriodPerImage,
    file_number_start,
    scanEncoder=3,
    changeState=True,
):  # scan encoder 0=x, 1=y,2=z,3=omega

    yield from bps.mv(vector.sync, 1)
    yield from bps.mv(vector.expose, 1)

    if imgWidth == 0:
        angle_end = angle_start
        numImages = scanWidth
    else:
        angle_end = angle_start + scanWidth
        numImages = int(round(scanWidth / imgWidth))
    total_exposure_time = exposurePeriodPerImage * numImages
    if total_exposure_time < 1.0:
        yield from bps.mv(vector.buffer_time, 1000)
    else:
        yield from bps.mv(vector.buffer_time, 3)
        pass
    detector_dead_time = detector_single.cam.dead_time.get()
    yield from setup_vector_program(
        vector=vector,
        num_images=numImages,
        angle_start=angle_start,
        angle_end=angle_end,
        exposure_period_per_image=exposurePeriodPerImage,
    )

def configure_zebra(zebra, angle_start, exposurePeriodPerImage, detector_dead_time, scanWidth, imgWidth, numImages)
    yield from zebra_daq_prep(zebra)
    yield from bps.sleep(1.0)

    PW = (exposurePeriodPerImage - detector_dead_time) * 1000.0
    PS = (exposurePeriodPerImage) * 1000.0
    GW = scanWidth - (1.0 - (PW / PS)) * (imgWidth / 2.0)
    yield from setup_zebra_vector_scan(
        zebra=zebra,
        angle_start=angle_start,
        gate_width=GW,
        scan_width=scanWidth,
        pulse_width=PW,
        pulse_step=PS,
        exposure_period_per_image=exposurePeriodPerImage,
        num_images=numImages,
        is_still=imgWidth == 0,
    )


def configure_nyx_flyer():
    ...


def actual_scan(
    mx_flyer,
    detector,
    vector,
    zebra,
    angle_start,
    scanWidth,
    imgWidth,
    exposurePeriodPerImage,
    file_prefix,
    data_directory_name,
):
    # file_prefix = "abc"
    # data_directory_name = "def"

    yield from configure_detector(
        detector,
        file_prefix,
        data_directory_name
    )
    detector_dead_time = detector.cam.dead_time.get()
    yield from configure_vector(
        vector,
        angle_start,
        scanWidth,
        imgWidth,
        exposurePeriodPerImage,
        1,
    )
    yield from configure_zebra(
        zebra,
        angle_start,
        exposurePeriodPerImage,
        detector_dead_time,
        scanWidth,
        imgWidth,
        numImages
    }

    yield from bp.fly([mx_flyer])


# vector, zebra, detector_single are assumed to be in the namespace already
