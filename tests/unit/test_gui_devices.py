from sonus.gui.devices import parse_bluetoothctl_devices


def test_parse_bluetoothctl_devices_handles_names_and_deduplicates():
    output = """\
Device 58:18:62:1F:C9:CB WH-1000XM6
Device 11:22:33:44:55:66 Living Room TV
Device 58:18:62:1F:C9:CB WH-1000XM6
garbage line
"""

    assert parse_bluetoothctl_devices(output) == [
        {"mac": "58:18:62:1F:C9:CB", "name": "WH-1000XM6", "channel": 9},
        {"mac": "11:22:33:44:55:66", "name": "Living Room TV", "channel": 9},
    ]


def test_parse_bluetoothctl_devices_ignores_invalid_addresses():
    assert parse_bluetoothctl_devices("Device not-a-mac Something\n") == []
