// LegitLex — Coverage map, Records, Settings.

// ── Stylized jurisdiction map ────────────────────────────────────────────────
function JurisMap() {
  const L = window.LOCATION;
  return (
    <div className="ll-map">
      <svg className="ll-map-grid" viewBox="0 0 360 220" preserveAspectRatio="xMidYMid slice">
        {/* parks / open space */}
        <path d="M-10 150 Q 60 120 120 160 T 260 150 L 380 180 L 380 240 L -10 240 Z" fill="var(--map-park)" />
        <ellipse cx="280" cy="55" rx="70" ry="40" fill="var(--map-park)" opacity="0.7" />
        {/* water */}
        <path d="M0 40 Q 80 70 160 45 T 360 60 L 360 0 L 0 0 Z" fill="var(--map-water)" opacity="0.55" />
        {/* street grid */}
        <g stroke="var(--map-road)" strokeWidth="6" opacity="0.9" strokeLinecap="round">
          <path d="M40 -10 L70 230" /><path d="M150 -10 L150 230" /><path d="M250 -20 L290 230" />
          <path d="M-10 70 L370 60" /><path d="M-10 150 L370 165" />
        </g>
        <g stroke="var(--map-road2)" strokeWidth="2.5" opacity="0.8">
          <path d="M95 -10 L110 230" /><path d="M200 -10 L205 230" /><path d="M-10 110 L370 112" /><path d="M-10 195 L370 205" />
        </g>
        {/* jurisdiction boundary */}
        <rect x="14" y="14" width="332" height="192" rx="14" fill="none"
          stroke="var(--primary)" strokeWidth="2" strokeDasharray="2 7" opacity="0.65" />
      </svg>
      <div className="ll-map-boundary-lbl"><Icon name="building" size={12} /> {L.city ? `City of ${L.city}` : 'Your area'}</div>
      {/* user pin */}
      <div className="ll-map-pin">
        <span className="ll-map-acc" />
        <span className="ll-map-dot" />
      </div>
      <div className="ll-map-where">
        <Icon name="crosshair" size={14} color="var(--primary)" />
        <span><strong>{[L.city, L.county].filter(Boolean).join(', ') || 'Unknown'}</strong> · {L.state}</span>
      </div>
    </div>
  );
}

const STATUS_META = {
  complete: { label: 'Complete', cls: 'ok' },
  partial:  { label: 'Partial',  cls: 'partial' },
  missing:  { label: 'Missing',  cls: 'missing' },
};

const LEVEL_NAMES = { city: 'City', county: 'County', state: 'State', federal: 'Federal' };

function CoverageScreen({ onNav }) {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [err, setErr] = React.useState('');

  const load = React.useCallback(() => {
    if (!(window.LL_LIVE && window.LL_API && typeof window.LL_API.coverage === 'function')) {
      setLoading(false);   // demo mode / older client: fall back to bundled mock
      return;
    }
    setLoading(true); setErr('');
    Promise.resolve()
      .then(() => window.LL_API.coverage(window.LOCATION))
      .then(d => { setData(d); setLoading(false); })
      .catch(e => { setErr(e.message || 'failed'); setLoading(false); });
  }, []);
  React.useEffect(() => { load(); }, [load]);

  // Build the rows: live data if available, else the bundled mock.
  const live = data && data.sources;
  const sources = live ? data.sources : window.COVERAGE.map(c => ({
    level: c.level, source_title: c.name, sections: c.sections, status: c.status,
  }));
  const totalSections = live ? data.total_sections : sources.reduce((n, c) => n + (c.sections || 0), 0);
  const sourceCount = live ? sources.filter(s => s.sections > 0).length : sources.filter(s => s.status !== 'missing').length;
  const missing = live ? (data.missing_levels || []) : ['county'];
  const L = window.LOCATION;

  return (
    <Screen tab="coverage" onNav={onNav}>
      <AppBar left={<div className="ll-appbar-h1">Coverage</div>} title="" border={false}
        right={<IconBtn name="refresh" title="Refresh" onClick={load} />} />
      <Scroll padBottom={96}>
        <JurisMap />

        {loading ? (
          <div className="ll-think" style={{ padding: '40px 0' }}>
            <Spinner size={26} color="var(--primary)" />
            <div className="ll-think-q" style={{ fontSize: 15 }}>Checking what law we have for {L.city || 'your area'}…</div>
          </div>
        ) : (
          <React.Fragment>
            <div className="ll-cov-summary">
              <div className="ll-cov-stat"><b>{sourceCount}</b><span>sources cover {L.city || 'this spot'}</span></div>
              <div className="ll-cov-divider" />
              <div className="ll-cov-stat"><b>{(totalSections || 0).toLocaleString()}</b><span>sections searchable here</span></div>
            </div>

            {err ? <div className="ll-cov-gap"><Icon name="info" size={16} /><span>Couldn’t load live coverage ({err}).</span></div> : null}

            <SectionLabel>Legal layers at {[L.city, L.state].filter(Boolean).join(', ') || 'your location'}</SectionLabel>
            <div className="ll-cov-list">
              {sources.length === 0 ? (
                <div className="ll-cov-row"><span>No law ingested for this location yet.</span></div>
              ) : sources.map((c, i) => (
                <div key={i} className="ll-cov-row">
                  <span className={'ll-cov-ic ll-level-' + c.level}><Icon name={(window.LEVELS[c.level] || {}).icon} size={18} /></span>
                  <div className="ll-cov-main">
                    <div className="ll-cov-name">{c.source_title}</div>
                    <div className="ll-cov-sub">
                      <LevelBadge level={c.level} />
                      <span>{(c.sections || 0).toLocaleString()} sections</span>
                    </div>
                  </div>
                  <span className="ll-status ll-status-ok">Active</span>
                </div>
              ))}
            </div>

            {missing.length > 0 && (
              <div className="ll-cov-gap">
                <Icon name="info" size={16} />
                <span>No <strong>{missing.map(m => LEVEL_NAMES[m] || m).join(' / ')}</strong>-level law is ingested for this location yet — verdicts won’t reflect those layers until it’s added.</span>
              </div>
            )}
          </React.Fragment>
        )}
        <Disclaimer compact />
      </Scroll>
    </Screen>
  );
}

