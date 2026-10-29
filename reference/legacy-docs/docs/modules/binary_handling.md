# Binary Handling

**Package:** `xc_ce_utils.binary_handling`
**Purpose:** Low-level binary file manipulation for embedded firmware builds

## Overview

Provides format conversions, signing, CRC computation, padding, splitting, and cropping for binary firmware images. Supports Intel HEX, Motorola S-record, sparse images, and raw binary formats.

## Modules

| Module | Description |
|---|---|
| `bin_converter.py` | HEX/SREC/sparse â†’ BIN conversion (`convert_to_bin()`) |
| `hex_converter.py` | BIN â†’ HEX/SREC conversion (`convert_bin_to_hex()`, `convert_bin_to_srec()`) |
| `bin_splittler.py` | Chunk splitting by size (`split_file()`) |
| `bin_padder.py` | Block-size alignment/padding (`pad_bin_file()`) |
| `bin_signer.py` | ECU-PKI binary signing via `ecupki_signing.exe` (`sign_binary()`) |
| `bin_crc_calculator.py` | CRC8/16/32/64 computation (`process_file()`) |
| `binary_cropper.py` | Address-range removal (`cut_binary()`) |
| `bin_utils.py` | Helpers: `is_binary()`, `is_intel_hex()`, `is_motorola_srec()`, `is_sparse_image()`, `flip_endianness()`, `calculate_crc()` |

## Build Step Types

Registered via `BinaryStep` in the step registry:

| Step Type | Operation |
|---|---|
| `bin_convert_to_bin` | Convert HEX/SREC/sparse to raw BIN |
| `bin_split_in_chunks` | Split binary into sized chunks |
| `bin_convert_to_hex` | Convert BIN to HEX or SREC |
| `bin_compute_file_crc` | Compute CRC over file or address range |

## Key Functions

```python
convert_to_bin(file_path, output_folder, switch_endianness=False, byte_group_size=4)
convert_bin_to_hex(bin_file_path, hex_file_path, start_address=0)
convert_bin_to_srec(bin_file_path, srec_file_path, srec_type="s3")
split_file(file_path, chunk_size, chunk_size_unit="bytes", output_dir=None)
pad_bin_file(file_path, block_size, padding_byte=0xFF, output_path=None)
sign_binary(file_path, output_path, key_id, application_code_name, ...)
process_file(file_path, crc_type, polynom, start_address, end_address)
cut_binary(input_path, start_address, end_address, output_path)
```

## Dependencies

- **External:** `bincopy`, `crcmod`, `sparse`
- **Internal:** `xc_ce_utils.rb_logger`

## See Also

- [SW Container Generator](sw_container_generator.md) â€” consumes binary_handling operations in the firmware packaging pipeline
- [Step Reference](../core_engine/reference/step_reference.md) â€” binary step type registration
