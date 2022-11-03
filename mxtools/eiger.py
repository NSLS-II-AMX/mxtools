import datetime
import logging
import os
import time as ttime
from collections import OrderedDict, deque
from pathlib import PurePath
from types import SimpleNamespace

import h5py
from ophyd import Component as Cpt
from ophyd import Device, EpicsPathSignal, EpicsSignal, ImagePlugin, Signal, SingleTrigger
from ophyd.areadetector import EigerDetector
from ophyd.areadetector.base import ADComponent, EpicsSignalWithRBV
from ophyd.areadetector.filestore_mixins import FileStoreBase  # , new_short_uid

from . import print_now

logger = logging.getLogger(__name__)

DEFAULT_DATUM_DICT = {"data": None, "omega": None}

# TODO: convert it to Enum class.
INTERNAL_SERIES = 0
INTERNAL_ENABLE = 1
EXTERNAL_SERIES = 2
EXTERNAL_ENABLE = 3


class EigerSimulatedFilePlugin(Device, FileStoreBase):
    sequence_id = ADComponent(EpicsSignal, "SequenceId")
    file_path = ADComponent(EpicsPathSignal, "FilePath", string=True, path_semantics="posix")
    file_write_name_pattern = ADComponent(EpicsSignalWithRBV, "FWNamePattern", string=True)
    file_write_images_per_file = ADComponent(EpicsSignalWithRBV, "FWNImagesPerFile")
    current_run_start_uid = Cpt(Signal, value="", add_prefix=())
    enable = SimpleNamespace(get=lambda: True)
    external_name = Cpt(Signal, value="")

    def __init__(self, *args, **kwargs):
        self.sequence_id_offset = 1
        # This is changed for when a datum is a slice
        # also used by ophyd
        self.filestore_spec = "AD_EIGER_MX"
        self.frame_num = None
        super().__init__(*args, **kwargs)
        self._datum_kwargs_map = dict()  # store kwargs for each uid

    def stage(self):
        print(f"{print_now()} staging detector {self.name}")
        res_uid = self.external_name.get()
        write_path = datetime.datetime.now().strftime(self.write_path_template)
        self.file_path.set(f"{write_path}/")
        self.file_write_name_pattern.set("{}_$id".format(res_uid))
        super().stage()
        fn = PurePath(self.file_path.get()) / res_uid
        ipf = int(self.file_write_images_per_file.get())  # noqa
        # logger.debug("Inserting resource with filename %s", fn)
        self._fn = fn
        # res_kwargs = {"images_per_file": ipf}
        seq_id = int(self.sequence_id.get())  # det writes to the NEXT one
        res_kwargs = {"seq_id": seq_id}
        self._generate_resource(res_kwargs)
        print(f"{print_now()} done staging detector {self.name}")

    def generate_datum(self, key, timestamp, datum_kwargs):
        # The detector keeps its own counter which is uses label HDF5
        # sub-files.  We access that counter via the sequence_id
        # signal and stash it in the datum.
        if self.frame_num is not None:
            datum_kwargs.update({"frame_num": self.frame_num})
        return super().generate_datum(key, timestamp, datum_kwargs)


class EigerBaseV26(EigerDetector):
    # cam = Cpt(EigerDetectorCamV33, 'cam1:')
    file = Cpt(
        EigerSimulatedFilePlugin,
        suffix="cam1:",
        write_path_template="",
    )
    image = Cpt(ImagePlugin, "image1:")

    # hotfix: shadow non-existant PV
    size_link = None

    def __init__(self, *args, **kwargs):
        beamline = kwargs.pop("beamline", "fmx")
        super().__init__(*args, **kwargs)
        self.file.write_path_template = f"/nsls2/data/{beamline}/legacy"

    def stage(self, *args, **kwargs):
        # before parent
        ret = super().stage(*args, **kwargs)
        # after parent
        # self.cam.manual_trigger.set(1)
        return ret

    def unstage(self):
        # self.cam.manual_trigger.set(0)
        super().unstage()


class EigerSingleTriggerV26(SingleTrigger, EigerBaseV26):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.stage_sigs["cam.trigger_mode"] = 0 #original: single manual trigger
        self.stage_sigs.pop("cam.acquire")  # remove acquire=0
        # self.stage_sigs['shutter_mode'] = 1  # 'EPICS PV'
        self.stage_sigs.update({"cam.compression_algo": "BS LZ4"})  # TODO is this useful? seems too late
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

    def describe_collect(self):
        return_dict = {}
        return_dict["primary"] = {
            f"{self.detector.name}_image": {
                "source": f"{self.detector.name}_data",
                "dtype": "array",
                "shape": [
                    self.cam.num_images.get(),
                    self.cam.array_size.array_size_y.get(),
                    self.cam.array_size.array_size_x.get(),
                ],
                "dims": ["images", "row", "column"],
                "external": "FILESTORE:",
            },
            "omega": {
                "source": f"{self.detector.name}_omega",
                "dtype": "array",
                "shape": [self.cam.num_images.get()],
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
        ((name, resource),) = self.file.collect_asset_docs()

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

        seq_id = self.cam.sequence_id.get()

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
        self.cam.acquire.put(0)
        super().unstage()

    def stage(self, *args, **kwargs):
        return super().stage(*args, **kwargs)

    def trigger(self, *args, **kwargs):
        status = super().trigger(*args, **kwargs)
        self.cam.special_trigger_button.set(1)
        return status

    def read(self, *args, streaming=False, **kwargs):
        """
        This is a test of using streaming read.
        Ideally, this should be handled by a new _stream_attrs property.
        For now, we just check for a streaming key in read and
        call super() if False, or read the one key we know we should read
        if True.

        Parameters
        ----------
        streaming : bool, optional
            whether to read streaming attrs or not
        """
        if streaming:
            key = self._image_name  # this comes from the SingleTrigger mixin
            read_dict = super().read()
            ret = OrderedDict({key: read_dict[key]})
            return ret
        else:
            ret = super().read(*args, **kwargs)
            return ret

    def describe(self, *args, streaming=False, **kwargs):
        """
        This is a test of using streaming read.
        Ideally, this should be handled by a new _stream_attrs property.
        For now, we just check for a streaming key in read and
        call super() if False, or read the one key we know we should read
        if True.

        Parameters
        ----------
        streaming : bool, optional
            whether to read streaming attrs or not
        """
        if streaming:
            key = self._image_name  # this comes from the SingleTrigger mixin
            read_dict = super().describe()
            ret = OrderedDict({key: read_dict[key]})
            return ret
        else:
            ret = super().describe(*args, **kwargs)
            return ret

    def super_unstage(self):
        super().unstage()


def set_eiger_defaults(eiger):
    """Choose which attributes to read per-step (read_attrs) or
    per-run (configuration attrs)."""

    eiger.read_attrs = [
        "file",
        # 'stats1', 'stats2', 'stats3', 'stats4', 'stats5',
    ]
    # for stats in [eiger.stats1, eiger.stats2, eiger.stats3,
    #               eiger.stats4, eiger.stats5]:
    #     stats.read_attrs = ['total']
    eiger.file.read_attrs = []
    eiger.cam.read_attrs = []
