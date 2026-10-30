#!/usr/bin/env python3
"""Checked SELF/ELF serialization helpers for the exact supplied executable.
Only container/branch utilities; see build_vpk.py for the v3 changes.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import zipfile
import zlib

ORIGINAL_EBOOT_SHA256 = 'ffae9cef5b2819570ae95ca4fc5c9663879f8de0b0ef14d2f1a22925928ad24b'
CODE_BASE, DATA_BASE = 0x81000000, 0x81320000
H = struct.Struct('<IIHHI14Q')
E = struct.Struct('<16sHHIIIIIHHHHHH')
P = struct.Struct('<8I')
S = struct.Struct('<4Q')
H_NAMES = ('magic version sdk_type header_type metadata_offset header_len '
           'elf_filesize self_filesize unknown self_offset appinfo_offset '
           'elf_offset phdr_offset shdr_offset section_info_offset '
           'sceversion_offset controlinfo_offset controlinfo_size padding').split()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def align(value: int, boundary: int) -> int:
    return (value + boundary - 1) & ~(boundary - 1)


def encode_bl(site: int, target: int) -> bytes:
    delta = target - (site + 4)
    require(delta % 2 == 0 and -(1 << 24) <= delta < (1 << 24), 'BL target out of range')
    sign = (delta >> 24) & 1
    i1, i2 = (delta >> 23) & 1, (delta >> 22) & 1
    j1, j2 = ((~i1) ^ sign) & 1, ((~i2) ^ sign) & 1
    first = 0xF000 | (sign << 10) | ((delta >> 12) & 0x3FF)
    second = 0xD000 | (j1 << 13) | (j2 << 11) | ((delta >> 1) & 0x7FF)
    return struct.pack('<HH', first, second)


def decode_bl(site: int, instruction: bytes) -> int:
    first, second = struct.unpack('<HH', instruction)
    sign = (first >> 10) & 1
    i1 = (~((second >> 13) & 1) ^ sign) & 1
    i2 = (~((second >> 11) & 1) ^ sign) & 1
    delta = ((sign << 24) | (i1 << 23) | (i2 << 22) |
             ((first & 0x3FF) << 12) | ((second & 0x7FF) << 1))
    if sign:
        delta -= 1 << 25
    return site + 4 + delta


def parse_self(blob: bytes):
    require(len(blob) >= 4096, 'Input is too small for this SELF layout')
    header = dict(zip(H_NAMES, H.unpack_from(blob)))
    require(header['magic'] == 0x454353 and header['version'] == 3, 'Not a supported SELF')
    require(header['self_filesize'] == len(blob), 'SELF length field mismatch')
    elf = list(E.unpack_from(blob, header['elf_offset']))
    require(elf[0][:7] == b'\x7fELF\x01\x01\x01', 'Not little-endian ELF32')
    require(elf[1] == 0xFE04 and elf[2] == 40 and elf[10] == 3, 'Unsupported ELF/segment layout')
    phdrs, segments = [], []
    for i in range(elf[10]):
        ph = list(P.unpack_from(blob, header['phdr_offset'] + i * P.size))
        offset, length, compression, encryption = S.unpack_from(blob, header['section_info_offset'] + i * S.size)
        require(encryption == 2 and offset + length <= len(blob), 'Encrypted/truncated segment')
        packed = blob[offset:offset + length]
        require(compression in (1, 2), 'Unknown compression')
        raw = zlib.decompress(packed) if compression == 2 else packed
        require(len(raw) == ph[4], 'Decompressed segment length mismatch')
        phdrs.append(ph)
        segments.append(raw)
    require([p[0] for p in phdrs] == [1, 1, 0x60000000], 'Unexpected segment types')
    require(phdrs[0][2] == CODE_BASE and phdrs[1][2] == DATA_BASE, 'Unexpected load addresses')
    return header, elf, phdrs, segments


def plain_elf(elf: list, phdrs: list, segments: list[bytes]) -> bytes:
    require(elf[5] == 52 and elf[9] == 32, 'Unexpected ELF header dimensions')
    output = bytearray(max(ph[1] + len(seg) for ph, seg in zip(phdrs, segments)))
    output[:E.size] = E.pack(*elf)
    for i, (ph, seg) in enumerate(zip(phdrs, segments)):
        P.pack_into(output, elf[5] + i * P.size, *ph)
        output[ph[1]:ph[1] + len(seg)] = seg
    return bytes(output)


def wrap_self(original: bytes, header: dict, elf: list, phdrs: list, segments: list[bytes]):
    # Build a coherent stripped ELF file and retain the original load addresses.
    elf = elf.copy()
    elf[6], elf[11], elf[12], elf[13] = 0, 0, 0, 0
    cursor = 0x1000
    for ph, seg in zip(phdrs, segments):
        cursor = align(cursor, ph[7])
        ph[1], ph[4] = cursor, len(seg)
        cursor += len(seg)
    raw_elf = plain_elf(elf, phdrs, segments)
    output = bytearray(original[:header['header_len']])
    E.pack_into(output, header['elf_offset'], *elf)
    for i, ph in enumerate(phdrs):
        P.pack_into(output, header['phdr_offset'] + i * P.size, *ph)
    # Keep application permissions, firmware, module ID, and memory-budget fields.
    control = header['controlinfo_offset']
    control_end = control + header['controlinfo_size']
    digest_written = False
    while control < control_end:
        typ, size, _, _ = struct.unpack_from('<4I', output, control)
        require(size >= 16 and control + size <= control_end, 'Invalid control-info record')
        if typ == 4:
            require(size >= 68, 'Invalid digest record')
            output[control + 36:control + 68] = hashlib.sha256(raw_elf).digest()
            digest_written = True
        control += size
    require(digest_written, 'No SELF digest record')
    for i, seg in enumerate(segments):
        output += b'\0' * (align(len(output), 16) - len(output))
        offset = len(output)
        packed = zlib.compress(seg, level=9)
        packed += b'\0' * (align(len(packed), 4) - len(packed))
        output += packed
        S.pack_into(output, header['section_info_offset'] + i * S.size, offset, len(packed), 2, 2)
    header = header.copy()
    header['elf_filesize'], header['self_filesize'] = len(raw_elf), len(output)
    H.pack_into(output, 0, *(header[n] for n in H_NAMES))
    return bytes(output), raw_elf


