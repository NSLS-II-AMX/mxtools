from ophyd import Device, Component as Cpt, EpicsSignal
import socket


class BeamlineCalibrations(Device):
    LoMagCal = Cpt(EpicsSignal, 'LoMagCal}')
    HiMagCal = Cpt(EpicsSignal, 'HiMagCal}')


class PuckSafety(Device):
    On = Cpt(EpicsSignal, 'On.PROC')
    Off = Cpt(EpicsSignal, 'Off.PROC')


def blStrGet():
    """
    Return beamline string

    blStr: 'AMX' or 'FMX'

    Beamline is determined by querying hostname
    """
    hostStr = socket.gethostname()
    if hostStr.startswith('xf17id2'):
        blStr = 'FMX'
    elif hostStr.startswith('xf17id1'):
        blStr = 'AMX'
    else:
        print('Error - this code must be executed on one of the -ca1 machines')
        blStr = -1

    return blStr


def get_energy(vdcm=None, hdcm=None):
    """
    Returns the current photon energy in eV derived from the DCM Bragg angle
    """
    blStr = blStrGet()
    if blStr == -1:
        return -1

    if blStr == 'AMX':
        energy = vdcm.e.user_readback.get()
    elif blStr == 'FMX':
        energy = hdcm.e.user_readback.get()

    return energy
