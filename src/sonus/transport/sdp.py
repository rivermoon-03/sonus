"""Minimal SDP (Service Discovery Protocol) client.

Implements just enough of the Bluetooth Core Specification (Vol 3, Part B)
to resolve an RFCOMM channel number for a given 128-bit service UUID on a
remote device. This is a public, standardized protocol — not specific to
any vendor's implementation.
"""
from __future__ import annotations

import socket

_PDU_SERVICE_SEARCH_ATTRIBUTE_REQUEST = 0x06
_PDU_SERVICE_SEARCH_ATTRIBUTE_RESPONSE = 0x07
_DES_UINT8_LEN = 0x35  # Data Element Sequence, 1-byte length follows
_DES_UINT16_LEN = 0x36  # Data Element Sequence, 2-byte length follows
_UUID16_RFCOMM = 0x0003
_ATTR_PROTOCOL_DESCRIPTOR_LIST = 0x0004
_SDP_PSM = 0x0001


class SdpLookupError(Exception):
    """Raised when the SDP response does not contain an RFCOMM channel."""


def _encode_uuid128(service_uuid: str) -> bytes:
    return bytes.fromhex(service_uuid.replace("-", ""))


def build_service_search_attribute_request(
    service_uuid: str,
    transaction_id: int = 0,
    max_attribute_bytes: int = 512,
) -> bytes:
    uuid_bytes = _encode_uuid128(service_uuid)
    # ServiceSearchPattern: DES { UUID128 }
    service_search_pattern = bytes([0x1C]) + uuid_bytes  # 0x1C = UUID, 16-byte
    service_search_pattern = bytes([_DES_UINT8_LEN, len(service_search_pattern)]) + service_search_pattern

    # AttributeIDList: DES { uint16 attribute ID }
    attribute_id_list = bytes([0x09]) + _ATTR_PROTOCOL_DESCRIPTOR_LIST.to_bytes(2, "big")
    attribute_id_list = bytes([_DES_UINT8_LEN, len(attribute_id_list)]) + attribute_id_list

    params = (
        service_search_pattern
        + max_attribute_bytes.to_bytes(2, "big")
        + attribute_id_list
        + bytes([0x00])  # ContinuationState: none
    )

    return (
        bytes([_PDU_SERVICE_SEARCH_ATTRIBUTE_REQUEST])
        + transaction_id.to_bytes(2, "big")
        + len(params).to_bytes(2, "big")
        + params
    )


def _read_des_header(data: bytes, offset: int) -> tuple[int, int]:
    """Return (content_start_offset, content_length) for a DES at offset.

    Supports the 1-byte and 2-byte length encodings used by SDP responses.
    """
    if offset >= len(data):
        raise SdpLookupError(f"missing DES at offset {offset}")

    des_type = data[offset]
    if des_type == _DES_UINT8_LEN:
        content_start = offset + 2
    elif des_type == _DES_UINT16_LEN:
        content_start = offset + 3
    else:
        raise SdpLookupError(f"expected DES at offset {offset}, got {des_type:#x}")

    length_start = offset + 1
    if content_start > len(data):
        raise SdpLookupError(f"truncated DES length at offset {offset}")
    length = int.from_bytes(data[length_start:content_start], "big")
    if content_start + length > len(data):
        raise SdpLookupError(f"truncated DES content at offset {offset}")
    return content_start, length


def parse_rfcomm_channel(response: bytes) -> int:
    if not response or response[0] != _PDU_SERVICE_SEARCH_ATTRIBUTE_RESPONSE:
        raise SdpLookupError("not a ServiceSearchAttributeResponse")

    # 헤더 뒤의 속성 목록 길이는 응답 전체 길이와 별도로 주어진다.
    body = response[5:]
    attr_list_byte_count = int.from_bytes(body[0:2], "big")
    attribute_list = body[2 : 2 + attr_list_byte_count]

    # 실제 BlueZ 응답은 서비스 레코드를 DES로 한 번 더 감싸는 경우가 있다.
    offset, outer_len = _read_des_header(attribute_list, 0)
    attributes = attribute_list[offset : offset + outer_len]
    if attributes and attributes[0] in (_DES_UINT8_LEN, _DES_UINT16_LEN):
        record_start, record_len = _read_des_header(attributes, 0)
        attributes = attributes[record_start : record_start + record_len]

    # uint16 속성 ID는 자료형 표식 0x09 뒤에 2바이트 값이 온다.
    offset = 0
    if not attributes or attributes[offset] != 0x09:
        raise SdpLookupError("expected uint16 attribute ID")
    offset += 3

    # value is DES { protocol entries... }
    pdl_start, pdl_len = _read_des_header(attributes, offset)
    pdl = attributes[pdl_start : pdl_start + pdl_len]

    pos = 0
    while pos < len(pdl):
        entry_start, entry_len = _read_des_header(pdl, pos)
        entry = pdl[entry_start : entry_start + entry_len]
        pos = entry_start + entry_len

        # entry is UUID16(2 header bytes: 0x19 + 2-byte uuid) [+ uint8 param]
        if len(entry) >= 3 and entry[0] == 0x19:
            uuid16 = int.from_bytes(entry[1:3], "big")
            if uuid16 == _UUID16_RFCOMM and len(entry) >= 5 and entry[3] == 0x08:
                return entry[4]

    raise SdpLookupError("RFCOMM channel not found in ProtocolDescriptorList")


def find_rfcomm_channel(mac: str, service_uuid: str, timeout: float = 5.0) -> int:
    """Query the remote device's SDP server for the RFCOMM channel of service_uuid."""
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP)
    sock.settimeout(timeout)
    try:
        sock.connect((mac, _SDP_PSM))
        sock.send(build_service_search_attribute_request(service_uuid))
        response = sock.recv(4096)
    finally:
        sock.close()
    return parse_rfcomm_channel(response)
