// LegitLex — iconography + the verdict Seal (the signature visual).

// ── Line icon set (civic, 24px, currentColor stroke) ─────────────────────────
const ICON_PATHS = {
  pin:      '<path d="M12 21s7-5.5 7-11a7 7 0 1 0-14 0c0 5.5 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/>',
  crosshair:'<circle cx="12" cy="12" r="7"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/><circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/>',
  bike:     '<circle cx="6" cy="16" r="3.2"/><circle cx="18" cy="16" r="3.2"/><path d="M6 16l4-7h5l-3 7M9.5 9h3.5M14 9l2.5 7"/>',
  paw:      '<circle cx="8" cy="9" r="1.6"/><circle cx="16" cy="9" r="1.6"/><circle cx="5.5" cy="13" r="1.4"/><circle cx="18.5" cy="13" r="1.4"/><path d="M12 13c-2.5 0-4.5 1.8-4.5 3.8C7.5 18.6 9.4 19.5 12 19.5s4.5-.9 4.5-2.7C16.5 14.8 14.5 13 12 13Z"/>',
  wave:     '<path d="M3 12h2.5M18.5 12H21M7 8v8M11 5v14M15 8v8"/>',
  car:      '<path d="M5 16v2M19 16v2M4 13l1.6-4.2A2 2 0 0 1 7.5 7.5h9a2 2 0 0 1 1.9 1.3L20 13M4 13h16v3H4z"/><circle cx="7.5" cy="13.5" r=".4" fill="currentColor" stroke="none"/><circle cx="16.5" cy="13.5" r=".4" fill="currentColor" stroke="none"/>',
  drone:    '<rect x="9" y="9" width="6" height="6" rx="1.2"/><path d="M9 9 6 6M15 9l3-3M9 15l-3 3M15 15l3 3"/><circle cx="5" cy="5" r="1.8"/><circle cx="19" cy="5" r="1.8"/><circle cx="5" cy="19" r="1.8"/><circle cx="19" cy="19" r="1.8"/>',
  camera:   '<path d="M4 8h3l1.5-2h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z"/><circle cx="12" cy="13" r="3.4"/>',
  scan:     '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2M4 12h16"/>',
  scales:   '<path d="M12 4v16M7 20h10M5 8h14M5 8l-2.5 5h5L5 8ZM19 8l-2.5 5h5L19 8Z"/><circle cx="12" cy="4.5" r="1.2"/>',
  check:    '<path d="M5 12.5 10 17.5 19 7" stroke-width="2.2"/>',
  cross:    '<path d="M7 7l10 10M17 7 7 17" stroke-width="2.2"/>',
  bang:     '<path d="M12 6v8" stroke-width="2.2"/><circle cx="12" cy="18" r="1.1" fill="currentColor" stroke="none"/>',
  query:    '<path d="M9 9a3 3 0 1 1 4.5 2.6c-1 .6-1.5 1.2-1.5 2.4" stroke-width="2"/><circle cx="12" cy="18" r="1.1" fill="currentColor" stroke="none"/>',
  chevron:  '<path d="M9 6l6 6-6 6"/>',
  chevL:    '<path d="M15 6l-6 6 6 6"/>',
  arrowR:   '<path d="M5 12h14M13 6l6 6-6 6"/>',
  arrowUp:  '<path d="M12 19V5M6 11l6-6 6 6"/>',
  map:      '<path d="M9 5 4 7v12l5-2 6 2 5-2V5l-5 2-6-2ZM9 5v12M15 7v12"/>',
  doc:      '<path d="M7 3h7l4 4v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>',
  gear:     '<circle cx="12" cy="12" r="3"/><path d="M12 2.5v2.5M12 19v2.5M4.6 4.6l1.8 1.8M17.6 17.6l1.8 1.8M2.5 12H5M19 12h2.5M4.6 19.4l1.8-1.8M17.6 6.4l1.8-1.8"/>',
  search:   '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4-4"/>',
  plus:     '<path d="M12 5v14M5 12h14"/>',
  info:     '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5"/><circle cx="12" cy="8" r="1" fill="currentColor" stroke="none"/>',
  share:    '<path d="M12 15V4M8 8l4-4 4 4M5 13v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/>',
  download: '<path d="M12 4v11M8 11l4 4 4-4M5 20h14"/>',
  clock:    '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  layers:   '<path d="M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5M3 17l9 5 9-5" stroke-width="1.5"/>',
  building: '<path d="M5 21V6l7-3 7 3v15M5 21h14M9 9h2M13 9h2M9 13h2M13 13h2M9 17h2M13 17h2"/>',
  flag:     '<path d="M5 21V4M5 4h11l-1.5 3L16 10H5"/>',
  bookmark: '<path d="M7 4h10a1 1 0 0 1 1 1v15l-6-3.5L6 20V5a1 1 0 0 1 1-1Z"/>',
  sliders:  '<path d="M5 8h8M17 8h2M5 16h2M11 16h8"/><circle cx="15" cy="8" r="2"/><circle cx="9" cy="16" r="2"/>',
  bolt:     '<path d="M13 3 5 14h6l-1 7 8-11h-6l1-7Z"/>',
  shield:   '<path d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6l7-3Z"/><path d="M9 12l2 2 4-4"/>',
  lock:     '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  ext:      '<path d="M14 5h5v5M19 5l-8 8M11 5H6a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"/>',
  spark:    '<path d="M12 3l1.6 5.4L19 10l-5.4 1.6L12 17l-1.6-5.4L5 10l5.4-1.6L12 3Z"/>',
  refresh:  '<path d="M4 12a8 8 0 0 1 14-5.3L20 8M20 4v4h-4M20 12a8 8 0 0 1-14 5.3L4 16M4 20v-4h4"/>',
  bell:     '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4l2-2ZM10 20a2 2 0 0 0 4 0"/>',
  mic:      '<rect x="9.5" y="3.5" width="5" height="11" rx="2.5"/><path d="M6 11a6 6 0 0 0 12 0M12 17v3.5M9 21h6"/>',
  image:    '<rect x="4" y="5" width="16" height="14" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M5 17l4.5-4 3 2.5L16 11l3 3"/>',
  target:   '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="1" fill="currentColor" stroke="none"/>',
  history:  '<path d="M4 12a8 8 0 1 1 2.4 5.7M4 12H7M4 12V9"/><path d="M12 8v4l3 2"/>',
  copy:     '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  edit:     '<path d="M5 19h3l9-9-3-3-9 9v3ZM14 6l3 3"/>',
};

