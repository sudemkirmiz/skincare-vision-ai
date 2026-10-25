// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (C) 2026 Sudem Kırmız
/**
 * SkinCare Vision AI icon set.
 *
 * One drawing language for every icon: 24px grid, 1.6px rounded strokes in `currentColor`,
 * plus a soft "serum" fill (currentColor at low opacity) on the main shape. That duotone fill
 * is what makes the set feel like skincare rather than generic UI icons.
 * Icons are decorative by default (aria-hidden); pass `title` when an icon carries meaning alone.
 */
import type { ReactNode, SVGProps } from 'react'

export type IconProps = SVGProps<SVGSVGElement> & { size?: number; title?: string }

function Icon({ size = 22, title, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
      focusable="false"
      {...rest}
    >
      {title ? <title>{title}</title> : null}
      {children}
    </svg>
  )
}

/** Soft duotone fill used inside the primary shape. */
const Soft = ({ d }: { d: string }) => <path d={d} fill="currentColor" fillOpacity={0.14} stroke="none" />

/*
 * Brand mark: a drop with a sparkle. Unlike the line icons it is full colour; the colours are theme tokens
 * (--logo-*) so it follows light and dark mode. The master files live in public/brand/.
 */
const DROP = 'M30 10.6C35.4 16.2 46 26.6 46 38.4A16 16 0 0 1 14 38.4C14 26.6 24.6 16.2 30 10.6Z'
const SPARKLE = 'M30 29.6C31.84 36.96 31.84 36.96 39.2 38.8C31.84 40.64 31.84 40.64 30 48C28.16 40.64 28.16 40.64 20.8 38.8C28.16 36.96 28.16 36.96 30 29.6Z'
const SPARKLE_SMALL = 'M50.6 8C51.68 12.32 51.68 12.32 56 13.4C51.68 14.48 51.68 14.48 50.6 18.8C49.52 14.48 49.52 14.48 45.2 13.4C49.52 12.32 49.52 12.32 50.6 8Z'

/** `tile` adds the rounded app-icon background; below 28 px the small outer sparkle is dropped, as in the brand sheet. */
export const LogoMark = ({ size = 28, tile = false, title, className }: { size?: number; tile?: boolean; title?: string; className?: string }) => {
  const sparkle = size >= 28
  const transform = tile ? (sparkle ? 'translate(32 32) scale(0.94) translate(-31 -33)' : 'translate(32 32) scale(1.12) translate(-30 -33.6)') : undefined
  return (
    <svg width={size} height={size} viewBox={tile ? '0 0 64 64' : sparkle ? '9 5 50 54' : '10 7 40 52'} className={className}
      aria-hidden={title ? undefined : true} role={title ? 'img' : undefined} focusable="false">
      {title ? <title>{title}</title> : null}
      {tile ? <rect width="64" height="64" rx="15" fill="var(--logo-tile)" /> : null}
      <g transform={transform}>
        <path d={DROP} fill="var(--logo-fill)" stroke="var(--logo-stroke)" strokeWidth={4.4} strokeLinejoin="round" />
        <path d={SPARKLE} fill="var(--logo-inner)" />
        {sparkle ? <path d={SPARKLE_SMALL} fill="var(--logo-outer)" /> : null}
      </g>
    </svg>
  )
}

/** Mark + two-line wordmark ("SkinCare" / "VİSİON AI") used in the header and onboarding. */
export const BrandLogo = ({ compact = false }: { compact?: boolean }) => (
  <span className="flex items-center gap-2.5">
    <LogoMark size={36} tile className={compact ? 'size-8 sm:size-9' : undefined} />
    <span className={compact ? 'hidden leading-none md:block' : 'block leading-none'}>
      <span className="block font-display text-[19px] font-semibold tracking-tight text-ink">SkinCare</span>
      <span className="mt-0.5 block text-[9.5px] font-semibold tracking-[0.2em] text-brand-600">VİSİON AI</span>
    </span>
  </span>
)

