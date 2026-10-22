/**
 * TechTaru DocIQ brand mark.
 * Gradient tile + document glyph with a detached extraction node —
 * "unstructured document → structured data". Pure SVG (crisp at any
 * resolution); used in the header, empty state and favicon.
 */
export default function Logo({ size = 36, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="TechTaru DocIQ"
      role="img"
    >
      <defs>
        <linearGradient id="ttTile" x1="4" y1="2" x2="44" y2="46" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#6366F1" />
          <stop offset="0.55" stopColor="#7C3AED" />
          <stop offset="1" stopColor="#D946EF" />
        </linearGradient>
        <radialGradient id="ttGlow" cx="0.28" cy="0.18" r="0.9">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.32" />
          <stop offset="0.55" stopColor="#FFFFFF" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="ttSheet" x1="13" y1="10" x2="32" y2="36" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#FFFFFF" />
          <stop offset="1" stopColor="#EDE9FE" />
        </linearGradient>
      </defs>

      {/* tile */}
      <rect x="1.5" y="1.5" width="45" height="45" rx="12.5" fill="url(#ttTile)" />
      <rect x="1.5" y="1.5" width="45" height="45" rx="12.5" fill="url(#ttGlow)" />
      <rect x="1.9" y="1.9" width="44.2" height="44.2" rx="12.2" stroke="#FFFFFF" strokeOpacity="0.22" strokeWidth="0.8" fill="none" />

      {/* document sheet with folded corner */}
      <path
        d="M13.5 10.5 h13 a2.5 2.5 0 0 1 1.77 0.73 l4.5 4.5 a2.5 2.5 0 0 1 0.73 1.77 v17 a2.5 2.5 0 0 1 -2.5 2.5 h-17.5 a2.5 2.5 0 0 1 -2.5 -2.5 V13 a2.5 2.5 0 0 1 2.5 -2.5 Z"
        fill="url(#ttSheet)"
      />
      <path d="M27.5 10.73 v4.27 a2.5 2.5 0 0 0 2.5 2.5 h4.27 Z" fill="#C4B5FD" opacity="0.85" />

      {/* content lines */}
      <rect x="16" y="18.2" width="11.5" height="2.3" rx="1.15" fill="#7C3AED" opacity="0.5" />
      <rect x="16" y="22.6" width="7.5" height="2.3" rx="1.15" fill="#7C3AED" opacity="0.4" />
      <rect x="16" y="27" width="11.5" height="2.3" rx="1.15" fill="#7C3AED" opacity="0.3" />

      {/* extraction node + connective beam */}
      <path d="M29.5 32.5 L33.2 35.4" stroke="#FFFFFF" strokeWidth="2.6" strokeLinecap="round" opacity="0.9" />
      <circle cx="37.2" cy="37.2" r="3.4" fill="#FFFFFF" opacity="0.95" />
      <circle cx="37.2" cy="37.2" r="1.5" fill="#A855F7" />
    </svg>
  );
}
