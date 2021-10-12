import datetime
from collections import OrderedDict
from pathlib import PurePath
from types import SimpleNamespace

from ophyd import Component as Cpt
from ophyd import Device, EpicsPathSignal, EpicsSignal, ImagePlugin, Signal, SingleTrigger
from ophyd.areadetector import EigerDetector
from ophyd.areadetector.base import ADComponent, EpicsSignalWithRBV
from ophyd.areadetector.filestore_mixins import FileStoreBase  # , new_short_uid
from ophyd.utils import set_and_wait

from . import print_now

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
        set_and_wait(self.file_path, f"{write_path}/")
        set_and_wait(self.file_write_name_pattern, "{}_$id".format(res_uid))
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
        write_path_template="/GPFS/CENTRAL/xf17id2/jaishima/",
        root="/GPFS/CENTRAL/xf17id2",
    )
    image = Cpt(ImagePlugin, "image1:")

    # hotfix: shadow non-existant PV
    size_link = None

    def stage(self, *args, **kwargs):
        # before parent
        ret = super().stage(*args, **kwargs)
        # after parent
        # set_and_wait(self.cam.manual_trigger, 1)
        return ret

    def unstage(self):
        # set_and_wait(self.cam.manual_trigger, 0)
        super().unstage()


class EigerSingleTriggerV26(SingleTrigger, EigerBaseV26):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.stage_sigs["cam.trigger_mode"] = 0 #original: single manual trigger
        self.stage_sigs["cam.trigger_mode"] = EXTERNAL_SERIES
        self.stage_sigs.pop("cam.acquire")  # remove acquire=0
        # self.stage_sigs['shutter_mode'] = 1  # 'EPICS PV'
        self.stage_sigs.update({"cam.num_triggers": 1, "cam.compression_algo": "BS LZ4"})

    def stage(self, *args, **kwargs):
        return super().stage(*args, **kwargs)

    def trigger(self, *args, **kwargs):
        status = super().trigger(*args, **kwargs)
        set_and_wait(self.cam.special_trigger_button, 1)
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
