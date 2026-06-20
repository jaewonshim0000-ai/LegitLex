// LegitLex — core screens: Onboarding, Ask (home), Thinking, Verdict.

// ── Brand emblem (neutral, primary-colored seal w/ scales) ───────────────────
function BrandMark({ size = 120 }) {
  return (
    <div className="ll-brandmark" style={{ width: size, height: size }}>
      <svg viewBox="0 0 120 120" width={size} height={size}>
        <circle cx="60" cy="60" r="56" fill="none" stroke="var(--primary)" strokeWidth="2.4" />
        <circle cx="60" cy="60" r="50" fill="none" stroke="var(--primary)" strokeWidth="1" opacity="0.5" />
        <g stroke="var(--primary)" fill="none" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round"
           transform="translate(60,60) scale(1.7) translate(-12,-12)">
          <path d="M12 4v16M7 20h10M5 8h14M5 8l-2.5 5h5L5 8ZM19 8l-2.5 5h5L19 8Z" />
          <circle cx="12" cy="4.5" r="1.2" fill="var(--primary)" />
        </g>
      </svg>
    </div>
  );
}

// ── Onboarding / location detect ─────────────────────────────────────────────
function OnboardingScreen({ onEnter }) {
  const [located, setLocated] = React.useState(false);
  const L = window.LOCATION;
  React.useEffect(() => {
    // Resolve real GPS -> jurisdiction. Falls back to the bundled demo
    // location if permission is denied, geocoding fails, or it takes too long.
    let done = false;
    const finish = () => { if (!done) { done = true; setLocated(true); } };
    const safety = setTimeout(finish, 6000);
    if (navigator.geolocation && window.LL_API) {
      navigator.geolocation.getCurrentPosition(
        async (pos) => {
          try {
            const loc = await window.LL_API.geocode(pos.coords.latitude, pos.coords.longitude);
            Object.assign(window.LOCATION, loc);
            if (window.__forceUpdate) window.__forceUpdate();
          } catch (e) { /* keep demo location */ }
          finish();
        },
        () => finish(),
        { enableHighAccuracy: true, timeout: 5000, maximumAge: 60000 }
      );
    } else {
      setTimeout(finish, 1700);
    }
    return () => clearTimeout(safety);
  }, []);
  return (
    <Screen bg="var(--primary)">
      <div className="ll-onb">
        <div className="ll-onb-grain" />
        <div className="ll-onb-top">
          <div className="ll-onb-emblem">
            <svg viewBox="0 0 120 120" width="118" height="118">
              <circle cx="60" cy="60" r="56" fill="none" stroke="var(--primary-ink)" strokeWidth="2.2" opacity="0.9" />
              <circle cx="60" cy="60" r="49" fill="none" stroke="var(--primary-ink)" strokeWidth="0.8" opacity="0.45" />
              <g stroke="var(--primary-ink)" fill="none" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"
                 transform="translate(60,60) scale(1.7) translate(-12,-12)">
                <path d="M12 4v16M7 20h10M5 8h14M5 8l-2.5 5h5L5 8ZM19 8l-2.5 5h5L19 8Z" />
                <circle cx="12" cy="4.5" r="1.2" fill="var(--primary-ink)" />
              </g>
            </svg>
          </div>
          <h1 className="ll-onb-word">LegitLex</h1>
          <p className="ll-onb-tag">Know what’s legal — right where you stand.</p>
        </div>

        <div className="ll-onb-bottom">
          <div className={'ll-locate' + (located ? ' is-done' : '')}>
            {!located ? (
              <React.Fragment>
                <span className="ll-locate-radar"><Icon name="crosshair" size={20} color="var(--primary-ink)" /></span>
                <div className="ll-locate-text">
                  <strong>Pinpointing your jurisdiction…</strong>
                  <span>Reading GPS · resolving city, county & state</span>
                </div>
              </React.Fragment>
            ) : (
              <React.Fragment>
                <span className="ll-locate-check"><Icon name="check" size={18} color="var(--primary)" strokeWidth={2.4} /></span>
                <div className="ll-locate-text">
                  <strong>{L.city}, {L.county}</strong>
                  <span>{L.state} · {L.cross_streets} · ±{L.accuracy_m} m</span>
                </div>
                <span className="ll-locate-cov">2 codes ready</span>
              </React.Fragment>
            )}
          </div>

          <button className="ll-onb-enter" disabled={!located} onClick={onEnter}>
            <span>{located ? 'Enter LegitLex' : 'Locating…'}</span>
            {located && <Icon name="arrowR" size={20} />}
          </button>
          <p className="ll-onb-fine">Legal information, not legal advice. We never store your GPS coordinates.</p>
        </div>
      </div>
    </Screen>
  );
}

