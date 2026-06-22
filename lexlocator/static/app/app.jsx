// LegitLex — app shell: navigation, location sheet, brand Tweaks.

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "indigo",
  "sealTilt": -7,
  "inkedStamp": true,
  "startScreen": "onboarding"
}/*EDITMODE-END*/;

const SCREEN_OPTIONS = [
  'onboarding', 'ask', 'verdict', 'camera', 'scanresult', 'snapshot', 'coverage', 'records', 'settings',
];

// Jurisdictions we actually have data for — lets you switch without real GPS.
const COVERED_PLACES = [
  { city: 'Irvine', county: 'Orange County', state: 'CA', country: 'US', lat: 33.6846, lng: -117.8265 },
  { city: 'Montgomery', county: 'Montgomery County', state: 'AL', country: 'US', lat: 32.3668, lng: -86.3000 },
  { city: 'Seoul', county: '', state: 'KR', country: 'KR', lat: 37.5665, lng: 126.9780 },
];
window.COVERED_PLACES = COVERED_PLACES;

function LocationSheet({ open, onClose }) {
  const L = window.LOCATION;
  const coords = (L.lat != null && L.lng != null) ? `${L.lat.toFixed(4)}, ${L.lng.toFixed(4)}` : '—';
  const pick = (p) => {
    const changed = (p.city !== L.city || p.state !== L.state);
    Object.assign(window.LOCATION, p, { neighborhood: '', cross_streets: '', accuracy_m: 0 });
    if (changed) window.__jurAlert = { city: p.city, county: p.county, state: p.state, ts: Date.now() };
    if (window.__forceUpdate) window.__forceUpdate();
    onClose();
  };
  return (
    <div className={'ll-sheet-scrim' + (open ? ' is-open' : '')} onClick={onClose}>
      <div className={'ll-sheet' + (open ? ' is-open' : '')} onClick={e => e.stopPropagation()}>
        <div className="ll-sheet-grip" />
        <div className="ll-sheet-title">Your location</div>
        <div className="ll-sheet-cur">
          <span className="ll-sheet-cur-ic"><Icon name="crosshair" size={20} color="var(--primary)" /></span>
          <div className="ll-sheet-cur-main">
            <strong>{[L.city, L.county].filter(Boolean).join(', ')}</strong>
            <span className="mono">{L.state} · {coords}</span>
          </div>
          <span className="ll-status ll-status-ok">Active</span>
        </div>
        <div className="ll-sheet-lbl">Switch jurisdiction (covered areas)</div>
        {COVERED_PLACES.map((p, i) => {
          const active = p.city === L.city && p.state === L.state;
          return (
            <div key={i} className="ll-sheet-other" style={{ cursor: 'pointer' }} onClick={() => pick(p)}>
              <Icon name="pin" size={16} color={active ? 'var(--primary)' : 'var(--ink-3)'} />
              <span>{p.city}, {p.state}</span>
              <span className={'ll-status ' + (active ? 'll-status-ok' : 'll-status-partial')}>
                {active ? 'Active' : 'Switch'}
              </span>
            </div>
          );
        })}
        <Button variant="ghost" full icon="crosshair" onClick={onClose} style={{ marginTop: 14 }}>Use my GPS location</Button>
      </div>
    </div>
  );
}

