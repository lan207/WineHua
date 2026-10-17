# DXVK source and packaged-build identity

The imported `dxvk-runtime.lock.json` retains the source project's reviewed source
commit, source digest and historical DLL hashes as provenance. Its historical
binary hashes are not requirements for a new WineHua build: compiler versions,
paths and PE timestamps can change rebuilt bytes. The source commit and source
file digest remain required.

During assembly, the generated runtime manifest records the verified source
commit/digest and the SHA-256 of each newly built x86, ARM64X and x64-alias DLL.
`scripts/dxvk_runtime_contract.py` and `check_runtime_components.py` verify those
manifest hashes against the actual ZIP/HAP contents, the expected PE machine
identities, the required shader-fix marker and byte-identical ARM64X/x64 aliases.
Changing only a manifest commit or hash cannot repair an incorrect payload.

Build and assemble through the top-level Makefile. The migration does not provide
an ad hoc binary replacement path. `make test-dxvk-package-identity` exercises
rebuilt-byte acceptance and rejects source mismatch, payload tampering, wrong
architectures, divergent aliases and missing shader-fix markers.

Upstream device observations are historical provenance only. They do not certify
the newly compiled WineHua package; rendering and runtime acceptance require a
separate test of that final package on hardware.
