// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
/** True in the static GitHub Pages build (`VITE_DEMO=1`): the API is answered in the browser from recorded data. */
export const DEMO = import.meta.env.VITE_DEMO === '1'

/** A file from public/, correct under the Pages sub-path (`/skincare-vision-ai/`) as well as at the site root. */
export const asset = (path: string) => `${import.meta.env.BASE_URL}${path.replace(/^\//, '')}`

export const REPO_URL = 'https://github.com/sudemkirmiz/skincare-vision-ai'

/** The one ingredient list the demo can check (must match SAMPLE_INCI in scripts/build_demo_fixtures.py). */
export const SAMPLE_INCI = 'Aqua, Glycerin, Niacinamide, Ceramide NP, Panthenol, Sodium Hyaluronate, Parfum, Linalool'