// ── Jurisdiction-boundary alert ──────────────────────────────────────────────
function JurisdictionAlert({ onNav }) {
  const a = window.__jurAlert;
  const [, force] = React.useReducer(x => x + 1, 0);
  const [cov, setCov] = React.useState(null);
  React.useEffect(() => {
    if (!a) return;
    if (window.LL_LIVE && window.LL_API && window.LL_API.coverage) {
      window.LL_API.coverage(window.LOCATION).then(setCov).catch(() => {});
    }
  }, [a && a.ts]);
  if (!a) return null;
  const dismiss = () => { window.__jurAlert = null; force(); };
  const where = [a.city, a.state].filter(Boolean).join(', ');
  const missing = cov && cov.missing_levels && cov.missing_levels.length
    ? ` No ${cov.missing_levels.join('/')}-level law here yet.` : '';
  const stat = cov ? `${cov.total_sections.toLocaleString()} sections across ${cov.sources.length} sources cover this area.` : 'Rules here may differ from where you were.';
  return (
    <div className="ll-juralert">
      <div className="ll-juralert-top">
        <span className="ll-juralert-dot" />
        <strong>You’ve entered {where}</strong>
        <button className="ll-juralert-x" onClick={dismiss}><Icon name="cross" size={14} /></button>
      </div>
      <div className="ll-juralert-body">Law changes at this boundary. {stat}{missing}</div>
      <button className="ll-juralert-btn" onClick={() => { onNav('coverage'); dismiss(); }}>Review what applies here →</button>
    </div>
  );
}