function Icon({ name, size = 22, color = 'currentColor', strokeWidth = 1.7, style = {} }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, display: 'block', ...style }}
      dangerouslySetInnerHTML={{ __html: ICON_PATHS[name] || '' }} />
  );
}

// ── The Seal ────────────────────────────────────────────────────────────────
// A rubber-stamp verdict mark: double ring, circular legend, big verdict word.
// Color comes from the verdict; slight rotation + turbulence = inked, official.
let _sealSeq = 0;
function Seal({ verdict = 'warning', size = 230, rotate = -7, jurisdiction = 'IRVINE · CA', date = '14 JUN 2026', flat = false, inked = true }) {
  const meta = (window.VERDICT_META || {})[verdict] || window.VERDICT_META.unknown;
  const uid = React.useMemo(() => 'seal' + (_sealSeq++), []);
  const c = `var(${meta.varc})`;
  const C = 120;
  const glyphPaths = {
    check: 'M-15 2 L-5 12 L16 -12',
    cross: 'M-12 -12 L12 12 M12 -12 L-12 12',
    bang:  'M0 -15 L0 4 M0 13 L0 13',
    query: 'M-7 -8 a8 8 0 1 1 8.5 13 c-2 1.2 -2.5 2.2 -2.5 5 M0 15 L0 15',
  };
  const topText = '★  LEGITLEX  COMPLIANCE  CHECK  ★';
  const weathered = inked && !flat;
  // fine tick ring (rosette) between the outer band and the inner circle
  const ticks = [];
  for (let i = 0; i < 84; i++) {
    const a = (i / 84) * Math.PI * 2;
    const r1 = 104, r2 = i % 7 === 0 ? 97 : 100;
    ticks.push(
      <line key={i} x1={C + r1 * Math.cos(a)} y1={C + r1 * Math.sin(a)}
        x2={C + r2 * Math.cos(a)} y2={C + r2 * Math.sin(a)}
        stroke={c} strokeWidth={i % 7 === 0 ? 1.4 : 0.7} opacity={weathered ? 0.5 : 0.65} />
    );
  }
  return (
    <svg viewBox="0 0 240 240" width={size} height={size}
      style={{ transform: `rotate(${flat ? 0 : rotate}deg)`, overflow: 'visible', display: 'block',
        filter: flat ? undefined : 'drop-shadow(0 1px 0 rgba(255,255,255,.5))' }}
      aria-label={`Verdict: ${meta.word}`}>
      <defs>
        <path id={uid + '-top'} d="M 40,120 A 80,80 0 0 1 200,120" fill="none" />
        <path id={uid + '-bot'} d="M 44,120 A 76,76 0 0 0 196,120" fill="none" />
      </defs>
      <g fill="none" stroke={c} opacity={weathered ? 0.92 : 1}>
        <circle cx={C} cy={C} r="114" strokeWidth="1.2" opacity={weathered ? 0.5 : 0.7} />
        <circle cx={C} cy={C} r="109" strokeWidth="3.4"
          strokeDasharray={weathered ? '40 1.1' : undefined} strokeLinecap="round" />
        <circle cx={C} cy={C} r="86" strokeWidth="1" opacity={weathered ? 0.55 : 0.75} />
        {ticks}
        <circle cx={C} cy={C} r="66" strokeWidth="1.6"
          strokeDasharray={weathered ? '28 1' : undefined} strokeLinecap="round" />
        <circle cx={C} cy={C} r="62" strokeWidth="0.8" opacity={weathered ? 0.5 : 0.65} />
        {/* circular legends */}
        <text fill={c} stroke="none" fontFamily="var(--font-ui)" fontWeight="700"
              fontSize="11.5" letterSpacing="2.4">
          <textPath href={`#${uid}-top`} startOffset="50%" textAnchor="middle">{topText}</textPath>
        </text>
        <text fill={c} stroke="none" fontFamily="var(--font-ui)" fontWeight="700"
              fontSize="11" letterSpacing="2.8">
          <textPath href={`#${uid}-bot`} startOffset="50%" textAnchor="middle">{jurisdiction}</textPath>
        </text>
        {/* divider stars between legends */}
        <text fill={c} stroke="none" fontSize="12" x="20" y="124" textAnchor="middle">✦</text>
        <text fill={c} stroke="none" fontSize="12" x="220" y="124" textAnchor="middle">✦</text>
        {/* center glyph */}
        <g transform={`translate(${C}, 84)`} stroke={c} strokeWidth="4.4" strokeLinecap="round" strokeLinejoin="round">
          <path d={glyphPaths[meta.glyph]} />
        </g>
        {/* verdict word */}
        <text x={C} y="138" textAnchor="middle" fill={c} stroke="none"
              fontFamily="var(--font-legal)" fontWeight="800"
              fontSize={meta.word.length > 9 ? 26 : 31} letterSpacing="0.5">{meta.word}</text>
        {/* date line */}
        <text x={C} y="162" textAnchor="middle" fill={c} stroke="none"
              fontFamily="var(--font-mono)" fontWeight="500" fontSize="11" letterSpacing="1.5"
              opacity="0.85">{date}</text>
      </g>
    </svg>
  );
}

Object.assign(window, { Icon, Seal, ICON_PATHS });
