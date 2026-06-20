// LegitLex — shared chrome: app bar, tab bar, buttons, badges, citation cards.

const TABS = [
  { id: 'ask',      icon: 'scales',  label: 'Ask' },
  { id: 'scan',     icon: 'scan',    label: 'Scan' },
  { id: 'coverage', icon: 'map',     label: 'Coverage' },
  { id: 'records',  icon: 'doc',     label: 'Records' },
  { id: 'settings', icon: 'gear',    label: 'Settings' },
];

// ── Screen scaffold ──────────────────────────────────────────────────────────
function Screen({ children, tab, onNav, dark, style = {}, bg = 'var(--paper)' }) {
  return (
    <div className="ll-screen" style={{ background: bg, ...style }}>
      <div className="ll-screen-body">{children}</div>
      {tab && <TabBar active={tab} onNav={onNav} dark={dark} />}
    </div>
  );
}

// scrollable region
function Scroll({ children, style = {}, padBottom = 24, className = '' }) {
  return (
    <div className={'ll-scroll ' + className} style={{ paddingBottom: padBottom, ...style }}>
      {children}
    </div>
  );
}

// ── App bar ──────────────────────────────────────────────────────────────────
function AppBar({ title, eyebrow, left, right, border = true, bg = 'var(--paper)', color = 'var(--ink)' }) {
  return (
    <div className="ll-appbar" style={{ background: bg, borderBottom: border ? '1px solid var(--line)' : 'none' }}>
      <div className="ll-appbar-side" style={{ justifyContent: 'flex-start' }}>{left}</div>
      <div className="ll-appbar-title" style={{ color }}>
        {eyebrow && <div className="ll-appbar-eyebrow">{eyebrow}</div>}
        <div>{title}</div>
      </div>
      <div className="ll-appbar-side" style={{ justifyContent: 'flex-end' }}>{right}</div>
    </div>
  );
}

function IconBtn({ name, onClick, active = false, color, size = 21, title, soft = false }) {
  return (
    <button className={'ll-iconbtn' + (active ? ' is-active' : '') + (soft ? ' is-soft' : '')}
      onClick={onClick} aria-label={title} title={title}>
      <Icon name={name} size={size} color={color || 'currentColor'} />
    </button>
  );
}

function BackBtn({ onClick, label = 'Back' }) {
  return (
    <button className="ll-back" onClick={onClick}>
      <Icon name="chevL" size={20} />
      <span>{label}</span>
    </button>
  );
}