// ── Ask / home ───────────────────────────────────────────────────────────────
function AskScreen({ onAsk, onScan, onComplaint, onCompare, onOpenLoc, onNav }) {
  const [text, setText] = React.useState('');
  const [ctxOpen, setCtxOpen] = React.useState(false);
  const [activity, setActivity] = React.useState('Class 3 e-bike');
  const [speed, setSpeed] = React.useState('30');
  const S = window.SUGGESTIONS;

  const routeQid = (t) => {
    const s = t.toLowerCase();
    if (/e-?bike|bike|trail|scooter/.test(s)) return 'ebike';
    if (/dog|leash|pet/.test(s)) return 'dog';
    if (/noise|quiet|loud|curfew/.test(s)) return 'noise';
    if (/park|overnight|rv|vehicle/.test(s)) return 'parking';
    if (/drone|uas|fly/.test(s)) return 'drone';
    return 'ebike';
  };
  const submit = () => {
    const q = text.trim() || 'Can I ride my Class 3 e-bike on this trail?';
    onAsk(routeQid(q), { activity, speed, ctxOpen, question: q });
  };

  // ── Voice ask (Web Speech API) ──
  const [listening, setListening] = React.useState(false);
  const recogRef = React.useRef(null);
  const startVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert('Voice input is not supported in this browser. Try Chrome.'); return; }
    if (listening && recogRef.current) { recogRef.current.stop(); return; }
    const rec = new SR();
    rec.lang = 'en-US'; rec.interimResults = true; rec.continuous = false;
    recogRef.current = rec;
    let finalText = '';
    rec.onresult = (e) => {
      let interim = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript;
        if (e.results[i].isFinal) finalText += t; else interim += t;
      }
      setText((finalText + interim).replace(/\s+/g, ' ').trimStart());
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    setListening(true);
    try { rec.start(); } catch (e) { setListening(false); }
  };

  return (
    <Screen tab="ask" onNav={onNav}>
      <AppBar
        left={<LocChip onClick={onOpenLoc} />}
        title=""
        right={<IconBtn name="history" title="Records" onClick={() => onNav('records')} />}
      />
      <Scroll className="ll-ask-scroll" padBottom={96}>
        <JurisdictionAlert onNav={onNav} />
        <div className="ll-ask-hero">
          <div className="ll-ask-kicker">
            <Icon name={window.LL_LIVE ? 'spark' : 'info'} size={15} />
            {window.LL_LIVE
              ? `Live AI · grounded in ${window.LOCATION.city || 'local'} code`
              : 'Demo mode · sample answers (no API key on server)'}
          </div>
          <h1 className="ll-ask-h1">Can I do this <em>here</em>?</h1>
          <p className="ll-ask-sub">Ask anything about local law. We check the code for your exact spot and cite the section.</p>
        </div>

        <div className="ll-askbox">
          <textarea
            className="ll-askinput"
            rows={3}
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="Is my e-bike legal on this trail?  ·  What’s the noise curfew?  ·  Can my dog be off-leash here?"
          />
          <div className="ll-askbox-row">
            <div style={{ display: 'flex', gap: 8 }}>
              <button className={'ll-ctxbtn' + (listening ? ' is-on' : '')} onClick={startVoice} title="Speak your question">
                <Icon name="mic" size={15} />
                {listening ? 'Listening…' : 'Voice'}
              </button>
            </div>
            <button className="ll-asksubmit" onClick={submit}>
              <span>Get verdict</span>
              <Icon name="arrowR" size={18} />
            </button>
          </div>
        </div>

        <SectionLabel>Try near you</SectionLabel>
        <div className="ll-sugg">
          {S.map(s => (
            <button key={s.id} className="ll-sugg-row" onClick={() => onAsk(s.id, { activity, speed, ctxOpen: s.id === 'ebike' && ctxOpen, question: s.text })}>
              <span className="ll-sugg-ic"><Icon name={s.icon} size={19} /></span>
              <span className="ll-sugg-text">{s.text}</span>
              <Icon name="chevron" size={16} style={{ opacity: 0.4 }} />
            </button>
          ))}
        </div>

        <button className="ll-scanbanner" onClick={onScan}>
          <span className="ll-scanbanner-ic"><Icon name="camera" size={22} /></span>
          <span className="ll-scanbanner-txt">
            <strong>See a posted sign?</strong>
            <span>Photograph it — we’ll verify it against the real code.</span>
          </span>
          <Icon name="arrowR" size={18} style={{ opacity: 0.6 }} />
        </button>

        <button className="ll-scanbanner" onClick={onComplaint} style={{ marginTop: 10 }}>
          <span className="ll-scanbanner-ic"><Icon name="doc" size={22} /></span>
          <span className="ll-scanbanner-txt">
            <strong>Got a complaint or notice?</strong>
            <span>Upload it for a plain-English summary &amp; risk assessment.</span>
          </span>
          <Icon name="arrowR" size={18} style={{ opacity: 0.6 }} />
        </button>

        <button className="ll-scanbanner" onClick={onCompare} style={{ marginTop: 10 }}>
          <span className="ll-scanbanner-ic"><Icon name="map" size={22} /></span>
          <span className="ll-scanbanner-txt">
            <strong>Compare two locations</strong>
            <span>See how the same question is answered in two places.</span>
          </span>
          <Icon name="arrowR" size={18} style={{ opacity: 0.6 }} />
        </button>

        <Disclaimer compact />
      </Scroll>
    </Screen>
  );
}

// ── Thinking / retrieval ─────────────────────────────────────────────────────
function ThinkingScreen({ qid }) {
  const v = window.VERDICTS[qid] || window.VERDICTS.ebike;
  const q = window.__thinkingQ || v.q;
  const [step, setStep] = React.useState(0);
  const [count, setCount] = React.useState(0);
  const steps = [
    'Locating your jurisdiction',
    `Searching ${window.LOCATION.city || 'local'} municipal code`,
    'Ranking the relevant sections',
    'Reasoning with citations',
  ];
  React.useEffect(() => {
    const ts = [350, 800, 1300, 1750].map((ms, i) => setTimeout(() => setStep(i + 1), ms));
    let n = 0;
    const ci = setInterval(() => { n += 137; setCount(Math.min(n, 1926)); }, 60);
    return () => { ts.forEach(clearTimeout); clearInterval(ci); };
  }, []);
  return (
    <Screen bg="var(--paper)">
      <div className="ll-think">
        <BrandMark size={92} />
        <div className="ll-think-q">“{q}”</div>
        <div className="ll-think-count">
          <span className="ll-think-num">{count.toLocaleString()}</span> sections searched
        </div>
        <div className="ll-think-steps">
          {steps.map((s, i) => (
            <div key={i} className={'ll-think-step' + (i < step ? ' is-done' : i === step ? ' is-active' : '')}>
              <span className="ll-think-dot">
                {i < step ? <Icon name="check" size={14} color="var(--primary)" strokeWidth={2.4} /> : <Spinner size={14} color="var(--primary)" />}
              </span>
              {s}
            </div>
          ))}
        </div>
      </div>
    </Screen>
  );
}

