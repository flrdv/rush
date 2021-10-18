from typing import Union


def make_sure_bytes_or_none(obj: Union[str, bytes]) -> Union[bytes, None]:
    if obj is None:
        return None

    return obj if isinstance(obj, bytes) else obj.encode()
