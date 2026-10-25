// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
/**
 * Renders the install icons in public/icons (and the PDF report's logo) from the master brand files in public/brand. Re-run after changing the logo:
 *   node scripts/pwa-icons.mjs
 * "any" icons keep the rounded tile; "maskable" and the iOS touch icon fill the square (the platform rounds the corners)
 * and keep the mark inside the 80 % safe zone.
 */
import { Resvg } from '@resvg/resvg-js'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'

const tile = readFileSync('public/brand/logo-tile.svg', 'utf8')
const square = readFileSync('public/brand/logo-square.svg', 'utf8')
const render = (svg, size) => new Resvg(svg, { fitTo: { mode: 'width', value: size } }).render().asPng()

mkdirSync('public/icons', { recursive: true })
for (const size of [192, 512]) {
  writeFileSync(`public/icons/icon-${size}.png`, render(tile, size))
  writeFileSync(`public/icons/maskable-${size}.png`, render(square, size))
}
writeFileSync('public/icons/apple-touch-icon.png', render(square, 180))
// The PDF report (backend) uses the same mark in its header.
mkdirSync('../assets/brand', { recursive: true })
writeFileSync('../assets/brand/logo.png', render(tile, 256))
console.log('icons written to public/icons')