export const FaceScan = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2" />
    <Soft d="M12 6.8c2.7 0 4.4 2.2 4.4 5 0 2.9-1.9 5.4-4.4 5.4s-4.4-2.5-4.4-5.4c0-2.8 1.7-5 4.4-5Z" />
    <path d="M12 6.8c2.7 0 4.4 2.2 4.4 5 0 2.9-1.9 5.4-4.4 5.4s-4.4-2.5-4.4-5.4c0-2.8 1.7-5 4.4-5Z" />
    <path d="M10.4 11.2h.01M13.6 11.2h.01M10.8 14.1c.7.5 1.7.5 2.4 0" />
  </Icon>
)

export const Camera = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2l1.4-2h6.2l1.4 2h2A1.5 1.5 0 0 1 20 8.5v9A1.5 1.5 0 0 1 18.5 19h-13A1.5 1.5 0 0 1 4 17.5Z" />
    <path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2l1.4-2h6.2l1.4 2h2A1.5 1.5 0 0 1 20 8.5v9A1.5 1.5 0 0 1 18.5 19h-13A1.5 1.5 0 0 1 4 17.5Z" />
    <circle cx="12" cy="12.8" r="3.3" />
    <path d="M17 10h.01" />
  </Icon>
)

export const ImageUpload = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M5 5h10v14H5z" />
    <rect x="4" y="4" width="13" height="16" rx="2.5" />
    <path d="m4.5 16 3.6-3.6a1.4 1.4 0 0 1 2 0L13 15.3" />
    <circle cx="9" cy="8.8" r="1.3" />
    <path d="M19.5 9.5v6M17 12l2.5-2.5L22 12" />
  </Icon>
)

export const Drop = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 3.5c3.3 3.7 5.6 6.8 5.6 9.8a5.6 5.6 0 0 1-11.2 0c0-3 2.3-6.1 5.6-9.8Z" />
    <path d="M12 3.5c3.3 3.7 5.6 6.8 5.6 9.8a5.6 5.6 0 0 1-11.2 0c0-3 2.3-6.1 5.6-9.8Z" />
    <path d="M9.4 14.2a2.7 2.7 0 0 0 2.4 2.5" />
  </Icon>
)

export const Sun = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8Z" />
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2.8v1.8M12 19.4v1.8M2.8 12h1.8M19.4 12h1.8M5.5 5.5l1.3 1.3M17.2 17.2l1.3 1.3M5.5 18.5l1.3-1.3M17.2 6.8l1.3-1.3" />
  </Icon>
)

export const Moon = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M19 14.6A7.5 7.5 0 0 1 9.4 5a7.5 7.5 0 1 0 9.6 9.6Z" />
    <path d="M19 14.6A7.5 7.5 0 0 1 9.4 5a7.5 7.5 0 1 0 9.6 9.6Z" />
    <path d="M16.5 4.5v2M15.5 5.5h2M19.8 8.6v1.2M19.2 9.2h1.2" />
  </Icon>
)

export const Serum = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 3.5h4M10.6 3.5v2.8M13.4 3.5v2.8" />
    <Soft d="M8.5 9.3a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v9.2a2 2 0 0 1-2 2h-3a2 2 0 0 1-2-2Z" />
    <path d="M8.5 9.3a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v9.2a2 2 0 0 1-2 2h-3a2 2 0 0 1-2-2Z" />
    <path d="M8.5 12.5h7M12 15c.9 1 1.3 1.6 1.3 2.2a1.3 1.3 0 0 1-2.6 0c0-.6.4-1.2 1.3-2.2Z" />
  </Icon>
)

export const Jar = (p: IconProps) => (
  <Icon {...p}>
    <rect x="5" y="5" width="14" height="4" rx="1.6" />
    <Soft d="M6 9h12v8.5a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 6 17.5Z" />
    <path d="M6 9h12v8.5a2.5 2.5 0 0 1-2.5 2.5h-7A2.5 2.5 0 0 1 6 17.5Z" />
    <path d="M9 13.2c1-.9 2-.9 3 0s2 .9 3 0" />
  </Icon>
)

export const Cleanser = (p: IconProps) => (
  <Icon {...p}>
    <path d="M10 6.5V4h3.5M13.5 4h2" />
    <Soft d="M8 9a2.5 2.5 0 0 1 2.5-2.5h1A2.5 2.5 0 0 1 14 9v9.5a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2Z" />
    <path d="M8 9a2.5 2.5 0 0 1 2.5-2.5h1A2.5 2.5 0 0 1 14 9v9.5a2 2 0 0 1-2 2h-2a2 2 0 0 1-2-2Z" />
    <circle cx="17.5" cy="10" r="1.3" />
    <circle cx="19" cy="14" r="0.9" />
    <circle cx="16.8" cy="16.6" r="0.7" />
  </Icon>
)

