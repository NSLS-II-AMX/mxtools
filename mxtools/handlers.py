import logging
import pathlib

import dask.array as da
import h5py
from area_detector_handlers import HandlerBase

logger = logging.getLogger(__name__)


class EigerHandlerMX(HandlerBase):
    spec = "AD_EIGER_MX"

    def __init__(self, fpath, seq_id):
        self._seq_id = seq_id
        # From https://github.com/bluesky/area-detector-handlers/blob/0f47155b31a6b4bf92c1c2b6fe98b5f141194c78/area_detector_handlers/eiger.py#L84  # noqa
        #
        #         master_path = Path(f'{self._file_prefix}_{seq_id}_master.h5').absolute()
        #
        self._fpath = pathlib.Path(f"{fpath}_{seq_id}_master.h5").absolute()
        if not self._fpath.is_file():
            raise RuntimeError(f"File {self._fpath} does not exist")

        # print(f"Eiger master file: {self._fpath}")  # TODO make this a logging debug message

    def __call__(self, data_key="data", **kwargs):
        self._file = h5py.File(self._fpath, "r")  # but make it cached

        if data_key == "data":
            temp = []
            group = self._file["entry"]["data"]
            for i, k in enumerate(group):
                reta = da.from_array(group[k])
                logger.debug(f"{i} {reta.shape}")
                temp.append(reta)

            ret = da.stack(temp)
            newret = ret.reshape(-1, *ret.shape[-2:])
            logger.debug(f"{newret.shape}")
            return newret

        elif data_key == "omega":
            return da.from_array(self._file["entry"]["sample"]["goniometer"][data_key])

        elif data_key == "bit_mask":
            ...
            # code to pull out bit mask
            raise NotImplementedError()

        elif data_key in self._file["entry"]["instrument"]:
            return da.from_array(self._file["entry"]["instrument"][data_key])

        else:
            raise RuntimeError(f"Unknown key: {data_key}")
