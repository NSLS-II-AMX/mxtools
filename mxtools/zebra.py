import time as ttime

from ophyd import Component as Cpt
from ophyd import Device, EpicsSignal, EpicsSignalRO
from ophyd.signal import Signal
from ophyd.status import DeviceStatus


class ZebraPCBase(Device):
    sel = Cpt(EpicsSignal, "SEL", kind="config", auto_monitor=True)
    start = Cpt(EpicsSignal, "START", kind="config", auto_monitor=True)
    width = Cpt(EpicsSignal, "WID", kind="config", auto_monitor=True)
    step = Cpt(EpicsSignal, "STEP", kind="config", auto_monitor=True)


class ZebraPCGate(ZebraPCBase):
    num_gates = Cpt(EpicsSignal, "NGATE", kind="config", auto_monitor=True)


class ZebraPCPulse(ZebraPCBase):
    max = Cpt(EpicsSignal, "MAX", kind="config", auto_monitor=True)
    delay = Cpt(EpicsSignal, "DLY", kind="config", auto_monitor=True)
    # status = Cpt(EpicsSignalRO, "INP.STA", kind="omitted")


class ZebraPCArm(Device):
    trig_source = Cpt(
        EpicsSignal,
        write_pv="SEL",
        read_pv="SEL:RBV",
        kind="omitted",
        auto_monitor=True,
        add_prefix=("write_pv", "read_pv"),
        doc="Example: XF:17IDC-ES:FMX{Zeb:3}:PC_ARM_SEL",
    )
    arm_status = Cpt(
        EpicsSignalRO,
        "INP:STA",
        kind="omitted",
        auto_monitor=True,
        doc="Example: XF:17IDC-ES:FMX{Zeb:3}:PC_ARM_INP:STA",
    )
    output = Cpt(EpicsSignalRO, "OUT", kind="omitted", auto_monitor=True)
    # This is handled by vector.go(...), so we don't need the 'arm' component.
    # arm = Cpt(EpicsSignal, "", kind="normal", auto_monitor=True)
    # Example: XF:17IDC-ES:FMX{Zeb:3}:PC_ARM_INP:STA


class ZebraPositionCaptureData(Device):
    num_captured = Cpt(EpicsSignalRO, "NUM_CAP", kind="normal")
    num_downloaded = Cpt(EpicsSignalRO, "NUM_DOWN", kind="normal")

    time = Cpt(EpicsSignalRO, "TIME", kind="normal")

    enc1 = Cpt(EpicsSignalRO, "ENC1", kind="omitted")
    enc2 = Cpt(EpicsSignalRO, "ENC2", kind="omitted")
    enc3 = Cpt(EpicsSignalRO, "ENC3", kind="omitted")
    enc4 = Cpt(EpicsSignalRO, "ENC4", kind="normal")

    sys1 = Cpt(EpicsSignalRO, "SYS1", kind="omitted")
    sys2 = Cpt(EpicsSignalRO, "SYS2", kind="omitted")

    div1 = Cpt(EpicsSignalRO, "DIV1", kind="omitted")
    div2 = Cpt(EpicsSignalRO, "DIV2", kind="omitted")
    div3 = Cpt(EpicsSignalRO, "DIV3", kind="omitted")
    div4 = Cpt(EpicsSignalRO, "DIV4", kind="omitted")


class ZebraPositionCompare(Device):
    arm = Cpt(ZebraPCArm, "ARM_", kind="omitted")
    # arm_status = Cpt(EpicsSignalRO, "ARM_INP.STA", kind="omitted")
    # arm_sel = Cpt(EpicsSignal, "ARM_SEL", kind="omitted")
    download_count = Cpt(EpicsSignalRO, "NUM_DOWN", kind="omitted")

    arm_signal = Cpt(EpicsSignal, "ARM", kind="omitted")
    disarm = Cpt(EpicsSignal, "DISARM", kind="omitted", doc="Example: XF:17IDC-ES:FMX{Zeb:3}:PC_DISARM")

    encoder = Cpt(EpicsSignal, "ENC", kind="config", auto_monitor=True)
    enc_x = Cpt(EpicsSignal, "ENC1", kind="omitted")
    enc_y = Cpt(EpicsSignal, "ENC2", kind="omitted")
    enc_z = Cpt(EpicsSignal, "ENC3", kind="omitted")
    enc_omega = Cpt(EpicsSignal, "ENC4", kind="omitted")
    direction = Cpt(EpicsSignal, "DIR", kind="config", auto_monitor=True)
    gate = Cpt(ZebraPCGate, "GATE_", kind="config")
    pulse = Cpt(ZebraPCPulse, "PULSE_")
    time = Cpt(EpicsSignalRO, "TIME", kind="omitted")
    data = Cpt(ZebraPositionCaptureData, "", kind="normal")


