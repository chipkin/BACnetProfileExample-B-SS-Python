#
# property_buffer_helper.py - Python helper for packing the CAS BACnet Stack propertyArrays
# buffers consumed by CASBACnetStackAdapter.SendReadProperty / SendWriteProperty /
# SendCreateObject / SendWriteGroup / SendSubscribeCOVPropertyMultiple.
#
# See ../README.md for the canonical byte-maps and known-answer hex vectors. All multi-byte
# fields are little-endian; `struct.pack("<...")` already does this correctly regardless of host
# byte order, so no manual shift-and-mask is needed the way the C helper needs it.
#
# VALUES ARE PASSED AS TEXT, NOT RAW BINARY - EXCEPT encode_write_group_change_list and
# encode_create_object_initial_values (see their own docstrings below; #1594 converted
# SendWriteGroup's and SendCreateObject's value encoding to raw binary on 2026-09-09, a hard
# cutover, ahead of the other buffers here). For everything else, a Real 72.5 is the 4 bytes
# b"72.5", not an IEEE-754 float. See the `value` key docs on each encode_* function below; getting
# this wrong is a silent wire-level bug that is acknowledged normally by the far end. (The Node.js
# sibling, adapters/node/@chipkin/cas-bacnet-stack/src/property-arrays.ts, carries the same
# warning - keep the two in agreement.)
#
import math
import struct

# Highest BACnet primitive application datatype tag accepted by the write/create paths.
WRITABLE_TAG_MAX = 12

# Highest BACnet write priority (cl. 19.2). 1..16 are valid; 0 means "no priority".
WRITE_PRIORITY_MAX = 16

_UINT16_MAX = 0xFFFF
_UINT32_MAX = 0xFFFFFFFF


def _is_plain_int(value):
    """True for an int that is not a bool. Python's `isinstance(x, int)` also accepts `bool`
    (bool is a subclass of int), which would let `True`/`False` silently masquerade as 0/1 in a
    numeric field - explicitly excluding bool here is this file's equivalent of the Node.js port's
    `Number.isInteger` check (which already rejects non-numbers and non-integers uniformly)."""
    return isinstance(value, int) and not isinstance(value, bool)


def assert_writable_tag(tag):
    """Rejects any datatype that is not a BACnet primitive application tag (0..12). Constructed/
    complex types are not supported by the v6 write/create path and are rejected by the stack at
    decode time regardless - reject at pack time so the caller gets a clear error instead of a
    wire-level one."""
    if not isinstance(tag, int) or tag < 0 or tag > WRITABLE_TAG_MAX:
        raise ValueError(
            "datatype tag %r is not a BACnet primitive application type (0..%d); "
            "constructed/complex types are not supported by the write/create path" % (tag, WRITABLE_TAG_MAX)
        )


def assert_unsigned_field(path, value, max_value, width_name):
    """Rejects a numeric field that does not fit the fixed-width buffer writer backing it.

    Without this, an out-of-range value reaches struct.pack and raises a raw struct.error naming
    an internal format code rather than the offending field - so every consumer had to re-derive
    this library's bounds tables to produce a usable error (issue #444 parity with the Node.js
    port). The message names the element path, the value, and the limit.

    path: element path for the message, e.g. "elements[2].objectType".
    value: the caller-supplied value.
    max_value: highest accepted value (the writer's width, or a tighter BACnet limit).
    width_name: name of the bound for the message, e.g. "uint16".
    """
    if not _is_plain_int(value) or value < 0 or value > max_value:
        raise ValueError("%s = %r is not an integer in 0..%d (%s)" % (path, value, max_value, width_name))


def assert_sentinel_field(path, value, max_value, width_name):
    """Validates a field that uses a negative value as an "absent" sentinel (propertyArrayIndex,
    priority). Negative passes through as absent; a non-negative value must fit its writer.

    The sentinel itself is deliberately preserved - it is the documented convention on these
    interfaces - but a non-integer (including a bool or float) no longer silently selects the
    absent branch.

    path: element path for the message.
    value: the caller-supplied value.
    max_value: highest accepted value when present.
    width_name: name of the bound for the message.
    """
    if not _is_plain_int(value):
        raise ValueError(
            "%s = %r is not an integer (negative means absent, otherwise 0..%d %s)"
            % (path, value, max_value, width_name)
        )
    if value > max_value:
        raise ValueError("%s = %r is not an integer in 0..%d (%s)" % (path, value, max_value, width_name))


