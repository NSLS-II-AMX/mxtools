import datetime
import time as ttime  # tea time
from collections import OrderedDict
from pathlib import PurePath
from types import SimpleNamespace

from bluesky.plan_stubs import (close_run, open_run, pause, stage,
                                trigger_and_read, unstage)
from nslsii.ad33 import CamV33Mixin, SingleTriggerV33, StatsPluginV33
from ophyd import AreaDetector
from ophyd import Component as Cpt
from ophyd import (DetectorBase, Device, DeviceStatus, EpicsPathSignal,
                   EpicsSignal, EpicsSignalRO, HDF5Plugin, ImagePlugin,
                   OverlayPlugin, ProcessPlugin, ProsilicaDetector,
                   ProsilicaDetectorCam, ROIPlugin, Signal, SingleTrigger,
                   StatsPlugin, TIFFPlugin, TransformPlugin)
from ophyd.areadetector import EigerDetector
from ophyd.areadetector.base import ADComponent, EpicsSignalWithRBV
from ophyd.areadetector.cam import AreaDetectorCam, EigerDetectorCam
from ophyd.areadetector.filestore_mixins import (FileStoreBase,
                                                 FileStoreHDF5IterativeWrite,
                                                 FileStoreIterativeWrite,
                                                 FileStoreTIFFIterativeWrite,
                                                 new_short_uid)
from ophyd.device import Staged
from ophyd.status import StatusBase
from ophyd.utils import set_and_wait


class EigerSimulatedFilePlugin(Device, FileStoreBase):
    sequence_id = ADComponent(EpicsSignalRO, 'SequenceId')
    file_path = ADComponent(EpicsPathSignal, 'FilePath', string=True,
                            path_semantics='posix')
    file_write_name_pattern = ADComponent(EpicsSignalWithRBV, 'FWNamePattern',
                                          string=True)
    file_write_images_per_file = ADComponent(EpicsSignalWithRBV,
                                             'FWNImagesPerFile')
    current_run_start_uid = Cpt(Signal, value='', add_prefix=())
    enable = SimpleNamespace(get=lambda: True)

    def __init__(self, *args, **kwargs):
        self.sequence_id_offset = 1
        # This is changed for when a datum is a slice
        # also used by ophyd
        self.filestore_spec = "AD_EIGER2"
        self.frame_num = None
        super().__init__(*args, **kwargs)
        self._datum_kwargs_map = dict()  # store kwargs for each uid

    def stage(self):
        res_uid = new_short_uid()
        write_path = datetime.datetime.now().strftime(self.write_path_template)
        set_and_wait(self.file_path, f'{write_path}/')
        set_and_wait(self.file_write_name_pattern, '{}_$id'.format(res_uid))
        super().stage()
        fn = (PurePath(self.file_path.get()) / res_uid)
        ipf = int(self.file_write_images_per_file.get())
        # logger.debug("Inserting resource with filename %s", fn)
        self._fn = fn
        res_kwargs = {'images_per_file' : ipf}
        self._generate_resource(res_kwargs)

    def generate_datum(self, key, timestamp, datum_kwargs):
        # The detector keeps its own counter which is uses label HDF5
        # sub-files.  We access that counter via the sequence_id
        # signal and stash it in the datum.
        seq_id = int(self.sequence_id_offset) + int(self.sequence_id.get())  # det writes to the NEXT one
        datum_kwargs.update({'seq_id': seq_id})
        if self.frame_num is not None:
            datum_kwargs.update({'frame_num': self.frame_num})
        return super().generate_datum(key, timestamp, datum_kwargs)


class EigerDetectorCamV33(EigerDetectorCam):
    '''This is used to update the Eiger detector to AD33.
    '''
    wait_for_plugins = Cpt(EpicsSignal, 'WaitForPlugins',
                           string=True, kind='config')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs['wait_for_plugins'] = 'Yes'

    def ensure_nonblocking(self):
        self.stage_sigs['wait_for_plugins'] = 'Yes'
        for c in self.parent.component_names:
            cpt = getattr(self.parent, c)
            if cpt is self:
                continue
            if hasattr(cpt, 'ensure_nonblocking'):
                cpt.ensure_nonblocking()


