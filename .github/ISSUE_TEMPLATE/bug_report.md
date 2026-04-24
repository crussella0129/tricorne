---
name: Bug report
about: Report a bug in Tricorne-authored code (packaging, policy, engage, docs)
title: "[bug] "
labels: bug
assignees: ''
---

<!--
SPDX-FileCopyrightText: 2026 Thread & Signal LLC
SPDX-License-Identifier: CC-BY-SA-4.0
-->

<!--
  Bug reports for Tricorne itself. If you found a bug in an upstream
  packaged tool (nmap, metasploit, etc.), please report it to that
  upstream project — Tricorne packages upstream tools; we do not
  maintain fixes to them.
-->

## Component

Which part of Tricorne is affected?

- [ ] `packaging/` (RPM spec)
- [ ] `selinux/` (policy module)
- [ ] `engage/` (Purple Corner CLI)
- [ ] `kickstart/` (ISO build)
- [ ] `metapackages/` (metapackage spec)
- [ ] Documentation
- [ ] Other: ___

## What did you do?

<!-- Exact commands, copy-paste preferred over retyped. -->

## What did you expect?

## What actually happened?

## Environment

- Fedora version: (e.g. F41)
- Tricorne version: (`dnf info tricorne-*` or commit hash)
- SELinux mode: (`getenforce`)
- Architecture: (`uname -m`)

## SELinux AVCs (if applicable)

```
# paste output of:
# sudo ausearch -m avc -ts recent
```

## Logs

<!-- journalctl, dnf logs, rpmbuild logs, whatever is relevant -->

## Additional context