// ── Records / history (real, on-device evidence trail) ───────────────────────
function relTime(ts) {
  if (!ts) return '';
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return Math.floor(s / 60) + ' min ago';
  if (s < 86400) return Math.floor(s / 3600) + ' hr ago';
  const d = new Date(ts);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

const RISK_GLYPH = { low: 'check', medium: 'bang', high: 'bang', critical: 'cross', unknown: 'query' };

function RecordsScreen({ onOpen, onNav }) {
  const [recs, setRecs] = React.useState(window.LL_RECORDS ? window.LL_RECORDS.all() : []);
  const refresh = () => setRecs(window.LL_RECORDS ? window.LL_RECORDS.all() : []);
  React.useEffect(() => { refresh(); }, []);

  const openSnap = (r) => {
    if (r.snapshot_id && window.LL_API) window.open(window.LL_API.snapshotUrl(r.snapshot_id), '_blank');
  };
  const clearAll = () => { if (window.LL_RECORDS) { window.LL_RECORDS.clear(); refresh(); } };

  return (
    <Screen tab="records" onNav={onNav}>
      <AppBar left={<div className="ll-appbar-h1">Records</div>} title="" border={false}
        right={recs.length ? <IconBtn name="cross" title="Clear all" onClick={clearAll} /> : null} />
      <Scroll padBottom={96}>
        <p className="ll-records-intro">Every verdict and complaint you run is saved here as a timestamped, citation-bearing snapshot — your private evidence trail, stored only on this device.</p>

        {recs.length === 0 ? (
          <Card className="ll-nocite" style={{ marginTop: 8 }}>
            <Icon name="doc" size={18} color="var(--ink-3)" />
            <span>No records yet. Ask a question or analyze a complaint, and it’ll be saved here automatically.</span>
          </Card>
        ) : (
          <div className="ll-rec-list">
            {recs.map(r => {
              const isCmp = r.kind === 'complaint';
              const meta = isCmp ? (window.RISK_META[r.risk] || window.RISK_META.unknown)
                                 : (window.VERDICT_META[r.verdict] || window.VERDICT_META.unknown);
              const glyph = isCmp ? (RISK_GLYPH[r.risk] || 'query')
                                  : (meta.glyph === 'check' ? 'check' : meta.glyph === 'cross' ? 'cross' : meta.glyph === 'bang' ? 'bang' : 'query');
              return (
                <button key={r.id} className="ll-rec" onClick={() => openSnap(r)}>
                  <span className="ll-rec-seal" style={{ borderColor: `var(${meta.varc})`, color: `var(${meta.varc})` }}>
                    <Icon name={glyph} size={16} strokeWidth={2.3} />
                  </span>
                  <div className="ll-rec-main">
                    <div className="ll-rec-label">{r.label}</div>
                    <div className="ll-rec-sub">
                      <Icon name={isCmp ? 'doc' : 'pin'} size={12} /> {r.where || '—'} · {relTime(r.ts)}
                    </div>
                  </div>
                  <div className="ll-rec-right">
                    <span className={'ll-status ' + (isCmp ? 'll-status-partial' : 'll-status-ok')} style={{ color: `var(${meta.varc})`, background: `var(${meta.varc}-soft, var(--surface-2))` }}>
                      {isCmp ? (meta.label || r.risk) : (window.VERDICT_META[r.verdict] || {}).label}
                    </span>
                    <span className="ll-rec-id mono">{r.id}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
        <Disclaimer compact />
      </Scroll>
    </Screen>
  );
}

// ── Settings ─────────────────────────────────────────────────────────────────
function SettingsRow({ icon, title, detail, control, last, onClick, danger }) {
  return (
    <div className={'ll-set-row' + (last ? ' is-last' : '')} onClick={onClick} style={{ cursor: onClick ? 'pointer' : 'default' }}>
      {icon && <span className="ll-set-ic"><Icon name={icon} size={17} /></span>}
      <span className={'ll-set-title' + (danger ? ' is-danger' : '')}>{title}</span>
      {detail && <span className="ll-set-detail">{detail}</span>}
      {control}
      {onClick && !control && <Icon name="chevron" size={15} style={{ opacity: 0.4 }} />}
    </div>
  );
}

function Toggle({ on, onChange }) {
  return (
    <button className={'ll-toggle' + (on ? ' is-on' : '')} onClick={() => onChange(!on)} aria-pressed={on}>
      <span className="ll-toggle-knob" />
    </button>
  );
}

function SettingsScreen({ onNav, onOpenLoc, theme, onTheme }) {
  const [precise, setPrecise] = React.useState(true);
  const [live, setLive] = React.useState(true);
  const [conservative, setConservative] = React.useState(true);
  const [autoUpdate, setAutoUpdate] = React.useState(true);
  const L = window.LOCATION;
  return (
    <Screen tab="settings" onNav={onNav}>
      <AppBar left={<div className="ll-appbar-h1">Settings</div>} title="" border={false} />
      <Scroll padBottom={96}>
        <SectionLabel>Location</SectionLabel>
        <div className="ll-set-group">
          <SettingsRow icon="pin" title="Current location" detail={`${L.city}, ${L.state}`} onClick={onOpenLoc} />
          <SettingsRow icon="crosshair" title="Precise GPS" control={<Toggle on={precise} onChange={setPrecise} />} />
          <SettingsRow icon="map" title="Distance units" detail="Metric (km)" onClick={() => {}} last />
        </div>

        <SectionLabel>Verdicts</SectionLabel>
        <div className="ll-set-group">
          <SettingsRow icon="bolt" title="Use live context" detail="speed · activity" control={<Toggle on={live} onChange={setLive} />} />
          <SettingsRow icon="shield" title="Conservative mode" detail="flag gaps" control={<Toggle on={conservative} onChange={setConservative} />} last />
        </div>

        <SectionLabel>Data sources</SectionLabel>
        <div className="ll-set-group">
          <SettingsRow icon="layers" title="Manage jurisdictions" detail="5 sources" onClick={() => onNav('coverage')} />
          <SettingsRow icon="refresh" title="Auto-update code" control={<Toggle on={autoUpdate} onChange={setAutoUpdate} />} last />
        </div>

        <SectionLabel>Appearance</SectionLabel>
        <div className="ll-set-themes">
          {Object.entries(window.THEMES).map(([id, t]) => (
            <button key={id} className={'ll-themecard' + (theme === id ? ' is-on' : '')} onClick={() => onTheme(id)}
              style={window.themeStyle(id)}>
              <span className="ll-themecard-swatch">
                <span style={{ background: 'var(--primary)' }} />
                <span style={{ background: 'var(--accent)' }} />
                <span style={{ background: 'var(--surface)', border: '1px solid var(--line-2)' }} />
              </span>
              <span className="ll-themecard-name" style={{ color: 'var(--ink)' }}>{t.label}</span>
              {theme === id && <span className="ll-themecard-check"><Icon name="check" size={13} color="var(--primary)" strokeWidth={2.6} /></span>}
            </button>
          ))}
        </div>

        <SectionLabel>Privacy</SectionLabel>
        <div className="ll-set-group">
          <SettingsRow icon="lock" title="GPS coordinates" detail="Never stored" />
          <SettingsRow icon="doc" title="Snapshots" detail="On this device" last />
        </div>

        <div className="ll-set-about">
          <BrandMark size={44} />
          <div className="ll-set-ver">LegitLex · v0.9.0 (Irvine pilot)</div>
          <p>{window.DISCLAIMER}</p>
          <div className="ll-set-links"><a>Terms</a> · <a>Privacy</a> · <a>Source data</a></div>
        </div>
      </Scroll>
    </Screen>
  );
}

Object.assign(window, { JurisMap, CoverageScreen, RecordsScreen, SettingsScreen, Toggle });
