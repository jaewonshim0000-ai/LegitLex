// LegitLex — Complaint analyzer: scan/upload/paste a complaint or notice and get
// a plain-English summary + risk assessment grounded in the dataset's laws.

const RISK_META = {
  low:      { label: 'Low risk',      varc: '--yes' },
  medium:   { label: 'Medium risk',   varc: '--warn' },
  high:     { label: 'High risk',     varc: '--no' },
  critical: { label: 'Critical risk', varc: '--no' },
  unknown:  { label: 'Risk unclear',  varc: '--unknown' },
};

function ComplaintScreen({ onBack, onNav }) {
  const [phase, setPhase] = React.useState('input');   // input | loading | result
  const [text, setText] = React.useState('');
  const [file, setFile] = React.useState(null);
  const [res, setRes] = React.useState(null);
  const [err, setErr] = React.useState('');
  const fileRef = React.useRef(null);

  const submit = async () => {
    if (!file && text.trim().length < 15) {
      setErr('Upload a complaint file or paste at least a sentence of text.');
      return;
    }
    setErr(''); setPhase('loading');
    try {
      let data;
      if (window.LL_LIVE && window.LL_API) {
        data = await window.LL_API.analyzeComplaint({ file, text: text.trim(), location: window.LOCATION });
      } else {
        await new Promise(r => setTimeout(r, 1400));
        data = window.COMPLAINT_DEMO;   // bundled demo result
      }
      setRes(data); setPhase('result');
      if (window.LL_RECORDS && data.analysis) {
        const loc = window.LOCATION;
        window.LL_RECORDS.add({
          kind: 'complaint',
          label: data.analysis.complaint_type || 'Complaint analysis',
          risk: data.analysis.risk_level,
          where: [loc.city, loc.state].filter(Boolean).join(', '),
          snapshot_id: data.snapshot_id,
        });
      }
    } catch (e) {
      setErr(e.message || 'Analysis failed'); setPhase('input');
    }
  };

  if (phase === 'loading') {
    return (
      <Screen tab="scan" onNav={onNav} bg="var(--paper)">
        <AppBar left={<BackBtn onClick={() => setPhase('input')} label="Cancel" />} title="Analyzing" />
        <div className="ll-think" style={{ paddingTop: 60 }}>
          <Spinner size={30} color="var(--primary)" />
          <div className="ll-think-q">Reading the complaint &amp; checking it against the law…</div>
          <div className="ll-think-count">Summary · applicable laws · risk assessment</div>
        </div>
      </Screen>
    );
  }

  if (phase === 'result' && res) {
    return <ComplaintResult res={res} onBack={() => setPhase('input')} onNav={onNav} />;
  }

  return (
    <Screen tab="scan" onNav={onNav}>
      <AppBar left={<BackBtn onClick={onBack} label="Back" />} title="Analyze a complaint" />
      <Scroll padBottom={96}>
        <div className="ll-ask-hero">
          <div className="ll-ask-kicker"><Icon name="doc" size={15} /> Plain-English summary + risk</div>
          <h1 className="ll-ask-h1" style={{ fontSize: 28 }}>Got a notice or <em>complaint</em>?</h1>
          <p className="ll-ask-sub">Upload a citation, code-enforcement notice, or lawsuit — we summarize it and assess your risk against the laws in your area.</p>
        </div>

        <label className="file-drop ll-cmp-drop">
          <input ref={fileRef} type="file" accept=".pdf,.txt,image/*" style={{ display: 'none' }}
            onChange={e => setFile(e.target.files[0] || null)} />
          <Icon name="doc" size={22} color="var(--primary)" />
          <span>{file ? file.name : 'Tap to upload a PDF, photo, or text file'}</span>
        </label>

        <div className="ll-cmp-or">or paste the text</div>
        <div className="ll-askbox">
          <textarea className="ll-askinput" rows={5} value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Paste the complaint / notice text here…" />
        </div>

        {err && <div className="ll-cmp-err"><Icon name="info" size={14} /> {err}</div>}

        <Button variant="primary" full size="lg" icon="shield" onClick={submit}
          style={{ marginTop: 14 }}>Analyze complaint</Button>
        <Disclaimer />
      </Scroll>
    </Screen>
  );
}

