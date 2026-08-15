import pytest

from sonus.transport.sdp import (
    SdpLookupError,
    build_service_search_attribute_request,
    parse_rfcomm_channel,
)

SERVICE_UUID = "956c7b26-d49a-4ba8-b03f-b17d393cb6e2"


def test_build_request_starts_with_service_search_attribute_pdu_id():
    request = build_service_search_attribute_request(SERVICE_UUID, transaction_id=0x1234)
    # PDU ID 0x06 = SDP_ServiceSearchAttributeRequest
    assert request[0] == 0x06
    # Transaction ID is the next 2 bytes, big-endian
    assert request[1:3] == b"\x12\x34"


def test_build_request_embeds_the_128_bit_uuid_bytes():
    request = build_service_search_attribute_request(SERVICE_UUID)
    uuid_bytes = bytes.fromhex(SERVICE_UUID.replace("-", ""))
    assert uuid_bytes in request


def test_parse_rfcomm_channel_extracts_channel_from_protocol_descriptor_list():
    # Hand-built synthetic SDP_ServiceSearchAttributeResponse per the public
    # SDP wire format: PDU header + attribute list containing a
    # ProtocolDescriptorList (attribute ID 0x0004) whose second protocol
    # entry is RFCOMM (UUID 0x0003) with a single uint8 channel parameter.
    #
    # DES(ProtocolDescriptorList) = [
    #   DES[ UUID(0x0100) L2CAP ],
    #   DES[ UUID(0x0003) RFCOMM, uint8 channel=8 ],
    # ]
    l2cap_proto = bytes([0x35, 0x03, 0x19, 0x01, 0x00])  # DES(3) { UUID16 0x0100 }
    rfcomm_proto = bytes([0x35, 0x05, 0x19, 0x00, 0x03, 0x08, 0x08])  # DES(5) { UUID16 0x0003, uint8 8 }
    protocol_descriptor_list = bytes([0x35, len(l2cap_proto) + len(rfcomm_proto)]) + l2cap_proto + rfcomm_proto

    attr_id = bytes([0x09, 0x00, 0x04])  # uint16 attribute ID 0x0004
    attribute_list = bytes([0x35, len(attr_id) + len(protocol_descriptor_list)]) + attr_id + protocol_descriptor_list

    # SDP_ServiceSearchAttributeResponse: PDU ID(1) + TxId(2) + ParamLen(2)
    # + AttributeListByteCount(2) + AttributeList + ContinuationState(1, 0=none)
    body = len(attribute_list).to_bytes(2, "big") + attribute_list + bytes([0x00])
    response = bytes([0x07]) + bytes([0x12, 0x34]) + len(body).to_bytes(2, "big") + body

    assert parse_rfcomm_channel(response) == 8


def test_parse_rfcomm_channel_accepts_real_xm6_two_byte_des_lengths():
    # Captured from the paired WH-1000XM6 (58:18:62:1F:C9:CB). BlueZ's SDP
    # response wraps the service record in an outer sequence and uses 16-bit
    # sequence lengths (DES type 0x36) for both wrappers.
    response = bytes.fromhex(
        "070000001a0017360014360011090004350c35031901003505190003080900"
    )

    assert parse_rfcomm_channel(response) == 9


def test_parse_rfcomm_channel_raises_when_rfcomm_not_present():
    # L2CAP-only protocol descriptor (no RFCOMM)
    l2cap_only = bytes([0x35, 0x03, 0x19, 0x01, 0x00])
    protocol_descriptor_list = bytes([0x35, len(l2cap_only)]) + l2cap_only
    attr_id = bytes([0x09, 0x00, 0x04])
    attribute_list = bytes([0x35, len(attr_id) + len(protocol_descriptor_list)]) + attr_id + protocol_descriptor_list
    body = len(attribute_list).to_bytes(2, "big") + attribute_list + bytes([0x00])
    response = bytes([0x07]) + bytes([0x00, 0x00]) + len(body).to_bytes(2, "big") + body

    with pytest.raises(SdpLookupError):
        parse_rfcomm_channel(response)
