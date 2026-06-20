// LegitLex — Compare two locations: "Can I do this here vs there?"

function ComparePlacePicker({ value, onChange, label }) {
  const places = window.COVERED_PLACES || [
    { city: 'Irvine', county: 'Orange County', state: 'CA' },
    { city: 'Montgomery', county: 'Montgomery County', state: 'AL' },
  ];
  return (
    <label className="ll-field" style={{ flex: 1 }}>
      <span>{label}</span>
      <select className="ll-cmp-select"
        value={value.city}
        onChange={e => onChange(places.find(p => p.city === e.target.value))}>
        {places.map(p => <option key={p.city} value={p.city}>{p.city}, {p.state}</option>)}
      </select>
    </label>
  );
}

function CompareScreen({ onBack, onNav }) {
  const places = window.COVERED_PLACES || [
    { city: 'Irvine', county: 'Orange County', state: 'CA' },
    { city: 'Montgomery', county: 'Montgomery County', state: 'AL' },
  ];
  const [a, setA] = React.useState(places[0]);
  const [b, setB] = React.useState(places[1] || places[0]);
  const [text, setText] = React.useState('Can I ride my Class 3 e-bike on a bike path?');
  const [phase, setPhase] = React.useState('input'); // input | loading | result
  const [res, setRes] = React.useState(null);
  const [err, setErr] = React.useState('');

  const run = async () => {
    if (text.trim().length < 8) { setErr('Type a question first.'); return; }
    setErr(''); setPhase('loading');
    try {
      let data;
      if (window.LL_LIVE && window.LL_API && window.LL_API.compare) {
        data = await window.LL_API.compare({ question: text.trim(), locationA: a, locationB: b });
      } else {
        await new Promise(r => setTimeout(r, 1400));
        data = demoCompare(text.trim(), a, b);
      }
      setRes(data); setPhase('result');
    } catch (e) { setErr(e.message || 'failed'); setPhase('input'); }
  };

  return (
    <Screen tab="ask" onNav={onNav}>
      <AppBar left={<BackBtn onClick={onBack} label="Back" />} title="Compare locations" />
      <Scroll padBottom={96}>
        <div className="ll-ask-hero">
          <div className="ll-ask-kicker"><Icon name="map" size={15} /> Same question · two places</div>
          <h1 className="ll-ask-h1" style={{ fontSize: 27 }}>Here <em>vs</em> there</h1>
        </div>

        <div className="ll-askbox">
          <textarea className="ll-askinput" rows={2} value={text}
            onChange={e => setText(e.target.value)} placeholder="Can I do this…?" />
        </div>
        <div className="ll-cmp-places">
          <ComparePlacePicker value={a} onChange={setA} label="Location A" />
          <span className="ll-cmp-vs">vs</span>
          <ComparePlacePicker value={b} onChange={setB} label="Location B" />
        </div>
        {err && <div className="ll-cmp-err"><Icon name="info" size={14} /> {err}</div>}
        <Button variant="primary" full size="lg" icon="scales" onClick={run} style={{ marginTop: 12 }}
          disabled={phase === 'loading'}>
          {phase === 'loading' ? 'Comparing…' : 'Compare'}
        </Button>

        {phase === 'loading' && (
          <div className="ll-think" style={{ padding: '26px 0' }}>
            <Spinner size={24} color="var(--primary)" />
            <div className="ll-think-q" style={{ fontSize: 14 }}>Checking the law in both places…</div>
          </div>
        )}

        {phase === 'result' && res && (
          <React.Fragment>
            {res.differ ? (
              <div className="ll-cmp-differ"><Icon name="info" size={15} /> The answer is different in each place.</div>
            ) : (
              <div className="ll-cmp-same"><Icon name="check" size={15} /> Same outcome in both places.</div>
            )}
            <div className="ll-cmp-cards">
              {res.results.map((r, i) => {
                const v = r.verdict; const meta = window.VERDICT_META[v.verdict] || window.VERDICT_META.unknown;
                const loc = r.location;
                return (
                  <div key={i} className="ll-cmp-card" style={{ borderTopColor: `var(${meta.varc})` }}>
                    <div className="ll-cmp-card-loc"><Icon name="pin" size={13} /> {[loc.city, loc.state].filter(Boolean).join(', ')}</div>
                    <div className="ll-cmp-card-verdict" style={{ color: `var(${meta.varc})` }}>
                      <Icon name={meta.glyph === 'check' ? 'check' : meta.glyph === 'cross' ? 'cross' : meta.glyph === 'bang' ? 'bang' : 'query'} size={18} strokeWidth={2.4} />
                      {meta.label}
                    </div>
                    <p className="ll-cmp-card-answer">{v.answer}</p>
                    <div className="ll-cmp-card-foot">{(v.citations || []).length} citation{(v.citations || []).length === 1 ? '' : 's'}</div>
                  </div>
                );
              })}
            </div>
          </React.Fragment>
        )}
        <Disclaimer compact />
      </Scroll>
    </Screen>
  );
}

// demo fallback (no API key): builds a plausible two-place comparison
function demoCompare(question, a, b) {
  const mk = (loc, verdict, answer, n) => ({
    location: loc, citation_count: n,
    verdict: { verdict, confidence: 0.8, answer, citations: new Array(n).fill({ section_id: '—', paraphrase: '' }), penalty: '', penalty_severity: 'infraction', conflicts: [], caveats: '' },
  });
  return {
    question,
    results: [
      mk(a, 'warning', `In ${a.city}, this is allowed only with restrictions — local rules limit where Class 3 e-bikes may go.`, 2),
      mk(b, 'yes', `In ${b.city}, state law treats this more permissively and no local ban was found.`, 1),
    ],
    differ: true,
  };
}

Object.assign(window, { CompareScreen });