def assert_write_priority(path, priority):
    """Rejects a write priority outside BACnet's 1..16 (cl. 19.2), treating 0-or-negative as
    "absent" per the documented convention on these interfaces.

    path: element path for the message, e.g. "elements[2].priority".
    priority: the caller-supplied priority.
    """
    if not _is_plain_int(priority):
        raise ValueError(
            "%s = %r is not an integer (0 or negative means absent, otherwise 1..%d)"
            % (path, priority, WRITE_PRIORITY_MAX)
        )
    if priority > WRITE_PRIORITY_MAX:
        raise ValueError(
            "%s = %r exceeds the maximum BACnet write priority %d (cl. 19.2)" % (path, priority, WRITE_PRIORITY_MAX)
        )


def assert_value_buffer(path, value):
    """Rejects a value payload that is not bytes/bytearray, or whose length overflows the uint16
    valueLength field that precedes it on the wire. An over-long value would otherwise wrap
    silently (or raise an unhelpful generic struct.error with no field path).

    path: element path for the message, e.g. "elements[2].value".
    value: the caller-supplied payload.
    """
    if not isinstance(value, (bytes, bytearray)):
        raise ValueError("%s must be bytes/bytearray of already-encoded value bytes, got %s" % (path, type(value).__name__))
    if len(value) > _UINT16_MAX:
        raise ValueError("%s.length = %d exceeds the maximum %d (uint16 valueLength)" % (path, len(value), _UINT16_MAX))


def _assert_cov_increment(path, cov_increment):
    """Rejects a covIncrement that is not finite, or that would saturate to +/-inf when narrowed
    to float32 (the wire width this field is encoded as).

    Python floats are C doubles, so this is the same narrowing scenario as the Node.js port's
    `Math.fround` check - but unlike JavaScript's Buffer.writeFloatLE (which silently saturates an
    out-of-range double to +/-Infinity), CPython's struct.pack("<f", ...) itself raises
    OverflowError for a *finite* double too large for float32 ("float too large to pack with f
    format"); it only accepts an already-infinite/NaN input without complaint. So both failure
    modes have to be caught explicitly: a literal inf/nan input (which struct.pack lets through)
    via the isfinite check below, and an out-of-range finite double (which struct.pack itself
    raises on) via the try/except.
    """
    if not math.isfinite(cov_increment):
        raise ValueError("%s = %r is not a finite number (IEEE-754 float)" % (path, cov_increment))
    try:
        narrowed = struct.unpack("<f", struct.pack("<f", cov_increment))[0]
    except OverflowError:
        raise ValueError(
            "%s = %r overflows the 32-bit float this field is encoded as (max ~3.4e38); "
            "it would be written as Infinity" % (path, cov_increment)
        )
    if not math.isfinite(narrowed):
        raise ValueError(
            "%s = %r overflows the 32-bit float this field is encoded as (max ~3.4e38); "
            "it would be written as Infinity" % (path, cov_increment)
        )


def encode_read_property_arrays(elements):
    """Packs one or more ReadProperty / ReadPropertyMultiple elements - 15 bytes each:
      [0]      uint8_t  flags (bit0 = useArrayIndex)
      [1..2]   uint16_t objectType
      [3..6]   uint32_t objectInstance
      [7..10]  uint32_t propertyIdentifier
      [11..14] uint32_t propertyArrayIndex

    Each element is a dict with keys: objectType, objectInstance, propertyIdentifier,
    propertyArrayIndex (negative means "no array index").

    Every numeric field is validated against the writer backing it; a bad value raises ValueError
    naming the element index, the field, and the limit (issue #444).

    Returns (buffer: bytes, count: int) - pass count as propertyArraysCount.
    """
    chunks = []
    for i, e in enumerate(elements):
        assert_unsigned_field("elements[%d].objectType" % i, e["objectType"], _UINT16_MAX, "uint16")
        assert_unsigned_field("elements[%d].objectInstance" % i, e["objectInstance"], _UINT32_MAX, "uint32")
        assert_unsigned_field("elements[%d].propertyIdentifier" % i, e["propertyIdentifier"], _UINT32_MAX, "uint32")
        assert_sentinel_field("elements[%d].propertyArrayIndex" % i, e["propertyArrayIndex"], _UINT32_MAX, "uint32")
        use_index = e["propertyArrayIndex"] >= 0
        chunks.append(struct.pack(
            "<BHIII",
            0x01 if use_index else 0x00,
            e["objectType"],
            e["objectInstance"],
            e["propertyIdentifier"],
            e["propertyArrayIndex"] if use_index else 0,
        ))
    return b"".join(chunks), len(elements)


