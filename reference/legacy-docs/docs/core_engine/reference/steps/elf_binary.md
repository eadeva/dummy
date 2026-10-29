# ELF & Binary Operations

Inspect ELF binaries and transform hex/binary firmware files.

```{note}
**Shape: PARAMS-DICT.** All fields below are nested under a `params:` mapping — the source
docstrings for these steps say `parameters:` in their example, but the code actually reads
`self.config.get('params', {})`. Use `params:`, not `parameters:`.
```

## `elf_read_symbols`

- **Source:** [`elf_steps.py`](../../../../xc_ce_utils/core_engine/steps/elf_steps.py)
- **Behavior:** Reads symbols via `xc_ce_utils.elf_utils.get_symbols(...)` and stores results in `global_variables`. Struct symbols may decompose with `store_members_as` (use `*` to capture every member with an auto-generated prefix).
- **`interpret_as` values:** `auto`, `string`, `version_u16`, `u8`, `u16`, `u32`, `hex`, `struct`, `none`.
- **`symbols` shape:** a **dict** keyed by symbol name (not a list) — each value is
  `{interpret_as?, store_address_as?, store_value_as?, store_members_as?, set_env?}`.

```yaml
read_app_symbols:
  type: elf_read_symbols
  params:
    elf_path: "${APP_ELF}"
    symbols:
      rbx_vilib_BoschApp_InternalBoschAppSwVersion:
        interpret_as: version_u16
        store_address_as: APP_VERSION_ADDR
        store_value_as: APP_VERSION
        set_env: true
      rbx_vilib_BoschApp_BoschAppCommitHash:
        interpret_as: string
        store_value_as: APP_COMMIT_HASH
```

## `elf_list_sections`

- **Behavior:** Logs a `Name / Address / Size / Flags / Type` table. Computes flash/RAM usage via `get_memory_usage(...)` and optionally stores totals as globals.

```yaml
elf_sections:
  type: elf_list_sections
  params:
    elf_path: "${APP_ELF}"
    allocated_only: true
    store_flash_used_as: FLASH_USED
    store_ram_used_as: RAM_USED
    store_total_as: APP_FOOTPRINT
```

## `bin_convert_to_bin`

- **Fields:** `input_path`, `output_dir`, `output_variable` (required); `flip_endianness`,
  `endianness_byte_group_size` (optional). There is **no** `output_file`, `start_address`, or
  `end_address` field on this step.

```yaml
hex_to_bin:
  type: bin_convert_to_bin
  params:
    input_path: _bin/firmware.hex
    output_dir: _bin/converted
    output_variable: BIN_PATH
    flip_endianness: false
    endianness_byte_group_size: 4
```

## `bin_split_in_chunks`

- **Fields:** `input_path`, `chunk_size`, `output_dir`, `output_variable` (required);
  `chunk_size_unit` (optional, default `'bytes'`).

```yaml
chunk_firmware:
  type: bin_split_in_chunks
  params:
    input_path: _bin/firmware.bin
    chunk_size: 65536
    chunk_size_unit: bytes
    output_dir: _bin/chunks
    output_variable: CHUNKS_DIR
```

## `bin_convert_to_hex`

- **Fields:** `input_path`, `output_dir`, `output_variable` (required); `hex_type` (optional,
  default `'intel'`).

```yaml
bin_to_hex:
  type: bin_convert_to_hex
  params:
    input_path: _bin/firmware.bin
    output_dir: _bin/hex
    output_variable: HEX_PATH
    hex_type: intel
```

## `bin_compute_file_crc`

- **Fields:** `input_file` (note: **not** `input_path` — this step alone uses `input_file`),
  `crc_type`, `output_variable` (required); `polynom`, `start_address`, `end_address`, `output_dir`
  (optional).

```yaml
crc_check:
  type: bin_compute_file_crc
  params:
    input_file: _bin/firmware.bin
    crc_type: crc32
    polynom: "0x04C11DB7"
    start_address: "0x0"
    end_address: "0x40000"
    output_variable: FW_CRC
```

## Category index

| Step type | Description |
|---|---|
| `elf_read_symbols` | Read ELF symbols (typed) into globals |
| `elf_list_sections` | List sections with flash/RAM totals |
| `bin_convert_to_bin` | Hex → binary |
| `bin_split_in_chunks` | Split a binary into chunks |
| `bin_convert_to_hex` | Binary → hex |
| `bin_compute_file_crc` | Compute file CRC |
