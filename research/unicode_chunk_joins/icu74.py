"""Minimal ICU4C binding for the pinned development environment (Linux)."""

import ctypes as c
import sys
from functools import lru_cache

lib = c.CDLL("libicuuc.so.74")
ptr = c.c_void_p
unit = c.c_uint16
integer = c.c_int32
flag = c.c_int8
pointer = c.POINTER
codec = "utf-16-le" if sys.byteorder == "little" else "utf-16-be"


def bind(name, result, *args):
    fn = getattr(lib, name + "_74")
    fn.argtypes = args
    fn.restype = result
    return fn


def version(name):
    buf = (c.c_uint8 * 4)()
    bind(name, None, pointer(c.c_uint8))(buf)
    return tuple(buf)


def check(status):
    if status.value > 0:
        raise RuntimeError(f"ICU error {status.value}")


if version("u_getVersion") != (74, 2, 0, 0) or version("u_getUnicodeVersion") != (15, 1, 0, 0):
    raise RuntimeError("This comparison requires ICU 74.2 with Unicode 15.1")

before = bind("unorm2_hasBoundaryBefore", flag, ptr, integer)
after = bind("unorm2_hasBoundaryAfter", flag, ptr, integer)
ccc = bind("u_getCombiningClass", c.c_uint8, integer)
_normalize = bind(
    "unorm2_normalize",
    integer,
    ptr,
    pointer(unit),
    integer,
    pointer(unit),
    integer,
    pointer(integer),
)
_is_normal = bind("unorm2_isNormalized", flag, ptr, pointer(unit), integer, pointer(integer))


@lru_cache
def instance(form):
    status = integer()
    value = bind(f"unorm2_get{form}Instance", ptr, pointer(integer))(c.byref(status))
    check(status)
    return value


def units(s):
    data = s.encode(codec)
    return (unit * (len(data) // 2)).from_buffer_copy(data)


@lru_cache(maxsize=32768)
def normalize(form, s):
    src = units(s)
    status = integer()
    required = _normalize(instance(form), src, len(src), None, 0, c.byref(status))
    if status.value != 15:  # U_BUFFER_OVERFLOW_ERROR is expected during preflight.
        check(status)
    dest = (unit * (required + 1))()
    status = integer()
    size = _normalize(instance(form), src, len(src), dest, len(dest), c.byref(status))
    check(status)
    return bytes(dest)[: 2 * size].decode(codec)


@lru_cache(maxsize=32768)
def is_normal(form, s):
    src = units(s)
    status = integer()
    result = _is_normal(instance(form), src, len(src), c.byref(status))
    check(status)
    return bool(result)
