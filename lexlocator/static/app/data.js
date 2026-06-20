// LegitLex — mock data, grounded in the real Irvine, CA municipal code that
// ships with the project. Verdicts mirror the server's Verdict schema:
// { verdict, confidence, answer, citations[], caveats } plus retrieved[] previews.

const LOCATION = {
  city: 'Irvine',
  county: 'Orange County',
  state: 'CA',
  country: 'US',
  lat: 33.6839,
  lng: -117.8214,
  neighborhood: 'Woodbridge',
  cross_streets: 'Barranca Pkwy & Lake Rd',
  accuracy_m: 8,
};

// Jurisdiction coverage — what code we actually have ingested for this spot.
const COVERAGE = [
  { level: 'city',    name: 'Irvine Municipal Code',        sections: 1284, status: 'complete', updated: 'May 2026', note: 'Full ordinance set' },
  { level: 'city',    name: 'Irvine Zoning Ordinance',      sections: 642,  status: 'complete', updated: 'May 2026', note: 'Land-use & zoning' },
  { level: 'county',  name: 'Orange County Ordinances',     sections: 0,    status: 'missing',  updated: '—',        note: 'Not yet ingested' },
  { level: 'state',   name: 'California Vehicle Code',      sections: 212,  status: 'partial',  updated: 'Apr 2026', note: 'Traffic excerpts only' },
  { level: 'federal', name: 'Federal baseline rules',       sections: 38,   status: 'partial',  updated: 'Jan 2026', note: 'Selected floors' },
];

// Quick-ask chips on the home screen.
const SUGGESTIONS = [
  { id: 'ebike',   icon: 'bike',   text: 'Can I ride my Class 3 e-bike on this trail?' },
  { id: 'dog',     icon: 'paw',    text: 'Can my dog be off-leash at this park?' },
  { id: 'noise',   icon: 'wave',   text: 'What are the quiet hours here?' },
  { id: 'parking', icon: 'car',    text: 'Is overnight street parking allowed?' },
  { id: 'drone',   icon: 'drone',  text: 'Can I fly a drone in this park?' },
];

