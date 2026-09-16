# SPDX-License-Identifier: CC0-1.0
# Public-domain example code (CC0) - see ../LICENSE.

# cas_bacnet_stack_example_constants.py
# =============================================================================
# A small, self-contained set of the BACnet enumeration values this example
# project needs. The CAS BACnet Stack defines the FULL enumerations inside
# cas_bacnet_stack/CASBACnetStackAdapter.py (the bacnet_* dictionaries) - this
# file only adds the handful of names that module does NOT already define
# (mostly because that module's dictionaries are hand-written and have not
# grown every BACnet enumeration yet, or because a value here is more
# convenient as a plain constant than a dict lookup at every call site).
# Where the vendored adapter already has an equivalent value, this file reuses
# it directly instead of duplicating it - see the comment on each block below.
#
# Every value matches the BACnet standard (ANSI/ASHRAE 135) and the CAS
# BACnet Stack enumerations, and every constant name matches the C++/C#/Node
# editions of this file (common/CASBACnetStackExampleConstants.h in
# BACnetProfileExample-B-SS-CPP, common/CASBACnetStackExampleConstants.cs in
# BACnetProfileExample-B-SS-CS) so the languages diff 1:1. Add more as your
# own project needs them.
# =============================================================================

# -- BACnet object types (Object_Type enumeration) --------------------------
#    Already in cas_bacnet_stack.CASBACnetStackAdapter.bacnet_objectType
#    (e.g. bacnet_objectType["analogInput"] == 0). This example uses plain
#    integer constants below instead of dict lookups, for a 1:1 diff against
#    the C++/C# editions' OBJECT_TYPE_* names.
OBJECT_TYPE_ANALOG_INPUT = 0
OBJECT_TYPE_BINARY_INPUT = 3
OBJECT_TYPE_DEVICE = 8
OBJECT_TYPE_MULTI_STATE_INPUT = 13
OBJECT_TYPE_NETWORK_PORT = 56

# -- BACnet property identifiers (Property_Identifier enumeration) ----------
#    Already in cas_bacnet_stack.CASBACnetStackAdapter.bacnet_propertyIdentifier
#    (all-lowercase keys, e.g. "objectname"). Spelled out here as
#    PROPERTY_IDENTIFIER_* constants, matching the other editions' names 1:1.
PROPERTY_IDENTIFIER_OBJECT_NAME = 77
PROPERTY_IDENTIFIER_OBJECT_TYPE = 79
PROPERTY_IDENTIFIER_PRESENT_VALUE = 85
PROPERTY_IDENTIFIER_DESCRIPTION = 28
PROPERTY_IDENTIFIER_VENDOR_NAME = 121
PROPERTY_IDENTIFIER_VENDOR_IDENTIFIER = 120
PROPERTY_IDENTIFIER_MODEL_NAME = 70
PROPERTY_IDENTIFIER_FIRMWARE_REVISION = 44
PROPERTY_IDENTIFIER_APPLICATION_SOFTWARE_VERSION = 12
PROPERTY_IDENTIFIER_OUT_OF_SERVICE = 81
PROPERTY_IDENTIFIER_UNITS = 117
PROPERTY_IDENTIFIER_POLARITY = 84
PROPERTY_IDENTIFIER_NUMBER_OF_STATES = 74
PROPERTY_IDENTIFIER_STATE_TEXT = 110
PROPERTY_IDENTIFIER_APDU_LENGTH = 399
PROPERTY_IDENTIFIER_REFERENCE_PORT = 483
PROPERTY_IDENTIFIER_BACNET_IP_UDP_PORT = 412
PROPERTY_IDENTIFIER_BACNET_IP_MODE = 408
PROPERTY_IDENTIFIER_IP_ADDRESS = 400
PROPERTY_IDENTIFIER_IP_SUBNET_MASK = 411
PROPERTY_IDENTIFIER_IP_DEFAULT_GATEWAY = 401

# -- BACnet engineering units (Engineering_Units enumeration) ---------------
#    Full list: submodules/cas-bacnet-stack/source/BACnetEngineeringUnits.h
#    Also in cas_bacnet_stack.CASBACnetStackAdapter.bacnet_engineeringUnits
#    ("degreescelsius": 62) - spelled out here for the 1:1 diff.
ENGINEERING_UNITS_DEGREES_CELSIUS = 62

# -- BACnet polarity (Polarity enumeration, for Binary objects) -------------
#    Full list: submodules/cas-bacnet-stack/source/BACnetPolarity.h
#    Not in the vendored adapter's dictionaries - defined here.
POLARITY_NORMAL = 0

# -- BACnet/IP mode (BACnetIPMode enumeration, for the Network Port) --------
#    Full list: submodules/cas-bacnet-stack/source/BACnetIPMode.h
#    Not in the vendored adapter's dictionaries - defined here.
BACNET_IP_MODE_NORMAL = 0

# -- BACnet services (Services_Supported enumeration) -----------------------
#    Used with BACnetStack_SetServiceEnabled() to turn individual services
#    on/off. These are BIT NUMBERS, not service-choice values - see the
#    docstring on BACnetStack_SetServiceEnabled in
#    cas_bacnet_stack/CASBACnetStackAdapterBindings.py.
SERVICE_READ_PROPERTY = 12
SERVICE_WHO_HAS = 33
SERVICE_WHO_IS = 34
SERVICE_I_HAVE = 27
SERVICE_I_AM = 26

# -- Network Port object network type (BACnetNetworkType enumeration, used
#    by BACnetStack_AddNetworkPortObject). IPV4 = 5 (same value as the
#    C++/C# editions' NETWORK_PORT_NETWORK_TYPE_IPV4 /
#    NETWORK_PORT_OBJECT_NETWORK_TYPE_IPV4).
NETWORK_PORT_NETWORK_TYPE_IPV4 = 5

# -- Network Port object protocol level (BACnetProtocolLevel enumeration,
#    used by BACnetStack_AddNetworkPortObject). BACnet Application = 2 (same
#    value as the C++/C# editions' NETWORK_PORT_PROTOCOL_LEVEL_BACNET_APPLICATION
#    / PROTOCOL_LEVEL_BACNET_APPLICATION).
NETWORK_PORT_PROTOCOL_LEVEL_BACNET_APPLICATION = 2

# The lowest protocol layer references this sentinel instead of another port.
# Also used as the default networkPortInstance for a single-port device that
# never calls AddNetworkPortObject (BACNET_NETWORK_PORT_DEFAULT). Not in the
# vendored adapter's dictionaries - defined here.
NETWORK_PORT_REFERENCE_PORT_NONE = 4194303

# -- Network_Number_Quality (BACnetNetworkNumberQuality, cl. 12.56.11). Says
#    how the port learned its Network_Number. A port that has not been told
#    and has not learned one reports "unknown" with Network_Number = 0.
NETWORK_NUMBER_QUALITY_UNKNOWN = 0

# -- Character string encoding (the encoding byte written by the
#    character-string Get callback). 0 = UTF-8. The BACnet character-set
#    values are defined by ANSI/ASHRAE 135 Clause 20.2.9.
CHARACTER_STRING_ENCODING_UTF8 = 0

# -- BACnet error codes (Error_Code enumeration) -----------------------------
#    Full list: submodules/cas-bacnet-stack/source/BACnetErrorCode.h
#    A GetProperty* callback (stack issue #974) may write one of these to its
#    trailing errorCode out-param and return False to name the BACnet error a
#    client receives, instead of letting the stack silently substitute a
#    default. This example uses it in exactly one place: an out-of-range
#    State_Text array index.
ERROR_CODE_INVALID_ARRAY_INDEX = 42