class EigerBaseV26(EigerDetector):
    # cam = Cpt(EigerDetectorCamV33, 'cam1:')
    file = Cpt(EigerSimulatedFilePlugin, suffix='cam1:',
               write_path_template='/GPFS/CENTRAL/xf17id2/mfuchs/fmxoperator/20200222/mx999999-1665/',
               root='/GPFS/CENTRAL/xf17id2')
    image = Cpt(ImagePlugin, 'image1:')
    # stats1 = Cpt(StatsPluginV33, 'Stats1:')
    # stats2 = Cpt(StatsPluginV33, 'Stats2:')
    # stats3 = Cpt(StatsPluginV33, 'Stats3:')
    # stats4 = Cpt(StatsPluginV33, 'Stats4:')
    # stats5 = Cpt(StatsPluginV33, 'Stats5:')
    # roi1 = Cpt(ROIPlugin, 'ROI1:')
    # roi2 = Cpt(ROIPlugin, 'ROI2:')
    # roi3 = Cpt(ROIPlugin, 'ROI3:')
    # roi4 = Cpt(ROIPlugin, 'ROI4:')
    # proc1 = Cpt(ProcessPlugin, 'Proc1:')

    # hotfix: shadow non-existant PV
    size_link = None

    def stage(self, *args, **kwargs):
        # before parent
        ret = super().stage(*args, **kwargs)
        # after parent
        set_and_wait(self.cam.manual_trigger, 1)
        return ret

    def unstage(self):
        set_and_wait(self.cam.manual_trigger, 0)
        super().unstage()


class EigerSingleTriggerV26(SingleTrigger, EigerBaseV26):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs['cam.trigger_mode'] = 0
        # self.stage_sigs['shutter_mode'] = 1  # 'EPICS PV'
        self.stage_sigs.update({'cam.num_triggers': 1,
                                'cam.compression_algo': 'BS LZ4'})

    def stage(self, *args, **kwargs):
        return super().stage(*args, **kwargs)

    def trigger(self, *args, **kwargs):
        status = super().trigger(*args, **kwargs)
        set_and_wait(self.cam.special_trigger_button, 1)
        return status

    def read(self, *args, streaming=False, **kwargs):
        '''
            This is a test of using streaming read.
            Ideally, this should be handled by a new _stream_attrs property.
            For now, we just check for a streaming key in read and
            call super() if False, or read the one key we know we should read
            if True.

            Parameters
            ----------
            streaming : bool, optional
                whether to read streaming attrs or not
        '''
        if streaming:
            key = self._image_name  # this comes from the SingleTrigger mixin
            read_dict = super().read()
            ret = OrderedDict({key: read_dict[key]})
            return ret
        else:
            ret = super().read(*args, **kwargs)
            return ret

    def describe(self, *args, streaming=False, **kwargs):
        '''
            This is a test of using streaming read.
            Ideally, this should be handled by a new _stream_attrs property.
            For now, we just check for a streaming key in read and
            call super() if False, or read the one key we know we should read
            if True.

            Parameters
            ----------
            streaming : bool, optional
                whether to read streaming attrs or not
        '''
        if streaming:
            key = self._image_name  # this comes from the SingleTrigger mixin
            read_dict = super().describe()
            ret = OrderedDict({key: read_dict[key]})
            return ret
        else:
            ret = super().describe(*args, **kwargs)
            return ret


class FastShutterTrigger(Device):
    """This represents the fast trigger *device*.

    See below, FastTriggerMixin, which defines the trigging logic.
    """
    auto_shutter_mode = Cpt(EpicsSignal, 'Mode-Sts', write_pv='Mode-Cmd')
    num_images = Cpt(EpicsSignal, 'NumImages-SP')
    exposure_time = Cpt(EpicsSignal, 'ExposureTime-SP')
    acquire_period = Cpt(EpicsSignal, 'AcquirePeriod-SP')
    acquire = Cpt(EpicsSignal, 'Acquire-Cmd', trigger_value=1)


class EigerFastTriggerV26(EigerBaseV26):
    tr = Cpt(FastShutterTrigger, '')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stage_sigs['cam.trigger_mode'] = 3  # 'External Enable' mode
        # self.stage_sigs['shutter_mode'] = 0  # 'EPICS PV'
        # self.stage_sigs['tr.auto_shutter_mode'] = 1  # 'Enable'

    def trigger(self):
        self.dispatch('image', ttime.time())
        return self.tr.trigger()
