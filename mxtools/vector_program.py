from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, EpicsSignalRO


class VectorProgramStart(Device):
    omega = Cpt(EpicsSignal, "Pos:OStart-SP")
    x = Cpt(EpicsSignal, "Pos:XStart-SP")
    y = Cpt(EpicsSignal, "Pos:YStart-SP")
    z = Cpt(EpicsSignal, "Pos:ZStart-SP")


class VectorProgramEnd(Device):
    omega = Cpt(EpicsSignal, "Pos:OEnd-SP")
    x = Cpt(EpicsSignal, "Pos:XEnd-SP")
    y = Cpt(EpicsSignal, "Pos:YEnd-SP")
    z = Cpt(EpicsSignal, "Pos:ZEnd-SP")


class VectorProgram(Device):
    start = Cpt(VectorProgramStart, "")
    end = Cpt(VectorProgramEnd, "")

    abort = Cpt(EpicsSignal, "Cmd:Abort-Cmd", kind="omitted")
    go = Cpt(EpicsSignal, "Cmd:Go-Cmd", kind="omitted")
    proceed = Cpt(EpicsSignal, "Cmd:Proceed-Cmd", kind="omitted")
    sync = Cpt(EpicsSignal, "Cmd:Sync-Cmd", kind="omitted")

    expose = Cpt(EpicsSignal, "Expose-Sel")
    hold = Cpt(EpicsSignal, "Hold-Sel")

    buffer_time = Cpt(EpicsSignal, "Val:BufferTime-SP")
    frame_exptime = Cpt(EpicsSignal, "Val:Exposure-SP")
    num_frames = Cpt(EpicsSignal, "Val:NumSamples-SP")

    active = Cpt(EpicsSignalRO, "Sts:Running-Sts")
    state = Cpt(EpicsSignalRO, "Sts:State-Sts")
