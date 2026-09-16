# `cas_bacnet_stack/` - vendored Python adapter

This directory is a **source-inclusion copy**, not an installable package: it
is the untouched contents of
`submodules/cas-bacnet-stack/adapters/python/` at the commit this example's
submodule is pinned to (see `submodules/cas-bacnet-stack` and `.gitmodules`,
branch `6.x`). There is no `pip install` step for it and no `setup.py` - it
is imported the way a vendored C header is `#include`d: `main.py` and
`common/` add this directory to `sys.path` and `import` it directly. **Do not
edit these three files.** If the adapter needs a fix, that fix belongs
upstream in `cas-bacnet-stack`, and this copy is refreshed by re-copying from
a newer submodule pin.

## What's here

| File | What it is |
|---|---|
| `CASBACnetStackAdapterBindings.py` | **Generated** (`ci_scripts/generate-python-adapter.js`, from `source/CASBACnetStackDLL.h`, 231 exports). `ctypes.CFUNCTYPE` callback-signature constants (`FPCallbackGetPropertyReal`, etc. - all cdecl, not `WINFUNCTYPE`, and every `Get*Property` callback ends in a trailing `ctypes.POINTER(ctypes.c_uint32)` errorCode out-param), plus a thin wrapper function per export (`BACnetStack_AddDevice`, `BACnetStack_Tick`, ...) that calls through a module-level `_library` set by `bind()`. |
| `CASBACnetStackAdapter.py` | Hand-written: platform detection (`libname` - `CASBACnetStack_x64_Release.dll` on 64-bit Windows, `libCASBACnetStack_x64_Release.so` on 64-bit Linux) and the BACnet enumeration dictionaries (`bacnet_objectType`, `bacnet_propertyIdentifier`, `bacnet_engineeringUnits`, ...). |
| `property_buffer_helper.py` | Packs the buffer-shaped `Send*` calls (ReadProperty/WriteProperty/CreateObject **as a client**). **Unused by this example** - see below. |

## A stale docstring, and why it doesn't mean what it says

`CASBACnetStackAdapter.py`'s module docstring is titled **"HELPERS ONLY, NOT
A WORKING ADAPTER"** and says the file "never loads the native library and
never calls any `BACnetStack_*` export." That was true when it was the only
Python adapter file. It is **stale**: `CASBACnetStackAdapterBindings.py` (the
generated bindings file, with `bind()` and all 231 wrapper functions) landed
later and is exactly the "real Python adapter... tracked as a separate
feature request" the docstring says doesn't exist yet. Read the two files
**together** - `CASBACnetStackAdapter.py` for platform detection and
enumerations, `CASBACnetStackAdapterBindings.py` for `bind()` and the actual
`BACnetStack_*` calls - and the combination is a real, working adapter, used
exactly that way by `common/cas_example_helper.py` and `main.py` in this
repository. Do not re-litigate the docstring's warning against this
combination; it predates it.

## Why `property_buffer_helper.py` is here but unused

It is vendored for parity with the adapter's expected three-file set (the
same reasoning the C# port documented for `PropertyBufferHelper.cs`), but it
packs `Send*` calls - ReadProperty/WriteProperty/CreateObject **as a
client** - that this read-only B-SS example never makes. A Smart Sensor only
ever *answers* ReadProperty; it never *initiates* one. It is imported
nowhere in this repository. It compiles/imports cleanly and sits unused; that
is a documented, deliberate choice, not an oversight.

## Submodule pin

Copied from `submodules/cas-bacnet-stack` at branch `6.x`. See the repository
root's `.gitmodules` and `git -C submodules/cas-bacnet-stack rev-parse HEAD`
for the exact commit this copy was taken from.