# 
# 
# class EigerManualTrigger(SingleTrigger, EigerBase):
#     '''
#         Like Eiger Single Trigger but the triggering is done through the
#         special trigger button.
#     '''
#     def __init__(self, *args, **kwargs):
#         self._set_st = None
#         super().__init__(*args, **kwargs)
#         # in this case, we don't need this + 1 sequence id cludge
#         # this is because we write datum after image is acquired
#         self.file.sequence_id_offset = 0
#         self.file.filestore_spec = "AD_EIGER_SLICE"
#         self.file.frame_num = 0
#         # set up order
#         self.stage_sigs = OrderedDict()
#         self.stage_sigs['cam.image_mode'] = 1
#         self.stage_sigs['cam.trigger_mode'] = 0
#         self.stage_sigs['shutter_mode'] = 1
#         self.stage_sigs['manual_trigger'] = 1
#         #self.stage_sigs['cam.acquire'] = 1
#         self.stage_sigs['num_triggers'] = 10
# 
#         # monkey patch
#         # override with special trigger button, not acquire
#         #self._acquisition_signal = self.special_trigger_button
# 
#     def stage(self):
#         self.file.frame_num = 0
#         super().stage()
#         # for some reason if doing this too fast in staging
#         # this gets reset. so I do it here instead.
#         # the bit gets unset when done but we should unset again in unstage
#         time.sleep(1)
#         self.cam.acquire.put(1)
#         # need another sleep to ensure the sequence ID is updated
#         time.sleep(1)
# 
#     def unstage(self):
#         self.file.frame_num = 0
#         super().unstage()
#         time.sleep(.1)
#         self.cam.acquire.put(0)
# 
# 
#     def trigger(self):
#         ''' custom trigger for Eiger Manual'''
#         if self._staged != Staged.yes:
#             raise RuntimeError("This detector is not ready to trigger."
#                                "Call the stage() method before triggering.")
# 
#         if self._set_st is not None:
#             raise RuntimeError(f'trying to set {self.name}'
#                                ' while a set is in progress')
# 
#         st = StatusBase()
#         # idea : look at the array counter and the trigger value
#         # the logic here is that I want to check when the status is back to zero
#         def counter_cb(value, timestamp, **kwargs):
#             # whenevr it counts just move on
#             #print("changed : {}".format(value))
#             self._set_st = None
#             self.cam.array_counter.clear_sub(counter_cb)
#             st._finished()
# 
# 
#         # first subscribe a callback
#         self.cam.array_counter.subscribe(counter_cb, run=False)
# 
#         # then call trigger on the PV
#         self.special_trigger_button.put(1, wait=False)
#         self.dispatch(self._image_name, ttime.time())
#         self.file.frame_num += 1
# 
#         return st

# test_trig4M = FastShutterTrigger('XF:11IDB-ES{Trigger:Eig4M}', name='test_trig4M')


def set_eiger_defaults(eiger):
    """Choose which attributes to read per-step (read_attrs) or
    per-run (configuration attrs)."""

    eiger.read_attrs = ['file', 
                        # 'stats1', 'stats2', 'stats3', 'stats4', 'stats5',
                        ]
    # for stats in [eiger.stats1, eiger.stats2, eiger.stats3,
    #               eiger.stats4, eiger.stats5]:
    #     stats.read_attrs = ['total']
    eiger.file.read_attrs = []
    eiger.cam.read_attrs = []


# Eiger 1M using internal trigger
eiger_single = EigerSingleTriggerV26('XF:17IDC-ES:FMX{Det:Eig16M}',
                                       name='eiger_single')
# TODO: uncomment for V33
# eiger_single.cam.ensure_nonblocking()
set_eiger_defaults(eiger_single)

# Eiger 1M using fast trigger assembly
eiger = EigerFastTriggerV26('XF:17IDC-ES:FMX{Det:Eig16M}', name='eiger')
# TODO: uncomment for V33
# eiger.cam.ensure_nonblocking()
set_eiger_defaults(eiger)

# eiger4m_manual = EigerManualTrigger('XF:11IDB-ES{Det:Eig4M}', name='eiger4m_single')
# set_eiger_defaults(eiger4m_manual)


def dscan_manual(dets, motor, start, stop, num):
    for det in dets:
        det.stage_sigs.update({'num_triggers': num})

    yield from dscan(dets, motor, start, stop, num)


def manual_count(det=eiger_single):
    detectors = [det]
    for det in detectors:
        yield from stage(det)
        yield from open_run()
        print("All slow setup code has been run. "
              "Type RE.resume() when ready to acquire.")
        yield from pause()
        yield from trigger_and_read(detectors)
        yield from close_run()
        for det in detectors:
            yield from unstage(det)


# from eiger_io.fs_handler import EigerHandler
# db.reg.register_handler('AD_EIGER2', EigerHandler, overwrite=True)
