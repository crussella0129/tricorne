# SPDX-FileCopyrightText: 2026 Thread & Signal LLC
# SPDX-License-Identifier: Apache-2.0
"""Module entrypoint so `python -m tricorne_engage` works.

This is a fallback path; the primary entrypoint is the
`tricorne-engage` console script installed by pip / pipx.
"""

from tricorne_engage.cli import app

if __name__ == "__main__":
    app()
