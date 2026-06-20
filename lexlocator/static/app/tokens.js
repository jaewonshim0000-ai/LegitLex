// LegitLex — brand themes (the requested "overall visual style" exploration).
// Each theme is a full set of CSS variables applied on the app root. The app
// structure is identical across themes; only the skin changes.

const THEMES = {
  indigo: {
    label: 'Indigo Civic',
    blurb: 'Clean, modern civic — indigo authority, emerald assent.',
    statusDark: false,
    vars: {
      '--paper': '#E9EBF4',
      '--paper-2': '#DFE2EF',
      '--surface': '#FFFFFF',
      '--surface-2': '#F4F5FB',
      '--surface-3': '#ECEEF7',
      '--ink': '#181A2C',
      '--ink-2': '#4B4F68',
      '--ink-3': '#878BA6',
      '--line': '#E2E4F0',
      '--line-2': '#D3D6E6',
      '--primary': '#3F38C9',
      '--primary-press': '#322CA8',
      '--primary-ink': '#FFFFFF',
      '--primary-soft': '#ECEBFB',
      '--primary-soft-ink': '#352FA6',
      '--accent': '#06915E',
      '--yes': '#0B7A4B', '--yes-soft': '#E1F2E9', '--yes-ink': '#0B5B39',
      '--no': '#C02A2A', '--no-soft': '#FAE6E4', '--no-ink': '#8E1F1F',
      '--warn': '#B26206', '--warn-soft': '#FBEEDB', '--warn-ink': '#824907',
      '--unknown': '#4E5468', '--unknown-soft': '#E9EBF1', '--unknown-ink': '#3A3F50',
      '--font-ui': "'Public Sans', system-ui, sans-serif",
      '--font-legal': "'Spectral', Georgia, serif",
      '--font-mono': "'JetBrains Mono', ui-monospace, monospace",
      '--radius': '20px',
      '--radius-sm': '13px',
      '--seal-grain': '0.06',
    },
  },

  parchment: {
    label: 'Ink & Parchment',
    blurb: 'Notary warmth — oxblood seal on aged paper, serif-forward.',
    statusDark: false,
    vars: {
      '--paper': '#E6DECC',
      '--paper-2': '#DCD2BC',
      '--surface': '#FBF7EC',
      '--surface-2': '#F3ECDA',
      '--surface-3': '#EDE4CE',
      '--ink': '#241E15',
      '--ink-2': '#5E5340',
      '--ink-3': '#928straw', // overridden below
      '--line': '#DDD0B5',
      '--line-2': '#CDBE9C',
      '--primary': '#7C2D27',
      '--primary-press': '#641F1A',
      '--primary-ink': '#FBF3E6',
      '--primary-soft': '#F0E1D5',
      '--primary-soft-ink': '#6A241F',
      '--accent': '#9A7B1F',
      '--yes': '#3F6B3A', '--yes-soft': '#E6ECD9', '--yes-ink': '#2F5029',
      '--no': '#7C2D27', '--no-soft': '#F1DFD8', '--no-ink': '#5E1E19',
      '--warn': '#9A6614', '--warn-soft': '#F2E4C9', '--warn-ink': '#714A0D',
      '--unknown': '#5E5340', '--unknown-soft': '#EBE2CD', '--unknown-ink': '#473E2F',
      '--font-ui': "'Public Sans', system-ui, sans-serif",
      '--font-legal': "'Spectral', Georgia, serif",
      '--font-mono': "'JetBrains Mono', ui-monospace, monospace",
      '--radius': '16px',
      '--radius-sm': '11px',
      '--seal-grain': '0.10',
    },
  },

  navy: {
    label: 'Federal Navy',
    blurb: 'Passport-grade — deep navy, gold star, crisp white.',
    statusDark: false,
    vars: {
      '--paper': '#E4E9F1',
      '--paper-2': '#D7DEEA',
      '--surface': '#FFFFFF',
      '--surface-2': '#F1F4FA',
      '--surface-3': '#E7ECF5',
      '--ink': '#0E2238',
      '--ink-2': '#3A5474',
      '--ink-3': '#7C90AC',
      '--line': '#D8E0EC',
      '--line-2': '#C5D1E2',
      '--primary': '#133B66',
      '--primary-press': '#0D2C4E',
      '--primary-ink': '#FFFFFF',
      '--primary-soft': '#E3ECF7',
      '--primary-soft-ink': '#123459',
      '--accent': '#B08621',
      '--yes': '#0B6E54', '--yes-soft': '#DDF0E9', '--yes-ink': '#0A523F',
      '--no': '#B22234', '--no-soft': '#F8E1E3', '--no-ink': '#8A1626',
      '--warn': '#A66A12', '--warn-soft': '#F7E9CF', '--warn-ink': '#7C4E0C',
      '--unknown': '#3A5474', '--unknown-soft': '#E7ECF4', '--unknown-ink': '#2B3F58',
      '--font-ui': "'Public Sans', system-ui, sans-serif",
      '--font-legal': "'Spectral', Georgia, serif",
      '--font-mono': "'JetBrains Mono', ui-monospace, monospace",
      '--radius': '18px',
      '--radius-sm': '12px',
      '--seal-grain': '0.07',
    },
  },
};

// fix the stray token (kept explicit to avoid silent fallback)
THEMES.parchment.vars['--ink-3'] = '#988A6E';

function themeStyle(themeId) {
  const t = THEMES[themeId] || THEMES.indigo;
  return { ...t.vars };
}

Object.assign(window, { THEMES, themeStyle });
