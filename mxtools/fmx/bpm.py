from ophyd import Device, EpicsSignal, EpicsSignalRO, Component as Cpt

class Bpm(Device):
    x = Cpt(EpicsSignalRO, 'PosX:MeanValue_RBV')
    y = Cpt(EpicsSignalRO, 'PosY:MeanValue_RBV')
    a = Cpt(EpicsSignalRO, 'Current1:MeanValue_RBV')
    b = Cpt(EpicsSignalRO, 'Current2:MeanValue_RBV')
    c = Cpt(EpicsSignalRO, 'Current3:MeanValue_RBV')
    d = Cpt(EpicsSignalRO, 'Current4:MeanValue_RBV')
    sum_x = Cpt(EpicsSignalRO, 'SumX:MeanValue_RBV')
    sum_y = Cpt(EpicsSignalRO, 'SumY:MeanValue_RBV')
    sum_all = Cpt(EpicsSignalRO, 'SumAll:MeanValue_RBV')
    sum_all_precision = Cpt(EpicsSignal, 'SumAll:MeanValue_RBV.PREC')