function ComplaintResult({ res, onBack, onNav }) {
  const a = res.analysis || {};
  const m = RISK_META[a.risk_level] || RISK_META.unknown;
  const cites = a.citations || [];
  return (
    <Screen tab="scan" onNav={onNav} bg="var(--paper)">
      <AppBar bg="var(--paper)" left={<BackBtn onClick={onBack} label="New" />} title="Complaint analysis" />
      <Scroll padBottom={60}>
        {/* Risk banner */}
        <div className="ll-cmp-risk" style={{ background: `var(${m.varc})` }}>
          <span>{m.label}</span>
          {a.complaint_type ? <span className="ll-cmp-risk-type">{a.complaint_type}</span> : null}
        </div>

        {a.deadline ? (
          <div className="ll-cmp-deadline"><Icon name="clock" size={16} /> <strong>Deadline:</strong>&nbsp;{a.deadline}</div>
        ) : null}

        <SectionLabel>Summary</SectionLabel>
        <Card><p style={{ margin: 0, fontFamily: 'var(--font-legal)', fontSize: 16, lineHeight: 1.55 }}>{a.summary}</p></Card>

        {a.risk_rationale ? (
          <React.Fragment>
            <SectionLabel>Why this risk level</SectionLabel>
            <Card className="ll-nocite"><span>{a.risk_rationale}</span></Card>
          </React.Fragment>
        ) : null}

        {(a.allegations || []).length > 0 && (
          <React.Fragment>
            <SectionLabel right={<span className="ll-seclabel-n">{a.allegations.length}</span>}>What you're accused of</SectionLabel>
            <div className="ll-cmp-alleg">
              {a.allegations.map((al, i) => (
                <div key={i} className="ll-cmp-alleg-row">
                  <Icon name="bang" size={14} color={`var(${m.varc})`} />
                  <span>{al.claim}{al.law_area ? <em className="muted"> · {al.law_area}</em> : null}</span>
                </div>
              ))}
            </div>
          </React.Fragment>
        )}

        {a.potential_penalties ? (
          <PenaltyCard penalty={a.potential_penalties} severity={a.risk_level === 'low' ? 'infraction' : a.risk_level === 'critical' || a.risk_level === 'high' ? 'misdemeanor' : 'civil'} />
        ) : null}

        <SectionLabel right={<span className="ll-seclabel-n">{cites.length}</span>}>Applicable law</SectionLabel>
        {cites.length === 0 ? (
          <Card className="ll-nocite"><Icon name="info" size={18} color="var(--ink-3)" />
            <span>No matching law was found in this app's dataset for these allegations.</span></Card>
        ) : (
          <div className="ll-cites">
            {cites.map((c, i) => (
              <div key={i} className="ll-cite">
                <div className="ll-cite-top">
                  <LevelBadge level={c.level || 'unknown'} />
                  <span className="ll-cite-sid">§ {c.section_id}</span>
                </div>
                {c.section_name ? <div className="ll-cite-name">{c.section_name}</div> : null}
                <p className="ll-cite-para">{c.paraphrase}</p>
                {c.jurisdiction ? <div className="ll-cite-meta"><Icon name="pin" size={12} /> {c.jurisdiction}</div> : null}
              </div>
            ))}
          </div>
        )}

        {(a.recommended_actions || []).length > 0 && (
          <React.Fragment>
            <SectionLabel>Recommended next steps</SectionLabel>
            <div className="ll-cmp-actions">
              {a.recommended_actions.map((s, i) => (
                <div key={i} className="ll-cmp-action"><Icon name="check" size={15} color="var(--primary)" strokeWidth={2.2} /> <span>{s}</span></div>
              ))}
            </div>
          </React.Fragment>
        )}

        {a.caveats ? (
          <div className="ll-caveat"><div className="ll-caveat-head"><Icon name="info" size={15} /> Limits</div><p>{a.caveats}</p></div>
        ) : null}

        <Button variant="ghost" full icon="doc" onClick={onBack} style={{ marginTop: 18 }}>Analyze another</Button>
        <Disclaimer />
      </Scroll>
    </Screen>
  );
}

Object.assign(window, { ComplaintScreen, RISK_META });
