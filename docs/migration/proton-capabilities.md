# Proton capability migration

Source: `yifengling0/VintagePomeloPro`, commit
`4071c079804af5052dc01473b5d593f3e9595b35`.
Target baseline: `winehua/WineHua`, branch `feature/proton-wine-ohos`, commit
`3f55395cc4e5ec0dd5e4c71498135b7f80820ce5`.

## Scope

The migration carries native Wine/Proton startup and process lifecycle fixes,
FEX Windows/WoW64/ARM64EC adaptations, DXVK Legacy/Modern, Mesa/Venus and VirGL
managed overlays, VKD3D mapped upload handling, native compositor/input/audio
compatibility, and the corresponding build, package identity and regression code.

The target ArkTS pages, components, services, application identity, resources,
package declarations and existing native TypeScript interface are retained.
The source account/cloud/membership/authentication/payment implementation,
product UI, Steam depot decoder/ZIP importer, font ZIP import UI backend,
performance HUD service and unused experiment staging module are excluded.
Native audio logging remains because the audio capture code depends on it.
The existing twelve-argument `launchClient` and `runWineProgram` interfaces remain
available. Additional native graphics diagnostics do not install source UI.

## Source dependency availability

Mesa gitlink `557fa3e781ea6e78fcff3ee759c25f60c3055064` initially could not
be resolved remotely. On 2026-10-17 at 04:48 UTC the exact object became
fetchable from `winehua/mesa-ohos`; it was verified with tree
`4c284a49ea18f90f5c5477aabdf32008ca097beb`. All nine managed Mesa overlays
applied successfully, including a second idempotence pass. No replacement pin
was used. This establishes source availability, not a completed build.

## Dependency identity and validation

`proton-runtime.lock.json` records the requested exact submodule identities,
normalized managed-patch hashes, and hashes of protected target product files.
Run `python3 scripts/verify_runtime_migration.py --product-only` for the independent
UI/native-interface boundary. The full gate additionally checks patch order and
populated, exact gitlinks. Use `--index` before committing.

The new VKD3D mapped-upload overlay is numbered `0020`, preserving its original
bytes and order after the existing `0019` demo overlay. Native build invalidation
includes the VirGL overlay script and patch files. Source product-only graphics
assertions are not imported into WineHua's validation gate.

## FEX overlay correction

The source VM patch was an aggregate snapshot that duplicated existing unaligned,
call/return, JIT-symbol and file-loading overlays. It failed on the declared
production sequence. Its original bytes are retained as the test-only fixture
`host_tests/fixtures/fex-vm-aggregate.original.patch` (SHA-256
`86009659a7f61071aa0ab83b92e0701479b28b0ab7e18e5a5eb788fd17f28111`).
The managed VM patch is now a pure delta after those prerequisites (SHA-256
`601504cebc03e7faec3b4f9333bb7b6dfcbc42b905b899596567f2e6670682aa`).
No source submodule commit is changed by this correction.

`make test-fex-patch-sequence` archives the pinned pristine FEX tree, extracts the
actual production patch phase, replays it twice, and independently reconstructs
the original aggregate intent plus only its missing prerequisite file sections.
Both default and exact-store-diagnostics trees must match byte for byte, with
zero rejects and a zero-fuzz VM reverse check. Verified manifest hashes are
`6fa31d43705bfdbfcc4ea3f216a797064bec8de73ac690dadb86d51d96ce4b7a` and
`a619962d807c8c3248474556443e52313a3ffb7b65816535ae2cd8af0f6c8a92`.
The independent VM tracker test exercises 23 behavioral cases.

Build recovery also checks generated CMake files rather than mistaking an
incomplete configure cache for a successful configuration. Native libffi
bootstrap runs autoreconf in its source directory and preserves failures.

Build through the top-level Makefile. Final acceptance requires both FEX DLLs,
Wine, DXVK x86/ARM64X, VKD3D, guest and host graphics, native HAP libraries, and an
unsigned HAP with matching packaged-runtime identities. The imported DXVK locks
are upstream reviewed-artifact provenance; never claim a locally rebuilt binary
matches them without checking its hash.

Run the host suite on a runner that supports Unix-domain sockets and sanitizers.
`ASAN_OPTIONS` can explicitly configure sanitizer options where LeakSanitizer
cannot run under a tracing sandbox; the default retains leak detection. A run
with `detect_leaks=0` does not validate leaks. Broker/gamepad IPC tests must still
pass on a supported runner and must not be silently skipped.

Clean-prefix, upgraded-prefix, rendering, audio and input acceptance on real
hardware remains separate from build success. No device runtime pass is implied
by this migration's host checks or CI configuration.

## Existing GNU TLS release-source lane

The inherited GnuTLS builder uses official release archives for GMP, Nettle,
libtasn1, libunistring and GnuTLS instead of bootstrapping their Git trees.
`gnutls-archives.lock.json` now pins their bytes to independently published
upstream/distribution checksum metadata. This is a checksum comparison, not a
fresh local verification of upstream PGP signatures. The build checks both
cached archive bytes and cached extracted source contents before reuse.
These release-source builds are recorded separately from Git submodule checks.

The existing libunistring Git pin is unchanged. Savannah returned HTTP 503
locally; the exact Git object was separately read from a third-party mirror
for fsck/commit/tree identity evidence only. No mirror script is executed and
neither `.gitmodules` nor CI switches to that mirror. CI must still fetch the
original official submodule source successfully.

