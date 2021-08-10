import time as ttime
from collections import deque

from bluesky import plan_stubs as bps
from bluesky import plans as bp
from ophyd.sim import NullStatus
from ophyd.status import SubscriptionStatus

from .scans import (setup_vector_program, setup_zebra_vector_scan,
                    zebra_daq_prep)


class MXFlyer:
    def __init__(self, vector, zebra, eiger=None) -> None:
        self.name = "MXFlyer"
        self.vector = vector
        self.zebra = zebra
        self.detector = eiger

        self._asset_docs_cache = deque()
        self._resource_uids = []
        self._datum_counter = None
        self._datum_ids = []

        self._collection_dictionary = None

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

        motion_status = SubscriptionStatus(self.vector.active, callback_motion)
        return motion_status

    def describe_collect(self):
        return {self.name: {}}

    def collect(self):
        self.unstage()

        now = ttime.time()
        data = {}
        yield {
            "data": data,
            "timestamps": {key: now for key in data},
            "time": now,
            "filled": {key: False for key in data},
        }

    def collect_asset_docs(self):
        items = list(self._asset_docs_cache)
        self._asset_docs_cache.clear()
        for item in items:
            yield item

    def unstage(self):
        self.detector.unstage()


def configure_flyer(
    vector,
    zebra,
    eiger_single,
    angle_start,
    scanWidth,
    imgWidth,
    exposurePeriodPerImage,
    filePrefix,
    data_directory_name,
    file_number_start,
    scanEncoder=3,
    changeState=True,
):  # scan encoder 0=x, 1=y,2=z,3=omega
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
    detector_dead_time = eiger_single.cam.dead_time.get()
    yield from setup_vector_program(
        vector=vector,
        num_images=numImages,
        angle_start=angle_start,
        angle_end=angle_end,
        exposure_period_per_image=exposurePeriodPerImage,
    )
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


def actual_scan(mx_flyer, eiger, vector, zebra, angle_start, scanWidth, imgWidth, exposurePeriodPerImage):
    file_prefix = "abc"
    data_directory_name = "def"
    yield from bps.mv(eiger.file.external_name, "prefix_name")
    yield from configure_flyer(
        vector,
        zebra,
        eiger,
        angle_start,
        scanWidth,
        imgWidth,
        exposurePeriodPerImage,
        file_prefix,
        data_directory_name,
        1,
    )
    yield from bp.fly([mx_flyer])


# vector, zebra, eiger_single are assumed to be in the namespace already