// Full verdicts keyed by question id.
const VERDICTS = {
  ebike: {
    q: 'Can I ride my Class 3 e-bike on this trail?',
    context: { activity: 'Class 3 e-bike', speed_kmh: 30 },
    verdict: 'warning',
    confidence: 0.82,
    answer: "Not on this path. Class 3 e-bikes are barred from Irvine's Class I bike paths and off-street trails unless a sign expressly allows them. They are legal in the street and in on-road bike lanes — move to the adjacent roadway.",
    citations: [
      {
        level: 'city', jurisdiction: 'Irvine, CA',
        section_id: '6-3-208', section_name: 'Electric bicycles on trails and Class I bikeways',
        paraphrase: 'Type 3 (Class 3) electric bicycles are prohibited on equestrian, hiking, recreational, and Class I bicycle trails unless a posted sign expressly permits them.',
        source: 'Irvine Municipal Code', page: 418, last_amended: '2024',
        preview: 'No type 3 electric bicycle shall be operated upon any equestrian trail, hiking or recreational trail, or Class I bikeway unless that use is authorized by ordinance or expressly permitted by posted signage…',
        distance: 0.21,
      },
      {
        level: 'state', jurisdiction: 'California',
        section_id: 'CVC §21207.5', section_name: 'Motorized bicycles on paths and trails',
        paraphrase: 'State law bars motorized bicycles and Class 3 e-bikes from bicycle paths and trails except where a local authority permits the use by ordinance.',
        source: 'California Vehicle Code', page: 0,
        preview: '…a motorized bicycle or a class 3 electric bicycle shall not be operated on a bicycle path or trail, bikeway, equestrian trail, or hiking or recreational trail, unless it is within or adjacent to a roadway or unless the local authority permits…',
        distance: 0.29,
      },
    ],
    caveats: 'Orange County regional-trail rules were not in the retrieved set and may add restrictions on wilderness or county-managed trails. Posted trail signage overrides this answer where present.',
    penalty: 'Infraction. A first violation is punishable by a fine of up to $100; subsequent violations within one year carry higher fines.',
    penalty_severity: 'infraction',
    conflicts: ['California Vehicle Code lets local authorities decide; Irvine’s city ordinance bans Class 3 e-bikes on Class I paths. The stricter local rule governs here.'],
  },

  dog: {
    q: 'Can my dog be off-leash at this park?',
    context: { activity: null, speed_kmh: null },
    verdict: 'no',
    confidence: 0.91,
    answer: 'No. Dogs must be leashed in every Irvine park and public place. Off-leash is allowed only inside the city\u2019s designated, fenced dog parks — the nearest is Central Bark, about 1.4 mi away.',
    citations: [
      {
        level: 'city', jurisdiction: 'Irvine, CA',
        section_id: '4-5-103', section_name: 'Dogs at large prohibited',
        paraphrase: 'No person having control of a dog may permit it to be off-leash on public property except within an area the City has designated as an off-leash dog area.',
        source: 'Irvine Municipal Code', page: 286,
        preview: 'It is unlawful for any person owning or having charge, care, custody or control of any dog to permit such dog to be upon any public street, sidewalk, park or public place unless restrained by a leash not exceeding six feet…',
        distance: 0.18,
      },
    ],
    caveats: 'Leash-length limits and dog-park operating hours are set by the Community Services Department and were not part of the retrieved sections.',
    penalty: 'Infraction. Fine up to $100 for a first offense, rising to $200 and $500 for repeat offenses within a year; an impounded dog incurs additional pickup and boarding fees.',
    penalty_severity: 'infraction',
  },

  noise: {
    q: 'What are the quiet hours here?',
    context: { activity: null, speed_kmh: null },
    verdict: 'warning',
    confidence: 0.77,
    answer: 'A noise curfew applies. Loud or disturbing noise is restricted from 10:00 PM to 7:00 AM in and next to residential zones, and construction noise is limited to 7:00 AM\u20137:00 PM on weekdays. Daytime ordinary activity is fine.',
    citations: [
      {
        level: 'city', jurisdiction: 'Irvine, CA',
        section_id: '6-8-501', section_name: 'Noise control — prohibited hours',
        paraphrase: 'It is unlawful to make loud, disturbing or unnecessary noise that disturbs the peace between 10:00 p.m. and 7:00 a.m. within or adjacent to any residential zone.',
        source: 'Irvine Municipal Code', page: 455,
        preview: 'No person shall make, continue or cause to be made any loud, disturbing or unnecessary noise which disturbs the peace or quiet of any neighborhood between the hours of 10:00 p.m. and 7:00 a.m…',
        distance: 0.24,
      },
    ],
    caveats: 'Specific decibel thresholds and amplified-sound permit rules live in a separate chapter that was not retrieved for this answer.',
    penalty: 'Misdemeanor or infraction. A continuing noise violation can be charged as a misdemeanor (fine up to $1,000 and/or up to 6 months) or an infraction for a first offense.',
    penalty_severity: 'misdemeanor',
  },

  parking: {
    q: 'Is overnight street parking allowed?',
    context: { activity: null, speed_kmh: null },
    verdict: 'warning',
    confidence: 0.69,
    answer: 'Usually, but watch the posted signs. Irvine has no blanket overnight parking ban, yet many residential streets post street-sweeping and permit-only restrictions. Vehicles over 22 ft and unhitched trailers cannot park on the street overnight.',
    citations: [
      {
        level: 'city', jurisdiction: 'Irvine, CA',
        section_id: '6-6-312', section_name: 'Parking of oversized & recreational vehicles',
        paraphrase: 'No vehicle longer than 22 feet, trailer, or recreational vehicle may be parked on a public street between 2:00 a.m. and 5:00 a.m. without a permit.',
        source: 'Irvine Municipal Code', page: 441,
        preview: 'No person shall park or leave standing any oversized vehicle, recreational vehicle or trailer upon any public street between the hours of 2:00 a.m. and 5:00 a.m…',
        distance: 0.33,
      },
    ],
    caveats: 'Street-sweeping schedules and HOA-enforced private-street rules vary block to block and are not in the city code we retrieved.',
    penalty: 'Parking citation. A fine is set by the local bail schedule (typically $50–$75); the vehicle may also be towed at the owner’s expense.',
    penalty_severity: 'civil',
  },

  drone: {
    q: 'Can I fly a drone in this park?',
    context: { activity: null, speed_kmh: null },
    verdict: 'unknown',
    confidence: 0.0,
    answer: 'The retrieved Irvine code sections don\u2019t settle this. The city defers most drone rules to the FAA, and park-specific UAS restrictions weren\u2019t in the ingested set — treat this as unconfirmed and check posted park signage and FAA B4UFLY.',
    citations: [],
    caveats: 'No matching ordinance was retrieved. FAA Part 107 and any Orange County park-district UAS rules apply but are outside our current database.',
    penalty: 'Not specified in the retrieved law.',
    penalty_severity: 'unknown',
  },
};

