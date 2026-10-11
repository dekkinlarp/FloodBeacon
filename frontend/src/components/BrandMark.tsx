/** FloodBeacon mark: a beacon ring, half full of water. Same geometry as public/favicon.svg. */
export function BrandMark({ size = 24 }: { size?: number }) {
  return (
    <svg className="topbar__logo" width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <clipPath id="brandmark-water">
        <circle cx="16" cy="16" r="9.5" />
      </clipPath>
      <rect x="6" y="17" width="20" height="10" fill="#38bdf8" fillOpacity={0.55} clipPath="url(#brandmark-water)" />
      <circle cx="16" cy="16" r="12" fill="none" stroke="#38bdf8" strokeWidth={4} />
    </svg>
  );
}