export const ShieldSun = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 3.2 18.8 6v5.6c0 4.2-2.8 7.4-6.8 9.2-4-1.8-6.8-5-6.8-9.2V6Z" />
    <path d="M12 3.2 18.8 6v5.6c0 4.2-2.8 7.4-6.8 9.2-4-1.8-6.8-5-6.8-9.2V6Z" />
    <circle cx="12" cy="12" r="2.2" />
    <path d="M12 7.9v.8M12 15.3v.8M7.9 12h.8M15.3 12h.8" />
  </Icon>
)

export const Leaf = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M19.5 4.5c.4 8.4-3.6 14-10.5 14.5-1.4-6.9 3.2-12.6 10.5-14.5Z" />
    <path d="M19.5 4.5c.4 8.4-3.6 14-10.5 14.5-1.4-6.9 3.2-12.6 10.5-14.5Z" />
    <path d="M4.5 20.5c2.6-4.8 6.2-8.7 11.2-11.6" />
  </Icon>
)

export const Sparkles = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M10 4.5c.6 3.5 2 5 5.5 5.5-3.5.6-4.9 2-5.5 5.5-.6-3.5-2-4.9-5.5-5.5 3.5-.5 4.9-2 5.5-5.5Z" />
    <path d="M10 4.5c.6 3.5 2 5 5.5 5.5-3.5.6-4.9 2-5.5 5.5-.6-3.5-2-4.9-5.5-5.5 3.5-.5 4.9-2 5.5-5.5Z" />
    <path d="M17.5 14.5c.3 1.6.9 2.2 2.5 2.5-1.6.3-2.2.9-2.5 2.5-.3-1.6-.9-2.2-2.5-2.5 1.6-.3 2.2-.9 2.5-2.5ZM18 3.5v2.4M16.8 4.7h2.4" />
  </Icon>
)

export const Calendar = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M4.5 9.5h15v8a2 2 0 0 1-2 2h-11a2 2 0 0 1-2-2Z" />
    <rect x="4.5" y="5.5" width="15" height="14" rx="2.5" />
    <path d="M4.5 9.5h15M8.5 3.5v3.5M15.5 3.5v3.5" />
    <path d="M12 16.4c1.3-.7 2-1.6 2-2.4a1 1 0 0 0-2-.3 1 1 0 0 0-2 .3c0 .8.7 1.7 2 2.4Z" />
  </Icon>
)

export const TrendUp = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M4 17.5 9 12l3.5 3.2L20 7.5V19H4Z" />
    <path d="M4 17.5 9 12l3.5 3.2L20 7.5" />
    <path d="M15 7.5h5v5" />
  </Icon>
)

export const History = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 4.5a7.5 7.5 0 1 1 0 15 7.5 7.5 0 0 1 0-15Z" />
    <path d="M4.5 12A7.5 7.5 0 1 0 7 6.4" />
    <path d="M4.5 4.8v3.4h3.4M12 8.2V12l2.6 1.8" />
  </Icon>
)

export const Bag = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M5.5 8.5h13l-.9 10a2 2 0 0 1-2 1.8H8.4a2 2 0 0 1-2-1.8Z" />
    <path d="M5.5 8.5h13l-.9 10a2 2 0 0 1-2 1.8H8.4a2 2 0 0 1-2-1.8Z" />
    <path d="M9 10.5V7a3 3 0 0 1 6 0v3.5" />
    <path d="M12 16.4c1.2-.7 1.9-1.4 1.9-2.2a.95.95 0 0 0-1.9-.3.95.95 0 0 0-1.9.3c0 .8.7 1.5 1.9 2.2Z" />
  </Icon>
)