// ── Compliance risk score (derived from verdict + penalty severity) ──────────
function complianceRisk(verdict, severity) {
  const rank = { none: 0, infraction: 1, civil: 1, misdemeanor: 2, felony: 3, unknown: 1 }[severity || 'unknown'] || 1;
  if (verdict === 'yes') return { n: 1, label: 'Low', varc: '--yes' };
  if (verdict === 'no') return rank >= 2 ? { n: 4, label: 'Critical', varc: '--no' } : { n: 3, label: 'High', varc: '--no' };
  if (verdict === 'warning') return rank >= 2 ? { n: 3, label: 'High', varc: '--warn' } : { n: 2, label: 'Medium', varc: '--warn' };
  return { n: 0, label: 'Unclear', varc: '--unknown' };
}

function RiskMeter({ verdict, severity }) {
  const r = complianceRisk(verdict, severity);
  return (
    <div className="ll-risk" title="Estimated from the verdict and statutory penalty severity">
      <span className="ll-risk-label">Compliance risk</span>
      <span className="ll-risk-dots">
        {[1, 2, 3, 4].map(i => (
          <span key={i} className="ll-risk-dot" style={{ background: i <= r.n ? `var(${r.varc})` : 'var(--surface-3)' }} />
        ))}
      </span>
      <span className="ll-risk-val" style={{ color: `var(${r.varc})` }}>{r.label}</span>
    </div>
  );
}

// ── #3: low-confidence / unknown "verify before relying" nudge ───────────────
function VerifyNudge({ verdict, confidence }) {
  const unknown = verdict === 'unknown';
  const low = unknown || (confidence || 0) < 0.55;
  if (!low) return null;
  return (
    <div className="ll-verify">
      <span className="ll-verify-ic"><Icon name="info" size={16} color="var(--warn)" /></span>
      <div className="ll-verify-txt">
        <strong>{unknown ? 'No clear answer in the retrieved law' : 'Lower confidence — verify before you rely on this'}</strong>
        <span>{unknown
          ? 'The dataset may not cover this, or the wording differs. Try rephrasing, check the official code, or consult a professional.'
          : 'The retrieved sections only partly settle this. Re-read the cited text below, and get professional advice for anything consequential.'}</span>
      </div>
    </div>
  );
}

