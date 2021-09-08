import pathlib
import h5py
import dask.array as da
from area_detector_handlers import HandlerBase


class EigerHandlerMX(HandlerBase):
    spec = "AD_EIGER_MX"

    def __init__(self, fpath, seq_id):
        self._seq_id = seq_id
        # From https://github.com/bluesky/area-detector-handlers/blob/0f47155b31a6b4bf92c1c2b6fe98b5f141194c78/area_detector_handlers/eiger.py#L84
        #
        #         master_path = Path(f'{self._file_prefix}_{seq_id}_master.h5').absolute()
        #
        self._fpath = pathlib.Path(f"{fpath}_{seq_id}_master.h5").absolute()
        if not self._fpath.is_file():
            raise RuntimeError(f"File {self._fpath} does not exist")

        # print(f"Eiger master file: {self._fpath}")

    def __call__(self, data_key="data", **kwargs):
        self._file = h5py.File(self._fpath, "r")  # but make it cached

        if data_key == "data":
            temp = []
            group = self._file["entry"]["data"]
            for k in group:
                temp.append(da.from_array(group[k]))

            return da.stack(temp)

        elif data_key == "omega":
            return da.from_array(self._file["entry"]["sample"]["goniometer"][data_key])

        elif data_key == "bit_mask":
            ...
            # code to pull out bit mask
            raise NotImplementedError()

        elif data_key in self._file["entry"]["instrument"]:
            return da.from_array(self._file["entry"]["instrument"][data_key])

        else:
            raise RuntimeError("Unknown key")


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

# event = {...: ..., "data": {"eiger_img": "a", "omega": "b"}}