export const LabelScan = (p: IconProps) => (
  <Icon {...p}>
    <path d="M8 4h4" />
    <Soft d="M6.5 7.5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2h-3a2 2 0 0 1-2-2Z" />
    <path d="M13.5 12V7.5a2 2 0 0 0-2-2h-3a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2H12" />
    <path d="M8.6 10h2.8M8.6 12.5h2" />
    <circle cx="16.5" cy="16" r="2.6" />
    <path d="m18.4 17.9 2.1 2.1" />
  </Icon>
)

export const Sliders = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 7h7M16 7h3M5 12h3M12 12h7M5 17h9M18 17h1" />
    <circle cx="14" cy="7" r="2" />
    <circle cx="10" cy="12" r="2" />
    <circle cx="16" cy="17" r="2" />
  </Icon>
)

export const UserCircle = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Z" />
    <circle cx="12" cy="12" r="8.5" />
    <circle cx="12" cy="10" r="2.8" />
    <path d="M6.8 18.2c1.1-2 3-3.2 5.2-3.2s4.1 1.2 5.2 3.2" />
  </Icon>
)

export const Alert = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M10.4 4.8a1.8 1.8 0 0 1 3.2 0l6.6 12.3A1.8 1.8 0 0 1 18.6 20H5.4a1.8 1.8 0 0 1-1.6-2.9Z" />
    <path d="M10.4 4.8a1.8 1.8 0 0 1 3.2 0l6.6 12.3A1.8 1.8 0 0 1 18.6 20H5.4a1.8 1.8 0 0 1-1.6-2.9Z" />
    <path d="M12 9.5v4M12 16.5h.01" />
  </Icon>
)

export const CheckCircle = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Z" />
    <circle cx="12" cy="12" r="8.5" />
    <path d="m8.4 12.3 2.4 2.4 4.8-5" />
  </Icon>
)

export const Info = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 3.5a8.5 8.5 0 1 1 0 17 8.5 8.5 0 0 1 0-17Z" />
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5M12 8h.01" />
  </Icon>
)

export const Lightbulb = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 3.5a5.5 5.5 0 0 1 3.3 9.9c-.6.5-.8 1.1-.8 1.8V16h-5v-.8c0-.7-.3-1.3-.8-1.8A5.5 5.5 0 0 1 12 3.5Z" />
    <path d="M12 3.5a5.5 5.5 0 0 1 3.3 9.9c-.6.5-.8 1.1-.8 1.8V16h-5v-.8c0-.7-.3-1.3-.8-1.8A5.5 5.5 0 0 1 12 3.5Z" />
    <path d="M9.8 19h4.4M10.6 21.2h2.8" />
  </Icon>
)

export const DocumentPdf = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M6.5 3.5h7l4 4v11a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2Z" />
    <path d="M6.5 3.5h7l4 4v11a2 2 0 0 1-2 2h-9a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2Z" />
    <path d="M13.5 3.5v4h4M8.5 12.5h7M8.5 15.5h5" />
  </Icon>
)

export const Download = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 4.5v10M8 10.5l4 4 4-4M5 19.5h14" />
  </Icon>
)

export const Trash = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4.5 7h15M9.5 7V5a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v2" />
    <Soft d="M6.5 7h11l-.8 11.5a2 2 0 0 1-2 1.8H9.3a2 2 0 0 1-2-1.8Z" />
    <path d="M6.5 7h11l-.8 11.5a2 2 0 0 1-2 1.8H9.3a2 2 0 0 1-2-1.8ZM10 11v5.5M14 11v5.5" />
  </Icon>
)

export const Edit = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="m15.5 5 3.5 3.5-9.5 9.5H6v-3.5Z" />
    <path d="m15.5 5 3.5 3.5-9.5 9.5H6v-3.5ZM13.5 7l3.5 3.5M5 20.5h14" />
  </Icon>
)

export const Plus = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
)

export const Close = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </Icon>
)

export const ChevronRight = (p: IconProps) => (
  <Icon {...p}>
    <path d="m9.5 6 6 6-6 6" />
  </Icon>
)

export const ArrowLeft = (p: IconProps) => (
  <Icon {...p}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </Icon>
)

export const ExternalLink = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14 5h5v5M19 5l-8 8M17 14v4.5a1.5 1.5 0 0 1-1.5 1.5h-10A1.5 1.5 0 0 1 4 18.5v-10A1.5 1.5 0 0 1 5.5 7H10" />
  </Icon>
)