def encode_write_property_arrays(elements):
    """Packs one or more WriteProperty / WritePropertyMultiple elements - 19 bytes + value each:
      [0]      uint8_t  flags (bit0 = useArrayIndex, bit1 = usePriority)
      [1..2]   uint16_t objectType
      [3..6]   uint32_t objectInstance
      [7..10]  uint32_t propertyIdentifier
      [11..14] uint32_t propertyArrayIndex
      [15]     uint8_t  dataType
      [16]     uint8_t  priority
      [17..18] uint16_t valueLength
      [19+]    bytes    value

    Each element is a dict with keys: objectType, objectInstance, propertyIdentifier,
    propertyArrayIndex (negative = none), priority (<= 0 = none), datatype (0..12),
    value (bytes - the stack's textual DecodeString form, e.g. b"72.5" - VALUES ARE PASSED AS
    TEXT, NOT RAW BINARY; see the module docstring above).

    Returns (buffer: bytes, count: int) - pass count as propertyArraysCount and len(buffer) as
    propertyArraysLength.
    """
    chunks = []
    for i, e in enumerate(elements):
        assert_writable_tag(e["datatype"])
        assert_unsigned_field("elements[%d].objectType" % i, e["objectType"], _UINT16_MAX, "uint16")
        assert_unsigned_field("elements[%d].objectInstance" % i, e["objectInstance"], _UINT32_MAX, "uint32")
        assert_unsigned_field("elements[%d].propertyIdentifier" % i, e["propertyIdentifier"], _UINT32_MAX, "uint32")
        assert_sentinel_field("elements[%d].propertyArrayIndex" % i, e["propertyArrayIndex"], _UINT32_MAX, "uint32")
        assert_write_priority("elements[%d].priority" % i, e["priority"])
        assert_value_buffer("elements[%d].value" % i, e["value"])
        use_index = e["propertyArrayIndex"] >= 0
        use_priority = e["priority"] > 0
        flags = (0x01 if use_index else 0) | (0x02 if use_priority else 0)
        value = e["value"]
        chunks.append(struct.pack(
            "<BHIIIBBH",
            flags,
            e["objectType"],
            e["objectInstance"],
            e["propertyIdentifier"],
            e["propertyArrayIndex"] if use_index else 0,
            e["datatype"],
            e["priority"] if use_priority else 0,
            len(value),
        ) + value)
    return b"".join(chunks), len(elements)


def encode_create_object_initial_values(values):
    """Packs one or more CreateObject initial-property-value elements - 13 bytes + value each
    (#961: widened to add flags/propertyArrayIndex/priority so a caller can create an object with
    e.g. a Weekly_Schedule[1] initial value or a commandable initial value at a priority - the
    field order matches encode_write_property_arrays' element above, minus objectType/
    objectInstance since an object being created has no identity yet):
      [0]      uint8_t  flags (bit0 = useArrayIndex, bit1 = usePriority)
      [1..4]   uint32_t propertyIdentifier
      [5..8]   uint32_t propertyArrayIndex
      [9]      uint8_t  dataType
      [10]     uint8_t  priority
      [11..12] uint16_t valueLength
      [13+]    bytes    value

    Each value is a dict with keys: propertyIdentifier, propertyArrayIndex (negative = none,
    defaults to -1 if omitted), priority (<= 0 = none, defaults to 0 if omitted), datatype (0..12),
    value (bytes). #1594 (2026-09-09): value is RAW BINARY here, NOT text - a hard cutover from
    the previous ASCII/UTF-8 form, unlike encode_write_property_arrays above. See
    BACnetStack_SendCreateObject's "VALUE ENCODING" block in CASBACnetStackDLL.h for the full
    per-type byte layout, e.g. struct.pack("<f", 72.5) for a Real, not b"72.5".

    Returns (buffer: bytes, count: int) - pass count as propertyArraysCount and len(buffer) as
    propertyArraysLength.
    """
    chunks = []
    for i, v in enumerate(values):
        assert_writable_tag(v["datatype"])
        assert_unsigned_field("values[%d].propertyIdentifier" % i, v["propertyIdentifier"], _UINT32_MAX, "uint32")
        property_array_index = v.get("propertyArrayIndex", -1)
        priority = v.get("priority", 0)
        assert_sentinel_field("values[%d].propertyArrayIndex" % i, property_array_index, _UINT32_MAX, "uint32")
        assert_write_priority("values[%d].priority" % i, priority)
        assert_value_buffer("values[%d].value" % i, v["value"])
        use_index = property_array_index >= 0
        use_priority = priority > 0
        flags = (0x01 if use_index else 0) | (0x02 if use_priority else 0)
        value = v["value"]
        chunks.append(struct.pack(
            "<BIIBBH",
            flags,
            v["propertyIdentifier"],
            property_array_index if use_index else 0,
            v["datatype"],
            priority if use_priority else 0,
            len(value),
        ) + value)
    return b"".join(chunks), len(values)


