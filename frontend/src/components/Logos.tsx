// Brand glyphs for conda + PyPI used wherever a colored dot used to live.
// Sized via the size prop; both paths use their own ecosystem colors so they
// read correctly against any background.

interface Props {
  size?: number;
  className?: string;
}

/**
 * Conda — green circle with a white "C". Conda's actual mark is a stylized
 * snake-swirl that's hard to read at ~12px, so we use the established
 * "green C" simplification that ships in many of conda's product surfaces.
 */
export function CondaLogo({ size = 14, className }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      className={className}
    >
      <circle cx="16" cy="16" r="15" fill="#43B02A" />
      <path
        d="M21.5 11.5 a7 7 0 1 0 0 9"
        stroke="white"
        strokeWidth="3.25"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * PyPI = the canonical Python two-snake logo. The blue head + yellow tail
 * are the iconic colors of the Python brand mark used across PyPI surfaces.
 */
export function PypiLogo({ size = 14, className }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 256 256"
      aria-hidden="true"
      className={className}
    >
      <path
        fill="#3776AB"
        d="M126.916.072c-64.832 0-60.784 28.115-60.784 28.115l.072 29.128h61.868v8.745H41.631S.145 61.355.145 126.77c0 65.417 36.21 63.097 36.21 63.097h21.61v-30.358s-1.165-36.21 35.632-36.21h61.362s34.475.557 34.475-33.319V33.97S194.67.072 126.916.072zM92.802 19.66a11.12 11.12 0 0 1 11.13 11.13 11.12 11.12 0 0 1-11.13 11.13 11.12 11.12 0 0 1-11.13-11.13 11.12 11.12 0 0 1 11.13-11.13z"
      />
      <path
        fill="#FFD43B"
        d="M128.757 254.126c64.832 0 60.784-28.115 60.784-28.115l-.072-29.127H127.6v-8.745h86.441s41.486 4.705 41.486-60.712c0-65.416-36.21-63.096-36.21-63.096h-21.61v30.357s1.165 36.21-35.632 36.21h-61.362s-34.475-.557-34.475 33.32v56.013s-5.235 33.895 62.518 33.895zm34.114-19.586a11.12 11.12 0 0 1-11.13-11.13 11.12 11.12 0 0 1 11.13-11.131 11.12 11.12 0 0 1 11.13 11.13 11.12 11.12 0 0 1-11.13 11.13z"
      />
    </svg>
  );
}

export function SideLogo({
  kind,
  size = 14,
  className,
}: {
  kind: "conda" | "pypi";
  size?: number;
  className?: string;
}) {
  return kind === "conda" ? (
    <CondaLogo size={size} className={className} />
  ) : (
    <PypiLogo size={size} className={className} />
  );
}