export const Pin = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 3.5a6 6 0 0 1 6 6c0 4.4-6 11-6 11s-6-6.6-6-11a6 6 0 0 1 6-6Z" />
    <path d="M12 3.5a6 6 0 0 1 6 6c0 4.4-6 11-6 11s-6-6.6-6-11a6 6 0 0 1 6-6Z" />
    <circle cx="12" cy="9.5" r="2.2" />
  </Icon>
)

export const Monitor = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M4.5 6a1.5 1.5 0 0 1 1.5-1.5h12A1.5 1.5 0 0 1 19.5 6v8a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 14Z" />
    <rect x="4.5" y="4.5" width="15" height="11" rx="1.5" />
    <path d="M9 19.5h6M12 15.5v4" />
  </Icon>
)

export const Bell = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M6.5 15.5V11a5.5 5.5 0 0 1 11 0v4.5l1.5 2h-14Z" />
    <path d="M6.5 15.5V11a5.5 5.5 0 0 1 11 0v4.5l1.5 2h-14Z" />
    <path d="M10.2 20a2 2 0 0 0 3.6 0M12 3.5v2" />
  </Icon>
)

export const Flame = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M12 3.5c.6 3 3.2 4.4 4.6 7a6 6 0 1 1-10.8 2.7c.3-1.6 1.2-2.8 2.4-3.6 0 1.6.7 2.6 1.8 3.1C9.6 9.4 10.6 6 12 3.5Z" />
    <path d="M12 3.5c.6 3 3.2 4.4 4.6 7a6 6 0 1 1-10.8 2.7c.3-1.6 1.2-2.8 2.4-3.6 0 1.6.7 2.6 1.8 3.1C9.6 9.4 10.6 6 12 3.5Z" />
    <path d="M12 20.5a2.6 2.6 0 0 1-2.6-2.6c0-1.6 1.4-2.4 2.6-4 1.2 1.6 2.6 2.4 2.6 4a2.6 2.6 0 0 1-2.6 2.6Z" />
  </Icon>
)

export const Layers = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="m12 4 8 4.2-8 4.2-8-4.2Z" />
    <path d="m12 4 8 4.2-8 4.2-8-4.2Z" />
    <path d="m4 12 8 4.2 8-4.2M4 15.8 12 20l8-4.2" />
  </Icon>
)

export const Hourglass = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M8 19.5c0-3 4-4.2 4-7.5 0 3.3 4 4.5 4 7.5Z" />
    <path d="M6.5 3.5h11M6.5 20.5h11M8 3.5c0 4 4 5 4 8.5s-4 4.5-4 8.5M16 3.5c0 4-4 5-4 8.5s4 4.5 4 8.5" />
  </Icon>
)

export const Share = (p: IconProps) => (
  <Icon {...p}>
    <Soft d="M5.5 11.5h13v7a1.5 1.5 0 0 1-1.5 1.5H7a1.5 1.5 0 0 1-1.5-1.5Z" />
    <path d="M8.5 11.5h-3v7A1.5 1.5 0 0 0 7 20h10a1.5 1.5 0 0 0 1.5-1.5v-7h-3" />
    <path d="M12 14.5V3.5M8.5 7 12 3.5 15.5 7" />
  </Icon>
)

/** Status glyphs: shape + colour + text label together, never colour alone. */
export const StatusGood = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <circle cx="12" cy="12" r="7" fill="currentColor" fillOpacity={0.18} />
    <path d="m8.8 12.2 2.2 2.2 4.2-4.4" />
  </Icon>
)
export const StatusMid = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <circle cx="12" cy="12" r="7" fill="currentColor" fillOpacity={0.18} />
    <path d="M8.5 12h7" />
  </Icon>
)
export const StatusWatch = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <path d="M12 5.5 19 18H5Z" fill="currentColor" fillOpacity={0.18} />
    <path d="M12 10.5v3M12 15.8h.01" />
  </Icon>
)
export const StatusPriority = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <path d="M12 4.5 19.5 12 12 19.5 4.5 12Z" fill="currentColor" fillOpacity={0.18} />
    <path d="M12 9v3.5M12 15h.01" />
  </Icon>
)