// ── #2: transparency — exactly what the AI retrieved, ranked by match ─────────
function WhyVerdict({ retrieved }) {
  const [open, setOpen] = React.useState(false);
  const rows = (retrieved || []).slice(0, 8);
  if (!rows.length) return null;
  return (
    <div className="ll-why">
      <button className="ll-why-toggle" onClick={() => setOpen(o => !o)} aria-expanded={open}>
        <Icon name="search" size={15} />
        <span>Why this verdict?</span>
        <span className="ll-why-count">{rows.length} sections</span>
        <Icon name="chevron" size={16} className={'ll-why-chev' + (open ? ' is-open' : '')} />
      </button>
      {open && (
        <div className="ll-why-body">
          <p className="ll-why-note">Grounded only in these sections, ranked by semantic match to your question. Nothing outside this list was used.</p>
          {rows.map((r, i) => {
            const sim = Math.max(0, Math.min(100, Math.round((1 - (r.distance || 0)) * 100)));
            const where = r.jurisdiction || [r.city, r.county, r.state].filter(Boolean).join(', ');
            return (
              <div key={i} className="ll-why-row">
                <div className="ll-why-row-top">
                  <span className="ll-why-lvl">{r.level || '—'}</span>
                  <span className="ll-why-sid">{r.section_id}{r.section_name ? ' · ' + r.section_name : ''}</span>
                  <span className="ll-why-sim">{sim}%</span>
                </div>
                {where && <div className="ll-why-where">{where}</div>}
                <div className="ll-why-bar"><div className="ll-why-bar-fill" style={{ width: Math.max(sim, 3) + '%' }} /></div>
                {r.text_preview && <div className="ll-why-prev">{r.text_preview.slice(0, 150)}…</div>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Verdict (hero) ───────────────────────────────────────────────────────────
function VerdictScreen({ qid, ctx, onBack, onSnapshot, onFollow, onCite }) {
  const v = window.VERDICTS[qid] || window.VERDICTS.ebike;
  const meta = window.VERDICT_META[v.verdict];
  const hasCtx = ctx && ctx.ctxOpen && (v.context.activity || v.context.speed_kmh);
  return (
    <Screen bg="var(--paper)">
      <AppBar
        bg="var(--paper)"
        left={<BackBtn onClick={onBack} label="Ask" />}
        title=""
        right={<IconBtn name="share" title="Share" onClick={onSnapshot} />}
      />
      <Scroll className="ll-verdict-scroll" padBottom={40}>
        <div className={'ll-cert ll-cert-' + v.verdict}>
          <div className="ll-cert-bar" />
          <div className="ll-cert-guilloche" />
          <div className="ll-cert-frame">
            <span className="ll-cert-corner tl" /><span className="ll-cert-corner tr" />
            <span className="ll-cert-corner bl" /><span className="ll-cert-corner br" />
          </div>
          <div className="ll-cert-eyebrow"><span>In the matter of</span></div>
          <div className="ll-cert-q">{v.q}</div>
          <div className="ll-cert-seal">
            <Seal verdict={v.verdict} size={202}
              jurisdiction={`${(window.LOCATION.city || '').toUpperCase()} · ${window.LOCATION.state}`} />
          </div>
          <div className="ll-cert-label" style={{ color: `var(${meta.varc})` }}>
            {meta.label.toUpperCase()}
          </div>
          <div className="ll-cert-conf">
            <Confidence value={v.confidence} varc={meta.varc} />
            <RiskMeter verdict={v.verdict} severity={v.penalty_severity} />
          </div>
        </div>

        <div className="ll-answer">
          <p>{v.answer}</p>
        </div>

        <VerifyNudge verdict={v.verdict} confidence={v.confidence} />

        {hasCtx && (
          <div className="ll-ctxnote">
            <Icon name="bolt" size={16} color={`var(${meta.varc})`} />
            <span>Weighed your live context:&nbsp;
              <strong>{v.context.activity}{v.context.speed_kmh ? ` · ${v.context.speed_kmh} km/h` : ''}</strong>
            </span>
          </div>
        )}

        <PenaltyCard penalty={v.penalty} severity={v.penalty_severity} />

        {v.conflicts && v.conflicts.length > 0 && (
          <div className="ll-conflict">
            <div className="ll-conflict-head"><Icon name="layers" size={15} /> Jurisdictions disagree</div>
            {v.conflicts.map((c, i) => (
              <div key={i} className="ll-conflict-row"><Icon name="info" size={14} /> <span>{c}</span></div>
            ))}
          </div>
        )}

        <SectionLabel right={<span className="ll-seclabel-n">{v.citations.length}</span>}>
          {v.citations.length ? 'Cited law' : 'Citations'}
        </SectionLabel>
        {v.citations.length === 0 ? (
          <Card className="ll-nocite">
            <Icon name="info" size={18} color="var(--ink-3)" />
            <span>No section settles this. The verdict reflects the <em>absence</em> of a matching ordinance in the retrieved code, not permission.</span>
          </Card>
        ) : (
          <div className="ll-cites">
            {v.citations.map((c, i) => <CitationCard key={i} c={c} index={i} defaultOpen={i === 0} />)}
          </div>
        )}

        <WhyVerdict retrieved={v.retrieved} />

        {(window.LOCATION.country || 'US') !== 'KR' && (
          <React.Fragment>
            <SectionLabel>Layers consulted</SectionLabel>
            <JurisStack citations={v.citations} />
          </React.Fragment>
        )}

        {v.caveats && (
          <div className="ll-caveat">
            <div className="ll-caveat-head"><Icon name="info" size={15} /> What this doesn’t cover</div>
            <p>{v.caveats}</p>
          </div>
        )}

        <div className="ll-verdict-actions">
          <Button variant="primary" icon="shield" full size="lg" onClick={onSnapshot}>Save compliance snapshot</Button>
          <Button variant="ghost" icon="plus" full onClick={onFollow}>Ask a follow-up</Button>
        </div>
        <Disclaimer />
      </Scroll>
    </Screen>
  );
}

Object.assign(window, { BrandMark, OnboardingScreen, AskScreen, ThinkingScreen, VerdictScreen });
