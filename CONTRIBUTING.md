# Contributing

Open an issue for a reproducible defect or a concrete proposed capability. Include a minimal nonconfidential input and the package version. Do not upload private calculation data or credentials.

For documentation-only text or link corrections, review the diff and check the
changed links, anchors and formatting. No package installation, Julia, full suite
or documentation build is required. Record checks that were not run; executable
examples, recipes and schema or runtime changes require their relevant checks.

For code or schema changes, create a focused pull request with relevant tests
demonstrating observable behavior, including rejected inputs and healthy controls.
Use the prepared environment for the selected checks. The README's installation,
complete-suite and distribution-build commands belong to separately assigned
stages with a finite shared budget; they are not prerequisites for a text-only
correction. A missing environment remains a reported limitation, not a passed
check. Public contracts must remain consistent with the producer and other
readers; format changes require an explicit shared contract revision. Numerical
acceptance must not be inferred from a successful process or export.

Integration CI runs in the [qcl-negf superproject](https://github.com/Afonenko-QCL-NEGF/qcl-negf) on its isolated local runner. Update the component gitlink there to test a selected change with the complete dependency graph. Maintainers review contributions before running them with access to laboratory infrastructure. Source code is MIT licensed.
