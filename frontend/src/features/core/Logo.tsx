// The Standard Motion mark: a pick-and-place arc from where the object starts into the box it
// lands in. It takes the text colour, so it follows the theme; public/favicon.svg is the same mark.
export function Logo(props: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={props.className}
    >
      <circle cx="3.6" cy="19.2" r="2.2" fill="currentColor" stroke="none" />
      <path d="M3.6 17.2 C 4.8 5.6, 12.6 2.4, 16.4 13.6" />
      <path d="M12.4 15 V12.4 H15 M19 12.4 H21.6 V15 M21.6 19 V21.6 H19 M15 21.6 H12.4 V19" />
      <circle cx="17" cy="17" r="1.9" fill="currentColor" stroke="none" />
    </svg>
  );
}
