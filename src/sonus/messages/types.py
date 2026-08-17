from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from sonus.protocol.framing import DATA_TYPE_MDR


class Safety(str, Enum):
    READ_ONLY = "read_only"
    REVERSIBLE = "reversible"
    EXPERIMENTAL_READ = "experimental_read"


Decoder = Callable[[bytes], Any]
Encoder = Callable[[Any], bytes]


@dataclass(frozen=True)
class FeatureSpec:
    key: str
    label: str
    request: bytes
    response_command: int
    response_type: int
    decoder: Decoder
    safety: Safety = Safety.READ_ONLY
    data_type: int = DATA_TYPE_MDR
    function_id: int | None = None
    encoder: Encoder | None = None
    write_response_command: int | None = None
    write_response_type: int | None = None
    write_decoder: Decoder | None = None

    @property
    def writable(self) -> bool:
        return self.safety is Safety.REVERSIBLE and self.encoder is not None

    def matches_payload(self, payload: bytes) -> bool:
        return len(payload) >= 2 and payload[:2] == bytes(
            (self.response_command, self.response_type)
        )

    def decode(self, payload: bytes) -> Any:
        return self.decoder(payload)

    def matches_write_payload(self, payload: bytes) -> bool:
        if self.write_response_command is None or self.write_response_type is None:
            return False
        return len(payload) >= 2 and payload[:2] == bytes(
            (self.write_response_command, self.write_response_type)
        )

    def decode_write(self, payload: bytes) -> Any:
        if self.write_decoder is None:
            return self.decode(payload)
        return self.write_decoder(payload)