// True on real phone-sized screens — we drop the simulated iPhone frame there
// and let the app fill the viewport (the device mockup is desktop-only chrome).
function useIsMobile() {
  const q = '(max-width: 600px)';
  const [m, setM] = React.useState(
    typeof window !== 'undefined' && window.matchMedia(q).matches);
  React.useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener ? mq.addEventListener('change', on) : mq.addListener(on);
    return () => { mq.removeEventListener ? mq.removeEventListener('change', on) : mq.removeListener(on); };
  }, []);
  return m;
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const isMobile = useIsMobile();
  const [screen, setScreen] = React.useState(t.startScreen || 'onboarding');
  const [qid, setQid] = React.useState('ebike');
  const [ctx, setCtx] = React.useState(null);
  const [snapBack, setSnapBack] = React.useState('verdict');
  const [locOpen, setLocOpen] = React.useState(false);
  const bootRef = React.useRef(false);
  const [, force] = React.useReducer(x => x + 1, 0);

  // honor the "start screen" tweak (first apply + on change)
  React.useEffect(() => {
    if (!bootRef.current) { bootRef.current = true; setScreen(t.startScreen || 'onboarding'); }
  }, []);

  // boot: probe the backend, then resolve real location (best-effort).
  // Components read window.LOCATION at render, so we force a re-render once it
  // updates. If anything fails we keep the bundled Irvine demo location.
  React.useEffect(() => {
    window.__forceUpdate = force;
    if (window.LL_API) window.LL_API.checkHealth().then(() => force());
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const loc = await window.LL_API.geocode(pos.coords.latitude, pos.coords.longitude);
            Object.assign(window.LOCATION, loc);
            force();
          } catch (e) { /* keep demo location */ }
        },
        () => {}, { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
      );
    }
  }, []);

  // thinking -> verdict (mock-only auto-advance; live flow advances on response)
  React.useEffect(() => {
    if (screen !== 'thinking') return;
    if (window.LL_LIVE) return;
    const to = setTimeout(() => setScreen('verdict'), 2150);
    return () => clearTimeout(to);
  }, [screen, qid]);

  const go = (tab) => setScreen(tab === 'scan' ? 'camera' : tab);

  // ask: live backend when available, otherwise the bundled mock verdict.
  const ask = async (id, c) => {
    const ctxObj = c || null;
    setCtx(ctxObj);
    const question =
      (ctxObj && ctxObj.question) ||
      (window.VERDICTS[id] && window.VERDICTS[id].q) ||
      String(id);
    window.__thinkingQ = question;
    setScreen('thinking');
    if (window.LL_LIVE && window.LL_API) {
      try {
        const live = await window.LL_API.ask({
          question,
          location: window.LOCATION,
          activity: ctxObj && ctxObj.ctxOpen ? ctxObj.activity : null,
          speed: ctxObj && ctxObj.ctxOpen ? ctxObj.speed : null,
        });
        window.VERDICTS.__live = live;
        window.__liveSnapshotId = live.snapshot_id;
        // save to the evidence trail (Records)
        if (window.LL_RECORDS) {
          const loc = window.LOCATION;
          window.LL_RECORDS.add({
            kind: 'verdict', label: question, verdict: live.verdict,
            where: [loc.city, loc.state].filter(Boolean).join(', '),
            snapshot_id: live.snapshot_id,
          });
        }
        setQid('__live');
        setScreen('verdict');
        return;
      } catch (e) {
        console.warn('Live ask failed; falling back to bundled data.', e);
        setQid(id);
        setTimeout(() => setScreen('verdict'), 1200);
        return;
      }
    }
    setQid(id); // mock: auto-advance effect moves to verdict
  };

  // expose seal tweaks to the patched Seal (read at render time)
  window.__LL_SEAL = { tilt: t.sealTilt, inked: t.inkedStamp };
  window.__nav = setScreen; // prototype nav hook
  window.__theme = (id) => setTweak('theme', id);
  const statusDark = screen === 'onboarding' || screen === 'camera';

  // scale the whole device to fit any viewport (letterboxed, centered)
  React.useEffect(() => {
    const fit = () => {
      const el = document.querySelector('.ll-fit');
      if (!el) return;
      const s = Math.min((window.innerWidth - 28) / 402, (window.innerHeight - 28) / 874, 1);
      el.style.transform = `scale(${s})`;
    };
    fit();
    window.addEventListener('resize', fit);
    return () => window.removeEventListener('resize', fit);
  }, []);

  let view;
  switch (screen) {
    case 'onboarding':
      view = <OnboardingScreen onEnter={() => setScreen('ask')} />; break;
    case 'ask':
      view = <AskScreen onAsk={ask} onScan={() => setScreen('camera')}
        onComplaint={() => setScreen('complaint')}
        onCompare={() => setScreen('compare')}
        onOpenLoc={() => setLocOpen(true)} onNav={go} />; break;
    case 'complaint':
      view = <ComplaintScreen onBack={() => setScreen('ask')} onNav={go} />; break;
    case 'compare':
      view = <CompareScreen onBack={() => setScreen('ask')} onNav={go} />; break;
    case 'thinking':
      view = <ThinkingScreen qid={qid} />; break;
    case 'verdict':
      view = <VerdictScreen qid={qid} ctx={ctx}
        onBack={() => setScreen('ask')}
        onSnapshot={() => { setSnapBack('verdict'); setScreen('snapshot'); }}
        onFollow={() => setScreen('ask')} />; break;
    case 'camera':
      view = <CameraScreen onCapture={() => setScreen('scanresult')} onClose={() => setScreen('ask')} />; break;
    case 'scanresult':
      view = <ScanResultScreen onBack={() => setScreen('ask')} onRescan={() => setScreen('camera')}
        onSnapshot={() => { setSnapBack('scanresult'); setQid('parking'); setScreen('snapshot'); }} onNav={go} />; break;
    case 'snapshot':
      view = <SnapshotScreen qid={qid} onBack={() => setScreen(snapBack)} onDone={() => setScreen('ask')} />; break;
    case 'coverage':
      view = <CoverageScreen onNav={go} />; break;
    case 'records':
      view = <RecordsScreen onOpen={(id) => { setQid(id); setSnapBack('records'); setScreen('snapshot'); }} onNav={go} />; break;
    case 'settings':
      view = <SettingsScreen onNav={go} onOpenLoc={() => setLocOpen(true)} theme={t.theme} onTheme={(id) => setTweak('theme', id)} />; break;
    default:
      view = <AskScreen onAsk={ask} onScan={() => setScreen('camera')} onOpenLoc={() => setLocOpen(true)} onNav={go} />;
  }

  const inner = (
    <div className="ll-device-inner">
      {view}
      <LocationSheet open={locOpen} onClose={() => setLocOpen(false)} />
    </div>
  );

  return (
    <div className={'ll-stage' + (isMobile ? ' ll-stage-mobile' : '')}>
      <div className={isMobile ? 'll-fit-mobile' : 'll-fit'}>
        <div className="ll-root" style={window.themeStyle(t.theme)} data-screen-label={screen}>
          {isMobile
            ? <div className="ll-mobile">{inner}</div>
            : <IOSDevice dark={statusDark}>{inner}</IOSDevice>}
        </div>
      </div>

      {!isMobile && (
      <TweaksPanel>
        <TweakSection label="Brand & visual style" />
        <TweakSelect label="Theme" value={t.theme}
          options={Object.keys(window.THEMES).map(id => ({ value: id, label: window.THEMES[id].label }))}
          onChange={(v) => setTweak('theme', v)} />
        <TweakToggle label="Weathered stamp edge" value={t.inkedStamp} onChange={(v) => setTweak('inkedStamp', v)} />
        <TweakSlider label="Seal tilt" value={t.sealTilt} min={-14} max={4} step={1} unit="°" onChange={(v) => setTweak('sealTilt', v)} />
        <TweakSection label="Prototype" />
        <TweakSelect label="Jump to screen" value={SCREEN_OPTIONS.includes(screen) ? screen : 'ask'}
          options={SCREEN_OPTIONS.map(s => ({ value: s, label: s }))}
          onChange={(v) => setScreen(v)} />
      </TweaksPanel>
      )}
    </div>
  );
}

// patch Seal defaults from tweaks (tilt + inked) without threading props everywhere
const _OrigSeal = window.Seal;
window.Seal = function PatchedSeal(props) {
  const cfg = window.__LL_SEAL || { tilt: -7, inked: true };
  if (props.flat) return _OrigSeal({ ...props, flat: true });
  return _OrigSeal({ ...props, rotate: cfg.tilt, inked: cfg.inked !== false });
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
