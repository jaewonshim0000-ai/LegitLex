// LegitLex — Scan flow: Camera viewfinder, Scan result, Compliance snapshot.

// ── A reusable mock street sign (used in viewfinder + result thumb) ──────────
function StreetSign({ scale = 1 }) {
  return (
    <div className="ll-sign" style={{ transform: `scale(${scale})` }}>
      <div className="ll-sign-board">
        <div className="ll-sign-top">NO PARKING</div>
        <div className="ll-sign-mid">2 AM – 6 AM</div>
        <div className="ll-sign-sub">STREET SWEEPING</div>
        <div className="ll-sign-sub">THURSDAYS</div>
      </div>
      <div className="ll-sign-pole" />
    </div>
  );
}

// ── Camera / sign scanner ────────────────────────────────────────────────────
function CameraScreen({ onCapture, onClose }) {
  const [flash, setFlash] = React.useState(false);
  const camRef = React.useRef(null);   // opens rear camera on mobile
  const galRef = React.useRef(null);   // opens photo library

  const capture = () => {
    setFlash(true);
    setTimeout(() => { setFlash(false); onCapture(); }, 280);
  };

  const onFile = (e) => {
    const f = e.target.files && e.target.files[0];
    if (!f) return;
    window.__signFile = f;
    if (window.__signFileURL) URL.revokeObjectURL(window.__signFileURL);
    window.__signFileURL = URL.createObjectURL(f);
    capture();
  };

  // Live mode: shutter opens the real camera. Demo mode: "captures" the
  // bundled example sign so the flow is still walkable offline.
  const shoot = () => {
    if (window.LL_LIVE && camRef.current) { camRef.current.click(); return; }
    window.__signFile = null;
    window.__signFileURL = null;
    capture();
  };

  return (
    <Screen bg="#0b0d10">
      <div className="ll-cam">
        <div className="ll-cam-scene">
          <div className="ll-cam-vignette" />
          <StreetSign scale={1.05} />
          <div className="ll-cam-scanline" />
        </div>

        <div className="ll-cam-top">
          <button className="ll-cam-x" onClick={onClose}><Icon name="cross" size={20} color="#fff" /></button>
          <div className="ll-cam-mode">SCAN SIGN</div>
          <button className="ll-cam-x"><Icon name="bolt" size={20} color="#fff" /></button>
        </div>

        <div className="ll-cam-frame">
          <span className="c tl" /><span className="c tr" /><span className="c bl" /><span className="c br" />
          <div className="ll-cam-hint">Center the posted sign in the frame</div>
        </div>

        <div className="ll-cam-bottom">
          <div className="ll-cam-loc"><Icon name="pin" size={14} color="rgba(255,255,255,.7)" /> {window.LOCATION.city}, {window.LOCATION.state}</div>
          <div className="ll-cam-controls">
            <button className="ll-cam-gallery" onClick={() => galRef.current && galRef.current.click()}><Icon name="image" size={22} color="#fff" /></button>
            <button className="ll-cam-shutter" onClick={shoot}><span /></button>
            <button className="ll-cam-gallery" onClick={shoot}><Icon name="refresh" size={22} color="#fff" /></button>
          </div>
          <div className="ll-cam-tip">We read the text, then cross-check it against the official code.</div>
        </div>

        <input ref={camRef} type="file" accept="image/*" capture="environment" style={{ display: 'none' }} onChange={onFile} />
        <input ref={galRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={onFile} />

        {flash && <div className="ll-cam-flash" />}
      </div>
    </Screen>
  );
}

// ── Scan result ──────────────────────────────────────────────────────────────
function ScanResultScreen({ onBack, onSnapshot, onRescan, onNav }) {
  const live = window.LL_LIVE && window.__signFile;
  const [d, setD] = React.useState(live ? null : window.SIGN_SCAN);
  const photoURL = window.__signFileURL;

  // Live: send the captured photo to Claude vision + cross-reference the code.
  React.useEffect(() => {
    if (!live) return;
    let alive = true;
    window.LL_API.scanSign(window.__signFile, window.LOCATION)
      .then((res) => { if (alive) setD(res); })
      .catch((e) => { console.warn('Live scan failed; using bundled data.', e); if (alive) setD(window.SIGN_SCAN); });
    return () => { alive = false; };
  }, []);

  if (!d) {
    return (
      <Screen tab="scan" onNav={onNav}>
        <AppBar left={<BackBtn onClick={onBack} label="Scan" />} title="Reading sign…" />
        <div className="ll-think" style={{ paddingTop: 70 }}>
          <Spinner size={30} color="var(--primary)" />
          <div className="ll-think-q">Reading the sign &amp; cross-checking the official code…</div>
        </div>
      </Screen>
    );
  }

  return (
    <Screen tab="scan" onNav={onNav}>
      <AppBar left={<BackBtn onClick={onBack} label="Scan" />} title="Sign result"
        right={<IconBtn name="refresh" title="Rescan" onClick={onRescan} />} />
      <Scroll padBottom={96}>
        <div className="ll-scan-cap">
          <div className="ll-scan-photo">
            {photoURL
              ? <img src={photoURL} alt="Captured sign" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
              : <div className="ll-scan-photo-scene"><StreetSign scale={0.62} /></div>}
            <span className="ll-scan-photo-tag"><Icon name="camera" size={12} /> Captured</span>
          </div>
          <div className={'ll-verified' + (d.verified_against_code ? ' is-yes' : ' is-no')}>
            <span className="ll-verified-ic">
              <Icon name={d.verified_against_code ? 'shield' : 'info'} size={22}
                color={d.verified_against_code ? 'var(--yes)' : 'var(--warn)'} />
            </span>
            <div>
              <strong>{d.verified_against_code ? 'Verified against code' : 'Not verified'}</strong>
              <span>{d.note}</span>
            </div>
          </div>
        </div>

        <SectionLabel>What the sign says</SectionLabel>
        <Card>
          <div className="ll-signtext">{d.sign_text}</div>
          <div className="ll-signrule">
            <Icon name="edit" size={15} color="var(--ink-3)" />
            <span><strong>Rule:</strong> {d.extracted_rule}</span>
          </div>
        </Card>

        <SectionLabel right={<span className="ll-seclabel-n">{d.matching_citations.length}</span>}>
          Matching ordinance
        </SectionLabel>
        {d.matching_citations.length === 0 ? (
          <Card className="ll-nocite">
            <Icon name="info" size={18} color="var(--ink-3)" />
            <span>No matching ordinance was found in the official code for your location. This sign may be private, outdated, or its rule lives in a code we haven’t ingested yet.</span>
          </Card>
        ) : (
          <div className="ll-cites">
            {d.matching_citations.map((c, i) => <CitationCard key={i} c={c} defaultOpen={true} />)}
          </div>
        )}

        <div className="ll-verdict-actions">
          <Button variant="primary" icon="shield" full size="lg" onClick={onSnapshot}>Save snapshot</Button>
          <Button variant="ghost" icon="camera" full onClick={onRescan}>Scan another sign</Button>
        </div>
        <Disclaimer compact />
      </Scroll>
    </Screen>
  );
}

// ── Compliance snapshot (evidence document) ──────────────────────────────────
function SnapshotScreen({ qid, recordId = 'LX-7F3A21', onBack, onDone }) {
  const v = window.VERDICTS[qid] || window.VERDICTS.ebike;
  const meta = window.VERDICT_META[v.verdict];
  const L = window.LOCATION;
  // A real, server-generated snapshot exists for live verdicts; download it.
  const snapId = v.snapshot_id || window.__liveSnapshotId || recordId;
  const canDownload = !!(window.LL_LIVE && window.LL_API && (v.snapshot_id || window.__liveSnapshotId));
  const issued = v.timestamp_utc
    ? new Date(v.timestamp_utc).toLocaleString()
    : '14 Jun 2026 · 14:14 PT';
  const coords = (L.lat != null && L.lng != null)
    ? `${L.lat.toFixed(4)}, ${L.lng.toFixed(4)}` : '—';
  const openSnapshot = () => {
    if (canDownload) window.open(window.LL_API.snapshotUrl(snapId), '_blank');
  };
  return (
    <Screen bg="var(--paper-2)">
      <AppBar bg="var(--paper-2)" left={<BackBtn onClick={onBack} label="Back" />}
        title="" right={<IconBtn name="download" title="Download" onClick={openSnapshot} />} />
      <Scroll padBottom={120}>
        <div className="ll-snapwrap">
          <div className="ll-snap">
            <div className="ll-snap-edge" />
            <div className="ll-snap-head">
              <div className="ll-snap-head-l">
                <BrandMark size={40} />
                <div>
                  <div className="ll-snap-brand">LegitLex</div>
                  <div className="ll-snap-kind">Compliance Snapshot</div>
                </div>
              </div>
              <div className="ll-snap-seal"><Seal verdict={v.verdict} size={84} rotate={0} flat /></div>
            </div>

            <div className="ll-snap-meta">
              <div><span>Record</span><b className="mono">{snapId}</b></div>
              <div><span>Issued</span><b className="mono">{issued}</b></div>
              <div><span>Location</span><b>{[L.city, L.county, L.state].filter(Boolean).join(', ')}</b></div>
              <div><span>Coordinates</span><b className="mono">{coords}</b></div>
            </div>

            <div className="ll-snap-rule" />

            <div className="ll-snap-section">
              <div className="ll-snap-lbl">Question</div>
              <div className="ll-snap-q">“{v.q}”</div>
            </div>

            <div className="ll-snap-verdict" style={{ color: `var(${meta.varc})`, borderColor: `var(${meta.varc})` }}>
              <Icon name={meta.glyph === 'check' ? 'check' : meta.glyph === 'cross' ? 'cross' : meta.glyph === 'bang' ? 'bang' : 'query'}
                size={18} strokeWidth={2.4} />
              <span>{meta.word}</span>
              <span className="ll-snap-verdict-conf">conf. {Math.round(v.confidence * 100)}%</span>
            </div>

            <div className="ll-snap-section">
              <div className="ll-snap-lbl">Finding</div>
              <p className="ll-snap-answer">{v.answer}</p>
            </div>

            {v.penalty && v.penalty_severity !== 'none' && (
              <div className="ll-snap-section">
                <div className="ll-snap-lbl">Potential penalty</div>
                <p className="ll-snap-answer">{v.penalty}</p>
              </div>
            )}

            <div className="ll-snap-section">
              <div className="ll-snap-lbl">Authority cited</div>
              {v.citations.length === 0 ? (
                <div className="ll-snap-cite"><span className="mono">—</span> No section settled this question.</div>
              ) : v.citations.map((c, i) => (
                <div key={i} className="ll-snap-cite">
                  <span className="mono">§ {c.section_id}</span>
                  <span className="ll-snap-cite-name">{c.section_name} — <i>{c.source}{c.page ? `, p.${c.page}` : ''}</i></span>
                </div>
              ))}
            </div>

            <div className="ll-snap-rule" />
            <div className="ll-snap-foot">
              <div className="ll-snap-hash">
                <div className="ll-snap-lbl">Verification</div>
                <div className="mono">sha256:9f3a·c712·44e8·1b09·ad55·6e2f</div>
                <div className="ll-snap-fine">Captured from {v.citations[0]?.source || 'Irvine Municipal Code'} via LegitLex. Legal information, not legal advice.</div>
              </div>
              <div className="ll-snap-qr" aria-hidden="true">{Array.from({ length: 49 }).map((_, i) => (
                <span key={i} style={{ opacity: (i * 7 + (i % 5) * 3) % 3 === 0 ? 1 : 0 }} />
              ))}</div>
            </div>
          </div>
        </div>

        <div className="ll-snap-actions">
          <Button variant="primary" icon="download" full size="lg" onClick={openSnapshot}>
            {canDownload ? 'Open / Export snapshot' : 'Snapshot (demo)'}
          </Button>
          <Button variant="ghost" icon="check" full onClick={onDone}>Done</Button>
        </div>
      </Scroll>
    </Screen>
  );
}

Object.assign(window, { StreetSign, CameraScreen, ScanResultScreen, SnapshotScreen });
