from construct import Struct, Int8ul, Int16ul, Int32ul, Bytes, Padding, GreedyBytes

PARTIAL_METADATA_LAYOUT = Struct(
    "key" / Int8ul,
    "update_authority" / Bytes(32),
    "mint" / Bytes(32),
    # No 4-byte padding; remove it unless you know exactly what it is
    "name_length" / Int32ul,
    "name" / Bytes(lambda ctx: ctx.name_length),
    "symbol_length" / Int32ul,
    "symbol" / Bytes(lambda ctx: ctx.symbol_length),
    "uri_length" / Int32ul,
    "uri" / Bytes(lambda ctx: ctx.uri_length),
    # Then a u16 (seller_fee_basis_points) if you want
    "seller_fee_basis_points" / Int16ul,
    # We will not parse creators, etc. here
    "remaining" / GreedyBytes,
)


def parse_metaplex(raw_data: bytes):
    if raw_data[0] != 4:
        print(f"Unexpected metadata account key: {raw_data[0]}")
        return None

    metadata = PARTIAL_METADATA_LAYOUT.parse(raw_data)

    return {
        "name": metadata.name.decode("utf-8", errors="replace").rstrip('\x00'),
        "symbol": metadata.symbol.decode("utf-8", errors="replace").rstrip('\x00'),
        "uri": metadata.uri.decode("utf-8", errors="replace").rstrip('\x00')
    }

if __name__ == "__main__":
  hex = "0406c5c1ce638d2567d26468b05eb951d1a28dcc6e123482b5c675149770e62bf25d79a019c2a72733d48b1bbc7ecf5808b10a4c3dd8e124130ef46034845bbccf200000004449434b20434f494e00000000000000000000000000000000000000000000000a0000004449434b434f494e0000c800000068747470733a2f2f697066732e696f2f697066732f516d54594778424c735562314d537948686b5572615844625a4a4362704c6d6b775a575241537362613472724a4500000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001fd0102000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
  raw_metadata = bytes.fromhex(hex)

  parsed_metadata = parse_metaplex(raw_metadata)
  print(hex)
  print("Name:", parsed_metadata["name"])
  print("Symbol:", parsed_metadata["symbol"])
  print("URI:", parsed_metadata["uri"])