def encode_write_group_change_list(entries):
    """Packs one or more SendWriteGroup change-list elements - 6 bytes + value each:
      [0..1] uint16_t channel
      [2]    uint8_t  overridingPriority (0 = absent; valid priorities 1..16)
      [3]    uint8_t  valueDatatype
      [4..5] uint16_t valueLength
      [6+]   bytes    value

    Each entry is a dict with keys: channel, overridingPriority, valueDatatype (0..12),
    value (bytes). #1594 (2026-09-09): value is RAW BINARY here, NOT text - a hard cutover from
    the previous ASCII/UTF-8 form, unlike the other encode_* functions in this module. See
    BACnetStack_SendWriteGroup's "VALUE ENCODING" block in CASBACnetStackDLL.h for the full
    per-type byte layout, e.g. struct.pack("<f", 23.5) for a Real, not b"23.5".

    Note: unlike the write element's `priority`, `overridingPriority` is written straight through
    with no absent-branch, so it is validated with the plain unsigned-bound check (0..16), not the
    negative-sentinel priority check - a negative value here is simply invalid, not "absent".

    Returns (buffer: bytes, count: int) - pass count as changeListCount and len(buffer) as
    changeListLength.
    """
    chunks = []
    for i, e in enumerate(entries):
        assert_writable_tag(e["valueDatatype"])
        assert_unsigned_field("entries[%d].channel" % i, e["channel"], _UINT16_MAX, "uint16")
        assert_unsigned_field(
            "entries[%d].overridingPriority" % i, e["overridingPriority"], WRITE_PRIORITY_MAX,
            "0 = absent, otherwise 1..16 per cl. 19.2",
        )
        assert_value_buffer("entries[%d].value" % i, e["value"])
        value = e["value"]
        chunks.append(struct.pack("<HBBH", e["channel"], e["overridingPriority"], e["valueDatatype"], len(value)) + value)
    return b"".join(chunks), len(entries)


def encode_cov_property_multiple_references(references):
    """Packs one or more SendSubscribeCOVPropertyMultiple COV references - FIXED 19 bytes each
    (no trailing value; a subscription reference carries no payload):
      [0]      uint8_t  flags (bit0 usePropertyArrayIndex, bit1 useCovIncrement, bit2 timestamped)
      [1..2]   uint16_t objectType
      [3..6]   uint32_t objectInstance
      [7..10]  uint32_t propertyIdentifier
      [11..14] uint32_t propertyArrayIndex
      [15..18] float    covIncrement (IEEE-754, little-endian)

    Each reference is a dict with keys: monitoredObjectType, monitoredObjectInstance,
    propertyIdentifier, usePropertyArrayIndex (bool), propertyArrayIndex, useCovIncrement (bool),
    covIncrement (float), timestamped (bool).

    propertyArrayIndex is only validated when usePropertyArrayIndex is true: with the flag clear
    the field is zeroed rather than passed through, so a caller applying the sibling encoders'
    "negative means no array index" convention stays valid here. covIncrement is only validated
    when useCovIncrement is true, and is checked for float32 finiteness/saturation (see
    _assert_cov_increment).

    Returns (buffer: bytes, count: int) - pass count as referenceCount and len(buffer) as
    referencesLength.
    """
    chunks = []
    for i, r in enumerate(references):
        assert_unsigned_field("references[%d].monitoredObjectType" % i, r["monitoredObjectType"], _UINT16_MAX, "uint16")
        assert_unsigned_field("references[%d].monitoredObjectInstance" % i, r["monitoredObjectInstance"], _UINT32_MAX, "uint32")
        assert_unsigned_field("references[%d].propertyIdentifier" % i, r["propertyIdentifier"], _UINT32_MAX, "uint32")
        if r["usePropertyArrayIndex"]:
            assert_unsigned_field("references[%d].propertyArrayIndex" % i, r["propertyArrayIndex"], _UINT32_MAX, "uint32")
        if r["useCovIncrement"]:
            _assert_cov_increment("references[%d].covIncrement" % i, r["covIncrement"])
        flags = (0x01 if r["usePropertyArrayIndex"] else 0) | (0x02 if r["useCovIncrement"] else 0) | (0x04 if r["timestamped"] else 0)
        chunks.append(struct.pack(
            "<BHIIIf",
            flags,
            r["monitoredObjectType"],
            r["monitoredObjectInstance"],
            r["propertyIdentifier"],
            r["propertyArrayIndex"] if r["usePropertyArrayIndex"] else 0,
            r["covIncrement"] if r["useCovIncrement"] else 0.0,
        ))
    return b"".join(chunks), len(references)
