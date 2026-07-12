/**
 * Real judge-roster seed data (Task 22.3).
 *
 * Display names are PUBLIC Philadelphia First Judicial District (FJD) judges —
 * sitting Court of Common Pleas (criminal/trial division) and Municipal Court
 * judges — sourced from public judicial directories (PA UJS / FJD). Unlike the
 * obviously-fake Sprint 2 `JUDGE_SEEDS`, these are real public officials; a real
 * docket value is normalized against THIS roster, never against a fabricated
 * identity (the fake seeds are excluded from the match pool in the matcher).
 *
 * Storage convention (roster-gate Answer 3): `displayName` is the PUBLIC natural
 * order string ("Given [Middle] Surname [Suffix]"), the same surface the Sprint 2
 * endpoints return. The 22.3 matcher is display-format-independent: its
 * canonicalizer parses the captured CPCMS surname-first comma form and this
 * natural order into the same structured identity (hyphenated surnames fold to a
 * single token; generational suffixes are held separately). No comma-form alias
 * is needed for the hyphenated surnames in this set (there are no space-separated
 * compound surnames); `aliases` would carry a comma-form alias only for such a
 * compound, or a genuine name variant.
 *
 * The roster is the public criminal-relevant bench, not a corpus echo (pinned
 * decision 2). Two groups, both independently confirmed against the public FJD
 * criminal assignment chart / pacourts Municipal Court list at the roster gate:
 *
 *   1. Observed in-corpus AND directory-confirmed (the first 53).
 *   2. Directory-completeness additions (the final 23): sitting CP-criminal +
 *      Municipal Court judges (and recent-departed who could have sat in the 2025
 *      window) NOT observed in this corpus but who can appear on a CR docket.
 *
 * Every name is transcribed VERBATIM from the approved verified curation list;
 * no name is sourced or altered here. Slugs follow the deterministic convention
 * (surname tokens, then given tokens, then any generational suffix, lower-cased,
 * intra-name hyphens kept, apostrophes/periods dropped).
 */

export interface JudgeRosterSeed {
  slug: string;
  displayName: string;
  aliases: readonly string[];
}

