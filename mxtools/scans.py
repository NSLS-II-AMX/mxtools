import getpass
import grp
import logging
import os
import time

import bluesky.plan_stubs as bps

from mxtools.eiger import EXTERNAL_SERIES

logger = logging.getLogger(__name__)


def zebra_daq_prep(zebra):
    yield from bps.mv(zebra.reset, 1)
    yield from bps.sleep(2.0)
    yield from bps.mv(zebra.out1, 31)
    yield from bps.mv(zebra.m1_set_pos, 1)
    yield from bps.mv(zebra.m2_set_pos, 1)
    yield from bps.mv(zebra.m3_set_pos, 1)
    yield from bps.mv(zebra.pc.arm.trig_source, 1)


def setup_zebra_vector_scan(
    zebra,
    angle_start,
    gate_width,
    scan_width,
    pulse_width,
    pulse_step,
    exposure_period_per_image,
    num_images,
    is_still=False,
):
    yield from bps.mv(zebra.pc.gate.start, angle_start)
    if is_still is False:
        yield from bps.mv(zebra.pc.gate.width, gate_width, zebra.pc.gate.step, scan_width)
    yield from bps.mv(zebra.pc.gate.num_gates, 1)
    yield from bps.mv(zebra.pc.pulse.start, 0)
    yield from bps.mv(zebra.pc.pulse.width, pulse_width)
    yield from bps.mv(zebra.pc.pulse.step, pulse_step)
    yield from bps.mv(zebra.pc.pulse.delay, exposure_period_per_image / 2 * 1000)
    yield from bps.mv(zebra.pc.pulse.max, num_images)


def setup_zebra_vector_scan_for_raster(
    zebra,
    angle_start,
    image_width,
    exposure_time_per_image,
    exposure_period_per_image,
    detector_dead_time,
    num_images,
    scan_encoder=3,
):
    yield from bps.mv(zebra.pc.encoder, scan_encoder)
    yield from bps.sleep(1.0)
    yield from bps.mv(zebra.pc.direction, 0, zebra.pc.gate.sel, 0)  # direction, 0 = positive
    yield from bps.mv(zebra.pc.gate.start, angle_start)
    if image_width != 0:
        yield from bps.mv(
            zebra.pc.gate.width,
            num_images * image_width,
            zebra.pc.gate.step,
            num_images * image_width + 0.01,
        )
    yield from bps.mv(
        zebra.pc.gate.num_gates,
        1,
        zebra.pc.pulse.sel,
        1,
        zebra.pc.pulse.start,
        0,
        zebra.pc.pulse.width,
        (exposure_time_per_image - detector_dead_time) * 1000,
        zebra.pc.pulse.step,
        exposure_period_per_image * 1000,
        zebra.pc.pulse.delay,
        exposure_period_per_image / 2 * 1000,
    )


def setup_vector_program(vector, num_images, angle_start, angle_end, exposure_period_per_image):
    yield from bps.mv(
        vector.num_frames,
        num_images,
        vector.start.omega,
        angle_start,
        vector.end.omega,
        angle_end,
        vector.frame_exptime,
        exposure_period_per_image * 1000.0,
    )
    yield from bps.mv(vector.hold, 0)


def setup_eiger_stop_acquire_and_wait(eiger):
    yield from bps.mv(eiger.cam.acquire, 0)
    # wait until Acquire_RBV is 0


# use it as follows:
# RE(setup_eiger_arming(eiger_single, 0, 100, 10, 0.01, 'test20210729',\
#    '/GPFS/CENTRAL/xf17id2/mfuchs/fmxoperator/20200222/mx999999-1665/', 2851, 2002.125, 2245.850, 0.9793, 0.250))
# RE(actual_scan(mx_flyer, eiger_single, vector, zebra, 0, 100, 0.2, 0.01))
# and it should all work - but doesn't at the moment (Eiger not getting triggered)