## Target launch semantics and rebuilt DXVK identity

WineHua's existing 12-argument launch interface, independent direct-NCP and
Vulkan-desktop switches, explicit present backend, default graphics environment,
and final per-session environment precedence are preserved. New shared graphics
profiles are opt-in; an empty or unknown profile does not impose source-product
defaults. The target launch-policy gate compiles the production parsing and
environment logic and covers both boolean controls, defaults, invalid input,
D3D backends and explicit overrides. The existing direct-session gate covers
explicit profile opt-in, overrides and capability-dependent Venus fallback.

DXVK source commit/digest are checked against reviewed provenance. The assembly
manifest hashes the six locally rebuilt DLLs; package validation checks those
bytes, machine types, shader-fix marker and ARM64X/x64 alias identity. Historical
source-project DLL hashes are retained as evidence, not falsely equated with a
new WineHua build. Seven independent package-identity regression cases cover
these distinctions. No upstream device result is claimed for this new package.

Local host-suite execution completed with two environment-blocked IPC targets:
`test-broker-startup` and `test-gamepad-bridge` could not create Unix sockets in
the sandbox. All other aggregate targets passed, with LeakSanitizer explicitly
disabled locally; this is not a full-suite or leak-detection pass. CI keeps both
IPC targets and default sanitizer settings as required acceptance gates.

For Box64 WoW64, `BOX64_CONFIGURE_CC` optionally selects the AArch64 GNU/Linux
compiler used only by its top-level configuration. The nested DLL build retains
the required LLVM-MinGW Windows compiler. This does not select a GNU/Linux
compiler for OHOS native libraries.

At the 2026-10-17 05:20 UTC branch review, source HEAD had advanced to
`69f284e5af667b11a7fc42c5665824219b43058c`. Its three additional commits change
only membership checkout/legal/service UI, configuration and their tests (nine
paths). They contain no native, managed-overlay or gitlink change and are
excluded. The reviewed underlying-capability baseline remains `4071c079`.
Target HEAD was still the baseline at that check; it must be checked again
before publication.

VKD3D's pinned nested dxil-spirv header used `std::terminate` without including
`<exception>`. LLVM-MinGW 23 exposed this missing transitive include during the
real build. Local managed overlay `0021` adds only that standard header, after
the unchanged 20 capability overlays; the upstream and nested Git pins remain
unchanged. The patch is applied to the builder's isolated copy and its checksum
is included in the managed-overlay lock (142 patches total).

Overlay `0022` aligns the swapchain helper and its two COM method macros with
the existing stored `ID3D12Device10` interface. The inherited helper declared
Device9 while returning Device10, rejected by current Clang C type checking.
This completes the swapchain adaptation omitted by overlay `0014`; it does not
add an interface or alter the selected rendering path.

Overlay `0023` protects the MinGW x86 intrinsic header tree from the inherited
WIDL `static` macro workaround. It pre-includes the same `x86intrin.h` boundary
used by `winnt.h`, with matching x86/ARM64EC/resource-compiler guards and C++
linkage. This preserves intrinsic storage classes without changing CPU flags,
COM wrappers, or linker duplicate-symbol checks.

Smoke Vulkan import selection follows the compiler's effective target, including
its target flags, rather than the logical `x64` test slot. An explicit AMD64
probe in the ARM64 Wine build receives an AMD64 import archive generated from
all named exports of the freshly built ARM64X `vulkan-1.dll` facade. Forwarder
names are not expanded, and i386 never uses this fallback. The archive is
regenerated each time, so no stale export cache can survive a DLL rebuild.
The real AMD64 regression executable was checked for PE machine `0x8664` and
its `vulkan-1.dll` import; this proves linkage, not device execution. The smoke
builder itself is a payload rebuild prerequisite, and target-selection/failure
cases are part of the required host suite.

The 06:07 UTC source recheck found `0a140d7e8b5764d0e59dcbccd35040e9207aca1e`,
a membership sandbox-diagnostics commit affecting only three product UI/service
and test files. It is also excluded; the native baseline remains unchanged.

## Local build result (2026-10-17)

The production ARM64 native stack, both FEX DLLs, multiarchitecture Wine,
Legacy and Modern DXVK x86/ARM64X, VKD3D x64, guest Mesa VirGL/Venus, host Vulkan,
and Box64 WoW64 DLL all compiled successfully. The final unsigned HAP completed
all 33 Hvigor tasks and passed the packaged-runtime closure and stub guards.
All 70 packaged native `.so` files have ELF machine 183. Build identities and
remaining host/device validation limits are recorded in `local-validation.json`.
For local SDK 26, target SDK syntax is `26.0.0`; compatible remains `6.1.0(23)`.
The target's existing SDK 23 defaults and product files remain unchanged.

GNU release caches remain pristine across repeated dependency builds. Each
Autotools build configures a separate, verified source copy under its own build
directory, because upstream generators can write into `srcdir` even during a
VPATH build (for example, libunistring's export-symbol temporary files).
Archive and cached-source checks remain strict; unexpected cache additions or
changed source bytes are still rejected. This separates build-generated files
without weakening provenance checks or changing the runtime source inputs.