class ZebraAnd(Device):
    inp1 = Cpt(EpicsSignal, "INP1:STA", kind="omitted")
    inp2 = Cpt(EpicsSignal, "INP2:STA", kind="omitted")


class Zebra(Device):
    download_status = Cpt(EpicsSignalRO, "ARRAY_ACQ", kind="omitted")
    reset = Cpt(EpicsSignal, "SYS_RESET.PROC", kind="omitted")
    m1_set_pos = Cpt(EpicsSignal, "M1:SETPOS.PROC", kind="omitted")
    m2_set_pos = Cpt(EpicsSignal, "M2:SETPOS.PROC", kind="omitted")
    m3_set_pos = Cpt(EpicsSignal, "M3:SETPOS.PROC", kind="omitted")
    m4_set_pos = Cpt(EpicsSignal, "M4:SETPOS.PROC", kind="omitted")
    out1 = Cpt(EpicsSignal, "OUT1_TTL", kind="config", auto_monitor=True)
    pc = Cpt(ZebraPositionCompare, "PC_")
    and1 = Cpt(ZebraAnd, "AND1_")
    enc_of_interest = Cpt(Signal, value=[4], kind="config")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        formatted_to_be_normal = [f"{self.pc.data.name}_enc{num}" for num in self.enc_of_interest.get()]
        for cpt in self.pc.data.component_names:
            cpt_obj = getattr(self.pc.data, cpt)
            if "enc" in cpt:
                if cpt_obj.name in formatted_to_be_normal:
                    cpt_obj.kind = "normal"
                else:
                    cpt_obj.kind = "omitted"

    def kickoff(self):
        armed_status = DeviceStatus(self)
        self._disarmed_status = disarmed_status = DeviceStatus(self)

        pc = self.pc
        external = pc.arm.trig_source.get(as_string=True) == "External"  # Using external trigger?

        if external:
            armed_signal = pc.arm.arm_status
        else:
            armed_signal = pc.arm.output

        disarmed_signal = self.download_status

        self._collection_ts = ttime.time()

        def armed_status_cb(value, old_value, obj, **kwargs):
            if int(old_value) == 0 and int(value) == 1:
                armed_status._finished()
                obj.clear_sub(armed_status_cb)

        def disarmed_status_cb(value, old_value, obj, **kwargs):
            # I'm getting a stale 1 -> 0 update, so use timestamps to filter that out
            if int(old_value) == 1 and int(value) == 0:
                disarmed_status._finished()
                obj.clear_sub(disarmed_status_cb)

        armed_signal.subscribe(armed_status_cb, run=False)
        disarmed_signal.subscribe(disarmed_status_cb, run=False)

        # Arm it if not External
        if not external:
            self.pc.arm_signal.put(1)

        return armed_status

    def collect(self):
        pc = self.pc

        # Array of timestamps
        ts = pc.data.time.get() + self._collection_ts

        # Arrays of captured positions
        data = {
            f"enc{i}": getattr(pc.data, f"enc{i}").get()
            for i in self.enc_of_interest.get()
            if getattr(pc, f"capture_enc{i}").get()
        }

        for i, timestamp in enumerate(ts):
            yield {
                "data": {k: v[i] for k, v in data.items()},
                "timestamps": {k: timestamp for k in data.keys()},
                "time": timestamp,
            }

    def describe_collect(self):
        return {
            "primary": {
                f"enc{i}": {
                    "source": "PV:" + getattr(self.pc.data, f"enc{i}").pvname,
                    "shape": [],
                    "dtype": "number",
                }
                for i in self.enc_of_interest.get()
                if getattr(self.pc, f"capture_enc{i}").get()
            }
        }
