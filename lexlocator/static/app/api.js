// LegitLex — live backend client.
//
// Talks to the FastAPI server (same origin). Converts the server's
// AskResponse / SignScanResponse / JurisdictionResponse into the exact data
// shapes the design screens already render (window.VERDICTS entries, etc.).
//
// LL_LIVE gates everything: it becomes true only after /api/health confirms the
// vector DB is loaded AND an Anthropic key is set on the server. When false,
// the UI falls back to the bundled mock data so the prototype always demos.

(function () {
  window.LL_LIVE = false; // flipped on by checkHealth()

  async function checkHealth() {
    try {
      const r = await fetch('/api/health');
      const h = await r.json();
      window.LL_HEALTH = h;
      window.LL_LIVE = !!(h.ok && (h.llm_key || h.anthropic_key));
      return h;
    } catch (e) {
      window.LL_HEALTH = { ok: false, error: String(e) };
      window.LL_LIVE = false;
      return window.LL_HEALTH;
    }
  }

  // ── Reverse geocode ────────────────────────────────────────────────────────
  async function geocode(lat, lng) {
    const fd = new FormData();
    fd.append('lat', lat);
    fd.append('lng', lng);
    const r = await fetch('/api/geocode', { method: 'POST', body: fd });
    if (!r.ok) throw new Error('geocode failed');
    return r.json(); // {city, county, state, country, lat, lng}
  }

  // ── Adapters: server shape -> design shape ─────────────────────────────────
  // Citation enrichment: the server's verdict citations carry section_id +
  // paraphrase; the full quoted text + page live in the retrieved[] array.
  // We join on section_id so the "Read the section" panel shows real text.
  function indexRetrieved(retrieved) {
    const byId = {};
    (retrieved || []).forEach((r) => {
      if (!byId[r.section_id]) byId[r.section_id] = r;
    });
    return byId;
  }

  function adaptCitation(c, retrievedById) {
    const r = (retrievedById && retrievedById[c.section_id]) || {};
    return {
      level: c.level || r.level || 'unknown',
      jurisdiction: c.jurisdiction || r.jurisdiction || '',
      section_id: c.section_id,
      section_name: c.section_name || r.section_name || '',
      paraphrase: c.paraphrase || '',
      source: c.source_url || r.breadcrumb || 'Municipal Code',
      page: c.page_start || r.page_start || 0,
      preview: r.text_preview || c.paraphrase || '',
      distance: typeof r.distance === 'number' ? r.distance : 0,
      last_amended: c.last_amended || '',
    };
  }

  function adaptAsk(resp, question, ctx) {
    const retrievedById = indexRetrieved(resp.retrieved);
    const v = resp.verdict || {};
    return {
      q: question,
      context: {
        activity: (ctx && ctx.activity) || null,
        speed_kmh: ctx && ctx.speed ? Number(ctx.speed) : null,
      },
      verdict: v.verdict || 'unknown',
      confidence: typeof v.confidence === 'number' ? v.confidence : 0,
      answer: v.answer || '',
      citations: (v.citations || []).map((c) => adaptCitation(c, retrievedById)),
      caveats: v.caveats || '',
      penalty: v.penalty || '',
      penalty_severity: v.penalty_severity || 'unknown',
      conflicts: v.conflicts || [],
      retrieved: resp.retrieved || [],
      snapshot_id: resp.snapshot_id || '',
      timestamp_utc: resp.timestamp_utc || '',
    };
  }

  function adaptSign(resp) {
    return {
      sign_text: resp.sign_text || '',
      extracted_rule: resp.extracted_rule || '',
      appears_official: /official/i.test(resp.note || ''),
      verified_against_code: !!resp.verified_against_code,
      note: resp.note || '',
      matching_citations: (resp.matching_citations || []).map((c) =>
        adaptCitation(c, null)
      ),
      timestamp_utc: resp.timestamp_utc || '',
    };
  }

  // ── Ask ────────────────────────────────────────────────────────────────────
  async function ask({ question, location, activity, speed }) {
    const body = {
      question,
      location: location || {},
      activity: activity || null,
      speed_kmh: speed ? Number(speed) : null,
    };
    const r = await fetch('/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(e.detail || 'ask failed');
    }
    const resp = await r.json();
    return adaptAsk(resp, question, { activity, speed });
  }

  // ── Scan sign ───────────────────────────────────────────────────────────────
  async function scanSign(file, location) {
    const fd = new FormData();
    fd.append('image', file);
    if (location) {
      if (location.lat != null) fd.append('lat', location.lat);
      if (location.lng != null) fd.append('lng', location.lng);
      if (location.city) fd.append('city', location.city);
      if (location.state) fd.append('state', location.state);
    }
    const r = await fetch('/api/scan-sign', { method: 'POST', body: fd });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(e.detail || 'scan failed');
    }
    return adaptSign(await r.json());
  }

  // ── Analyze complaint (file and/or pasted text) ─────────────────────────────
  async function analyzeComplaint({ file, text, location }) {
    const fd = new FormData();
    if (file) fd.append('file', file);
    if (text) fd.append('text', text);
    if (location) {
      if (location.lat != null) fd.append('lat', location.lat);
      if (location.lng != null) fd.append('lng', location.lng);
      if (location.city) fd.append('city', location.city);
      if (location.county) fd.append('county', location.county);
      if (location.state) fd.append('state', location.state);
    }
    const r = await fetch('/api/analyze-complaint', { method: 'POST', body: fd });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(e.detail || 'analysis failed');
    }
    return r.json();   // { analysis, location, extracted_text_preview, retrieved, ... }
  }

  // ── Compare two locations ───────────────────────────────────────────────────
  async function compare({ question, locationA, locationB }) {
    const r = await fetch('/api/compare', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, location_a: locationA, location_b: locationB }),
    });
    if (!r.ok) {
      const e = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(e.detail || 'compare failed');
    }
    return r.json();
  }

  // ── Jurisdiction coverage ───────────────────────────────────────────────────
  async function jurisdiction(lat, lng) {
    const r = await fetch(`/api/jurisdiction?lat=${lat}&lng=${lng}`);
    if (!r.ok) throw new Error('jurisdiction failed');
    return r.json();
  }

  // Real per-source coverage for the current location.
  async function coverage(location) {
    const p = new URLSearchParams();
    if (location) {
      if (location.city) p.set('city', location.city);
      if (location.county) p.set('county', location.county);
      if (location.state) p.set('state', location.state);
      if (location.lat != null) p.set('lat', location.lat);
      if (location.lng != null) p.set('lng', location.lng);
    }
    const r = await fetch('/api/coverage?' + p.toString());
    if (!r.ok) throw new Error('coverage failed');
    return r.json();
  }

  function snapshotUrl(id) {
    return `/api/snapshot/${id}`;
  }

  window.LL_API = {
    checkHealth,
    geocode,
    ask,
    scanSign,
    analyzeComplaint,
    compare,
    jurisdiction,
    coverage,
    snapshotUrl,
    adaptAsk,
    adaptSign,
  };

  // ── Records: a private, on-device evidence trail (localStorage) ─────────────
  const RKEY = 'll_records_v1';
  window.LL_RECORDS = {
    all() {
      try { return JSON.parse(localStorage.getItem(RKEY) || '[]'); }
      catch (e) { return []; }
    },
    add(rec) {
      const a = this.all();
      a.unshift(Object.assign({ ts: Date.now(), id: 'LX-' + Math.random().toString(36).slice(2, 8).toUpperCase() }, rec));
      try { localStorage.setItem(RKEY, JSON.stringify(a.slice(0, 100))); } catch (e) {}
      return a[0];
    },
    clear() { try { localStorage.removeItem(RKEY); } catch (e) {} },
  };
})();
