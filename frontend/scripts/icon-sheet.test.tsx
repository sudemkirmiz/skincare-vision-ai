/**
 * Dev tool, not a regular test: renders every icon to ../outputs/icon-sheet.png for visual review.
 * Run with: ICON_SHEET=1 npx vitest run scripts/icon-sheet.test.tsx
 */
import { Resvg } from '@resvg/resvg-js'
import { writeFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, it } from 'vitest'
import * as Icons from '../src/icons'

describe.runIf(process.env.ICON_SHEET)('icon sheet', () => {
  it('renders', () => {
    const entries = Object.entries(Icons).filter(([, value]) => typeof value === 'function')
    const columns = 8
    const cell = 132
    const cells = entries
      .map(([name, Component], index) => {
        const x = (index % columns) * cell
        const y = Math.floor(index / columns) * cell
        const svg = renderToStaticMarkup(<Component size={56} />).replace('<svg', `<svg x="${x + 38}" y="${y + 18}" color="#2f6b45"`)
        return `${svg}<text x="${x + cell / 2}" y="${y + 104}" font-size="13" text-anchor="middle" fill="#68766d" font-family="Arial">${name}</text>`
      })
      .join('')
    const rows = Math.ceil(entries.length / columns)
    const sheet = `<svg xmlns="http://www.w3.org/2000/svg" width="${columns * cell}" height="${rows * cell}"><rect width="100%" height="100%" fill="#f4f9f4"/>${cells}</svg>`
    const png = new Resvg(sheet, { font: { loadSystemFonts: true } }).render().asPng()
    writeFileSync('../outputs/icon-sheet.png', png)
  })
})