// ── Tab bar ──────────────────────────────────────────────────────────────────
function TabBar({ active, onNav }) {
  return (
    <nav className="ll-tabbar">
      {TABS.map(t => {
        const on = active === t.id;
        return (
          <button key={t.id} className={'ll-tab' + (on ? ' is-on' : '')} onClick={() => onNav(t.id)}>
            <Icon name={t.icon} size={23} strokeWidth={on ? 2 : 1.7} />
            <span>{t.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

// ── Buttons & chips ──────────────────────────────────────────────────────────
function Button({ children, onClick, variant = 'primary', icon, iconRight, full, size = 'md', disabled, style = {} }) {
  return (
    <button className={`ll-btn ll-btn-${variant} ll-btn-${size}` + (full ? ' is-full' : '')}
      onClick={onClick} disabled={disabled} style={style}>
      {icon && <Icon name={icon} size={size === 'lg' ? 21 : 18} />}
      <span>{children}</span>
      {iconRight && <Icon name={iconRight} size={size === 'lg' ? 21 : 18} />}
    </button>
  );
}

function Chip({ children, onClick, icon, active }) {
  return (
    <button className={'ll-chip' + (active ? ' is-active' : '')} onClick={onClick}>
      {icon && <Icon name={icon} size={16} />}
      <span>{children}</span>
    </button>
  );
}

// ── Cards & labels ───────────────────────────────────────────────────────────
function Card({ children, style = {}, pad = 18, onClick, className = '' }) {
  return (
    <div className={'ll-card ' + className} onClick={onClick}
      style={{ padding: pad, cursor: onClick ? 'pointer' : 'default', ...style }}>
      {children}
    </div>
  );
}

function SectionLabel({ children, right }) {
  return (
    <div className="ll-seclabel">
      <span>{children}</span>
      {right}
    </div>
  );
}

const LEVELS = {
  city:    { label: 'CITY',    icon: 'building' },
  county:  { label: 'COUNTY',  icon: 'layers' },
  state:   { label: 'STATE',   icon: 'flag' },
  federal: { label: 'FEDERAL', icon: 'shield' },
  unknown: { label: 'UNKNOWN', icon: 'info' },
};

function LevelBadge({ level }) {
  const m = LEVELS[level] || LEVELS.unknown;
  return (
    <span className={'ll-level ll-level-' + level}>
      <Icon name={m.icon} size={12} strokeWidth={1.9} />
      {m.label}
    </span>
  );
}

function VerdictTag({ verdict, size = 'md' }) {
  const m = (window.VERDICT_META || {})[verdict] || window.VERDICT_META.unknown;
  return (
    <span className={'ll-vtag ll-vtag-' + size} style={{ color: `var(${m.varc})`, background: `var(${m.varc}` + '-soft, transparent)' }}>
      <span className="ll-vtag-dot" style={{ background: `var(${m.varc})` }} />
      {m.label}
    </span>
  );
}

// ── Confidence meter ─────────────────────────────────────────────────────────
function Confidence({ value, varc = '--ink' }) {
  const pct = Math.round((value || 0) * 100);
  const word = pct === 0 ? 'No basis' : pct < 55 ? 'Low' : pct < 80 ? 'Moderate' : 'High';
  return (
    <div className="ll-conf">
      <div className="ll-conf-head">
        <span className="ll-conf-label">Confidence</span>
        <span className="ll-conf-val" style={{ color: `var(${varc})` }}>{word} · {pct}%</span>
      </div>
      <div className="ll-conf-track">
        <div className="ll-conf-fill" style={{ width: Math.max(pct, 2) + '%', background: `var(${varc})` }} />
        {[25, 50, 75].map(t => <div key={t} className="ll-conf-tick" style={{ left: t + '%' }} />)}
      </div>
    </div>
  );
}

// ── Recency badge: flags recently-amended law ────────────────────────────────
function RecencyBadge({ year }) {
  const y = parseInt(year, 10);
  if (!y || y < 1900) return null;
  const recent = y >= (new Date().getFullYear() - 3);
  return (
    <span className="ll-recency" style={{
      color: recent ? 'var(--warn)' : 'var(--ink-3)',
      background: recent ? 'var(--warn-soft, var(--surface-2))' : 'var(--surface-2)',
    }}>
      {recent ? '🆕 ' : ''}{recent ? 'Updated ' : 'Amended '}{y}
    </span>
  );
}

// ── Citation card ────────────────────────────────────────────────────────────
function CitationCard({ c, index, defaultOpen = false }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="ll-cite">
      <div className="ll-cite-top">
        <LevelBadge level={c.level} />
        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <RecencyBadge year={c.last_amended} />
          <span className="ll-cite-sid">§ {c.section_id}</span>
        </span>
      </div>
      <div className="ll-cite-name">{c.section_name}</div>
      <p className="ll-cite-para">{c.paraphrase}</p>
      {open && (
        <div className="ll-cite-source">
          <div className="ll-cite-quote">“{c.preview}”</div>
          <div className="ll-cite-meta">
            <Icon name="doc" size={13} />
            <span>{c.source}{c.page ? ` · p.${c.page}` : ''} · {c.jurisdiction}</span>
          </div>
        </div>
      )}
      <button className="ll-cite-toggle" onClick={() => setOpen(o => !o)}>
        <Icon name={open ? 'arrowUp' : 'doc'} size={14} />
        {open ? 'Hide source text' : 'Read the section'}
      </button>
    </div>
  );
}

// ── Penalty card ─────────────────────────────────────────────────────────────
const PENALTY_META = {
  none:        { label: 'No penalty',      varc: '--yes' },
  infraction:  { label: 'Infraction',      varc: '--warn' },
  civil:       { label: 'Civil liability', varc: '--warn' },
  misdemeanor: { label: 'Misdemeanor',     varc: '--no' },
  felony:      { label: 'Felony',          varc: '--no' },
  unknown:     { label: 'Not specified',   varc: '--unknown' },
};

function PenaltyCard({ penalty, severity }) {
  const sev = severity || 'unknown';
  if (sev === 'none' || !penalty) return null;     // nothing to warn about
  const m = PENALTY_META[sev] || PENALTY_META.unknown;
  return (
    <div className="ll-penalty" style={{ borderLeftColor: `var(${m.varc})` }}>
      <div className="ll-penalty-head">
        <Icon name="bang" size={14} color={`var(${m.varc})`} strokeWidth={2.3} />
        <span>If you do it anyway</span>
        <span className="ll-penalty-chip"
          style={{ color: `var(${m.varc})`, background: `var(${m.varc}-soft, var(--surface-2))` }}>
          {m.label}
        </span>
      </div>
      <p className="ll-penalty-text">{penalty}</p>
    </div>
  );
}

// ── Jurisdiction stack: which layers were consulted for this answer ──────────
function JurisStack({ citations }) {
  const order = ['city', 'county', 'state', 'federal'];
  const used = new Set((citations || []).map(c => c.level));
  return (
    <div className="ll-jstack">
      {order.map(lv => {
        const on = used.has(lv);
        const m = (window.LEVELS || LEVELS)[lv] || LEVELS.unknown;
        return (
          <div key={lv} className={'ll-jstack-row' + (on ? ' is-on' : '')}>
            <span className="ll-jstack-ic"><Icon name={m.icon} size={14} /></span>
            <span className="ll-jstack-lbl">{m.label}</span>
            <span className="ll-jstack-state">{on ? 'consulted' : 'no rule'}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Misc ─────────────────────────────────────────────────────────────────────
function LocChip({ onClick, compact }) {
  const L = window.LOCATION;
  return (
    <button className={'ll-locchip' + (compact ? ' is-compact' : '')} onClick={onClick}>
      <span className="ll-locchip-dot" />
      <Icon name="pin" size={15} />
      <span className="ll-locchip-text">{L.city}, {L.state}</span>
      {!compact && <Icon name="chevron" size={14} style={{ opacity: 0.5 }} />}
    </button>
  );
}

function Disclaimer({ compact }) {
  return (
    <div className={'ll-disclaimer' + (compact ? ' is-compact' : '')}>
      <Icon name="info" size={14} />
      <span>{window.DISCLAIMER}</span>
    </div>
  );
}

function Spinner({ size = 20, color = 'currentColor' }) {
  return <span className="ll-spinner" style={{ width: size, height: size, borderColor: color, borderTopColor: 'transparent' }} />;
}

Object.assign(window, {
  TABS, Screen, Scroll, AppBar, IconBtn, BackBtn, TabBar, Button, Chip, Card,
  SectionLabel, LevelBadge, VerdictTag, Confidence, CitationCard, LocChip,
  Disclaimer, Spinner, LEVELS, PenaltyCard, PENALTY_META, RecencyBadge, JurisStack,
});