export const JUDGE_ROSTER_SEEDS: readonly JudgeRosterSeed[] = [
  { slug: 'shaffer-zachary-c', displayName: 'Zachary C. Shaffer', aliases: [] },
  { slug: 'bryant-powell-crystal', displayName: 'Crystal Bryant-Powell', aliases: [] },
  { slug: 'palumbo-frank', displayName: 'Frank Palumbo', aliases: [] },
  { slug: 'taylor-smith-natasha', displayName: 'Natasha Taylor-Smith', aliases: [] },
  { slug: 'hangley-michele', displayName: 'Michele Hangley', aliases: [] },
  { slug: 'johnson-shanese-i', displayName: 'Shanese I. Johnson', aliases: [] },
  { slug: 'woelpper-donna', displayName: 'Donna Woelpper', aliases: [] },
  { slug: 'sawyer-stephanie-m', displayName: 'Stephanie M. Sawyer', aliases: [] },
  { slug: 'covington-roxanne', displayName: 'Roxanne Covington', aliases: [] },
  { slug: 'gibbs-monica', displayName: 'Monica Gibbs', aliases: [] },
  { slug: 'brandeis-roman-tracy', displayName: 'Tracy Brandeis-Roman', aliases: [] },
  { slug: 'washington-tamika', displayName: 'Tamika Washington', aliases: [] },
  { slug: 'kamau-nicholas', displayName: 'Nicholas Kamau', aliases: [] },
  { slug: 'yu-kay', displayName: 'Kay Yu', aliases: [] },
  { slug: 'moore-mark-j', displayName: 'Mark J. Moore', aliases: [] },
  { slug: 'anhalt-diana-l', displayName: 'Diana L. Anhalt', aliases: [] },
  { slug: 'lightsey-chesley', displayName: 'Chesley Lightsey', aliases: [] },
  { slug: 'okeefe-j-scott', displayName: "J. Scott O'Keefe", aliases: [] },
  { slug: 'cianfrani-deborah-d', displayName: 'Deborah D. Cianfrani', aliases: [] },
  { slug: 'diclaudio-scott', displayName: 'Scott DiClaudio', aliases: [] },
  { slug: 'levin-craig-r', displayName: 'Craig R. Levin', aliases: [] },
  { slug: 'means-rayford-a', displayName: 'Rayford A. Means', aliases: [] },
  { slug: 'clemons-lucretia', displayName: 'Lucretia Clemons', aliases: [] },
  { slug: 'defino-nastasi-rose', displayName: 'Rose DeFino-Nastasi', aliases: [] },
  { slug: 'ross-elvin', displayName: 'Elvin Ross', aliases: [] },
  { slug: 'williams-samantha', displayName: 'Samantha Williams', aliases: [] },
  { slug: 'brown-jessica-r', displayName: 'Jessica R. Brown', aliases: [] },
  { slug: 'ehrlich-charles-a', displayName: 'Charles A. Ehrlich', aliases: [] },
  { slug: 'ransom-lillian', displayName: 'Lillian Ransom', aliases: [] },
  { slug: 'kyriakakis-anthony', displayName: 'Anthony Kyriakakis', aliases: [] },
  { slug: 'brady-frank-t', displayName: 'Frank T. Brady', aliases: [] },
  { slug: 'schultz-jennifer', displayName: 'Jennifer Schultz', aliases: [] },
  { slug: 'campbell-giovanni-o', displayName: 'Giovanni O. Campbell', aliases: [] },
  { slug: 'meehan-william-austin-jr', displayName: 'William Austin Meehan Jr.', aliases: [] },
  { slug: 'mcdermott-barbara-a', displayName: 'Barbara A. McDermott', aliases: [] },
  { slug: 'sabatina-john-p-jr', displayName: 'John P. Sabatina Jr.', aliases: [] },
  { slug: 'bronson-glenn-b', displayName: 'Glenn B. Bronson', aliases: [] },
  { slug: 'joel-kenneth', displayName: 'Kenneth Joel', aliases: [] },
  { slug: 'grey-daine-jr', displayName: 'Daine Grey Jr.', aliases: [] },
  { slug: 'hall-christopher', displayName: 'Christopher Hall', aliases: [] },
  { slug: 'hayden-charles', displayName: 'Charles Hayden', aliases: [] },
  { slug: 'capuzzi-john-p-sr', displayName: 'John P. Capuzzi Sr.', aliases: [] },
  { slug: 'coleman-robert-p', displayName: 'Robert P. Coleman', aliases: [] },
  { slug: 'hope-christine-m', displayName: 'Christine M. Hope', aliases: [] },
  { slug: 'king-leon', displayName: 'Leon King', aliases: [] },
  { slug: 'mccloskey-francis-w-jr', displayName: 'Francis W. McCloskey Jr.', aliases: [] },
  { slug: 'santiago-jennifer-a', displayName: 'Jennifer A. Santiago', aliases: [] },
  { slug: 'shuter-david-c', displayName: 'David C. Shuter', aliases: [] },
  { slug: 'stefanski-anthony', displayName: 'Anthony Stefanski', aliases: [] },
  { slug: 'shaffer-robert-m', displayName: 'Robert M. Shaffer', aliases: [] },
  { slug: 'kennedy-sean-f', displayName: 'Sean F. Kennedy', aliases: [] },
  { slug: 'moore-jimmie', displayName: 'Jimmie Moore', aliases: [] },
  { slug: 'conroy-david-h', displayName: 'David H. Conroy', aliases: [] },

  // --- Group 2: directory-completeness additions (not observed in-corpus) ---
  // CP Criminal Trial Division.
  { slug: 'eisenhower-james', displayName: 'James Eisenhower', aliases: [] },
  { slug: 'watson-stokes-deborah', displayName: 'Deborah Watson-Stokes', aliases: [] },
  // Farnese: nickname (Larry<->Lawrence) may unmatch on first live CPCMS form;
  // acceptable (fails to review, alias top-up then). No guessed legal-name alias.
  { slug: 'farnese-larry', displayName: 'Larry Farnese', aliases: [] },
  // Philadelphia Municipal Court.
  { slug: 'brumbach-marissa-j', displayName: 'Marissa J. Brumbach', aliases: [] },
  { slug: 'cohen-sherrie', displayName: 'Sherrie Cohen', aliases: [] },
  { slug: 'davidson-amanda', displayName: 'Amanda Davidson', aliases: [] },
  { slug: 'dicicco-christian-a', displayName: 'Christian A. DiCicco', aliases: [] },
  { slug: 'frazier-lyde-jacquelyn-m', displayName: 'Jacquelyn M. Frazier-Lyde', aliases: [] },
  { slug: 'lambert-michael-c', displayName: 'Michael C. Lambert', aliases: [] },
  { slug: 'lewandowski-henry-iii', displayName: 'Henry Lewandowski III', aliases: [] },
  // Williams Losier: surname granularity pending first live appearance; if
  // compound, comma-alias top-up then. Not pre-decided here.
  { slug: 'losier-sharon-williams', displayName: 'Sharon Williams Losier', aliases: [] },
  { slug: 'moss-bradley-k', displayName: 'Bradley K. Moss', aliases: [] },
  { slug: 'osborne-colleen-m', displayName: 'Colleen M. Osborne', aliases: [] },
  { slug: 'parkinson-michael-patrick', displayName: 'Michael Patrick Parkinson', aliases: [] },
  { slug: 'patton-cortez', displayName: 'Cortez Patton', aliases: [] },
  { slug: 'pew-wendy-l', displayName: 'Wendy L. Pew', aliases: [] },
  { slug: 'pittman-joffie-c-iii', displayName: 'Joffie C. Pittman III', aliases: [] },
  { slug: 'shields-t-francis', displayName: 'T. Francis Shields', aliases: [] },
  { slug: 'simmons-karen-y', displayName: 'Karen Y. Simmons', aliases: [] },
  // Real space-separated compound surname: comma-form alias is load-bearing.
  {
    slug: 'thomson-previdi-barbara-s',
    displayName: 'Barbara S. Thomson Previdi',
    aliases: ['Thomson Previdi, Barbara S.'],
  },
  { slug: 'twardy-george-r', displayName: 'George R. Twardy', aliases: [] },
  { slug: 'williams-marvin-l-sr', displayName: 'Marvin L. Williams Sr.', aliases: [] },
  { slug: 'yorgey-girdy-gregory-o', displayName: 'Gregory O. Yorgey-Girdy', aliases: [] },
];
