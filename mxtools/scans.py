import logging

import bluesky.plan_stubs as bps

logger = logging.getLogger(__name__)


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


def setup_eiger_exposure(eiger, exposure_time, exposure_period):
    yield from bps.mv(eiger.cam.acquire_time(exposure_time))
    yield from bps.mv(eiger.cam.acquire_period(exposure_period))


def setup_eiger_triggers(eiger, mode, num_triggers, exposure_per_image):
    yield from bps.mv(eiger.cam.trigger_mode, mode)
    yield from bps.mv(eiger.cam.num_triggers, num_triggers)
    yield from bps.mv(eiger.cam.trigger_exposure, exposure_per_image)


def setup_eiger_stop_acquire_and_wait(eiger):
    yield from bps.mv(eiger.cam.acquire, 0)
    # wait until Acquire_RBV is 0


# NOTE: BELOW IS NOW OBSOLETE BUT KEPT FOR ARCHIVAL DOCUMENTATION
# use it as follows:
# RE(setup_eiger_arming(eiger_single, 0, 100, 10, 0.01, 'test20210729',\
#    '/GPFS/CENTRAL/xf17id2/mfuchs/fmxoperator/20200222/mx999999-1665/', 2851, 2002.125, 2245.850, 0.9793, 0.250))
# RE(actual_scan(mx_flyer, eiger_single, vector, zebra, 0, 100, 0.2, 0.01))
# and it should all work - but doesn't at the moment (Eiger not getting triggered)