// Sign-scan example (mirrors SignScanResponse).
const SIGN_SCAN = {
  sign_text: 'NO PARKING\n2 AM – 6 AM\nSTREET SWEEPING\nTHURSDAYS',
  extracted_rule: 'No parking from 2:00 AM to 6:00 AM on Thursdays for street sweeping.',
  appears_official: true,
  verified_against_code: true,
  note: 'Sign appears official.',
  matching_citations: [
    {
      level: 'city', jurisdiction: 'Irvine, CA',
      section_id: '6-6-318', section_name: 'Parking prohibited during street sweeping',
      paraphrase: 'Parking is prohibited on posted streets during designated street-sweeping hours; vehicles in violation may be cited and towed.',
      source: 'Irvine Municipal Code', page: 442,
      preview: 'No person shall stop, park or leave standing any vehicle upon any street during the hours posted for street sweeping operations as designated by signs…',
    },
  ],
};

// Past compliance records (the "evidence" trail).
const RECORDS = [
  { id: 'LX-7F3A21', qid: 'ebike',   label: 'Class 3 e-bike on trail',     verdict: 'warning', when: 'Today, 2:14 PM',  where: 'Barranca Pkwy & Lake Rd' },
  { id: 'LX-6C1980', qid: 'dog',     label: 'Dog off-leash at park',        verdict: 'no',      when: 'Today, 9:02 AM',  where: 'Woodbridge Community Park' },
  { id: 'LX-5A77E3', qid: 'noise',   label: 'Quiet hours',                  verdict: 'warning', when: 'Yesterday',       where: 'Turtle Rock' },
  { id: 'LX-4B2204', qid: 'parking', label: 'Overnight street parking',     verdict: 'warning', when: 'Jun 11',          where: 'Northwood' },
];

const VERDICT_META = {
  yes:     { word: 'APPROVED',     label: 'Allowed',           glyph: 'check',  varc: '--yes' },
  no:      { word: 'PROHIBITED',   label: 'Not allowed',       glyph: 'cross',  varc: '--no' },
  warning: { word: 'CONDITIONAL',  label: 'Allowed, with limits', glyph: 'bang', varc: '--warn' },
  unknown: { word: 'UNDETERMINED', label: 'Not settled',       glyph: 'query',  varc: '--unknown' },
};

const DISCLAIMER = 'Legal information, not legal advice. Laws change and our scrape may be incomplete — verify against the official municipal code before you act.';

// Demo result for the complaint analyzer (used when no API key is set).
const COMPLAINT_DEMO = {
  analysis: {
    summary: 'This is a City of Irvine code-enforcement notice alleging that loud amplified music was played from your residence after 10:00 PM, disturbing neighbors. It directs you to stop the violation and warns that continued violations may lead to fines.',
    complaint_type: 'Code enforcement notice',
    allegations: [
      { claim: 'Amplified noise after the 10:00 PM residential curfew', law_area: 'noise' },
      { claim: 'Disturbing the peace of a neighboring residence', law_area: 'noise' },
    ],
    citations: [
      { level: 'city', jurisdiction: 'Irvine, CA', section_id: '6-8-501',
        section_name: 'Noise control — prohibited hours',
        paraphrase: 'Loud or disturbing noise that disturbs the peace between 10:00 p.m. and 7:00 a.m. in or near a residential zone is unlawful.' },
    ],
    risk_level: 'medium',
    risk_rationale: 'A first noise violation is typically an infraction with a modest fine, but repeat violations can escalate to a misdemeanor — so ignoring the notice raises your exposure.',
    potential_penalties: 'Infraction for a first offense (fine, often up to a few hundred dollars); continued violations may be charged as a misdemeanor.',
    recommended_actions: [
      'Stop the cited activity immediately to avoid escalation.',
      'Note the response deadline on the notice and reply in writing if you dispute it.',
      'Gather evidence (dates, times, any recordings) in case you contest it.',
      'Contact Irvine Code Enforcement with the case number for clarification.',
      'Consult a local attorney if a fine or hearing is involved.',
    ],
    deadline: 'Respond within 14 days of the notice date (see the notice).',
    caveats: 'Based only on the noise ordinance in this dataset; the actual notice may cite other sections or set different deadlines.',
  },
  location: LOCATION,
  extracted_text_preview: 'CITY OF IRVINE — NOTICE OF VIOLATION. Our office received a complaint of loud amplified music after 10:00 PM at the above address…',
  retrieved: [],
  snapshot_id: 'CMP-DEMO01',
  timestamp_utc: '2026-06-16T21:00:00Z',
};

Object.assign(window, {
  LOCATION, COVERAGE, SUGGESTIONS, VERDICTS, SIGN_SCAN, RECORDS, VERDICT_META, DISCLAIMER,
  COMPLAINT_DEMO,
});
